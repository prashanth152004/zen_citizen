from dataclasses import dataclass
import torch
import torchaudio
import os
from pyannote.audio import Pipeline

@dataclass
class SpeakerSegment:
    start: float
    end: float
    text: str
    speaker_id: str
    gender: str = "unknown"

def diarize(wav_path: str, hf_token: str) -> list[dict]:
    """
    Runs Pyannote speaker diarization on the full audio file.
    Returns a list of dicts: [{'start': float, 'end': float, 'speaker': str}]
    """
    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))
        else:
            pipeline.to(torch.device("cpu"))
            
        diarization = pipeline(wav_path)
        
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker
            })
        return segments
    except Exception as e:
        raise RuntimeError(f"Pyannote diarization failed. Ensure your HF_TOKEN is valid and terms are accepted: {e}")

def assign_speakers(transcription_segments: list, diarization_segments: list) -> list[SpeakerSegment]:
    """
    Aligns Whisper transcript segments with Pyannote diarization.
    For each text segment, finds the speaker with maximum temporal overlap.
    If no overlap is found, assigns the nearest speaker by start time.
    """
    assigned = []
    
    for t_seg in transcription_segments:
        best_speaker = "UNKNOWN"
        max_overlap = 0.0
        
        for d_seg in diarization_segments:
            overlap_start = max(t_seg.start, d_seg["start"])
            overlap_end = min(t_seg.end, d_seg["end"])
            overlap = overlap_end - overlap_start
            
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = d_seg["speaker"]
        
        # If no overlap found, pick the nearest diarization segment
        if max_overlap <= 0 and diarization_segments:
            nearest = min(diarization_segments, key=lambda d: abs(d["start"] - t_seg.start))
            best_speaker = nearest["speaker"]
                
        assigned.append(
            SpeakerSegment(
                start=t_seg.start,
                end=t_seg.end,
                text=t_seg.text,
                speaker_id=best_speaker
            )
        )
        
    return assigned

def detect_gender(wav_path: str, assigned_segments: list[SpeakerSegment]) -> dict[str, str]:
    """
    Detects the gender of each unique speaker using F0 (fundamental frequency) estimation.
    Aggregates pitch samples from MULTIPLE segments per speaker for reliability.
    Male: median F0 < 165 Hz, Female: median F0 >= 165 Hz.
    Returns: {"SPEAKER_00": "male", "SPEAKER_01": "female"}
    """
    speaker_gender_map = {}
    
    waveform, sample_rate = torchaudio.load(wav_path)
    
    # Group all segments by speaker
    speaker_segments: dict[str, list[SpeakerSegment]] = {}
    for seg in assigned_segments:
        speaker_segments.setdefault(seg.speaker_id, []).append(seg)
    
    for spk, segs in speaker_segments.items():
        all_pitches = []
        
        # Analyze up to 5 longest segments per speaker for robust estimation
        sorted_segs = sorted(segs, key=lambda s: s.end - s.start, reverse=True)
        analysis_segs = sorted_segs[:5]
        
        for seg in analysis_segs:
            duration = seg.end - seg.start
            if duration < 0.3:
                continue  # Too short
                
            start_frame = int(seg.start * sample_rate)
            end_frame = int(seg.end * sample_rate)
            
            # Clamp to waveform bounds
            end_frame = min(end_frame, waveform.shape[1])
            if start_frame >= end_frame:
                continue
                
            clip = waveform[:, start_frame:end_frame]
            
            try:
                pitch = torchaudio.functional.detect_pitch_frequency(clip, sample_rate)
                voiced = pitch[pitch > 50]  # Filter out noise/unvoiced (< 50Hz)
                if len(voiced) > 0:
                    all_pitches.append(voiced)
            except Exception:
                continue
        
        if all_pitches:
            combined = torch.cat(all_pitches)
            median_pitch = torch.median(combined).item()
            
            if median_pitch < 165.0:
                speaker_gender_map[spk] = "male"
            else:
                speaker_gender_map[spk] = "female"
        else:
            # Default fallback if no voiced frames found
            speaker_gender_map[spk] = "male"
    
    # Update all segments with the computed gender
    for seg in assigned_segments:
        seg.gender = speaker_gender_map.get(seg.speaker_id, "male")
        
    return speaker_gender_map
