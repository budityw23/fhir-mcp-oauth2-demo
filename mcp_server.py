"""MCP server exposing a search_observations tool, using OAuth2 client credentials."""

import os
import httpx
from mcp.server.mcpserver import MCPServer
from token_client import TokenClient

FHIR_BASE = os.environ["FHIR_BASE_URL"]
tokens = TokenClient(
    token_url=os.environ["TOKEN_URL"],
    client_id=os.environ["CLIENT_ID"],
    client_secret=os.environ["CLIENT_SECRET"],
    scope=os.environ.get("FHIR_SCOPE", "system-Observation.rs"),
)
mcp = MCPServer("fhir-observations")


@mcp.tool()
def search_observations(patient_id: str, code: str | None = None) -> dict:
    """Search Observations for a patient, optionally filtered by LOINC code."""
    params = {"patient": patient_id}
    if code:
        params["code"] = code
    for attempt in range(2):
        resp = httpx.get(
            f"{FHIR_BASE}/Observation",
            params=params,
            headers={"Authorization": f"Bearer {tokens.get()}",
                     "Accept": "application/fhir+json"},
        )
        if resp.status_code == 401 and attempt == 0:
            tokens.invalidate()
            continue
        break
    if resp.status_code == 403:
        return {"error": "forbidden",
                "detail": "This agent's token does not allow this request."}
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    mcp.run()
