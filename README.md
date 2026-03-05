# 🎬 AI Video Translator

A production-grade web application built with Streamlit that automatically translates videos into multiple languages with Documentary Voice Overlay Style audio and subtitle selection. The system preserves speaker identity, matches gender-appropriate voices, and perfectly syncs the translated audio back to the original video timeline.

## ✨ Features

- **Single-Pass Transcription:** Uses OpenAI's **Whisper** to transcribe the original video audio and force-translate foreign audio to English.
- **Deep Speaker Diarization:** Uses **Pyannote 3.1** to identify individual speakers and track when they are speaking.
- **Smart Gender Detection & Voice Mapping:** Analyzes audio pitch (F0) to determine speaker gender, ensuring male speakers get male AI voices and female speakers get female AI voices consistently throughout the video.
- **High-Quality Indic Translation:** Integrates with the **Sarvam AI API** for native-level translation into Hindi and Kannada.
- **Advanced Audio Engineering:** 
  - Generates natural speech using Microsoft Edge TTS.
  - Automatically speeds up translated audio to perfectly fit within the original speaker's time slot.
  - Performs intelligent audio ducking and EQ (mid-range scoop) so ambient/background languages (like Kannada) sit perfectly behind the primary audio.
- **Documentary Voice Overlay Style Video Player:** A custom HTML5 player built directly into Streamlit that allows you to instantly switch between language tracks (English, Hindi, Kannada) and toggle subtitles without reloading the page.

## 🛠 Technology Stack

| Component | Technology |
|---|---|
| **UI Framework** | Streamlit |
| **Transcription** | OpenAI Whisper |
| **Speaker ID** | Pyannote 3.1 |
| **Translation** | Sarvam AI API |
| **Voice Synthesis** | Microsoft Edge TTS |
| **Audio Processing** | Pydub, Librosa |
| **Video Processing** | FFmpeg |

## 🚀 Installation & Setup

### Prerequisites
1. **Python 3.9+**
2. **FFmpeg** installed on your system (`brew install ffmpeg` on macOS, or `apt install ffmpeg` on Linux).
3. **Hugging Face Token**: Required for Pyannote speaker diarization. You must accept the user conditions for `pyannote/speaker-diarization-3.1` and `pyannote/segmentation-3.0` on Hugging Face.
4. **Sarvam AI API Key**: Required for translating to Indic languages.

### Installation

1. Clone the repository:
```bash
git clone https://github.com/prashanth152004/zen_citizen.git
cd zen_citizen
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
streamlit run app.py
```

## 🎮 Usage

1. Open the application in your browser (usually `http://localhost:8501`).
2. Enter your **Hugging Face Token** and **Sarvam API Key** in the sidebar.
3. Upload an MP4 video file.
4. Click **Translate & Build Video**.
5. Once processing is complete, use the **Documentary Voice Overlay Style Video Player** to watch your video. Hover over the player and click the settings gear (⚙️) to switch audio languages and subtitles in real-time.

## 📁 Project Structure

```
├── app.py                      # Main Streamlit application
├── config.py                   # Configuration constants and Voice Mappings
├── requirements.txt            # Python dependencies
└── services/
    ├── audio_builder.py        # Compiles and normalizes TTS clips onto timeline
    ├── audio_extractor.py      # Extracts raw audio via FFmpeg
    ├── player_ui.py            # Local HTTP server and custom Documentary Voice Overlay Style HTML5 player
    ├── speaker_ai.py           # Pyannote diarization and librosa gender detection
    ├── subtitle_generator.py   # Generates precise SRT subtitle files
    ├── transcriber.py          # Whisper transcription
    ├── translator.py           # Sarvam AI API translation orchestration
    ├── tts_engine.py           # Edge TTS generation and speaker voice caching
    └── video_merger.py         # FFmpeg video multiplexing for per-language MP4s
```

## 📝 License
This project is for educational and portfolio purposes. Ensure you comply with the licensing terms of OpenAI Whisper, Pyannote, and Sarvam AI when deploying this application.
