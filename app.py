import streamlit as st
import os
import asyncio
from config import TEMP_DIR, OUTPUT_DIR, SUPPORTED_LANGUAGES

# Import our services
from services.audio_extractor import extract_audio
from services.transcriber import transcribe
from services.speaker_ai import diarize, assign_speakers, detect_gender
from services.translator import translate_segments
from services.tts_engine import generate_speech_for_track, reset_voice_cache
from services.audio_builder import build_audio_track
from services.subtitle_generator import generate_srt
from services.video_merger import merge_video, generate_per_language_videos
from services.player_ui import netflix_player

# --- Page Config ---
st.set_page_config(
    page_title="AI Video Translator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for premium look ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    
    /* Hero header styling */
    .hero-title {
        font-size: 2.6rem;
        font-weight: 700;
        background: linear-gradient(135deg, #a855f7 0%, #06b6d4 40%, #f59e0b 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
        letter-spacing: -0.5px;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 1.08rem;
        margin-bottom: 1.5rem;
        letter-spacing: 0.2px;
    }
    
    /* Info cards with glow border */
    .tech-card {
        background: linear-gradient(145deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
        border: 1px solid rgba(168, 85, 247, 0.25);
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 14px;
        color: #e2e8f0;
        transition: border-color 0.3s ease, box-shadow 0.3s ease;
    }
    .tech-card:hover {
        border-color: rgba(6, 182, 212, 0.5);
        box-shadow: 0 0 20px rgba(6, 182, 212, 0.08);
    }
    .tech-card h4 {
        color: #fff;
        margin: 0 0 8px 0;
        font-size: 1rem;
        font-weight: 600;
    }
    .tech-card p {
        color: #94a3b8;
        font-size: 0.85rem;
        margin: 0;
        line-height: 1.6;
    }
    .tech-badge {
        display: inline-block;
        padding: 3px 11px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-right: 5px;
        margin-top: 10px;
    }
    .tech-badge:nth-child(3n+1) {
        background: rgba(168, 85, 247, 0.15);
        color: #c084fc;
    }
    .tech-badge:nth-child(3n+2) {
        background: rgba(6, 182, 212, 0.15);
        color: #22d3ee;
    }
    .tech-badge:nth-child(3n) {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
    }
    
    /* Pipeline stages */
    .pipeline-step {
        background: #0f172a;
        border-left: 3px solid #a855f7;
        padding: 10px 16px;
        margin: 6px 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.9rem;
    }
    .pipeline-step strong {
        color: #c084fc;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0c0a1d 0%, #1e1b4b 50%, #0f172a 100%);
        border-right: 1px solid rgba(168, 85, 247, 0.15);
    }
    section[data-testid="stSidebar"] .stMarkdown h3 {
        background: linear-gradient(90deg, #a855f7, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 0.85rem;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        font-weight: 700;
    }
    
    /* Upload area */
    .stFileUploader > div {
        border: 2px dashed rgba(168, 85, 247, 0.3);
        border-radius: 14px;
        transition: border-color 0.3s;
    }
    .stFileUploader > div:hover {
        border-color: rgba(6, 182, 212, 0.5);
    }
    
    /* Primary button glow */
    .stButton > button[kind="primary"],
    button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #7c3aed, #a855f7, #06b6d4) !important;
        border: none !important;
        color: #fff !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px;
        transition: box-shadow 0.3s ease, transform 0.15s ease !important;
    }
    .stButton > button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover {
        box-shadow: 0 0 24px rgba(168, 85, 247, 0.35) !important;
        transform: translateY(-1px) !important;
    }
    
    /* Download buttons */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #1e1b4b, #0f172a) !important;
        border: 1px solid rgba(168, 85, 247, 0.3) !important;
        color: #c084fc !important;
        font-weight: 500 !important;
        transition: all 0.25s ease !important;
    }
    .stDownloadButton > button:hover {
        border-color: #a855f7 !important;
        box-shadow: 0 0 16px rgba(168, 85, 247, 0.2) !important;
        color: #e9d5ff !important;
    }
    
    /* Metrics */
    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, #1e1b4b, #0f172a);
        border: 1px solid rgba(168, 85, 247, 0.15);
        border-radius: 12px;
        padding: 12px 16px;
    }
    div[data-testid="stMetric"] label {
        color: #94a3b8 !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #22d3ee !important;
    }
    
    /* Progress bar */
    .stProgress > div > div {
        background: linear-gradient(90deg, #7c3aed, #a855f7, #06b6d4) !important;
    }
    
    /* Expander */
    details {
        border: 1px solid rgba(168, 85, 247, 0.15) !important;
        border-radius: 12px !important;
    }
    
    /* Dividers */
    hr {
        border-color: rgba(168, 85, 247, 0.12) !important;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────
# SIDEBAR — Credentials & Configuration
# ──────────────────────────────────────────

st.sidebar.markdown("### 🔐 API Credentials")

st.sidebar.markdown("""
<div style="background: linear-gradient(145deg, #1e1b4b, #0f172a); border: 1px solid rgba(168,85,247,0.2); padding: 14px; border-radius: 12px; margin-bottom: 16px;">
    <p style="color: #94a3b8; font-size: 0.8rem; margin: 0; line-height: 1.7;">
        <strong style="color: #c084fc;">🤗 Hugging Face</strong> — Speaker diarization. 
        <a href="https://huggingface.co/settings/tokens" target="_blank" style="color: #22d3ee;">Get token →</a><br>
        <strong style="color: #fbbf24;">🔑 Sarvam AI</strong> — Hindi & Kannada translation. 
        <a href="https://www.sarvam.ai/" target="_blank" style="color: #22d3ee;">Get API key →</a>
    </p>
</div>
""", unsafe_allow_html=True)

hf_token = st.sidebar.text_input("🤗 Hugging Face Token", type="password", help="Required for Pyannote speaker diarization. Accept model terms at huggingface.co first.")
sarvam_key = st.sidebar.text_input("🔑 Sarvam API Key", type="password", help="Required for translating English → Hindi / Kannada via Sarvam AI.")

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Model Configuration")

WHISPER_MODELS = {
    "tiny": "⚡ Tiny — Fastest, least accurate (~1 GB RAM)",
    "base": "🔹 Base — Good balance of speed & accuracy (~1.5 GB RAM)",
    "small": "🔸 Small — Better accuracy, slower (~2 GB RAM)",
    "medium": "🟠 Medium — High accuracy, much slower (~5 GB RAM)",
    "large": "🔴 Large — Best accuracy, very slow (~10 GB RAM)"
}
model_size = st.sidebar.selectbox(
    "Whisper Speech-to-Text Model",
    options=list(WHISPER_MODELS.keys()),
    index=1,
    format_func=lambda x: WHISPER_MODELS[x],
    help="OpenAI Whisper model for transcribing speech. Larger models are more accurate but use more RAM and are slower on CPU."
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🌍 Output Languages")

target_langs = st.sidebar.multiselect(
    "Select Target Languages",
    options=list(SUPPORTED_LANGUAGES.keys()),
    default=["English", "Hindi", "Kannada"],
    help="Choose which languages to generate audio tracks and subtitles for. English is the source language."
)

st.sidebar.markdown("---")

# Sidebar tech stack info
st.sidebar.markdown("### 🧠 Technology Stack")
st.sidebar.markdown("""
| Component | Technology |
|---|---|
| 🎙 Transcription | OpenAI Whisper |
| 👥 Speaker ID | Pyannote 3.1 |
| 🌐 Translation | Sarvam AI API |
| 🗣 Voice Synthesis | Microsoft Edge TTS |
| 🎬 Video Processing | FFmpeg |
| 🖥 UI Framework | Streamlit |
""")

# ──────────────────────────────────────────
# MAIN PAGE
# ──────────────────────────────────────────

st.markdown('<div class="hero-title">🎬 AI Video Translator</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">Netflix-style multi-language audio & subtitles — powered by AI</div>', unsafe_allow_html=True)

# How it works section
with st.expander("🔍 How It Works — Full Pipeline Explained", expanded=False):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="tech-card">
            <h4>🎙 Step 1 — Speech-to-Text (Whisper)</h4>
            <p>OpenAI's Whisper model transcribes your entire video audio in a <strong>single pass</strong> — no chunking, no repeated calls. 
            Produces timestamped text segments with word-level precision.</p>
            <span class="tech-badge">OpenAI Whisper</span>
            <span class="tech-badge">Single Pass</span>
            <span class="tech-badge">CPU Optimized</span>
        </div>
        
        <div class="tech-card">
            <h4>👥 Step 2 — Speaker Diarization</h4>
            <p>Pyannote 3.1 identifies <strong>who is speaking when</strong>. Each transcript segment is 
            assigned to a specific speaker. We also detect speaker gender using pitch analysis (F0 frequency) 
            so the translated voice matches the original speaker.</p>
            <span class="tech-badge">Pyannote 3.1</span>
            <span class="tech-badge">Gender Detection</span>
        </div>
        
        <div class="tech-card">
            <h4>🌐 Step 3 — Translation</h4>
            <p>Text is translated from English into your selected languages using <strong>Sarvam AI</strong>, 
            an Indic-language-focused translation API. Each segment is translated individually to preserve 
            timing and context. English segments pass through unchanged.</p>
            <span class="tech-badge">Sarvam AI</span>
            <span class="tech-badge">Hindi</span>
            <span class="tech-badge">Kannada</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="tech-card">
            <h4>🗣 Step 4 — Voice Generation (TTS)</h4>
            <p>Microsoft Edge TTS generates natural-sounding speech for each segment. 
            <strong>Male speakers get male voices, female speakers get female voices</strong> — automatically. 
            English is slowed slightly (-10%) for clarity.</p>
            <span class="tech-badge">Edge TTS</span>
            <span class="tech-badge">Gender-Aware</span>
            <span class="tech-badge">Per-Speaker Voice</span>
        </div>
        
        <div class="tech-card">
            <h4>🎚 Step 5 — Audio Mixing & Leveling</h4>
            <p>Each language track is precisely placed on a silent timeline at the exact timestamps from Whisper. 
            <strong>Kannada audio is ducked to -21 LUFS</strong> with a mid-frequency EQ cut so it sits 
            "behind" the main voice as ambient presence. English is normalized to -14 LUFS.</p>
            <span class="tech-badge">LUFS Normalization</span>
            <span class="tech-badge">EQ Processing</span>
        </div>
        
        <div class="tech-card">
            <h4>🎬 Step 6 — Final Merge & Player</h4>
            <p>FFmpeg combines the original video with all audio tracks and burns in English subtitles. 
            The custom <strong>Netflix-style player</strong> lets you switch audio language and subtitles 
            in real-time — right inside the browser.</p>
            <span class="tech-badge">FFmpeg</span>
            <span class="tech-badge">Multi-Audio MP4</span>
            <span class="tech-badge">Burned-in Captions</span>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ──────────────────────────────────────────
# UPLOAD & TRANSLATE
# ──────────────────────────────────────────

st.subheader("📤 Upload Your Video")
uploaded_file = st.file_uploader(
    "Drop your video here",
    type=["mp4"],
    help="Upload an MP4 video file. For best results, use a video with clear speech and minimal background noise."
)

if uploaded_file:
    st.info(f"📁 **{uploaded_file.name}** — {uploaded_file.size / (1024*1024):.1f} MB")

if st.button("🚀 Translate & Build Video", type="primary", use_container_width=True):
    if not uploaded_file:
        st.error("Please upload a video file first.")
        st.stop()
        
    if not target_langs:
        st.error("Please select at least one target language.")
        st.stop()
        
    if "Hindi" in target_langs or "Kannada" in target_langs:
        if not sarvam_key:
            st.warning("⚠️ Sarvam API Key is missing. Indic translation will fall back to English text.")
            
    if not hf_token:
        st.warning("⚠️ HF Token is missing. Pyannote diarization might fail if not authenticated.")

    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 1. Save uploaded file to temp
    # Reset voice cache for fresh speaker assignments
    reset_voice_cache()
    
    status_text.markdown("**💾 Saving uploaded video...**")
    input_video_path = os.path.join(TEMP_DIR, "input_video.mp4")
    with open(input_video_path, "wb") as f:
        f.write(uploaded_file.read())
    progress_bar.progress(5)
    
    try:
        # 2. Extract Audio
        status_text.markdown("**🎵 Extracting audio (FFmpeg → 16kHz mono WAV)...**")
        wav_path = extract_audio(input_video_path)
        progress_bar.progress(10)
        
        # 3. Transcribe with Whisper (Single Pass)
        status_text.markdown(f"**🎙 Transcribing full audio (Whisper `{model_size}` model)...**")
        transcription_segments = transcribe(wav_path, model_size)
        progress_bar.progress(30)
        
        # 4. Speaker Diarization
        status_text.markdown("**👥 Running Speaker Diarization (Pyannote 3.1)...**")
        diarization_segments = diarize(wav_path, hf_token)
        assigned_segments = assign_speakers(transcription_segments, diarization_segments)
        progress_bar.progress(45)
        
        # 5. Gender Detection
        status_text.markdown("**🧬 Detecting Speaker Genders (Pitch Analysis)...**")
        gender_map = detect_gender(wav_path, assigned_segments)
        progress_bar.progress(50)
        
        # 6. Translation
        langs_str = ", ".join(target_langs)
        status_text.markdown(f"**🌐 Translating to {langs_str} (Sarvam AI)...**")
        lang_tracks_text = translate_segments(assigned_segments, target_langs, sarvam_key)
        progress_bar.progress(60)
        
        # 7. Generate TTS & Audio Tracks
        status_text.markdown("**🗣 Generating Voice Tracks (Microsoft Edge TTS)...**")
        import wave
        with wave.open(wav_path, "r") as wf:
            total_duration_ms = int((wf.getnframes() / wf.getframerate()) * 1000)
            
        final_audio_tracks = {}
        
        async def build_all_tts():
            for idx, lang_name in enumerate(target_langs):
                status_text.markdown(f"**🗣 Synthesizing {lang_name} voices (Edge TTS)...**")
                track_segments = lang_tracks_text[lang_name]
                wav_paths = await generate_speech_for_track(lang_name, track_segments, idx)
                
                status_text.markdown(f"**🎚 Mixing & leveling {lang_name} audio track...**")
                final_track_path = build_audio_track(track_segments, wav_paths, total_duration_ms, lang_name)
                final_audio_tracks[lang_name] = final_track_path
                
        asyncio.run(build_all_tts())
        progress_bar.progress(80)
        
        # 8. Generate Subtitles for ALL languages
        status_text.markdown("**📝 Generating subtitles (SRT) for all languages...**")
        srt_paths = {}
        for lang_name in target_langs:
            srt_path = generate_srt(lang_tracks_text[lang_name], lang_name)
            srt_paths[lang_name] = srt_path
        
        primary_srt_lang = "English" if "English" in target_langs else target_langs[0]
        primary_srt_path = srt_paths[primary_srt_lang]
        progress_bar.progress(85)
        
        # 9. Merge Video (for download — multi-track)
        status_text.markdown("**🎬 Merging final multi-track video (FFmpeg)...**")
        final_output_path = merge_video(input_video_path, final_audio_tracks, primary_srt_path)
        progress_bar.progress(90)
        
        # 10. Generate per-language MP4s for the player
        status_text.markdown("**🎬 Generating per-language videos for Netflix player...**")
        per_lang_videos = generate_per_language_videos(input_video_path, final_audio_tracks)
        progress_bar.progress(100)
        
        status_text.markdown("**✅ Process Complete!**")
        
        # ── Results ──
        st.success("🎉 Translation and render successful!")
        st.balloons()
        
        # Netflix-Style Player
        st.markdown("---")
        st.subheader("🎬 Netflix-Style Video Player")
        st.caption("Hover over the player and click ⚙️ at the bottom-right to switch audio language and subtitles.")
        netflix_player(per_lang_videos, srt_paths, OUTPUT_DIR)
        
        st.markdown("---")
        
        # Pipeline summary
        with st.expander("📊 Processing Summary", expanded=True):
            sc1, sc2, sc3, sc4 = st.columns(4)
            sc1.metric("Segments", len(transcription_segments))
            sc2.metric("Speakers", len(gender_map))
            sc3.metric("Languages", len(target_langs))
            sc4.metric("Duration", f"{total_duration_ms / 1000:.0f}s")
            
            st.markdown("**Speaker Gender Map:**")
            for spk, gender in gender_map.items():
                icon = "👨" if gender == "male" else "👩"
                st.write(f"{icon} **{spk}** → {gender}")
        
        # Downloads
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📥 Download Video")
            with open(final_output_path, "rb") as file:
                st.download_button(
                    label="⬇️ Download Final Video (.mp4)",
                    data=file,
                    file_name="translated_multi_audio_video.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )
        with col2:
            st.subheader("📄 Download Subtitles")
            for lang_name, srt_file in srt_paths.items():
                with open(srt_file, "rb") as file:
                    st.download_button(
                        label=f"⬇️ {lang_name} Subtitles (.srt)",
                        data=file,
                        file_name=f"{lang_name}_subs.srt",
                        mime="text/plain",
                        key=f"srt_{lang_name}",
                        use_container_width=True
                    )
                
    except Exception as e:
        status_text.error(f"❌ Pipeline Failed: {str(e)}")
        progress_bar.empty()
