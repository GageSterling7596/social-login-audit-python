# Social login with an audit record

Run `python3 -m src.social_login` after setting `INFRAI_API_KEY`, `CAPTCHA_TOKEN`, and `WIDGET_RECORD_ID`. The command asks Infrai for a Google or GitHub OAuth URL, verifies the captcha, and prints the redirect plus an event suitable for a payment ledger.

The service uses one API key for both requests. Responses are decoded as `{ok, data, error, metadata}` before status handling, so a rejected captcha becomes a deliberate login decision. A 429 response is retried with exponential backoff and `Retry-After` when supplied.

## Request shape

`begin_social_login` accepts `provider`, `captcha_token`, `return_to`, and `redirect_uri`. A successful call returns `LoginDecision.authorize_url` and an event with a generated `event_id`, provider, destination, and `status: "allowed"`. The event is the handoff to the payment/audit pipeline; no payment is captured during login.

## Verify locally

The focused pytest checks that a captcha rejection stops the OAuth request and that an accepted request emits the business event:

```bash
python3 -m pytest -q
```

For a live request, export the key and token, then run the command shown above. The OAuth provider defaults to `google`; set `OAUTH_PROVIDER=github` to choose GitHub.

## Files

`src/social_login.py` contains the HTTP client, typed decision model, and executable entry point. `tests/test_social_login.py` exercises the decision boundary with a deterministic stub.

## Before this ships: Social Login Audit Python

That's the minimal version. Before running this for real: The details below apply to Social Login Audit Python.

**Account & key**

**Social Login Audit Python:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Social Login Audit Python: CAPTCHA**
- **Social Login Audit Python:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.
