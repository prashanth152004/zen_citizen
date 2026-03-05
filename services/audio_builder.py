import os
import subprocess
import tempfile
from pydub import AudioSegment
from config import OUTPUT_DIR, LUFS_MAIN


def build_original_audio_track(wav_path: str, total_duration_ms: int, lang_name: str) -> str:
    """
    Uses the original extracted audio as-is for the source language track.
    Applies light normalization to LUFS_MAIN (-14 dBFS) for consistent volume.
    """
    original = AudioSegment.from_wav(wav_path)
    
    # Resample to 44100 Hz stereo to match other tracks
    original = original.set_frame_rate(44100).set_channels(2)
    
    # Trim or pad to match total video duration
    if len(original) > total_duration_ms:
        original = original[:total_duration_ms]
    elif len(original) < total_duration_ms:
        pad = AudioSegment.silent(duration=total_duration_ms - len(original), frame_rate=44100)
        original = original + pad
    
    # Light normalization
    if original.dBFS != float("-inf") and original.max > 0:
        gain = LUFS_MAIN - original.dBFS
        gain = max(-6, min(10, gain))
        if abs(gain) > 0.5:
            original = original.apply_gain(gain)
    
    out_path = os.path.join(OUTPUT_DIR, f"track_{lang_name}.wav")
    original.export(out_path, format="wav")
    
    print(f"[audio_builder] {lang_name}: original audio track, {len(original)}ms, dBFS={original.dBFS:.1f}")
    return out_path


def _stretch_audio_with_ffmpeg(audio_segment: AudioSegment, speed_ratio: float) -> AudioSegment:
    """
    Uses FFmpeg's `atempo` filter to time-stretch audio while perfectly preserving pitch.
    This creates a smooth, studio-quality tempo adjustment without the chipmunk effect.
    """
    if speed_ratio <= 1.01 and speed_ratio >= 0.99:
        return audio_segment

    # atempo valid range is 0.5 to 100.0 (though extreme values degrade quality)
    clamped_ratio = max(0.5, min(100.0, float(speed_ratio)))

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_in:
        audio_segment.export(temp_in.name, format="wav")
        temp_out_name = temp_in.name.replace(".wav", "_out.wav")

    try:
        cmd = [
            "ffmpeg", "-y", "-i", temp_in.name,
            "-filter:a", f"atempo={clamped_ratio}",
            "-vn", temp_out_name
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        stretched = AudioSegment.from_wav(temp_out_name)
        return stretched
    except Exception as e:
        print(f"[audio_builder] Warning: FFmpeg atempo failed: {e}. Returning original clip.")
        return audio_segment
    finally:
        if os.path.exists(temp_in.name):
            os.remove(temp_in.name)
        if os.path.exists(temp_out_name):
            try:
                os.remove(temp_out_name)
            except Exception:
                pass


def build_audio_track(segments: list, wav_paths: list[str], total_duration_ms: int, lang_name: str) -> str:
    """
    Reconstructs the full timeline by placing each TTS audio clip at its designated start time.
    Time-compresses the clip if it exceeds the available gap to ensure lip-sync alignment.
    Applies per-segment loudness normalization and final track-level normalization.
    Output is always 44100 Hz stereo to match build_original_audio_track and ensure
    consistent FFmpeg merging.
    """
    # Create a silent canvas at standard sample rate — STEREO to match original audio track
    final_audio = AudioSegment.silent(duration=total_duration_ms, frame_rate=44100)
    final_audio = final_audio.set_channels(2)  # Force stereo for consistent merging
    
    segments_placed = 0
    
    for seg, p in zip(segments, wav_paths):
        if not os.path.exists(p):
            print(f"[audio_builder] {lang_name}: WARNING — segment file missing: {p}")
            continue
            
        clip = AudioSegment.from_wav(p)
        
        # Skip truly silent/empty clips (failed TTS)
        if clip.max == 0 or len(clip) < 50:
            print(f"[audio_builder] {lang_name}: skipping silent/empty clip: {p}")
            continue
        
        # Ensure clip is stereo to match the canvas
        clip = clip.set_frame_rate(44100).set_channels(2)
        
        # Normalize each individual clip to -16 dBFS BEFORE placing it on timeline
        # This ensures each voice segment is audible regardless of TTS output levels
        if clip.dBFS != float("-inf"):
            if clip.dBFS < -30 or clip.dBFS > -10:
                gain = -16 - clip.dBFS
                clip = clip.apply_gain(gain)
        
        # Original timing from Whisper
        start_ms = int(seg["start"] * 1000)
        end_ms = int(seg["end"] * 1000)
        target_duration = end_ms - start_ms
        
        # Time-stretch for perfect dubbing alignment using studio-quality FFmpeg `atempo`.
        # We aggressively stretch or compress the TTS audio to fit the exact millisecond 
        # duration of the original visual segment, ensuring frame-perfect lip-sync.
        if target_duration > 0:
            speed_ratio = len(clip) / target_duration
            
            # If the clip length differs by more than 2% from target, stretch/compress it
            if speed_ratio > 1.02 or speed_ratio < 0.98:
                # Cap stretching to avoid extreme distortion
                safe_ratio = max(0.75, min(1.5, speed_ratio))
                clip = _stretch_audio_with_ffmpeg(clip, safe_ratio)
            
            # Force exact match: trim or pad to hit the target duration precisely
            if len(clip) > target_duration:
                # Fade out the very end if we have to truncate to avoid clipping clicks
                clip = clip[:target_duration].fade_out(20)
            elif len(clip) < target_duration:
                # Pad with silence if it's slightly too short, ensuring the next 
                # segment starts at precisely the right visual time.
                pad = AudioSegment.silent(duration=target_duration - len(clip), frame_rate=clip.frame_rate)
                clip = clip + pad
        
        # Clamp start position
        if start_ms < 0:
            start_ms = 0
        if start_ms >= total_duration_ms:
            continue
            
        # Overlay the clip onto the silent canvas at the exact start time
        final_audio = final_audio.overlay(clip, position=start_ms)
        segments_placed += 1
    
    print(f"[audio_builder] {lang_name}: placed {segments_placed}/{len(segments)} segments on timeline")
    
    # Final track-level normalization — all tracks get the same treatment
    if final_audio.max > 0 and final_audio.dBFS != float("-inf"):
        current_dbfs = final_audio.dBFS
        gain_needed = LUFS_MAIN - current_dbfs
        
        # Limit gain adjustment to prevent extreme changes
        gain_needed = max(-10, min(15, gain_needed))
        
        if abs(gain_needed) > 0.5:
            final_audio = final_audio.apply_gain(gain_needed)
        
        print(f"[audio_builder] {lang_name}: dBFS={current_dbfs:.1f} -> target={LUFS_MAIN:.1f}, gain={gain_needed:.1f}dB")
    else:
        print(f"[audio_builder] WARNING: {lang_name} track appears to be entirely silent!")
    
    # Ensure final output is stereo
    final_audio = final_audio.set_channels(2)
    
    # Export as WAV
    out_path = os.path.join(OUTPUT_DIR, f"track_{lang_name}.wav")
    final_audio.export(out_path, format="wav")
    
    # Verify the output
    verify = AudioSegment.from_wav(out_path)
    print(f"[audio_builder] {lang_name} output: {len(verify)}ms, dBFS={verify.dBFS:.1f}, max={verify.max}, channels={verify.channels}")
    
    return out_path
