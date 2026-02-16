#!/usr/bin/env python3
"""
Convert Google Meet transcript HTML to SRT subtitle format.

Usage:
  python3 html_to_srt.py INPUT_HTML [OUTPUT_SRT]
  python3 html_to_srt.py day2.transcript.txt.html
  python3 html_to_srt.py day2.transcript.txt.html day2.transcript.srt
  python3 html_to_srt.py --verbose day2.transcript.txt.html

Options:
  --verbose, -v   Show debug output
"""

import argparse
import re
import sys
from pathlib import Path


def log(msg, verbose=False):
    if verbose:
        print(f"  [debug] {msg}", file=sys.stderr)


def ms_to_srt_time(ms):
    """Convert milliseconds to SRT timestamp format HH:MM:SS,mmm"""
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def parse_html_segments(html_content, verbose=False):
    """Extract segments from Google Meet transcript HTML."""
    segments = []

    # Match JnEIz divs (including variants like "JnEIz MuNFDe")
    segment_pattern = re.compile(
        r'<div\s+class="JnEIz[^"]*"[^>]*data-timestamp="(\d+)"[^>]*>'
        r'.*?<div\s+class="wyBDIb"[^>]*>(.*?)</div></div>',
        re.DOTALL
    )

    for match in segment_pattern.finditer(html_content):
        timestamp_ms = int(match.group(1))
        raw_text = match.group(2)

        # Clean HTML entities and tags
        text = re.sub(r'<[^>]+>', '', raw_text)
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")

        # Normalize whitespace: collapse multiple newlines to single
        text = re.sub(r'\n{2,}', '\n', text)
        text = text.strip()

        if text:
            segments.append((timestamp_ms, text))

    log(f"Parsed {len(segments)} segments from HTML", verbose)
    return segments


def segments_to_srt(segments, verbose=False):
    """Convert parsed segments to SRT format string."""
    lines = []

    for i, (start_ms, text) in enumerate(segments):
        seq = i + 1

        # End time = next segment's start, or start + 8000ms for last
        if i + 1 < len(segments):
            end_ms = segments[i + 1][0]
        else:
            end_ms = start_ms + 8000

        start_str = ms_to_srt_time(start_ms)
        end_str = ms_to_srt_time(end_ms)

        lines.append(f"{seq}")
        lines.append(f"{start_str} --> {end_str}")
        lines.append(text)
        lines.append("")  # blank line separator

    return "\n".join(lines) + "\n" if lines else ""


def main():
    parser = argparse.ArgumentParser(
        description="Convert Google Meet transcript HTML to SRT"
    )
    parser.add_argument("input", help="Input HTML file path")
    parser.add_argument("output", nargs="?", help="Output SRT file path (auto-generated if omitted)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show debug output")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    # Auto-generate output path: *.transcript.txt.html -> *.transcript.srt
    if args.output:
        output_path = Path(args.output)
    else:
        name = input_path.name
        if name.endswith(".transcript.txt.html"):
            base = name.replace(".transcript.txt.html", "")
            output_path = input_path.parent / f"{base}.transcript.srt"
        else:
            output_path = input_path.with_suffix(".srt")

    log(f"Input:  {input_path}", args.verbose)
    log(f"Output: {output_path}", args.verbose)

    html_content = input_path.read_text(encoding="utf-8")
    segments = parse_html_segments(html_content, args.verbose)

    if not segments:
        print("Error: No segments found in HTML", file=sys.stderr)
        sys.exit(1)

    srt_content = segments_to_srt(segments, args.verbose)
    output_path.write_text(srt_content, encoding="utf-8")

    # Verify
    entry_count = srt_content.strip().split("\n\n")
    print(f"OK: {len(entry_count)} entries written to {output_path}")


if __name__ == "__main__":
    main()
