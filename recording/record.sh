#!/usr/bin/env bash
# Clean terminal presentation for manual screen recording. Run with bash.
set -euo pipefail

demo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON:-python3}"
if command -v timeout >/dev/null 2>&1; then
    timeout_bin=timeout
elif command -v gtimeout >/dev/null 2>&1; then
    timeout_bin=gtimeout
else
    printf 'Install GNU coreutils (timeout or gtimeout is required).\n' >&2
    exit 1
fi

# Keep even a stalled request below 90 seconds; never change the token clock.
exec "$timeout_bin" --foreground --signal=TERM --kill-after=2s 85s \
    "$python_bin" -u - "$demo_dir" <<'PY'
import runpy
import sys
import time
from pathlib import Path

import httpx

demo_dir = Path(sys.argv[1])
sys.path.insert(0, str(demo_dir))
import demo


def observation_count():
    response = httpx.get(
        "http://localhost:8084/fhir/Observation",
        params={"patient": "example", "_summary": "count"},
        headers={"Cache-Control": "no-cache"},
        timeout=5,
    )
    response.raise_for_status()
    count = response.json().get("total")
    if not isinstance(count, int):
        raise RuntimeError("HAPI did not return an Observation count")
    return count


def command(text):
    print(f"\n$ {text}", flush=True)
    time.sleep(1)


print("FHIR OAuth2: scoped access and automatic token refresh")
print("Keycloak :8085 -> scope-checking gateway :8083 -> HAPI :8084")
print("The stack is already running; all requests below are live.")
time.sleep(3)

command("# Check the running stack")
with httpx.Client(timeout=5) as client:
    for name, url in (
        ("Keycloak", "http://localhost:8085/realms/fhir/.well-known/openid-configuration"),
        ("HAPI", "http://localhost:8084/fhir/metadata"),
        ("Gateway", "http://localhost:8083/fhir/Observation"),
    ):
        response = client.get(url)
        # An unauthenticated gateway request should be rejected.
        expected = 401 if name == "Gateway" else 200
        if response.status_code != expected:
            raise RuntimeError(f"{name}: expected {expected}, got {response.status_code}")
        print(f"  {name}: reachable (HTTP {response.status_code})")
time.sleep(2)

command("# Seed the synthetic demo data if needed")
count = observation_count()
if count == 0:
    print("$ python seed.py")
    runpy.run_path(str(demo_dir / "seed.py"), run_name="__main__")
elif count == 3:
    print("  Reusing the 3 existing Observations for Patient/example.")
else:
    raise RuntimeError(
        f"Expected 0 or 3 demo Observations, found {count}. "
        "Use a fresh demo stack before recording."
    )
if observation_count() != 3:
    raise RuntimeError("Seeding did not produce exactly 3 demo Observations")
time.sleep(3)

command("# Run the three cases from demo.py, with reading pauses")
print(f"Token endpoint: {demo.TOKEN_URL}")
print(f"FHIR endpoint:  {demo.FHIR_BASE}")
demo.case1_valid_token()
time.sleep(4)
demo.case2_wrong_scope()
time.sleep(4)
print("\nRefresh occurs inside the 30s cache margin, before JWT expiry.")
demo.case3_expired_token()
time.sleep(4)
print("\nDone. Valid scope: 200 | Wrong scope: 403 | Refreshed token: 200")
time.sleep(3)
PY
