#!/usr/bin/env python3
"""
Export Claude Code session JSONL files to readable markdown.

Usage:
  python3 export_sessions.py [OPTIONS]

Options:
  --project-dir PATH   Claude project directory (auto-detected from cwd if omitted)
  --output-dir PATH    Output directory for markdown files (default: ./sessions)
  --exclude-current    Exclude the currently active session
  --session ID         Export only a specific session by ID (partial match OK)
  --verbose, -v        Show debug output
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))


def log(msg, verbose=False):
    if verbose:
        print(f"  [debug] {msg}", file=sys.stderr)


def detect_project_dir(cwd, verbose=False):
    """Auto-detect the Claude project directory for the given cwd."""
    escaped = cwd.replace("/", "-").lstrip("-")
    projects_root = Path.home() / ".claude" / "projects"
    candidate = projects_root / escaped
    log(f"Looking for project dir: {candidate}", verbose)
    if candidate.is_dir():
        return candidate
    # Try partial match
    for d in projects_root.iterdir():
        if d.is_dir() and escaped in d.name:
            log(f"Partial match found: {d}", verbose)
            return d
    return None


def extract_text_from_content(content):
    """Extract readable text from message content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                btype = block.get("type", "")
                if btype == "text":
                    parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    tool_name = block.get("name", "unknown")
                    tool_input = block.get("input", {})
                    if tool_name in ("Read", "Glob", "Grep"):
                        target = tool_input.get("file_path") or tool_input.get("pattern", "")
                        parts.append(f"[Tool: {tool_name} → {target}]")
                    elif tool_name == "Edit":
                        parts.append(f"[Tool: Edit → {tool_input.get('file_path', '')}]")
                    elif tool_name == "Write":
                        parts.append(f"[Tool: Write → {tool_input.get('file_path', '')}]")
                    elif tool_name == "Bash":
                        cmd = tool_input.get("command", "")
                        desc = tool_input.get("description", "")
                        label = desc if desc else (cmd[:200] + "..." if len(cmd) > 200 else cmd)
                        parts.append(f"[Tool: Bash → `{label}`]")
                    elif tool_name == "AskUserQuestion":
                        for q in tool_input.get("questions", []):
                            parts.append(f"[질문: {q.get('question', '')}]")
                    elif tool_name == "Task":
                        parts.append(f"[Tool: Task → {tool_input.get('description', '')}]")
                    elif tool_name == "Skill":
                        parts.append(f"[Skill: {tool_input.get('skill', '')}]")
                    else:
                        parts.append(f"[Tool: {tool_name}]")
                elif btype in ("tool_result", "thinking"):
                    pass  # skip
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(p for p in parts if p.strip())
    return str(content)


def strip_system_tags(text):
    """Remove system-injected tags."""
    patterns = [
        r"<system-reminder>.*?</system-reminder>",
        r"<local-command-caveat>.*?</local-command-caveat>",
        r"<command-name>.*?</command-name>",
        r"<command-message>.*?</command-message>",
        r"<command-args>.*?</command-args>",
        r"<local-command-stdout>.*?</local-command-stdout>",
    ]
    for p in patterns:
        text = re.sub(p, "", text, flags=re.DOTALL)
    return text.strip()


def parse_session(filepath, verbose=False):
    """Parse a single JSONL session file into a list of messages."""
    messages = []
    log(f"Parsing {filepath.name}", verbose)
    with open(filepath, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                log(f"  Skipping invalid JSON at line {line_num}", verbose)
                continue

            entry_type = entry.get("type")
            if entry_type not in ("user", "assistant"):
                continue
            if entry.get("isSidechain"):
                continue

            msg = entry.get("message", {})
            role = msg.get("role", entry_type)
            content = msg.get("content", "")
            timestamp = entry.get("timestamp", "")

            text = extract_text_from_content(content)
            text = strip_system_tags(text)
            if not text.strip():
                continue

            ts_display = ""
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    dt_kst = dt.astimezone(KST)
                    ts_display = dt_kst.strftime("%H:%M:%S")
                except Exception:
                    ts_display = timestamp

            messages.append({
                "role": role,
                "text": text,
                "timestamp": ts_display,
                "raw_timestamp": timestamp,
            })

    log(f"  Found {len(messages)} messages", verbose)
    return messages


def extract_topic(messages):
    """Extract a short topic slug (alphabet + hyphens only) from the first user message."""
    first_user_msg = ""
    for m in messages:
        if m["role"] == "user":
            first_user_msg = m["text"].strip()
            break
    if not first_user_msg:
        return "untitled"
    # Extract English/alphanumeric words only
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9]*", first_user_msg)
    if not words:
        return "untitled"
    slug = "-".join(w.lower() for w in words[:5])
    return slug[:50] or "untitled"


def format_markdown(session_id, messages, index):
    """Format parsed messages as markdown."""
    if not messages:
        return "", ""

    first_ts = messages[0].get("raw_timestamp", "")
    try:
        dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
        dt_kst = dt.astimezone(KST)
        session_date = dt_kst.strftime("%Y-%m-%d %H:%M")
    except Exception:
        session_date = "unknown"

    topic = extract_topic(messages)

    first_user_msg = ""
    for m in messages:
        if m["role"] == "user":
            first_user_msg = m["text"][:80].replace("\n", " ")
            break

    lines = [
        f"# Session {index}: {first_user_msg}",
        "",
        f"- **Session ID**: `{session_id}`",
        f"- **시작 시각**: {session_date} KST",
        f"- **메시지 수**: {len(messages)}",
        "",
        "---",
        "",
    ]

    for msg in messages:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"### {role_label} ({msg['timestamp']})")
        lines.append("")
        lines.append(msg["text"])
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines), topic


def main():
    parser = argparse.ArgumentParser(description="Export Claude Code sessions to markdown")
    parser.add_argument("--project-dir", help="Claude project directory path")
    parser.add_argument("--output-dir", default="./sessions", help="Output directory (default: ./sessions)")
    parser.add_argument("--exclude-current", action="store_true", help="Exclude the currently active session")
    parser.add_argument("--current-session", help="Current session ID to exclude")
    parser.add_argument("--session", help="Export only a specific session (partial ID match)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug output")
    args = parser.parse_args()

    # Detect project directory
    project_dir = args.project_dir
    if not project_dir:
        project_dir = detect_project_dir(os.getcwd(), args.verbose)
    if not project_dir or not Path(project_dir).is_dir():
        print(f"Error: Could not find project directory. Use --project-dir.", file=sys.stderr)
        sys.exit(1)

    project_dir = Path(project_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find session files
    session_files = sorted(project_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime)

    if args.current_session:
        session_files = [f for f in session_files if f.stem != args.current_session]

    if args.session:
        session_files = [f for f in session_files if args.session in f.stem]

    if not session_files:
        print("No session files found.")
        sys.exit(0)

    print(f"Exporting {len(session_files)} session(s) to {output_dir}/")

    used_topics = {}
    for idx, sf in enumerate(session_files, 1):
        session_id = sf.stem
        messages = parse_session(sf, args.verbose)
        if not messages:
            print(f"  Session {idx} ({session_id[:8]}): empty, skipping")
            continue

        md, topic = format_markdown(session_id, messages, idx)

        # Deduplicate topic names
        if topic in used_topics:
            used_topics[topic] += 1
            topic = f"{topic}-{used_topics[topic]}"
        else:
            used_topics[topic] = 1

        out_path = output_dir / f"chatsession-{idx}-{topic}.md"
        with open(out_path, "w") as f:
            f.write(md)
        print(f"  Session {idx}: {out_path.name} ({len(messages)} messages)")

    print("Done.")


if __name__ == "__main__":
    main()
