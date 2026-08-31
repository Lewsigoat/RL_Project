"""Render the 1984 Part-One summary script to a single narrated MP3.

Reads script.md, speaks each paragraph with gTTS (en-GB voice), and stitches
the pieces together with ffmpeg, inserting short pauses between paragraphs and
longer ones between sections.

Usage:  python3 generate_audio.py [--script script.md] [--out 1984_part1_summary.mp3]
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

from gtts import gTTS

PARA_GAP = 0.45      # seconds of silence between paragraphs
SECTION_GAP = 1.30   # seconds of silence between sections
TLD = "co.uk"        # gives the en-GB accent
MAX_RETRIES = 5


def parse_sections(path):
    """Split script.md into [(section_name, [paragraph, ...]), ...]."""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()

    # Drop the document title line ("# ...") -- it is a heading, not narration.
    raw = re.sub(r"\A#[^#\n].*\n", "", raw)

    chunks = re.split(r"^##\s*\[([A-Z0-9 ]+)\]\s*$", raw, flags=re.MULTILINE)
    # chunks == ['', name1, body1, name2, body2, ...]
    sections = []
    for name, body in zip(chunks[1::2], chunks[2::2]):
        paras = [clean(p) for p in body.strip().split("\n\n")]
        paras = [p for p in paras if p]
        if paras:
            sections.append((name.strip(), paras))
    return sections


def clean(text):
    """Flatten a markdown paragraph into something a TTS engine reads well."""
    text = " ".join(text.split())
    text = text.replace("—", ",").replace("–", ",")
    text = re.sub(r"[*_`]", "", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",\s*,", ",", text)
    return text.strip()


def speak(text, dest):
    """gTTS one paragraph to dest, retrying with backoff on transient failures."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            gTTS(text=text, lang="en", tld=TLD).save(dest)
            if os.path.getsize(dest) > 0:
                return
            raise RuntimeError("empty audio file")
        except Exception as exc:  # network hiccup or rate limit
            if attempt == MAX_RETRIES:
                raise
            wait = 2 ** attempt
            print(f"    retry {attempt}/{MAX_RETRIES - 1} in {wait}s ({exc})",
                  file=sys.stderr)
            time.sleep(wait)


def make_silence(seconds, dest):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "anullsrc=r=24000:cl=mono", "-t", f"{seconds}",
         "-c:a", "libmp3lame", "-b:a", "64k", dest],
        check=True,
    )


def concat(parts, dest, workdir):
    listing = os.path.join(workdir, "parts.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for part in parts:
            fh.write(f"file '{part}'\n")
    # Re-encode rather than stream-copy so the varying gTTS chunks and the
    # silence clips end up with one consistent stream.
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", listing, "-c:a", "libmp3lame", "-b:a", "96k", "-ar", "24000",
         "-ac", "1", dest],
        check=True,
    )


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default=os.path.join(here, "script.md"))
    ap.add_argument("--out", default=os.path.join(here, "1984_part1_summary.mp3"))
    args = ap.parse_args()

    sections = parse_sections(args.script)
    total_paras = sum(len(p) for _, p in sections)
    print(f"{len(sections)} sections, {total_paras} paragraphs")

    workdir = tempfile.mkdtemp(prefix="tts_")
    try:
        para_gap = os.path.join(workdir, "gap_para.mp3")
        section_gap = os.path.join(workdir, "gap_section.mp3")
        make_silence(PARA_GAP, para_gap)
        make_silence(SECTION_GAP, section_gap)

        parts = []
        done = 0
        for s_idx, (name, paras) in enumerate(sections):
            print(f"[{name}]")
            for p_idx, para in enumerate(paras):
                piece = os.path.join(workdir, f"s{s_idx:02d}_p{p_idx:03d}.mp3")
                speak(para, piece)
                done += 1
                print(f"  {done}/{total_paras}  {para[:60]}...")
                if p_idx:
                    parts.append(para_gap)
                parts.append(piece)
            # Rebuild ordering: gap goes *before* each paragraph after the first,
            # and a section gap separates sections.
            if s_idx != len(sections) - 1:
                parts.append(section_gap)

        concat(parts, args.out, workdir)
        mins, secs = divmod(duration(args.out), 60)
        size = os.path.getsize(args.out) / 1e6
        print(f"\nWrote {args.out}  ({int(mins)}m {int(secs)}s, {size:.1f} MB)")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
