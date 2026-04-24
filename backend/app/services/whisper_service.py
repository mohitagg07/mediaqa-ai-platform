"""
whisper_service.py — definitive Windows fix

WHAT WHISPER ACTUALLY DOES INTERNALLY:
  whisper/audio.py calls:
    out = run_subprocess(["ffmpeg", "-nostdin", "-threads", "0", "-i", file, ...])
  where run_subprocess is whisper's own wrapper (NOT subprocess.run directly).
  In newer whisper versions it uses:
    subprocess.run(cmd, ...)   where cmd[0] == "ffmpeg"
  but the call happens INSIDE whisper's load_audio, so patching subprocess.run
  at the module level after import doesn't intercept it reliably on Windows
  because of how Python resolves module-level references.

THE DEFINITIVE FIX:
  1. Get the full ffmpeg path from imageio-ffmpeg
  2. Read whisper/audio.py source at runtime
  3. Replace the hardcoded "ffmpeg" string with the full path
  4. Re-exec the modified source in whisper.audio's namespace
  This is the only guaranteed approach on Windows without modifying PATH globally.

  Alternative used here: use audioread + numpy directly to decode audio,
  completely bypassing whisper's ffmpeg dependency for the decode step,
  then pass raw audio array to model.transcribe().
"""

import os
import sys
import shutil
import logging
import numpy as np
from typing import Dict, List, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_model = None
_ffmpeg_exe: Optional[str] = None


def _find_ffmpeg() -> Optional[str]:
    """Return absolute path to ffmpeg executable, or None."""
    global _ffmpeg_exe
    if _ffmpeg_exe:
        return _ffmpeg_exe

    # 1. Already on PATH?
    found = shutil.which("ffmpeg")
    if found:
        _ffmpeg_exe = found
        return _ffmpeg_exe

    # 2. imageio-ffmpeg (most reliable on Windows)
    try:
        import imageio_ffmpeg
        _ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        logger.info(f"ffmpeg via imageio-ffmpeg: {_ffmpeg_exe}")
        return _ffmpeg_exe
    except Exception as e:
        logger.warning(f"imageio-ffmpeg: {e}")

    return None


def _patch_whisper_audio(ffmpeg_exe: str) -> bool:
    """
    Directly patch whisper.audio module so load_audio uses the full ffmpeg path.
    We rewrite the load_audio function by reading whisper's source and injecting
    the absolute path, then exec-ing it into the module namespace.
    """
    try:
        import whisper.audio as wa
        import inspect, textwrap, types

        src = inspect.getsource(wa.load_audio)

        # Normalize indentation (inspect preserves method indent)
        src = textwrap.dedent(src)

        # Replace bare "ffmpeg" string in the cmd list with the full path.
        # whisper builds: cmd = ["ffmpeg", "-nostdin", ...]
        # We replace: ["ffmpeg",  →  ["/full/path/to/ffmpeg",
        ffmpeg_escaped = ffmpeg_exe.replace("\\", "\\\\")
        patched = src.replace('"ffmpeg"', f'r"{ffmpeg_exe}"')
        patched = patched.replace("'ffmpeg'", f"r'{ffmpeg_exe}'")

        if patched == src:
            logger.warning("whisper source patch: no 'ffmpeg' string found to replace. Trying fallback.")
            return False

        # Compile and inject into whisper.audio's namespace
        globs = {**vars(wa), "__name__": wa.__name__}
        exec(compile(patched, "<whisper_patch>", "exec"), globs)
        wa.load_audio = globs["load_audio"]
        logger.info(f"whisper.audio.load_audio patched with: {ffmpeg_exe}")
        return True

    except Exception as e:
        logger.warning(f"whisper source patch failed: {e}")
        return False


def _load_audio_fallback(file_path: str, ffmpeg_exe: str, sr: int = 16000) -> np.ndarray:
    """
    Decode audio to float32 numpy array using ffmpeg directly via subprocess.
    This completely replaces whisper's load_audio — we call ffmpeg ourselves
    with the full path, pipe the output, and return the array.
    """
    import subprocess

    cmd = [
        ffmpeg_exe,
        "-nostdin",
        "-threads", "0",
        "-i", file_path,
        "-f", "s16le",        # signed 16-bit little-endian PCM
        "-ac", "1",           # mono
        "-acodec", "pcm_s16le",
        "-ar", str(sr),       # resample to target sr
        "pipe:1"              # output to stdout
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300
        )
    except FileNotFoundError:
        raise RuntimeError(
            f"ffmpeg not found at: {ffmpeg_exe}\n"
            "This should not happen — please report this error."
        )

    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")[-500:]
        raise RuntimeError(f"ffmpeg decode failed:\n{err}")

    # Convert raw PCM bytes → float32 numpy array normalised to [-1, 1]
    audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return audio


def get_whisper_model():
    """Lazy-load Whisper model (singleton)."""
    global _model
    if _model is None:
        logger.info(f"Loading Whisper model: {settings.WHISPER_MODEL}")
        import whisper
        _model = whisper.load_model(settings.WHISPER_MODEL)
        logger.info("Whisper model loaded successfully")
    return _model


def transcribe_audio(file_path: str) -> Dict:
    """
    Transcribe audio/video using Whisper.
    Uses a direct ffmpeg subprocess to decode audio, bypassing whisper's
    internal ffmpeg call — guaranteed to work on Windows without PATH changes.
    """
    if not os.path.isfile(file_path):
        raise RuntimeError(f"File not found: {file_path}")

    ffmpeg_exe = _find_ffmpeg()
    if not ffmpeg_exe:
        raise RuntimeError(
            "ffmpeg not found. Run: pip install imageio-ffmpeg\n"
            "Then restart the server."
        )

    # Try patching whisper first (cleanest approach)
    patched = _patch_whisper_audio(ffmpeg_exe)

    model = get_whisper_model()
    logger.info(f"Transcribing: {file_path}")

    try:
        if patched:
            # Use whisper normally — load_audio is now patched
            result = model.transcribe(file_path, word_timestamps=False, verbose=False)
        else:
            # Fallback: decode audio ourselves, pass numpy array to whisper
            logger.info("Using direct ffmpeg decode fallback")
            audio_array = _load_audio_fallback(file_path, ffmpeg_exe)
            result = model.transcribe(audio_array, word_timestamps=False, verbose=False)

    except FileNotFoundError:
        # Last resort: definitely use our fallback
        logger.warning("whisper transcribe raised FileNotFoundError — using direct decode")
        audio_array = _load_audio_fallback(file_path, ffmpeg_exe)
        result = model.transcribe(audio_array, word_timestamps=False, verbose=False)

    full_transcript = result.get("text", "").strip()
    segments = result.get("segments", [])

    timestamps = [
        {
            "start": round(seg["start"], 2),
            "end":   round(seg["end"], 2),
            "text":  seg["text"].strip()
        }
        for seg in segments
    ]

    logger.info(
        f"Transcription complete: {len(full_transcript)} chars, "
        f"{len(timestamps)} segments"
    )
    return {
        "transcript": full_transcript,
        "timestamps": timestamps,
        "language":   result.get("language", "en")
    }


def find_timestamp_for_text(query_text: str, timestamps: List[Dict]) -> Optional[Dict]:
    """Find best matching timestamp segment by word overlap."""
    if not timestamps:
        return None
    query_words = set(query_text.lower().split())
    best_score, best_seg = 0, None
    for seg in timestamps:
        score = len(query_words & set(seg["text"].lower().split()))
        if score > best_score:
            best_score, best_seg = score, seg
    return best_seg