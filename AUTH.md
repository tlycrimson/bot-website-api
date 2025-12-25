# Authentication & OAuth (Discord)

This file explains how the Discord OAuth flow is configured and how to run it on non-localhost hosts.

## Key environment variables
- **DISCORD_CLIENT_ID** - Discord application client ID
- **DISCORD_CLIENT_SECRET** - Discord application secret
- **DISCORD_REDIRECT_URI** - The redirect URI registered in Discord (should point to your API callback, e.g., `https://api.example.com/auth/callback` or a ngrok URL for local testing)
- **ALLOWED_FRONTEND_ORIGINS** - (Optional) comma-separated list of allowed frontend origins (e.g., `https://example.com,http://localhost:5173`). If set, `next` values are validated against this list.
- **DEFAULT_FRONTEND** - (Optional) fallback frontend origin if the `next` param isn't present.

## How the flow works
1. Frontend calls GET `/auth/discord/login?next=<origin>` (where `<origin>` is `window.location.origin`).
2. Backend stores a short-lived `state` -> `{ next }` mapping and returns `{ auth_url }` which includes `state`.
3. Browser is redirected to Discord OAuth URL.
4. Discord calls your server's redirect URI (`DISCORD_REDIRECT_URI`) with `code` and `state`.
5. Backend exchanges the `code` for Discord tokens, mints your server token (JWT), and either:
   - Redirects the browser to `<next>/auth/redirect?token=...` (if called by the browser), or
   - Returns JSON `{ token, user }` when the frontend calls `/auth/callback?code=...&format=json` directly (backend supports both methods).

## Local testing tips
- For local development, run your API server and expose it with ngrok (or similar) and register the ngrok URL as a redirect URI in your Discord app settings.
- Example ngrok redirect: `https://<random>.ngrok.io/auth/callback` — set `DISCORD_REDIRECT_URI` to this value.
- Set `ALLOWED_FRONTEND_ORIGINS` to include `http://localhost:5173` and your deployed origins.

## Security notes
- Do not allow arbitrary redirects. Use `ALLOWED_FRONTEND_ORIGINS` or set `DEFAULT_FRONTEND`.
- Replace the development `SECRET_KEY` with a secure value in production.
- For multi-instance deployments, replace the in-memory state map with Redis or another shared store.

If you'd like, I can add Redis-based state storage or a sample `docker-compose` service for local testing with ngrok/letsencrypt. Let me know which you'd prefer.