"""
Video URL to Markdown Converter
Downloads audio-only + metadata via yt-dlp, transcribes with faster-whisper,
and produces a rich AI-optimized markdown file.

Uses faster-whisper (4x faster than openai/whisper on CPU, same accuracy).
"""

import json
import logging
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


def _check_ffmpeg() -> None:
    """Raise a clear RuntimeError if ffmpeg is not found on PATH."""
    result = subprocess.run(
        ["ffmpeg", "-version"],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "ffmpeg is not installed or not on your PATH.\n\n"
            "Install it with:\n"
            "  Windows:  winget install ffmpeg\n"
            "  Mac:      brew install ffmpeg\n"
            "  Linux:    sudo apt install ffmpeg\n\n"
            "After installing, restart this application."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seconds_to_hms(seconds: int) -> str:
    """Convert integer seconds to H:MM:SS string."""
    if not seconds:
        return "0:00:00"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:02d}"


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
    """Format Whisper segments as timestamped markdown paragraphs."""
    lines = []
    for start, text in segments:
        if text:
            lines.append(f"**[{_seconds_to_timestamp(start)}]** {text}")
    return "\n\n".join(lines)


def _parse_upload_date(raw: str) -> str:
    """Convert yt-dlp YYYYMMDD string to YYYY-MM-DD."""
    if raw and len(raw) == 8:
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw or "Unknown"


def _sanitize_filename(title: str, max_len: int = 100) -> str:
    """Turn a video title into a safe filename."""
    safe = re.sub(r'[\\/:*?"<>|]', '', title)   # strip forbidden chars
    safe = re.sub(r'\s+', '_', safe.strip())      # spaces → underscores
    safe = re.sub(r'_+', '_', safe)               # collapse multiple underscores
    safe = safe.strip('_')
    return safe[:max_len] if safe else "video"


def _format_chapters(chapters: list) -> str:
    """Format yt-dlp chapters list into a markdown list."""
    if not chapters:
        return ""
    lines = []
    for ch in chapters:
        start = ch.get("start_time", 0)
        title = ch.get("title", "Chapter")
        h = int(start) // 3600
        m = (int(start) % 3600) // 60
        s = int(start) % 60
        timestamp = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        lines.append(f"- **{timestamp}** — {title}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main converter function
# ---------------------------------------------------------------------------

def convert_video_url_to_markdown(
    url: str,
    output_folder: str | Path,
    whisper_model: str = "medium",
    progress_callback: Optional[Callable[[str], None]] = None
) -> str:
    """
    Download audio + metadata from a video URL, transcribe with faster-whisper,
    and write a rich AI-optimized markdown file.

    Args:
        url:               Video URL (YouTube or any yt-dlp supported site)
        output_folder:     Directory where the .md file will be saved
        whisper_model:     Model name: tiny / small / medium / large
        progress_callback: Optional callable(status_message) for live UI updates

    Returns:
        Absolute path to the created markdown file.

    Raises:
        RuntimeError: If yt-dlp or transcription fails.
        FileNotFoundError: If expected output files are missing.
    """

    def _status(msg: str):
        logging.info(msg)
        if progress_callback:
            progress_callback(msg)

    # Fail fast if ffmpeg is missing — before any download attempt
    _check_ffmpeg()

    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    temp_dir = output_folder / "_temp_video"
    temp_dir.mkdir(exist_ok=True)

    try:
        # ------------------------------------------------------------------
        # Step 1 — Download audio-only + metadata via yt-dlp
        # ------------------------------------------------------------------
        _status("Step 1 of 4: Downloading audio...")

        yt_result = subprocess.run(
            [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "mp3",
                "--write-info-json",
                "--no-playlist",
                "--output", str(temp_dir / "%(title)s.%(ext)s"),
                url,
            ],
            capture_output=True,
            text=True,
            timeout=600,   # 10 min download timeout
        )

        if yt_result.returncode != 0:
            raise RuntimeError(
                f"yt-dlp failed:\n{yt_result.stderr}"
            )

        # ------------------------------------------------------------------
        # Step 2 — Locate downloaded files and parse metadata
        # ------------------------------------------------------------------
        _status("Step 2 of 4: Reading metadata...")

        audio_files = list(temp_dir.glob("*.mp3"))
        info_files  = list(temp_dir.glob("*.info.json"))

        if not audio_files:
            raise FileNotFoundError("yt-dlp completed but no .mp3 file found.")
        if not info_files:
            raise FileNotFoundError("yt-dlp completed but no .info.json file found.")

        audio_file = audio_files[0]
        info_file  = info_files[0]

        audio_size_mb = audio_file.stat().st_size / (1024 * 1024)
        logging.info(f"Audio downloaded: {audio_file.name} ({audio_size_mb:.1f} MB)")

        with open(info_file, "r", encoding="utf-8") as f:
            info = json.load(f)

        title        = info.get("title", "Untitled Video")
        channel      = info.get("uploader") or info.get("channel", "Unknown")
        upload_date  = _parse_upload_date(info.get("upload_date", ""))
        duration_sec = int(info.get("duration") or 0)
        duration     = _seconds_to_hms(duration_sec)
        view_count   = info.get("view_count")
        like_count   = info.get("like_count")
        description  = (info.get("description") or "").strip()
        chapters     = info.get("chapters") or []
        tags         = info.get("tags") or []
        webpage_url  = info.get("webpage_url", url)

        logging.info(f"Metadata: '{title}' by {channel} ({duration})")

        # ------------------------------------------------------------------
        # Step 3 — Transcribe with faster-whisper
        # ------------------------------------------------------------------
        _status(
            f"Step 3 of 4: Transcribing '{title}' with faster-whisper "
            f"({whisper_model}) — this takes several minutes on CPU..."
        )

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError(
                "faster-whisper is not installed. Run: pip install faster-whisper"
            )

        # int8 = fastest on CPU, identical accuracy to float32
        model = WhisperModel(whisper_model, device="cpu", compute_type="int8")

        segments, _ = model.transcribe(
            str(audio_file),
            language="en",
            beam_size=5,
        )

        # Materialise the generator — this is where the work happens
        transcript_segments = [(seg.start, seg.text.strip()) for seg in segments]
        transcript_text = " ".join(text for _, text in transcript_segments).strip()

        if len(transcript_text) < 50:
            raise RuntimeError(
                f"Transcript is suspiciously short ({len(transcript_text)} chars). "
                "Video may have no audio or transcription failed silently."
            )

        logging.info(f"Transcription complete: {len(transcript_text):,} characters, "
                     f"{len(transcript_segments)} segments")

        # ------------------------------------------------------------------
        # Step 4 — Assemble and write markdown
        # ------------------------------------------------------------------
        _status("Step 4 of 4: Writing markdown file...")

        view_str = f"{view_count:,}" if view_count else "N/A"
        like_str = f"{like_count:,}" if like_count else "N/A"
        tags_str = ", ".join(tags[:20]) if tags else "N/A"
        now      = datetime.now().isoformat()

        frontmatter = f"""---
source_type: Video Transcription
source_url: {webpage_url}
title: "{title}"
channel: "{channel}"
upload_date: {upload_date}
duration: {duration}
view_count: {view_str}
like_count: {like_str}
tags: [{tags_str}]
whisper_model: faster-whisper/{whisper_model}
transcription_date: {now}
---
"""

        header = f"""# {title}

**Source:** [{webpage_url}]({webpage_url})  
**Channel:** {channel}  
**Published:** {upload_date}  
**Duration:** {duration}  
**Views:** {view_str} · **Likes:** {like_str}"""

        description_section = f"## Description\n\n{description}" if description else ""

        chapters_section = ""
        if chapters:
            chapters_section = f"## Chapters\n\n{_format_chapters(chapters)}"

        transcript_section = f"## Transcript\n\n{_format_transcript_segments(transcript_segments)}"

        footer = (
            f"---\n\n"
            f"*Transcribed using faster-whisper ({whisper_model} model) "
            f"on {datetime.now().strftime('%Y-%m-%d')}*"
        )

        parts = [header]
        if description_section:
            parts.append(description_section)
        if chapters_section:
            parts.append(chapters_section)
        parts.append(transcript_section)
        parts.append(footer)

        markdown_content = frontmatter + "\n\n---\n\n".join(parts)

        safe_name   = _sanitize_filename(title)
        output_path = output_folder / f"{safe_name}.md"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        logging.info(f"✓ Markdown written: {output_path}")
        return str(output_path)

    finally:
        # Always clean up temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
