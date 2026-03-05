import whisper
import numpy as np
import os
import tempfile
from pydub import AudioSegment
from dataclasses import dataclass

@dataclass
class Segment:
    start: float
    end: float
    text: str


def detect_language(wav_path: str, model_size: str = "base") -> tuple[str, str]:
    """
    Detects the spoken language in the audio using Whisper's language detection.
    Loads 30 seconds of audio and runs the language identification head.
    Returns: (language_code, language_name)  e.g. ("kn", "Kannada")
    """
    model = whisper.load_model(model_size, device="cpu")

    # Load and pad/trim to 30 seconds (Whisper's standard window)
    audio = whisper.load_audio(wav_path)
    audio = whisper.pad_or_trim(audio)

    mel = whisper.log_mel_spectrogram(audio).to(model.device)
    _, probs = model.detect_language(mel)

    detected_code = max(probs, key=probs.get)

    # Map common codes to readable names
    CODE_TO_NAME = {
        "en": "English",
        "hi": "Hindi",
        "kn": "Kannada",
        "ta": "Tamil",
        "te": "Telugu",
        "ml": "Malayalam",
        "mr": "Marathi",
        "bn": "Bengali",
        "gu": "Gujarati",
        "pa": "Punjabi",
        "ur": "Urdu",
    }
    detected_name = CODE_TO_NAME.get(detected_code, detected_code.upper())

    print(f"[transcriber] Detected source language: {detected_name} ({detected_code}), confidence: {probs[detected_code]:.2%}")
    return detected_code, detected_name

def transcribe(wav_path: str, model_size: str = "base") -> list[Segment]:
    """
    Transcribes the full audio using OpenAI Whisper (single-pass).
    Pads the audio with 1 second of silence to ensure the final words are captured.
    Forces the task to 'translate' so that non-English audio (like Kannada)
    is automatically translated to English text first.
    Returns a list of transcribed Segments with exact timestamps.
    """
    model = whisper.load_model(model_size, device="cpu")
    
    # Pad audio with 1 second of silence at the end to prevent Whisper
    # from cutting off the final words of the video abruptly.
    audio = AudioSegment.from_wav(wav_path)
    audio = audio + AudioSegment.silent(duration=1000)
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
        audio.export(temp_wav.name, format="wav")
        padded_wav_path = temp_wav.name
    try:
        # Force translation to English.
        # We use condition_on_previous_text=False and no_speech_threshold
        # to prevent severe hallucinations (e.g. generating Chinese/Greek text
        # during background noise) but keep compression_ratio off so we don't
        # accidentally drop large chunks of valid translated speech.
        result = model.transcribe(
            padded_wav_path, 
            task="translate",
            condition_on_previous_text=False,
            no_speech_threshold=0.6
        )
    finally:
        if os.path.exists(padded_wav_path):
            try:
                os.remove(padded_wav_path)
            except Exception:
                pass
    
    
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
