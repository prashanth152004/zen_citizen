import os
from pydub import AudioSegment
from config import OUTPUT_DIR, LUFS_MAIN, LUFS_BACKGROUND

def build_audio_track(segments: list, wav_paths: list[str], total_duration_ms: int, lang_name: str) -> str:
    """
    Reconstructs the full timeline by placing each TTS audio clip at its designated start time.
    Time-compresses the clip if it exceeds the available gap.
    Applies per-segment loudness boost and final normalization.
    """
    # Create a silent canvas at standard sample rate
    final_audio = AudioSegment.silent(duration=total_duration_ms, frame_rate=44100)
    
    segments_placed = 0
    
    for seg, p in zip(segments, wav_paths):
        if not os.path.exists(p):
            continue
            
        clip = AudioSegment.from_wav(p)
        
        # Skip truly silent/empty clips (failed TTS)
        if clip.max == 0 or len(clip) < 50:
            continue
        
        # Normalize each individual clip to -16 dBFS BEFORE placing it on timeline
        # This ensures each voice segment is audible regardless of TTS output levels
        if clip.dBFS != float("-inf") and clip.dBFS < -30:
            gain = -16 - clip.dBFS
            clip = clip.apply_gain(gain)
        elif clip.dBFS != float("-inf") and clip.dBFS > -10:
            # Too loud, bring it down
            gain = -16 - clip.dBFS
            clip = clip.apply_gain(gain)
        
        # Original timing from Whisper
        start_ms = int(seg["start"] * 1000)
        end_ms = int(seg["end"] * 1000)
        target_duration = end_ms - start_ms
        
        # If the clip is longer than the available time slot, speed it up
        if target_duration > 0 and len(clip) > target_duration:
            speed_ratio = len(clip) / target_duration
            new_sample_rate = int(clip.frame_rate * speed_ratio)
            clip = clip._spawn(clip.raw_data, overrides={'frame_rate': new_sample_rate})
            clip = clip.set_frame_rate(44100)
        
        # Clamp start position
        if start_ms < 0:
            start_ms = 0
        if start_ms >= total_duration_ms:
            continue
            
        # Overlay the clip onto the silent canvas at the exact start time
        final_audio = final_audio.overlay(clip, position=start_ms)
        segments_placed += 1
    
    print(f"[audio_builder] {lang_name}: placed {segments_placed}/{len(segments)} segments on timeline")
    
    # Final track-level adjustments
    # Only apply LUFS if there is actual audio content
    if final_audio.max > 0 and final_audio.dBFS != float("-inf"):
        target_lufs = LUFS_BACKGROUND if lang_name == "Kannada" else LUFS_MAIN
        current_dbfs = final_audio.dBFS
        
        # Only apply gain if the difference is significant and won't kill audio
        gain_needed = target_lufs - current_dbfs
        
        # Limit gain adjustment to prevent extreme changes
        gain_needed = max(-10, min(15, gain_needed))
        
        if abs(gain_needed) > 0.5:
            final_audio = final_audio.apply_gain(gain_needed)
        
        print(f"[audio_builder] {lang_name}: dBFS={current_dbfs:.1f} -> target={target_lufs:.1f}, gain={gain_needed:.1f}dB")
    else:
        print(f"[audio_builder] WARNING: {lang_name} track appears to be entirely silent!")
    
    # Apply Mid-EQ Cut for Kannada to sit 'behind' the English
    if lang_name == "Kannada":
        final_audio = final_audio.low_pass_filter(3000).high_pass_filter(300)
    
    # Export as WAV
    out_path = os.path.join(OUTPUT_DIR, f"track_{lang_name}.wav")
    final_audio.export(out_path, format="wav")
    
    # Verify the output
    verify = AudioSegment.from_wav(out_path)
    print(f"[audio_builder] {lang_name} output: {len(verify)}ms, dBFS={verify.dBFS:.1f}, max={verify.max}")
    
    return out_path
