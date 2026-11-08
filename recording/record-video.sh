#!/usr/bin/env bash
set -euo pipefail

recording_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Evaluator installations live here; keep an explicitly selected PATH tool first.
export PATH="${PATH}:${HOME}/.local/bin"
for tool in asciinema agg; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'Missing %s. Install asciinema 2.4.0 and agg 1.5.0 in ~/.local/bin or PATH.\n' "$tool" >&2
        exit 1
    fi
done

python_bin="${PYTHON:-}"
if [[ -z "$python_bin" ]]; then
    if [[ -x "$recording_dir/../.venv/bin/python" ]]; then
        python_bin="$recording_dir/../.venv/bin/python"
    else
        python_bin=python3
    fi
fi
if ! command -v "$python_bin" >/dev/null 2>&1; then
    printf 'Python unavailable: %s. Set PYTHON to an interpreter with the demo requirements.\n' "$python_bin" >&2
    exit 1
fi
# Resolve relative interpreter paths before the recorded command starts.
PYTHON="$(command -v "$python_bin")"
export PYTHON

output_dir="$recording_dir/output"
mkdir -p -- "$output_dir"
cast_path="$output_dir/demo.cast"
gif_path="$output_dir/demo.gif"
work_dir="$(mktemp -d)"
trap 'rm -rf -- "$work_dir"' EXIT
export RECORD_VIDEO_DIR="$recording_dir"
export RECORD_VIDEO_STATUS="$work_dir/status"
# Do not leave a previous successful GIF beside a failed new take.
rm -f -- "$gif_path"

# 2.4's tty_fds falls back to /dev/null without /dev/tty; explicit dimensions
# avoid terminal-size detection. EOF on stdin is supported; -q suppresses prompts.
# An isolated config keeps stdin recording off and idle_time_limit unset, even
# if the caller's config enables them. No -i: preserve the real 36-second wait.
# 2.4 discards the child's wait status, so save it outside the cast ourselves.
ASCIINEMA_CONFIG_HOME="$work_dir/asciinema" asciinema rec \
    --cols 120 --rows 32 --overwrite -q \
    --title 'LangCare FHIR OAuth2: scoped access + token refresh' \
    -c 'bash "$RECORD_VIDEO_DIR/record.sh"; status=$?; printf "%s\n" "$status" > "$RECORD_VIDEO_STATUS"; exit "$status"' \
    "$cast_path" </dev/null || {
        status=$?
        printf 'asciinema recording failed (exit %s); GIF not rendered.\n' "$status" >&2
        exit "$status"
    }
if [[ ! -s "$RECORD_VIDEO_STATUS" ]]; then
    printf 'Recorded command did not report an exit status; GIF not rendered.\n' >&2
    exit 1
fi
status="$(cat -- "$RECORD_VIDEO_STATUS")"
if [[ ! "$status" =~ ^[0-9]+$ ]] || (( status > 255 )); then
    printf 'Invalid recorded exit status; GIF not rendered.\n' >&2
    exit 1
fi
if (( status != 0 )); then
    printf 'record.sh failed (exit %s; 124 means timeout); GIF not rendered.\n' "$status" >&2
    exit "$status"
fi

# Validate decoded output events, joining chunks so PTY read boundaries do not
# split markers. Never count title/header text or recorded input as evidence.
duration="$("$PYTHON" - "$cast_path" <<'PY'
import json
import re
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as cast:
        header = json.loads(next(cast))
        events = [json.loads(line) for line in cast if line.strip()]
    if (header.get("version"), header.get("width"), header.get("height")) != (2, 120, 32):
        raise ValueError("expected a v2 cast at 120x32")
    if "idle_time_limit" in header:
        raise ValueError("raw cast must not have an idle-time limit")
    output = "".join(event[2] for event in events if event[1] == "o")
    required = (
        "Bundle with 3 entries",
        "-> 403",
        "token lacks required scope for GET Patient",
        "cache expired, fetched new token",
    )
    errors = [f"missing {marker!r}" for marker in required if marker not in output]
    if len(re.findall(r"-> 200(?!\d)", output)) < 3:
        errors.append("expected at least three -> 200 occurrences")
    # The case heading itself says -> 403; require the live response too.
    if not re.search(r"GET /fhir/Patient\?name=smith -> 403(?!\d)", output):
        errors.append("Patient search did not report 403")
    if "Traceback" in output:
        errors.append("Traceback present")
    if errors:
        raise ValueError("; ".join(errors))
    print(f"{max(event[0] for event in events):.3f}")
except (OSError, ValueError, KeyError, IndexError, TypeError, StopIteration) as exc:
    sys.exit(f"Cast validation failed: {exc}; GIF not rendered.")
PY
)"

agg --cols 120 --rows 32 --font-size 16 --theme dracula \
    --idle-time-limit 4 --fps-cap 10 "$cast_path" "$gif_path"

"$PYTHON" - "$cast_path" "$gif_path" "$duration" <<'PY'
from pathlib import Path
import sys

size = Path(sys.argv[2]).stat().st_size
print(f"Cast: {sys.argv[1]} ({sys.argv[3]} seconds)")
print(f"GIF:  {sys.argv[2]} ({size:,} bytes, {size / 1_000_000:.2f} MB)")
if size >= 5_000_000:
    print("GIF exceeds the 5 MB target; consider a lower font size or FPS cap.", file=sys.stderr)
PY
