"""
gemini_service.py — Calls Gemini to generate tailored CV and cover letter.
Uses google-genai SDK. Primary: gemini-2.0-flash, Fallback: gemini-1.5-flash.
Returns structured JSON that the frontend converts to .docx via docx.js.
"""
import os
import json
from google import genai

PRIMARY_MODEL  = "gemini-2.5-flash-lite"
FALLBACK_MODEL = "gemini-2.5-flash-lite"
_client = None


def _get_client():
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError("GEMINI_API_KEY environment variable not set.")
        _client = genai.Client(api_key=key)
    return _client


def _call_gemini(prompt: str) -> str:
    client = _get_client()
    try:
        return client.models.generate_content(model=PRIMARY_MODEL, contents=prompt).text
    except Exception as e:
        err = str(e)
        if any(x in err.lower() for x in ["503", "overloaded", "unavailable"]):
            try:
                return client.models.generate_content(model=FALLBACK_MODEL, contents=prompt).text
            except Exception as e2:
                raise RuntimeError(f"Both Gemini models failed. {err} | {str(e2)}")
        raise RuntimeError(f"Gemini error: {err}")


def _parse_json(raw: str, label: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Gemini returned invalid JSON for {label}: {e}\nPreview: {raw[:300]}")


# ── CV ──────────────────────────────────────────────────

CV_PROMPT = """You are an expert CV writer. Rewrite the candidate's CV to match the job description — without inventing any experience, skills, or education they don't have.

STRICT RULES:
- Never invent anything not in the original CV
- Banned words: "dynamic", "passionate", "results-driven", "synergy", "leverage", "utilize", "proactive"
- Banned weak verbs: "Helped", "Assisted", "Worked on", "Was responsible for", "Participated in"
- Every bullet = strong action verb + specific outcome
- Summary = max 3 tight sentences, no fluff
- Mirror keywords from the job description naturally

Return ONLY this JSON — no markdown, no preamble:
{
  "name": "FULL NAME",
  "contact": "Phone | Email | Location",
  "summary": "2-3 sentence summary tailored to the role",
  "experience": [
    {
      "title": "Job Title",
      "company": "Company Name",
      "period": "Month Year – Month Year",
      "bullets": ["Action verb + outcome.", "Action verb + outcome."]
    }
  ],
  "education": [
    {
      "degree": "Degree name",
      "institution": "Institution",
      "period": "Year – Year",
      "details": "Optional details"
    }
  ],
  "skills": ["Skill 1", "Skill 2"],
  "languages": ["Language (Proficiency)"],
  "referees": [
    { "name": "Name", "title": "Title", "company": "Company", "contact": "phone or email" }
  ]
}
If languages or referees are absent from the original CV, return empty arrays [].
"""


def generate_cv(cv_text: str, job_description: str) -> dict:
    prompt = f"""{CV_PROMPT}

ORIGINAL CV:
{cv_text}

JOB DESCRIPTION:
{job_description}

Return ONLY valid JSON."""
    return _parse_json(_call_gemini(prompt), "CV")


# ── Cover Letter ─────────────────────────────────────────

COVER_LETTER_PROMPT = """You are an expert cover letter writer. Write a compelling, human-sounding cover letter.

STRICT RULES:
- Sound like a real person wrote it — never use templates
- Never say: "I would be honoured", "I am writing to express my interest", "Please find attached", "To whom it may concern"
- Short paragraphs, 2-3 sentences each
- Confident, direct tone — no corporate fluff
- Only use experience actually in the CV — never invent

Return ONLY this JSON — no markdown, no preamble:
{
  "applicant_name": "Full Name",
  "applicant_contact": "Phone | Email | Location",
  "date": "Day Month Year",
  "re_line": "Application for [Job Title] — [Company if known]",
  "paragraphs": [
    "Opening — direct hook, why this role.",
    "What you bring — specific skills/experience matching the JD.",
    "Why this company/role — brief genuine reason.",
    "Close — confident call to action."
  ],
  "closing_name": "Full Name"
}
"""


def generate_cover_letter(cv_text: str, job_description: str) -> dict:
    prompt = f"""{COVER_LETTER_PROMPT}

ORIGINAL CV:
{cv_text}

JOB DESCRIPTION:
{job_description}

Return ONLY valid JSON."""
    return _parse_json(_call_gemini(prompt), "cover letter")
