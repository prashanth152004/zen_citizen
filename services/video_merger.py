import subprocess
import os
from config import OUTPUT_DIR, SUPPORTED_LANGUAGES

def merge_video(original_video: str, tracks: dict[str, str], srt_path: str) -> str:
    """
    Merges the original video with all newly generated audio tracks.
    Burns in the primary language subtitles (English).
    Sets the default audio track metadata properly.
    """
    out_path = os.path.join(OUTPUT_DIR, "final_multilingual_output.mp4")
    
    if os.path.exists(out_path):
        os.remove(out_path)
        
    cmd = [
        "ffmpeg",
        "-i", original_video
    ]
    
    # Add an input for each valid audio track built
    valid_tracks = list(tracks.items())
    for _, track_path in valid_tracks:
        cmd.extend(["-i", track_path])
        
    # Map video from first input
    cmd.extend(["-map", "0:v"])
    
    # Map audio tracks
    for idx_offset in range(len(valid_tracks)):
        cmd.extend(["-map", f"{idx_offset + 1}:a"])
        
    # Burn in subtitles
    # FFmpeg subtitles filter syntax requires proper escaping of paths, especially on Windows
    # Here on Mac, a relative path or standard absolute is usually okay, but we escape colons anyway
    escaped_srt = srt_path.replace(":", "\\:")
    cmd.extend(["-vf", f"subtitles='{escaped_srt}'"])
    
    # Set video/audio codecs
    cmd.extend(["-c:v", "libx264"])
    
    # Set codec and bitrate for each audio stream explicitly
    for i in range(len(valid_tracks)):
        cmd.extend([
            f"-c:a:{i}", "aac",
            f"-b:a:{i}", "192k",
            f"-ac:{i}", "2"  # Force stereo for better compatibility
        ])
    
    # Add metadata for each audio track
    for idx_offset, (lang_name, _) in enumerate(valid_tracks):
        lang_code = SUPPORTED_LANGUAGES[lang_name] # e.g., 'en', 'hi', 'kn'
        # Convert to ISO 639-2 if needed by FFmpeg, but 3-letter codes are standard (eng, hin, kan)
        code_map = {"en": "eng", "hi": "hin", "kn": "kan"}
        iso_code = code_map.get(lang_code, "eng")
        
        cmd.extend([
            f"-metadata:s:a:{idx_offset}", f"language={iso_code}",
            f"-metadata:s:a:{idx_offset}", f"title={lang_name}"
        ])
        
        # Set English as default track
        if lang_name == "English":
            cmd.extend([f"-disposition:a:{idx_offset}", "default"])
        else:
            cmd.extend([f"-disposition:a:{idx_offset}", "0"])
            
    cmd.append(out_path)
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg multi-audio merge failed: {e}")


def generate_per_language_videos(original_video: str, tracks: dict[str, str]) -> dict[str, str]:
    """
    Creates a separate MP4 file per language (video + single audio track).
    This is much more reliable for browser playback than multi-track MP4.
    Returns: {"English": "/path/to/output_English.mp4", "Hindi": "/path/to/output_Hindi.mp4", ...}
    """
    per_lang_paths = {}
    
    for lang_name, audio_path in tracks.items():
        out_path = os.path.join(OUTPUT_DIR, f"output_{lang_name}.mp4")
        if os.path.exists(out_path):
            os.remove(out_path)
        
        print(f"[video_merger] Generating per-language MP4 for {lang_name}: audio={audio_path}")
        
        cmd = [
            "ffmpeg", "-y",
            "-i", original_video,
            "-i", audio_path,
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",        # Don't re-encode video — just copy
            "-c:a", "aac",
            "-b:a", "192k",
            "-ac", "2",            # Force stereo output
            "-ar", "44100",        # Force 44100 Hz sample rate
            out_path
        ]
        
        try:
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            per_lang_paths[lang_name] = out_path
            # Verify the output has audio
            verify_cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_name,channels,bit_rate,duration",
                "-of", "compact",
                out_path
            ]
            verify_result = subprocess.run(verify_cmd, capture_output=True, text=True)
            print(f"[video_merger] {lang_name} MP4 audio info: {verify_result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            print(f"[video_merger] WARNING: Per-language MP4 generation failed for {lang_name}: {e}")
            if e.stderr:
                print(f"[video_merger] FFmpeg stderr: {e.stderr.decode('utf-8', errors='replace')[-500:]}")
    
    return per_lang_paths


def generate_hls(video_path: str, tracks: dict[str, str], srt_path: str):
    """
    Generates HLS (m3u8) with multiple audio tracks and subtitles.
    Used for the Netflix-style web player.
    """
    from config import HLS_DIR
    import shutil

    # Clear HLS dir
    if os.path.exists(HLS_DIR):
        shutil.rmtree(HLS_DIR)
    os.makedirs(HLS_DIR, exist_ok=True)

    master_playlist = os.path.join(HLS_DIR, "master.m3u8")
    
    # HLS command is complex. We use a simpler approach: 
    # Create the MP4 first (already done), then convert it to HLS with stream mapping.
    
    cmd = [
        "ffmpeg",
        "-i", video_path
    ]
    
    # Add audio tracks
    audio_items = list(tracks.items())
    for _, track_path in audio_items:
        cmd.extend(["-i", track_path])
        
    # Mapping
    cmd.extend(["-map", "0:v"])
    for i in range(len(audio_items)):
        cmd.extend(["-map", f"{i+1}:a"])
        
    # Subtitles (as a stream)
    cmd.extend(["-i", srt_path])
    cmd.extend(["-map", f"{len(audio_items) + 1}:s"])

    # Output flags for HLS
    cmd.extend([
        "-c:v", "libx264",
        "-c:a", "aac",
        "-c:s", "webvtt",
        "-f", "hls",
        "-hls_time", "6",
        "-hls_list_size", "0",
        "-hls_segment_filename", os.path.join(HLS_DIR, "seg_%d.ts"),
        "-master_pl_name", "master.m3u8"
    ])

    # Metadata and Grouping for HLS
    # This is quite advanced FFmpeg. For a simpler implementation, 
    # we'll stick to the multi-audio MP4 and use a custom player that can handle it if possible,
    # OR we use Video.js with HLS.
    
    # Let's use a simpler version of HLS for now
    cmd.append(os.path.join(HLS_DIR, "playlist.m3u8"))

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return master_playlist
    except subprocess.CalledProcessError as e:
        print(f"HLS generation failed: {e}")
        return None

