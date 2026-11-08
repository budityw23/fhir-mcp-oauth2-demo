"""Scope-checking gateway: validates JWT from Keycloak and enforces SMART-style scopes.

Keycloak does not allow '/' in client scope names, so we register scopes as
'system-Observation.rs' and normalize the dash to '/' when checking.
A SMART-native server would use 'system/Observation.rs' directly.
"""

import os
import re

import httpx
import jwt
from jwt import PyJWKClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

HAPI_BASE = os.environ.get("HAPI_BASE", "http://hapi:8082")
KEYCLOAK_JWKS = os.environ.get("KEYCLOAK_JWKS",
                               "http://keycloak:8080/realms/fhir/protocol/openid-connect/certs")
TOKEN_ISSUER = os.environ.get("TOKEN_ISSUER", "http://localhost:8081/realms/fhir")
GATEWAY_PORT = int(os.environ.get("GATEWAY_PORT", "8080"))

jwks_client = PyJWKClient(KEYCLOAK_JWKS)

RESOURCE_TYPE_RE = re.compile(r"^/fhir/([A-Z][a-zA-Z]+)")

PERMISSIONS = {"GET": "rs", "POST": "c", "PUT": "u", "DELETE": "d"}


def has_scope_for(granted: list[str], resource_type: str, method: str) -> bool:
    perms = PERMISSIONS.get(method, "")
    for scope in granted:
        normalized = scope.replace("system-", "system/", 1)
        if not normalized.startswith("system/"):
            continue
        rest = normalized[7:]
        dot = rest.rfind(".")
        if dot < 0:
            continue
        rt, sp = rest[:dot], rest[dot + 1:]
        if (rt == resource_type or rt == "*") and all(c in sp for c in perms):
            return True
    return False


async def proxy(request: Request) -> Response:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return JSONResponse({"error": "missing bearer token"}, status_code=401)

    token_str = auth_header[7:]
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token_str)
        claims = jwt.decode(
            token_str,
            signing_key.key,
            algorithms=["RS256", "RS384", "ES256", "ES384"],
            issuer=TOKEN_ISSUER,
            options={"verify_aud": False},
        )
    except jwt.InvalidTokenError as e:
        return JSONResponse({"error": f"invalid token: {e}"}, status_code=401)

    match = RESOURCE_TYPE_RE.match(request.url.path)
    if match:
        resource_type = match.group(1)
        granted = claims.get("scope", "").split()
        if not has_scope_for(granted, resource_type, request.method):
            return JSONResponse(
                {"error": "forbidden",
                 "detail": f"token lacks required scope for {request.method} {resource_type}"},
                status_code=403,
            )

    target_url = f"{HAPI_BASE}{request.url.path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "transfer-encoding")
    }

    body = await request.body()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            content=body if body else None,
        )

    excluded = {"transfer-encoding", "content-encoding", "content-length"}
    resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
    return Response(content=resp.content, status_code=resp.status_code, headers=resp_headers)


app = Starlette(routes=[Route("/{path:path}", proxy, methods=["GET", "POST", "PUT", "DELETE"])])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=GATEWAY_PORT)
