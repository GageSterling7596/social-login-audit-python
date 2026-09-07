import os
import pytest

from src.social_login import InfraiError, begin_social_login


class StubClient:
    def __init__(self, captcha_ok=True):
        self.captcha_ok = captcha_ok

    def verify_captcha(self, token, action):
        if not self.captcha_ok:
            raise InfraiError("CAPTCHA_REJECTED", {"message": "rejected"}, 422)
        return {"ok": True, "data": {}}

    def oauth_authorize_url(self, provider, return_to, redirect_uri):
        return f"https://accounts.example/{provider}?return_to={return_to}"


def test_captcha_rejection_stops_login():
    with pytest.raises(InfraiError) as caught:
        begin_social_login(StubClient(False), provider="github", captcha_token="t")
    assert caught.value.status == 422


def test_accepted_login_emits_auditable_event():
    result = begin_social_login(StubClient(), provider="google", captcha_token="t")
    assert result.audit_event["event_type"] == "social_login_started"
    assert result.audit_event["status"] == "allowed"
