## TODO
* add auth
* test diff models
* fix filters in search

## Gemini OCR Runtime Configuration
The main OCR pipeline now uses the Gemini API (`ocr.engine: gemini` in `config.yaml`).

Set your key before running OCR jobs:

```bash
export GEMINI_API_KEY="your-api-key"
```

Or create a project-level `.env` file and the app will auto-load it:

```dotenv
GEMINI_API_KEY=your-api-key
```

## Gemini OCR (Bake-off) Configuration
The Gemini integration is currently used by the OCR bake-off runner (`python -m southview bakeoff ...`).

Set one of these environment variables before running bake-off with Gemini models:

```bash
export GEMINI_API_KEY="your-api-key"
# or
export GOOGLE_API_KEY="your-api-key"
```

Example:

```bash
python -m southview bakeoff run \
  --manifest data/bakeoff/manifest.csv \
  --out-dir data/bakeoff/runs/latest \
  --models gemini-2.0-flash
```
