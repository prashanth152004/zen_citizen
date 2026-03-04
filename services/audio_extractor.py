import os
import subprocess
from config import TEMP_DIR

def extract_audio(video_path: str) -> str:
    """
    Extracts 16kHz mono audio from the input video.
    Returns the path to the extracted .wav file.
    """
    base_name = os.path.basename(video_path)
    name_no_ext, _ = os.path.splitext(base_name)
    output_wav = os.path.join(TEMP_DIR, f"{name_no_ext}_extracted.wav")

    # If already exists from a previous run, optionally delete or reuse
    if os.path.exists(output_wav):
        os.remove(output_wav)

    # ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 output.wav
    command = [
        "ffmpeg",
        "-i", video_path,
        "-vn",                   # No video
        "-acodec", "pcm_s16le",  # 16-bit PCM
        "-ar", "16000",          # 16 kHz sample rate
        "-ac", "1",              # Mono
        "-y",                    # Overwrite output
        output_wav
    ]

    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_wav
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg audio extraction failed: {e}")
