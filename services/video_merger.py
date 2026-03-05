import subprocess
import os
from config import OUTPUT_DIR, SUPPORTED_LANGUAGES

def merge_video(original_video: str, tracks: dict[str, str], srt_paths: dict[str, str]) -> str:
    """
    Merges the original video with all newly generated audio tracks.
    Embeds all generated subtitles as soft selectable tracks in the MP4.
    Sets the default audio & subtitle track metadata properly.
    """
    out_path = os.path.join(OUTPUT_DIR, "final_multilingual_output.mp4")
    
    if os.path.exists(out_path):
        os.remove(out_path)
        
    cmd = [
        "ffmpeg",
        "-i", original_video
    ]
    
    valid_tracks = list(tracks.items())
    for _, track_path in valid_tracks:
        cmd.extend(["-i", track_path])
        
    valid_srts = list(srt_paths.items())
    for _, srt_path in valid_srts:
        cmd.extend(["-i", srt_path])
        
    # Map video from first input
    cmd.extend(["-map", "0:v"])
    
    # Map audio tracks
    audio_start_idx = 1
    for idx_offset in range(len(valid_tracks)):
        cmd.extend(["-map", f"{audio_start_idx + idx_offset}:a"])
        
    # Map subtitle tracks
    srt_start_idx = 1 + len(valid_tracks)
    for idx_offset in range(len(valid_srts)):
        cmd.extend(["-map", f"{srt_start_idx + idx_offset}:s"])
    
    # Set codecs
    cmd.extend(["-c:v", "libx264"])
    if valid_srts:
        cmd.extend(["-c:s", "mov_text"])  # Standard subtitle codec for MP4
    
    # Set codec and bitrate for each audio stream explicitly
    for i in range(len(valid_tracks)):
        cmd.extend([
            f"-c:a:{i}", "aac",
            f"-b:a:{i}", "192k",
            f"-ac:{i}", "2"  # Force stereo for better compatibility
        ])
    
    # Add metadata for each audio track
    for idx_offset, (lang_name, _) in enumerate(valid_tracks):
        lang_code = SUPPORTED_LANGUAGES[lang_name]
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
            
    # Add metadata for each subtitle track
    for idx_offset, (lang_name, _) in enumerate(valid_srts):
        lang_code = SUPPORTED_LANGUAGES[lang_name]
        code_map = {"en": "eng", "hi": "hin", "kn": "kan"}
        iso_code = code_map.get(lang_code, "eng")
        
        cmd.extend([
            f"-metadata:s:s:{idx_offset}", f"language={iso_code}",
            f"-metadata:s:s:{idx_offset}", f"title={lang_name}"
        ])
        
        # Only set English subs as default, others inactive by default
        if lang_name == "English":
            cmd.extend([f"-disposition:s:{idx_offset}", "default"])
        else:
            cmd.extend([f"-disposition:s:{idx_offset}", "0"])
            
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
        
        cmd = [
            "ffmpeg", "-y",
            "-i", original_video,
            "-i", audio_path,
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",        # Don't re-encode video — just copy
            "-c:a", "aac",
            "-b:a", "192k",
            "-ac", "2",
            "-shortest",
            out_path
        ]
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            per_lang_paths[lang_name] = out_path
        except subprocess.CalledProcessError as e:
            print(f"Warning: Per-language MP4 generation failed for {lang_name}: {e}")
    
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

