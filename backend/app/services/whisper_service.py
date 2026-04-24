"""
whisper_service.py
Uses faster-whisper for speech transcription.
For silent videos (no speech), falls back to ffprobe metadata extraction
so the RAG pipeline still has meaningful content to work with.
"""
import os
import json
import subprocess
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
_model = None


def _ensure_ffmpeg_on_path():
    try:
        import imageio_ffmpeg
        ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    except Exception as e:
        logger.warning(f"imageio_ffmpeg not available: {e}")


def get_whisper_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading faster-whisper model (base)...")
        _model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("faster-whisper model loaded OK")
    return _model


def _get_ffprobe_exe() -> str:
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        probe = ffmpeg_exe.replace("ffmpeg", "ffprobe")
        if os.path.isfile(probe):
            return probe
    except Exception:
        pass
    return "ffprobe"


def _extract_video_metadata(file_path: str) -> Dict:
    """Run ffprobe and return parsed JSON metadata."""
    cmd = [
        _get_ffprobe_exe(), "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        logger.warning(f"ffprobe failed: {e}")
    return {}


def _build_metadata_description(file_path: str, meta: Dict) -> str:
    """Convert ffprobe metadata into a human-readable description for RAG."""
    filename = os.path.basename(file_path)
    lines = [f"This is a media file named '{filename}'."]

    fmt = meta.get("format", {})

    # Duration
    dur = float(fmt.get("duration", 0))
    if dur:
        mins, secs = int(dur // 60), int(dur % 60)
        lines.append(f"Duration: {mins} minutes and {secs} seconds.")

    # File size
    size_bytes = int(fmt.get("size", 0))
    if size_bytes:
        lines.append(f"File size: {size_bytes / 1_048_576:.1f} MB.")

    # Format name
    fmt_name = fmt.get("format_long_name", fmt.get("format_name", ""))
    if fmt_name:
        lines.append(f"Container format: {fmt_name}.")

    # Streams
    video_streams, audio_streams = [], []
    for s in meta.get("streams", []):
        (video_streams if s.get("codec_type") == "video" else
         audio_streams if s.get("codec_type") == "audio" else []).append(s)

    for vs in video_streams:
        codec = vs.get("codec_long_name", vs.get("codec_name", "unknown"))
        w, h = vs.get("width", "?"), vs.get("height", "?")
        fps_raw = vs.get("r_frame_rate", "")
        fps_str = ""
        if "/" in fps_raw:
            try:
                n, d = fps_raw.split("/")
                fps_str = f" at {int(n) // max(int(d), 1)} fps"
            except Exception:
                pass
        lines.append(f"Video: {codec}, {w}x{h}{fps_str}.")

    for aus in audio_streams:
        codec = aus.get("codec_long_name", aus.get("codec_name", "unknown"))
        sr = aus.get("sample_rate", "")
        ch = {1: "mono", 2: "stereo"}.get(aus.get("channels"), "")
        parts = [p for p in [codec, ch, f"{sr} Hz" if sr else ""] if p]
        lines.append(f"Audio: {', '.join(parts)}.")

    if not audio_streams:
        lines.append("This file has no audio track — it is a silent video.")
    else:
        lines.append(
            "No speech was detected in the audio. "
            "The audio may contain background music, ambient sound, or silence."
        )

    # Tags
    tags = fmt.get("tags", {})
    for key in ("title", "Title", "comment", "Comment", "artist", "Artist"):
        val = tags.get(key, "")
        if val:
            lines.append(f"{key.capitalize()}: {val}.")

    return " ".join(lines)


def transcribe_audio(file_path: str) -> Dict:
    """
    Transcribe speech from audio/video.
    Falls back to ffprobe metadata description for silent files,
    so RAG pipeline always has content to work with.
    """
    if not os.path.isfile(file_path):
        raise RuntimeError(f"File not found: {file_path}")

    _ensure_ffmpeg_on_path()
    model = get_whisper_model()
    logger.info(f"Transcribing: {file_path}")

    try:
        segments_gen, info = model.transcribe(
            file_path,
            beam_size=5,
            word_timestamps=False,
            vad_filter=True,
        )
        segments = list(segments_gen)
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {str(e)}")

    transcript_parts, timestamps = [], []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        transcript_parts.append(text)
        timestamps.append({"start": round(seg.start, 2),
                           "end": round(seg.end, 2), "text": text})

    full_transcript = " ".join(transcript_parts).strip()

    # ── Silent video fallback ────────────────────────────────────────────────
    if len(full_transcript) < 20:
        logger.info(f"No speech — using metadata description for: {file_path}")
        meta = _extract_video_metadata(file_path)
        description = _build_metadata_description(file_path, meta)
        return {
            "transcript": description,
            "timestamps": [],
            "language": getattr(info, "language", "en"),
            "is_silent": True,
        }

    logger.info(f"Transcription OK: {len(full_transcript)} chars, {len(timestamps)} segments")
    return {
        "transcript": full_transcript,
        "timestamps": timestamps,
        "language": getattr(info, "language", "en"),
        "is_silent": False,
    }


def find_timestamp_for_text(query_text: str, timestamps: List[Dict]) -> Optional[Dict]:
    if not timestamps:
        return None
    query_words = set(query_text.lower().split())
    best_score, best_seg = 0, None
    for seg in timestamps:
        score = len(query_words & set(seg["text"].lower().split()))
        if score > best_score:
            best_score, best_seg = score, seg
    return best_seg if best_seg else timestamps[0]