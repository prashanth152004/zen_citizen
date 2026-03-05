import os
import textwrap
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

def _split_segment_into_subtitles(start: float, end: float, text: str, max_chars_per_line: int = 42, max_lines: int = 2) -> list[dict]:
    """
    Splits a long text segment into smaller subtitle blocks ensuring max 2 lines per block.
    Timestamps are allocated proportionally based on character length.
    """
    # 1. Wrap text into lines of a safe subtitle width
    lines = textwrap.wrap(text, width=max_chars_per_line)
    
    # 2. Group lines into blocks of max_lines
    blocks = []
    for i in range(0, len(lines), max_lines):
        block_text = "\n".join(lines[i:i + max_lines])
        blocks.append(block_text)
        
    if not blocks:
        return []

    # 3. Calculate time for each block proportionally based on string length
    total_chars = sum(len(b) for b in blocks)
    total_duration = end - start
    
    subtitle_chunks = []
    current_start = start
    
    for b in blocks:
        b_len = len(b)
        ratio = b_len / total_chars if total_chars > 0 else 1.0 / len(blocks)
        
        chunk_duration = total_duration * ratio
        current_end = current_start + chunk_duration
        
        subtitle_chunks.append({
            "start": current_start,
            "end": current_end,
            "text": b
        })
        
        current_start = current_end
        
    return subtitle_chunks

def generate_srt(segments: list, lang_name: str) -> str:
    """
    Generates an SRT file for the given segments.
    Ensures that subtitles are cleanly split into a maximum of 2 lines visible at once
    and timed evenly.
    """
    out_path = os.path.join(OUTPUT_DIR, f"{lang_name}_subtitles.srt")
    
    with open(out_path, "w", encoding="utf-8") as f:
        srt_idx = 1
        for seg in segments:
            # Smartly chunk the segment if it's too long
            chunks = _split_segment_into_subtitles(seg['start'], seg['end'], seg['text'])
            
            for chunk in chunks:
                f.write(f"{srt_idx}\n")
                f.write(f"{format_timestamp(chunk['start'])} --> {format_timestamp(chunk['end'])}\n")
                f.write(f"{chunk['text']}\n\n")
                srt_idx += 1
            
    return out_path
