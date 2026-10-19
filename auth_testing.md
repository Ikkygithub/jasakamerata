# Auth-Gated App Testing Playbook

## Session setup
Create a test user and `user_sessions` record in the configured MongoDB database using a custom `user_id` and a session token expiring in seven days.

## API checks
- `GET /api/auth/me` with the session token must return the linked user.
- Protected customer, photographer, and admin endpoints must enforce role permissions.
- All responses must exclude MongoDB `_id`.

## Browser checks
- Verify OAuth callback reads `session_id` from the URL fragment.
- Verify the callback exchanges the session server-side, sets the session cookie, and redirects to the correct role dashboard.
- Verify protected routes redirect unauthenticated users and load for an authenticated role.

## Security checks
- Session cookies are httpOnly, secure, SameSite=None, and expire server-side.
- Photographer bank account data is encrypted at rest and masked in responses.
- No password credentials are stored for Google OAuth.