"""
MP4 Video to Markdown Converter
Transcribes MP4 video files using faster-whisper and converts to markdown format.
Uses faster-whisper (4x faster than openai/whisper on CPU, same accuracy).
"""

import logging
import subprocess
from datetime import datetime
from pathlib import Path


def _seconds_to_timestamp(seconds: float) -> str:
    """Convert float seconds to compact M:SS or H:MM:SS timestamp for inline use."""
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def _format_transcript_segments(segments: list) -> str:
    """Format faster-whisper segments as timestamped markdown paragraphs."""
    lines = []
    for start, text in segments:
        if text:
            lines.append(f"**[{_seconds_to_timestamp(start)}]** {text}")
    return "\n\n".join(lines)


def _get_duration(mp4_path: Path) -> str:
    """Return video duration as H:MM:SS using ffprobe. Returns 'unknown' if ffprobe is unavailable."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(mp4_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return _seconds_to_timestamp(float(result.stdout.strip()))
    except Exception:
        pass
    return "unknown"


def convert_mp4_to_markdown(mp4_path: Path, output_path, whisper_model: str = "medium") -> str:
    """
    Convert MP4 video to markdown by transcribing audio with faster-whisper.

    Args:
        mp4_path:       Path to the MP4 video file
        output_path:    Path where the markdown file should be saved
        whisper_model:  Model size: tiny / small / medium / large (default: small)

    Returns:
        Path to the created markdown file

    Raises:
        RuntimeError: If transcription fails
    """
    mp4_path = Path(mp4_path)
    output_path = Path(output_path) if not isinstance(output_path, Path) else output_path

    logging.info(f"Transcribing video: {mp4_path.name}")

    if not mp4_path.exists():
        raise FileNotFoundError(f"Video file not found: {mp4_path}")

    if mp4_path.suffix.lower() not in ['.mp4', '.mov', '.avi', '.mkv']:
        raise ValueError(f"Unsupported video format: {mp4_path.suffix}")

    file_size_mb = mp4_path.stat().st_size / (1024 * 1024)
    duration = _get_duration(mp4_path)
    logging.info(f"Video size: {file_size_mb:.1f} MB, duration: {duration}")
    logging.info(f"Starting faster-whisper transcription (model: {whisper_model})...")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        )

    # int8 = fastest on CPU, identical accuracy to float32
    model = WhisperModel(whisper_model, device="cpu", compute_type="int8")

    segments_gen, _ = model.transcribe(
        str(mp4_path),
        language="en",
        beam_size=5,
    )

    # Materialise the generator — this is where the work happens
    transcript_segments = [(seg.start, seg.text.strip()) for seg in segments_gen]
    transcript_text = " ".join(text for _, text in transcript_segments).strip()

    if len(transcript_text) < 50:
        raise RuntimeError(
            f"Transcript is suspiciously short ({len(transcript_text)} chars). "
            "Video may have no audio or transcription failed silently."
        )

    logging.info(f"Transcription complete: {len(transcript_text):,} characters, "
                 f"{len(transcript_segments)} segments")

    markdown_content = f"""---
source_file: {mp4_path.name}
file_type: Video Transcription
file_size: {file_size_mb:.2f} MB
duration: {duration}
transcription_date: {datetime.now().isoformat()}
transcription_model: faster-whisper/{whisper_model}
---

# Video Transcription: {mp4_path.stem}

**Source:** {mp4_path.name}  
**Size:** {file_size_mb:.1f} MB  
**Transcribed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Transcript

{_format_transcript_segments(transcript_segments)}

---

*Transcribed using faster-whisper ({whisper_model} model) on {datetime.now().strftime('%Y-%m-%d')}*
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    logging.info(f"✓ Video transcribed successfully: {output_path}")
    logging.info(f"  Transcript length: {len(transcript_text):,} characters")

    return str(output_path)


# Made with Bob
