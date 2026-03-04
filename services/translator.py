import requests
import time
from config import SUPPORTED_LANGUAGES

def translate_text(text: str, target_lang_code: str, gender: str, api_key: str) -> str:
    """
    Translates English text to the target Indic language using Sarvam AI API.
    Uses the actual speaker gender for better translation quality.
    Retries up to 3 times on failure.
    """
    if target_lang_code == "en":
        return text  # No translation needed for English
    
    # Map gender to Sarvam API format
    sarvam_gender = "Male" if gender.lower() == "male" else "Female"
        
    url = "https://api.sarvam.ai/translate"
    payload = {
        "input": text,
        "source_language_code": "en-IN",
        "target_language_code": f"{target_lang_code}-IN",
        "speaker_gender": sarvam_gender,
        "mode": "formal",
        "model": "mayura:v1"
    }
    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": api_key
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                result = response.json()
                return result.get("translated_text", text)
            else:
                if attempt == max_retries - 1:
                    print(f"Translation failed for '{text}': {response.text}")
                    return text
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Translation error for '{text}': {e}")
                return text
        time.sleep(1)
        
    return text

def translate_segments(segments: list, target_langs: list[str], api_key: str) -> dict[str, list]:
    """
    Translates all segments into all selected target languages.
    Preserves speaker_id and gender through the pipeline so TTS can assign
    the correct voice per speaker.
    """
    translated_tracks = {}
    
    for lang_name in target_langs:
        lang_code = SUPPORTED_LANGUAGES[lang_name]
        translated_segments = []
        
        for seg in segments:
            # Use actual speaker gender for translation quality
            translated_text = translate_text(
                text=seg.text,
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
        
    return translated_tracks
