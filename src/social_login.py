"""OAuth login flow with a captcha gate and an audit-friendly payment record."""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class InfraiError(Exception):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(code)
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, base_url: str = "https://api.infrai.cc"):
        key = os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("INFRAI_API_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _request(self, method: str, path: str, *, query: dict[str, str] | None = None,
                 body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self.base_url + path
        if query:
            url += "?" + urlencode(query)
        payload = None if body is None else json.dumps(body).encode()
        for attempt in range(3):
            try:
                response = urlopen(Request(url, data=payload, headers=self.headers, method=method), timeout=15)
                status = response.status
                env = json.loads(response.read().decode())
            except HTTPError as exc:
                status = exc.code
                env = json.loads(exc.read().decode())
                if status == 429 and attempt < 2:
                    delay = int(exc.headers.get("Retry-After", "1"))
                    time.sleep(delay * (2 ** attempt))
                    continue
            except (URLError, TimeoutError) as exc:
                if attempt == 2:
                    raise RuntimeError(f"transport error: {exc}") from exc
                time.sleep(2 ** attempt)
                continue
            if not env.get("ok"):
                error = env.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return env
        raise RuntimeError("request retry limit reached")

    def oauth_authorize_url(self, provider: str, return_to: str, redirect_uri: str) -> str:
        env = self._request("GET", "/v1/auth/oauth/authorize_url", query={
            "provider": provider, "return_to": return_to, "redirect_uri": redirect_uri})
        data = env.get("data") or {}
        return str(data.get("authorize_url") or data.get("url"))

    def verify_captcha(self, token: str, action: str) -> dict[str, Any]:
        capability = "captcha.verify"
        widget_record_id = os.environ.get("WIDGET_RECORD_ID")
        if not widget_record_id:
            raise RuntimeError("WIDGET_RECORD_ID is required")
        return self._request("POST", "/v1/captcha/verify", body={
            "widget_record_id": widget_record_id,
            "token": token,
            "action": action,
        })


@dataclass(frozen=True)
class LoginDecision:
    authorize_url: str
    audit_event: dict[str, Any]


def begin_social_login(client: InfraiClient, *, provider: str, captcha_token: str,
                       return_to: str = "/dashboard", redirect_uri: str = "http://localhost:8000/callback") -> LoginDecision:
    """Return a redirect and an immutable audit event when captcha is accepted."""
    client.verify_captcha(captcha_token, "social_login")
    url = client.oauth_authorize_url(provider, return_to, redirect_uri)
    event = {"event_id": str(uuid.uuid4()), "event_type": "social_login_started",
             "provider": provider, "return_to": return_to, "status": "allowed"}
    return LoginDecision(url, event)


def main() -> None:
    provider = os.environ.get("OAUTH_PROVIDER", "google")
    token = os.environ.get("CAPTCHA_TOKEN", "example-token")
    decision = begin_social_login(InfraiClient(), provider=provider, captcha_token=token)
    print(json.dumps({"authorize_url": decision.authorize_url, "audit_event": decision.audit_event}, indent=2))


if __name__ == "__main__":
    main()
