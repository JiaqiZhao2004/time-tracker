---
status: accepted
---

# Use SPA refresh-token renewal for persistent sign-in

The time tracker uses a browser-only Vue app with Amazon Cognito Hosted UI and Google federation. We will let the SPA persist Cognito auth state in browser storage and use the refresh token to renew expired ID tokens, so a signed-in user is not forced through Google sign-in every hour and can remain signed in for the Cognito refresh-token lifetime.

## Considered Options

- Keep auth state in session storage and require sign-in whenever the ID token expires. This minimizes persistent browser-token exposure but makes the app frustrating to use for routine daily tracking.
- Move to a backend-for-frontend session model with server-held refresh tokens and `HttpOnly` cookies. This is the stronger security architecture, but it adds a new auth/session backend boundary that is larger than the current app needs.
- Persist SPA auth state and renew with Cognito refresh tokens. This keeps the static frontend architecture and gives the desired 30-day sign-in experience, at the cost of exposing refresh-capable state to any successful same-origin JavaScript compromise.

## Consequences

This is an explicit usability-over-maximum-hardening choice for a small personal app. The app must keep ID tokens short-lived, treat XSS prevention as auth-critical, and prefer Cognito refresh token rotation when supported by the deployed app client. If the app starts protecting higher-risk data or serving more users, revisit this decision and prefer a backend-for-frontend session model.
