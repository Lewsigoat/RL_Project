# 1984 — Audio Summary (Part One, Chapters 1–6)

A narrated summary of the first six chapters of George Orwell's *Nineteen Eighty-Four*.

## Files

| File | Description |
| --- | --- |
| `script.md` | The narration script, split into `## [SECTION]` blocks (intro, one per chapter, outro). |
| `generate_audio.py` | Renders `script.md` to a single MP3 using gTTS + ffmpeg. |
| `1984_part1_summary.mp3` | The generated audio. |

## Regenerating the audio

Requires network access to Google Translate's TTS endpoint.

```bash
pip install gtts
apt-get install -y ffmpeg
python3 generate_audio.py
```

Options: `--script <path>` and `--out <path>`.

The generator speaks each paragraph separately (retrying with backoff on
transient network failures), then stitches the pieces together with ffmpeg,
inserting a short pause between paragraphs and a longer one between sections.
Voice is en-GB, set via the gTTS `tld` parameter.

## Note on content

`script.md` is an original plot-and-theme summary written for this repo. It is
not an excerpt of the novel; only a handful of short, well-known Party slogans
are quoted directly.
