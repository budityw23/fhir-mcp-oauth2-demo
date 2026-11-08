# Record the FHIR OAuth2 demo

This setup uses a **Bash script with clean, annotated terminal output** for manual
screen recording. It needs no VHS or asciinema installation. The requests and
token refresh are live, using the existing `seed.py` and all three functions from
`demo.py`, with pauses between cases.

## Prepare before recording

- Install Bash, Python 3.12+, and GNU coreutils (`timeout` on Linux; on macOS,
  `brew install coreutils` supplies `gtimeout`).
- Use your preferred screen recorder and a terminal around 120 columns by 32 rows.
- From `docs/article/demo/`, install the Python requirements and start the stack:

  ```bash
  python3 -m venv /tmp/fhir-recording-venv
  source /tmp/fhir-recording-venv/bin/activate
  python -m pip install -r requirements.txt
  docker compose up -d
  ```

Wait for all services to be ready on ports 8083, 8084, and 8085 before starting
the capture. Container startup and dependency installation are outside playback.
The script checks Keycloak and HAPI, and confirms the gateway rejects an
unauthenticated request with 401.

Use a dedicated demo stack with either zero or exactly three Observations for
`Patient/example`. The script seeds an empty dataset and reuses three existing
Observations on later recordings, avoiding duplicate inserts from `seed.py`.
It stops on other counts; it does not delete data or reset containers. Avoid
concurrent seeding while recording. Existing three-entry data should be the
synthetic data supplied by this demo.

## Capture

With the virtual environment active, start your screen recorder, then run from
`docs/article/demo/`:

```bash
clear
PYTHON=python bash recording/record.sh
```

The script also works from any directory when called by its absolute path.
`PYTHON` may specify an alternative Python executable or virtualenv interpreter.
Only terminal output is produced; save the video using your screen recorder.

The sequence shows an introduction, running-service checks, seeding (or reuse),
then valid scope → 200, wrong scope → 403, and automatic refresh → 200. Pauses of
3–4 seconds leave results readable. The refresh retains the real approximately
36-second wait from `demo.py`: the JWT has a 60-second lifetime, and the cache
refreshes inside its 30-second margin, before the JWT actually expires.

Expect roughly 65–80 seconds on a responsive, warmed-up stack. GNU `timeout`
ends the script at 85 seconds (forced termination by 87 seconds), keeping the
script's presentation below 90 seconds even if a request stalls. Stop the screen
recorder when the script exits. Exit status 124 indicates the time limit was
reached; a timeout or traceback means the take is incomplete and should be
recorded again after fixing stack readiness. Check that the displayed case
statuses are 200, 403, and 200/200 before using the take; the original demo
functions print unexpected statuses without necessarily failing the process.

## Automated capture (asciinema + GIF)

In addition to the prerequisites above, install asciinema 2.4.0 and agg 1.5.0
in `~/.local/bin` or on `PATH`. With the stack ready, from `docs/article/demo/`:

```bash
bash recording/record-video.sh
```

The script works from any cwd when called by its absolute path. It honours
`PYTHON`, otherwise uses `demo/.venv/bin/python` if available, then `python3`.
Outputs are `recording/output/demo.cast` and `recording/output/demo.gif`;
successful runs print the cast duration and GIF size (target under 5 MB).
Both use 120×32; the GIF uses a dark theme and 16 px font.
The raw cast retains the real ~36 s wait; only the GIF caps idle gaps at 4 s.
Asciinema 2.4 falls back to `/dev/null` without a controlling TTY. Explicit
dimensions, `-q`, stdin from `/dev/null`, and an isolated default config allow
headless capture with stdin recording off and no cast idle-time limit.
Its CLI discards child exit status; a temporary status file preserves failures
(including timeout 124). Failed takes or cast validation failures skip rendering.
Re-run the same command to overwrite both outputs. As above, use zero or three
Observations: empty data is seeded, three are reused, other counts stop capture.
