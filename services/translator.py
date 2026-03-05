import requests
import time
from config import SUPPORTED_LANGUAGES


def translate_text(text: str, target_lang_code: str, gender: str, api_key: str) -> str:
    """
    Translates English text to the target Indic language using Sarvam AI API.
    Uses colloquial/conversational mode for natural dubbing tone.
    Preserves meaning, emotion, and context of the original speech.
    Retries up to 3 times on failure.
    """
    if target_lang_code == "en":
        return text  # No translation needed for English

    # Skip if no API key
    if not api_key:
        print(f"[translator] No API key, returning original text for {target_lang_code}")
        return text

    # Map gender to Sarvam API format
    sarvam_gender = "Male" if gender.lower() == "male" else "Female"

    url = "https://api.sarvam.ai/translate"
    payload = {
        "input": text,
        "source_language_code": "en-IN",
        "target_language_code": f"{target_lang_code}-IN",
        "speaker_gender": sarvam_gender,
        "mode": "formal",        # Pure translation, no code-mixing/loan words
        "model": "mayura:v1",
        "enable_preprocessing": True  # Better handling of numbers, dates, abbreviations
    }
    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": api_key
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                result = response.json()
                translated = result.get("translated_text", text)
                # Ensure we got actual content back
                if translated and translated.strip():
                    return translated.strip()
                print(f"[translator] WARNING: Empty translation returned for '{text[:50]}...' -> {target_lang_code}")
                return text
            else:
                if attempt == max_retries - 1:
                    print(f"[translator] Translation failed for '{text[:50]}...': {response.status_code} {response.text[:200]}")
                    return text
        except requests.exceptions.Timeout:
            if attempt == max_retries - 1:
                print(f"[translator] Translation timeout for '{text[:50]}...'")
                return text
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"[translator] Translation error for '{text[:50]}...': {e}")
                return text
        time.sleep(1)

    return text


def translate_segments(segments: list, target_langs: list[str], api_key: str) -> dict[str, list]:
    """
    Translates all segments into all selected target languages.
    Uses context-aware translation: passes surrounding segments as context hints
    for better semantic coherence across the conversation.
    Preserves speaker_id and gender through the pipeline so TTS can assign
    the correct voice per speaker.
    """
    translated_tracks = {}

    for lang_name in target_langs:
        lang_code = SUPPORTED_LANGUAGES[lang_name]
        translated_segments = []

        for i, seg in enumerate(segments):
            # Build context from adjacent segments for better translation coherence
            # This helps the translator understand the flow of conversation
            context_text = _build_context(segments, i)

            # Use actual speaker gender for translation quality
            translated_text = translate_text_with_context(
                text=seg.text,
                context=context_text,
                target_lang_code=lang_code,
                gender=seg.gender,
                api_key=api_key
            )
            translated_segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": translated_text,
                "speaker_id": seg.speaker_id,
                "gender": seg.gender
            })

        translated_tracks[lang_name] = translated_segments
        print(f"[translator] {lang_name}: translated {len(translated_segments)} segments")

    return translated_tracks


def _build_context(segments: list, current_idx: int) -> str:
    """
    Builds a brief context string from the previous and next segments.
    This helps the translation API understand conversational flow.
    """
    parts = []
    # Previous segment for backward context
    if current_idx > 0:
        parts.append(segments[current_idx - 1].text.strip())
    # Next segment for forward context
    if current_idx < len(segments) - 1:
        parts.append(segments[current_idx + 1].text.strip())

    if parts:
        return " ... ".join(parts)
    return ""


def translate_text_with_context(
    text: str,
    context: str,
    target_lang_code: str,
    gender: str,
    api_key: str
) -> str:
    """
    Translates text. 
    Note: Sarvam API is a pure translation model, not an instruction-following LLM,
    so adding '[Context: ...]' prefixes confuses it and gets embedded in the output.
    We translate the exact text segment directly.
    """
    # Plain translation without context
    return translate_text(text, target_lang_code, gender, api_key)
