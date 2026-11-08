import time
import httpx


class TokenClient:
    def __init__(self, token_url: str, client_id: str, client_secret: str, scope: str):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self._token: str | None = None
        self._expires_at = 0.0
        self._last_response: dict | None = None

    def get(self) -> str:
        if self._token and time.time() < self._expires_at - 30:
            return self._token
        resp = httpx.post(
            self.token_url,
            data={"grant_type": "client_credentials", "scope": self.scope},
            auth=(self.client_id, self.client_secret),
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["access_token"]
        self._expires_at = time.time() + int(body.get("expires_in", 60))
        self._last_response = body
        return self._token

    def invalidate(self) -> None:
        self._token = None

    @property
    def last_response(self) -> dict | None:
        return self._last_response

    @property
    def seconds_remaining(self) -> float:
        return max(0, self._expires_at - time.time())
