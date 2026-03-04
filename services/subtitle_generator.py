import os
from config import OUTPUT_DIR

def format_timestamp(seconds: float) -> str:
    """
    Converts a float to an SRT timestamp: HH:MM:SS,mmm
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    mills = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{mills:03d}"

def generate_srt(segments: list, lang_name: str) -> str:
    """
    Generates an SRT file for the given segments.
    """
    out_path = os.path.join(OUTPUT_DIR, f"{lang_name}_subtitles.srt")
    
    with open(out_path, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(segments, start=1):
            f.write(f"{idx}\n")
            f.write(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")
            
    return out_path
