import asyncio
import edge_tts
import os
from pydub import AudioSegment
from config import VOICE_MAP, SUPPORTED_LANGUAGES, TEMP_DIR

# ── Per-speaker voice assignment cache ──
# Maps (speaker_id, lang_code) -> voice_name
# Ensures the same speaker always gets the same voice throughout the video
_speaker_voice_cache: dict[tuple[str, str], str] = {}
_gender_voice_counters: dict[tuple[str, str], int] = {}  # (lang_code, gender) -> next index


def assign_voice_for_speaker(speaker_id: str, gender: str, lang_name: str) -> str:
    """
    Assigns a consistent, unique TTS voice to a specific speaker for a given language.
    If two male speakers exist, they get different male voices (Christopher vs Guy, etc.).
    The assignment is cached so the same speaker always gets the same voice.
    """
    lang_code = SUPPORTED_LANGUAGES.get(lang_name, "en")
    cache_key = (speaker_id, lang_code)
    
    # Return cached voice if already assigned
    if cache_key in _speaker_voice_cache:
        return _speaker_voice_cache[cache_key]
    
    # Clean gender
    gender = gender.lower().strip()
    if gender not in ["male", "female"]:
        gender = "male"
    
    # Get the list of available voices for this language + gender
    voices = VOICE_MAP.get(lang_code, VOICE_MAP["en"]).get(gender, VOICE_MAP["en"]["male"])
    
    # Pick the next unused voice (round-robin if more speakers than voices)
    counter_key = (lang_code, gender)
    idx = _gender_voice_counters.get(counter_key, 0)
    voice = voices[idx % len(voices)]
    _gender_voice_counters[counter_key] = idx + 1
    
    # Cache it
    _speaker_voice_cache[cache_key] = voice
    return voice


async def synthesize_segment(text: str, voice_name: str, output_path: str, rate_adjustment: str = ""):
    """
    Synthesizes speech using edge-tts.
    Writes to an MP3 file first, then converts to WAV for the pydub pipeline.
    Falls back to silence on empty text or TTS failure.
    """
    text = text.strip()
    mp3_path = output_path.replace(".wav", ".mp3")
    
    if not text:
        AudioSegment.silent(duration=100).export(output_path, format="wav")
        return

    try:
        communicate = edge_tts.Communicate(text, voice_name, rate=rate_adjustment)
        await communicate.save(mp3_path)
        
        if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
            AudioSegment.silent(duration=100).export(output_path, format="wav")
            if os.path.exists(mp3_path):
                os.remove(mp3_path)
            return
            
        audio = AudioSegment.from_mp3(mp3_path)
        audio.export(output_path, format="wav")
        os.remove(mp3_path)
    except Exception as e:
        print(f"Warning: TTS failed for text '{text}': {e}. Using silence.")
        AudioSegment.silent(duration=100).export(output_path, format="wav")
        if os.path.exists(mp3_path):
            try:
                os.remove(mp3_path)
            except:
                pass


async def generate_speech_for_track(lang_name: str, segments: list, global_idx: int) -> list[str]:
    """
    Generates TTS for every segment in a specific language track.
    Each segment uses a voice assigned to its specific speaker_id, ensuring:
      - Male speakers always use male voices
      - Female speakers always use female voices
      - Different speakers of the same gender get different voice variants
      - The same speaker always gets the same voice (consistency)
    """
    wav_paths = []
    
    # English is slowed slightly for clarity
    rate_adjust = "-10%" if lang_name == "English" else "+0%"
    
    for i, seg in enumerate(segments):
        # Get the speaker-specific voice (consistent across all their segments)
        voice_name = assign_voice_for_speaker(
            speaker_id=seg["speaker_id"],
            gender=seg["gender"],
            lang_name=lang_name
        )
        
        out_path = os.path.join(TEMP_DIR, f"seg_{global_idx}_{lang_name}_{i}.wav")
        await synthesize_segment(seg["text"], voice_name, out_path, rate_adjust)
        wav_paths.append(out_path)
        
    return wav_paths


def reset_voice_cache():
    """Reset the voice assignment cache. Call this before a new translation run."""
    global _speaker_voice_cache, _gender_voice_counters
    _speaker_voice_cache = {}
    _gender_voice_counters = {}
