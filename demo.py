"""Run the three article demo cases: valid token, wrong scope, expired token."""

import time
import httpx
from token_client import TokenClient

TOKEN_URL = "http://localhost:8085/realms/fhir/protocol/openid-connect/token"
FHIR_BASE = "http://localhost:8083/fhir"
CLIENT_ID = "fhir-agent"
CLIENT_SECRET = "demo-secret-not-for-production"


def fhir_get(path: str, token: str) -> httpx.Response:
    return httpx.get(
        f"{FHIR_BASE}/{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/fhir+json"},
        timeout=30.0,
    )


def print_token_info(tc: TokenClient, label: str):
    resp = tc.last_response
    if resp:
        print(f"  token: requested scope={tc.scope}, "
              f"granted scope={resp.get('scope', 'N/A')}, "
              f"expires_in={resp.get('expires_in', 'N/A')}")
    print(f"  {label}")


def case1_valid_token():
    print("\n=== Case 1: Valid token, Observation search ===")
    tc = TokenClient(TOKEN_URL, CLIENT_ID, CLIENT_SECRET, scope="system-Observation.rs")
    token = tc.get()
    print_token_info(tc, "fetched new token")

    resp = fhir_get("Observation?patient=example", token)
    if resp.status_code == 200:
        bundle = resp.json()
        total = bundle.get("total", len(bundle.get("entry", [])))
        print(f"  GET /fhir/Observation?patient=example -> {resp.status_code}, "
              f"Bundle with {total} entries")
    else:
        print(f"  GET /fhir/Observation?patient=example -> {resp.status_code}")
        print(f"  Body: {resp.text[:200]}")


def case2_wrong_scope():
    print("\n=== Case 2: Wrong scope, Patient search -> 403 ===")
    tc = TokenClient(TOKEN_URL, CLIENT_ID, CLIENT_SECRET, scope="system-Observation.rs")
    token = tc.get()
    print_token_info(tc, "fetched new token (only Observation scope)")

    resp = fhir_get("Patient?name=smith", token)
    print(f"  GET /fhir/Patient?name=smith -> {resp.status_code}")
    if resp.status_code == 403:
        print(f"  Response: {resp.json()}")


def case3_expired_token():
    print("\n=== Case 3: Expired token, automatic refresh ===")
    tc = TokenClient(TOKEN_URL, CLIENT_ID, CLIENT_SECRET, scope="system-Observation.rs")

    token = tc.get()
    print_token_info(tc, "fetched first token")
    resp = fhir_get("Observation?patient=example", token)
    print(f"  GET /fhir/Observation?patient=example -> {resp.status_code}")

    remaining = tc.seconds_remaining
    # Token has 60s lifespan, cache margin is 30s, so effective life is ~30s.
    wait = max(0, remaining - 25) + 1
    print(f"  token expires in {remaining:.0f}s (cache margin 30s), waiting {wait:.0f}s...")
    time.sleep(wait)

    print(f"  {tc.seconds_remaining:.0f}s remaining, calling get() again...")
    token = tc.get()
    print_token_info(tc, "cache expired, fetched new token")

    resp = fhir_get("Observation?patient=example", token)
    print(f"  GET /fhir/Observation?patient=example -> {resp.status_code}")


if __name__ == "__main__":
    print("FHIR OAuth2 Demo")
    print(f"Token endpoint: {TOKEN_URL}")
    print(f"FHIR endpoint:  {FHIR_BASE} (via scope-checking gateway)")
    case1_valid_token()
    case2_wrong_scope()
    case3_expired_token()
    print("\nDone.")
