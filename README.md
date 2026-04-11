# Southview OCR

Southview OCR is a FastAPI + Vite app for historical index card digitization.

## Local setup

From `C:\Users\level\Desktop\South_View_OCR\southview-OCR`:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

To run the app:

```powershell
python -m southview serve
```

Open `http://localhost:8000`.

## Teammate setup

Each teammate needs the repo plus the same auth environment values used by the team.

### 1. Clone and install

```powershell
git clone <repo-url>
cd southview-OCR
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

If the frontend dependencies are not already installed:

```powershell
cd frontend
npm install
cd ..
```

### 2. Create a local `.env`

Create a repo-root `.env` file using the values shared by the project owner or team lead.

Required variables:

- `SOUTHVIEW_AUTH_USERNAME`
- `SOUTHVIEW_AUTH_PASSWORD_HASH`
- `SOUTHVIEW_AUTH_SESSION_SECRET`

Recommended local variables:

- `SOUTHVIEW_AUTH_SECURE_COOKIES=false`
- `SOUTHVIEW_AUTH_SESSION_TTL_SECONDS=43200`

Example template:

```env
SOUTHVIEW_AUTH_USERNAME=admin
SOUTHVIEW_AUTH_PASSWORD_HASH=<team-shared-password-hash>
SOUTHVIEW_AUTH_SESSION_SECRET=<team-shared-session-secret>
SOUTHVIEW_AUTH_SECURE_COOKIES=false
SOUTHVIEW_AUTH_SESSION_TTL_SECONDS=43200
GEMINI_API_KEY=<optional-if-using-gemini-ocr>
```

Notes:

- `.env` is gitignored and should not be committed.
- Teammates should get the actual values from a secure team channel or secret manager.
- The login page uses the plaintext password, but the app stores only the hash.

### 3. Start the app

```powershell
python -m southview serve
```

Then sign in at `http://localhost:8000`.

If the password is rejected, fully stop the server and start it again so it reloads the latest `.env`.

## Frontend development

For frontend hot reload:

```powershell
cd frontend
npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies API requests to `http://127.0.0.1:8000`.

## Admin auth model

The app uses one admin account configured by environment variables.

Required variables:

- `SOUTHVIEW_AUTH_USERNAME`
- `SOUTHVIEW_AUTH_PASSWORD_HASH`
- `SOUTHVIEW_AUTH_SESSION_SECRET`

Optional variables:

- `SOUTHVIEW_AUTH_SECURE_COOKIES`
- `SOUTHVIEW_AUTH_SESSION_TTL_SECONDS`

Useful command:

```powershell
python -m southview hash-password
```

That command generates a PBKDF2 password hash for a new admin password.

## Deployment setup

For production, the deployed app must have the same auth variables configured in the hosting environment. The local `.env` file does not deploy by itself.

### Required production env vars

```env
SOUTHVIEW_AUTH_USERNAME=admin
SOUTHVIEW_AUTH_PASSWORD_HASH=<generated password hash>
SOUTHVIEW_AUTH_SESSION_SECRET=<long random secret>
SOUTHVIEW_AUTH_SECURE_COOKIES=true
SOUTHVIEW_AUTH_SESSION_TTL_SECONDS=43200
```

If Gemini OCR is used in production, also set:

```env
GEMINI_API_KEY=<production-key>
```

### Production checklist

1. Generate or choose the admin password.
2. Run `python -m southview hash-password` locally to generate the hash.
3. Generate a long random value for `SOUTHVIEW_AUTH_SESSION_SECRET`.
4. Add those values to your hosting provider's environment variables.
5. Set `SOUTHVIEW_AUTH_SECURE_COOKIES=true` for HTTPS deployments.
6. Deploy the app.
7. Test login in the deployed environment with the shared admin username and password.

### Important security notes

- Do not commit plaintext passwords to the repo.
- Do not commit real production session secrets.
- If the admin password has been shared in an insecure place, rotate it by generating a new hash and updating deployment env vars.
- If you change the session secret, existing sessions will be invalidated, which is expected.

## Gemini OCR bake-off

To run model bake-off with Gemini, set one of these env vars:

```bash
export GEMINI_API_KEY="your-api-key"
# or
export GOOGLE_API_KEY="your-api-key"
```

Run:

```bash
python -m southview bakeoff run \
  --manifest data/bakeoff/manifest.csv \
  --out-dir data/bakeoff/runs/latest \
  --models gemini-2.0-flash
```
