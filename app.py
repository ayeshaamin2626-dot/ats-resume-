"""AI Resume ATS Checker - Streamlit + Gemini Flash."""

import io
import os
from typing import List, Optional

import streamlit as st
from docx import Document
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from pypdf import PdfReader

# Override with the GEMINI_MODEL environment variable (or Streamlit secret) if
# Google retires this version, e.g. GEMINI_MODEL="gemini-flash-latest".
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
MAX_RESUME_CHARS = 30000
MAX_FILE_MB = 5


# ----------------------------- Output schema ----------------------------- #
class SectionScores(BaseModel):
    keywords: int = Field(description="Keyword relevance, 0-100")
    formatting: int = Field(description="ATS-friendly structure and formatting, 0-100")
    impact: int = Field(description="Use of measurable achievements and action verbs, 0-100")
    clarity: int = Field(description="Clarity, grammar and conciseness, 0-100")


class Improvement(BaseModel):
    area: str = Field(description="Resume area, e.g. Summary, Experience, Skills")
    issue: str = Field(description="What is wrong or weak")
    suggestion: str = Field(description="Specific action to fix it")
    priority: str = Field(description="High, Medium or Low")


class ResumeAnalysis(BaseModel):
    ats_score: int = Field(description="Overall ATS score, 0-100")
    summary: str = Field(description="2-3 sentence overall assessment")
    section_scores: SectionScores
    strengths: List[str]
    missing_keywords: List[str]
    improvements: List[Improvement]
    rewrite_examples: List[str] = Field(
        description="2-4 weak bullet points rewritten stronger, as 'Before -> After'"
    )


# ------------------------------- Helpers --------------------------------- #
def extract_text(file_name: str, data: bytes) -> str:
    """Extract plain text from a PDF, DOCX or TXT file."""
    name = file_name.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.extend(cell.text for cell in row.cells)
        return "\n".join(parts).strip()
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore").strip()
    raise ValueError("Unsupported file type. Please upload a PDF, DOCX or TXT file.")


def get_api_key() -> Optional[str]:
    """Look for the key in Streamlit secrets, then environment variables."""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass  # no secrets file present
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def build_prompt(resume_text: str, job_description: str) -> str:
    jd_block = (
        f"JOB DESCRIPTION:\n{job_description.strip()}\n\n"
        "Score the resume against this job description and list the important "
        "keywords from it that are missing from the resume."
        if job_description.strip()
        else "No job description was provided. Score the resume for general ATS "
        "compatibility and list commonly expected keywords for the candidate's field "
        "that are missing."
    )
    return (
        "You are an expert recruiter and ATS (Applicant Tracking System) analyst.\n"
        "Analyse the resume below. Be honest, specific and strict; do not inflate the score.\n"
        "All scores are integers from 0 to 100. Priority must be High, Medium or Low.\n"
        "Never invent experience the candidate does not have.\n\n"
        f"{jd_block}\n\nRESUME:\n{resume_text[:MAX_RESUME_CHARS]}"
    )


def analyze_resume(api_key: str, resume_text: str, job_description: str) -> ResumeAnalysis:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=build_prompt(resume_text, job_description),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ResumeAnalysis,
            temperature=0.2,
        ),
    )
    result = response.parsed
    if result is None:  # fall back to parsing the raw text
        result = ResumeAnalysis.model_validate_json(response.text)
    result.ats_score = max(0, min(100, result.ats_score))
    return result


def score_label(score: int) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 65:
        return "Good"
    if score >= 50:
        return "Needs work"
    return "Poor"


# --------------------------------- UI ------------------------------------ #
def main() -> None:
    st.set_page_config(page_title="AI Resume ATS Checker", page_icon="📄", layout="wide")
    st.title("📄 AI Resume ATS Checker")
    st.caption("Upload your resume to get an ATS score and concrete improvements, powered by Gemini Flash.")

    api_key = get_api_key()
    with st.sidebar:
        st.header("Settings")
        if api_key:
            st.success("Gemini API key loaded.")
        else:
            api_key = st.text_input(
                "Gemini API key",
                type="password",
                help="Get a free key at https://aistudio.google.com/apikey",
            )
        st.markdown("Your resume is sent to Google's Gemini API for analysis. Don't upload anything you aren't comfortable sharing.")

    col_left, col_right = st.columns(2)
    with col_left:
        uploaded = st.file_uploader("Upload your resume", type=["pdf", "docx", "txt"])
    with col_right:
        job_description = st.text_area(
            "Job description (optional, improves accuracy)",
            height=150,
            placeholder="Paste the job posting here to get a tailored score...",
        )

    if st.button("Analyze resume", type="primary", disabled=uploaded is None):
        if not api_key:
            st.error("Please provide a Gemini API key in the sidebar.")
            return
        data = uploaded.getvalue()
        if len(data) > MAX_FILE_MB * 1024 * 1024:
            st.error(f"File is too large. Maximum size is {MAX_FILE_MB} MB.")
            return
        try:
            with st.spinner("Reading your resume..."):
                text = extract_text(uploaded.name, data)
        except Exception as exc:
            st.error(f"Could not read the file: {exc}")
            return
        if len(text) < 100:
            st.error(
                "Very little text was found. If your PDF is a scanned image, "
                "export a text-based PDF or upload a DOCX instead."
            )
            return
        try:
            with st.spinner("Analyzing with Gemini..."):
                st.session_state["analysis"] = analyze_resume(api_key, text, job_description)
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
            return

    analysis: Optional[ResumeAnalysis] = st.session_state.get("analysis")
    if analysis is None:
        return

    st.divider()
    top_left, top_right = st.columns([1, 2])
    with top_left:
        st.metric("ATS Score", f"{analysis.ats_score}/100")
        st.progress(analysis.ats_score / 100)
        st.caption(f"Rating: {score_label(analysis.ats_score)}")
    with top_right:
        st.subheader("Summary")
        st.write(analysis.summary)

    st.subheader("Score breakdown")
    scores = analysis.section_scores
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Keywords", scores.keywords)
    c2.metric("Formatting", scores.formatting)
    c3.metric("Impact", scores.impact)
    c4.metric("Clarity", scores.clarity)

    left, right = st.columns(2)
    with left:
        st.subheader("✅ Strengths")
        for item in analysis.strengths:
            st.markdown(f"- {item}")
    with right:
        st.subheader("🔑 Missing keywords")
        if analysis.missing_keywords:
            st.markdown(" ".join(f"`{k}`" for k in analysis.missing_keywords))
        else:
            st.write("None found.")

    st.subheader("🛠️ Improvements")
    order = {"high": 0, "medium": 1, "low": 2}
    for imp in sorted(analysis.improvements, key=lambda i: order.get(i.priority.lower(), 3)):
        with st.expander(f"[{imp.priority}] {imp.area}"):
            st.markdown(f"**Issue:** {imp.issue}")
            st.markdown(f"**Fix:** {imp.suggestion}")

    if analysis.rewrite_examples:
        st.subheader("✍️ Example rewrites")
        for ex in analysis.rewrite_examples:
            st.markdown(f"- {ex}")

    st.download_button(
        "Download report (JSON)",
        data=analysis.model_dump_json(indent=2),
        file_name="ats_report.json",
        mime="application/json",
    )


if __name__ == "__main__":
    main()
