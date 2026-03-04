import whisper
from dataclasses import dataclass

@dataclass
class Segment:
    start: float
    end: float
    text: str

def transcribe(wav_path: str, model_size: str = "base") -> list[Segment]:
    """
    Transcribes the full audio using OpenAI Whisper (single-pass).
    Forces the task to 'translate' so that non-English audio (like Kannada)
    is automatically translated to English text first.
    Returns a list of transcribed Segments with exact timestamps.
    """
    model = whisper.load_model(model_size, device="cpu")
    
    # Force translation to English. This assumes the output goal is English-centric 
    # before further translation (e.g., Kannada -> English -> Hindi).
    result = model.transcribe(wav_path, task="translate")
    
    segments = []
    for seg in result["segments"]:
        segments.append(
            Segment(
                start=seg["start"],
                end=seg["end"],
                text=seg["text"].strip()
            )
        )
    return segments
