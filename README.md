# ats-resume-# 📄 AI Resume ATS Checker

A Streamlit app that scores a resume for ATS (Applicant Tracking System) compatibility and suggests concrete improvements, powered by Google's Gemini Flash model.

## Features

- Upload a resume as **PDF, DOCX or TXT**
- Optional **job description** field for a tailored score and keyword gap analysis
- Overall **ATS score (0-100)** plus breakdown: keywords, formatting, impact, clarity
- Strengths, missing keywords, prioritized improvements and example bullet rewrites
- Download the full report as JSON

## Project structure

```
.
├── app.py             # Streamlit app
├── requirements.txt   # Python dependencies
└── README.md
```

## Run locally

1. Get a free Gemini API key at https://aistudio.google.com/apikey
2. Install and run:

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
export GEMINI_API_KEY="your-key"   # Windows PowerShell: $env:GEMINI_API_KEY="your-key"
streamlit run app.py
```

If you don't set the environment variable, you can paste the key into the app's sidebar instead.

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub (never commit your API key).
2. Go to https://share.streamlit.io and click **Create app**.
3. Select your repo, branch `main`, and main file `app.py`.
4. Open **Advanced settings → Secrets** and add:

```toml
GEMINI_API_KEY = "your-key"
```

5. Click **Deploy**.

## Notes

- The default model is `gemini-2.5-flash`. To use a different Gemini Flash version (for example if Google retires this one), set a `GEMINI_MODEL` environment variable locally or add `GEMINI_MODEL = "model-name"` to your Streamlit secrets.
- Scanned (image-only) PDFs contain no extractable text. Use a text-based PDF or DOCX.
- Resume text is sent to the Gemini API. Don't upload data you aren't comfortable sharing.
- The ATS score is an AI estimate, not the output of any specific real-world ATS.
