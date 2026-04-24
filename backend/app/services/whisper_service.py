"""
whisper_service.py

Key fixes:
  - CRASH FIX: "max() arg is an empty sequence" — faster-whisper bug with
    vad_filter=True on short/silent audio. We retry without VAD on failure.
  - ffprobe replaced with ffmpeg -i stderr parsing (imageio_ffmpeg only
    ships ffmpeg.exe on Windows, not ffprobe.exe).
  - is_silent flag returned so upload route can choose the right LLM prompt.
"""
import os
import re
import subprocess
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
_model = None


def _get_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        d = os.path.dirname(exe)
        if d not in os.environ.get("PATH", ""):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        return exe
    except Exception as e:
        logger.warning(f"imageio_ffmpeg not available: {e}")
        return "ffmpeg"


def get_whisper_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading faster-whisper model (base)...")
        _model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("faster-whisper model loaded OK")
    return _model


def _extract_raw_metadata(file_path: str) -> str:
    """Run ffmpeg -i and return stderr (contains all stream/format info)."""
    ffmpeg_exe = _get_ffmpeg_exe()
    try:
        result = subprocess.run(
            [ffmpeg_exe, "-i", file_path],
            capture_output=True, text=True, timeout=30,
        )
        return result.stderr   # ffmpeg -i always writes metadata to stderr
    except FileNotFoundError:
        logger.warning("ffmpeg not found")
        return ""
    except Exception as e:
        logger.warning(f"ffmpeg metadata failed: {e}")
        return ""


def _build_silent_description(file_path: str, raw: str) -> str:
    """
    Build a plain-English description of the media file from ffmpeg -i output.
    This becomes the RAG text AND the input to the LLM summary prompt.
    Intentionally written in natural language so the LLM can reason from it.
    """
    filename = os.path.basename(file_path)
    parts = [f"Video file: '{filename}'."]

    # Duration
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", raw)
    if m:
        h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        total_mins = int(h * 60 + mn)
        parts.append(
            f"Duration is {total_mins} minute{'s' if total_mins != 1 else ''} "
            f"and {int(s)} seconds."
        )

    # File size
    try:
        mb = os.path.getsize(file_path) / 1_048_576
        parts.append(f"File size is {mb:.1f} MB.")
    except Exception:
        pass

    # Video stream
    vm = re.search(r"Stream.*Video:\s*([\w]+).*?(\d{3,5})x(\d{3,5})", raw)
    if vm:
        parts.append(
            f"Video is encoded with {vm.group(1).upper()} codec "
            f"at {vm.group(2)}x{vm.group(3)} resolution."
        )

    # Audio stream
    am = re.search(r"Stream.*Audio:\s*([\w]+)", raw)
    if am:
        parts.append(
            f"An audio track is present ({am.group(1).upper()} codec) "
            "but no speech was detected — the audio likely contains "
            "background music, ambient sound, or silence."
        )
    else:
        parts.append(
            "There is no audio track — this is a completely silent video."
        )

    return " ".join(parts)


def _run_transcription(model, file_path: str, vad_filter: bool):
    segments_gen, info = model.transcribe(
        file_path,
        beam_size=5,
        word_timestamps=False,
        vad_filter=vad_filter,
    )
    return list(segments_gen), info   # evaluation happens here — crash point


def transcribe_audio(file_path: str) -> Dict:
    """
    Transcribe speech from audio/video with full crash recovery.

    Recovery order:
      1. Transcribe with vad_filter=True  (removes silence, best quality)
      2. Crash ("empty sequence") → retry with vad_filter=False
      3. Transcript still < 20 chars → silent/no-speech fallback
    """
    if not os.path.isfile(file_path):
        raise RuntimeError(f"File not found: {file_path}")

    _get_ffmpeg_exe()
    model = get_whisper_model()
    logger.info(f"Transcribing: {file_path}")

    segments, info = [], None

    # Attempt 1 — with VAD (best quality, fails on short/silent clips)
    try:
        segments, info = _run_transcription(model, file_path, vad_filter=True)
    except Exception as e:
        err = str(e)
        # Known faster-whisper crash on short/silent audio with vad_filter=True
        if any(k in err for k in ("empty sequence", "max()", "min()")):
            logger.warning(f"VAD crash ({err}) — retrying without vad_filter")
            try:
                segments, info = _run_transcription(model, file_path, vad_filter=False)
            except Exception as e2:
                logger.warning(f"Retry also failed: {e2}. Using silent fallback.")
                segments, info = [], None
        else:
            raise RuntimeError(f"Transcription failed: {err}")

    # Build transcript from segments
    transcript_parts, timestamps = [], []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        transcript_parts.append(text)
        timestamps.append({
            "start": round(seg.start, 2),
            "end":   round(seg.end, 2),
            "text":  text,
        })

    full_transcript = " ".join(transcript_parts).strip()

    # Silent / no-speech fallback
    if len(full_transcript) < 20:
        logger.info(f"No speech detected — using metadata fallback for: {file_path}")
        raw = _extract_raw_metadata(file_path)
        description = _build_silent_description(file_path, raw)
        return {
            "transcript": description,
            "timestamps": [],
            "language":   getattr(info, "language", "en") if info else "en",
            "is_silent":  True,
        }

    logger.info(
        f"Transcription OK: {len(full_transcript)} chars, {len(timestamps)} segments"
    )
    return {
        "transcript": full_transcript,
        "timestamps": timestamps,
        "language":   getattr(info, "language", "en"),
        "is_silent":  False,
    }


def find_timestamp_for_text(
    query_text: str, timestamps: List[Dict]
) -> Optional[Dict]:
    if not timestamps:
        return None
    query_words = set(query_text.lower().split())
    best_score, best_seg = 0, None
    for seg in timestamps:
        score = len(query_words & set(seg["text"].lower().split()))
        if score > best_score:
            best_score, best_seg = score, seg
    return best_seg if best_seg else timestamps[0]
