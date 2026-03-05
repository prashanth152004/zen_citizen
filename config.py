import os

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
HLS_DIR = os.path.join(BASE_DIR, "hls")

# Ensure directories exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(HLS_DIR, exist_ok=True)

# Whisper config
WHISPER_MODEL = "base"

# Supported Target Languages
# Netflix style: English, Hindi, Kannada
SUPPORTED_LANGUAGES = {
    "English": "en",
    "Hindi": "hi",
    "Kannada": "kn"
}

# Edge-TTS voice mapping per language
# Multiple voice variants per gender so each speaker gets a distinct voice
VOICE_MAP = {
    "en": {
        "male": [
            "en-US-ChristopherNeural",
            "en-US-GuyNeural",
            "en-US-EricNeural",
        ],
        "female": [
            "en-US-AriaNeural",
            "en-US-JennyNeural",
            "en-US-MichelleNeural",
        ]
    },
    "hi": {
        "male": [
            "hi-IN-MadhurNeural",
        ],
        "female": [
            "hi-IN-SwaraNeural",
        ]
    },
    "kn": {
        "male": [
            "kn-IN-GaganNeural",
        ],
        "female": [
            "kn-IN-SapnaNeural",
        ]
    }
}

# Audio tuning constants
# All voice tracks normalized to this level
LUFS_MAIN = -14.0

# Label used when keeping original audio for the source language
SOURCE_LANGUAGE_LABEL = "Source (Original)"

