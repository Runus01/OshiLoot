# 2. MyAnimeList sign-in with the session in an encrypted cookie

Status: accepted, October 2026

## Context

The public MyAnimeList API only returns lists that are set to public. To read a private
list, the user has to sign in with MyAnimeList (OAuth 2.0 with PKCE), and every list request
then carries their access token.

That token has to live somewhere between requests. The usual answer is a server-side
session table, but two constraints push against it:

- MAL's API agreement bars storing or processing users' personal information and list data
  on the server. A table of access tokens keyed by MAL username is exactly that.
- The backend is one stateless Lambda function. A session table adds reads and writes on
  every request and one more thing to expire and clean up.

## Decision

Keep the whole session in the browser, in a cookie the browser's JavaScript can't read:

- After MAL redirects back, the backend exchanges the code for tokens, then seals
  `{access_token, refresh_token, expires_at, username}` with Fernet (AES-128-CBC plus
  HMAC-SHA256) using `SESSION_SECRET`, and sets it as an `HttpOnly`, `SameSite=Lax` cookie
  (`Secure` in production) scoped to `/api/anime`.
- The OAuth `state` and PKCE verifier travel the same way, in a second cookie that lasts ten
  minutes and is scoped to `/api/anime/auth`.
- `GET /api/anime/me/lists` returns Completed and Watching together. MAL rotates the refresh
  token on every refresh and revokes the old one, so two parallel requests that both
  refreshed would race and one would sign the user out. One request means one refresh.
- If MAL rejects the access token, the backend refreshes once and retries. If the refresh
  fails, it clears the cookie and returns 401, and the page shows the sign-in button again.
- Sign-in stays hidden unless the client secret is set, and in AWS also unless
  `SESSION_SECRET` is not the development default and `PUBLIC_URL` is https.

## Consequences

- No database writes for sign-in, and nothing about the user on the server after the
  request ends. The backend stays stateless, so any Lambda instance can serve any request.
- Signing out deletes the cookie, but a copied cookie keeps working until the tokens inside
  it expire or a refresh replaces them, because there is no server-side list of sessions to
  revoke. Rotating `SESSION_SECRET` signs everyone out at once.
- Two MAL tokens fit in one cookie with room to spare (a test checks the 4 KB browser
  limit). Larger session data would need a different design.
- The site and the API must share an origin so the cookie is first-party. CloudFront
  provides that in production and the Vite proxy does in development.
- All sign-in routes are GET requests, which keeps the CloudFront API behaviour GET/HEAD
  only. Signing out is a GET too, so another site could sign a user out with a link. That
  is a nuisance, not a leak, and accepted for now.
