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
# ── Cover Letter Only ────────────────────────────────────

COVER_ONLY_PROMPT = """You are an expert cover letter writer. Write a compelling, human-sounding cover letter based on the candidate's background and the job description.

STRICT RULES:
- Sound like a real person wrote it — never use templates
- Never say: "I would be honoured", "I am writing to express my interest", "Please find attached"
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

def generate_cover_letter_only(cv_text: str, job_description: str) -> dict:
    prompt = f"""{COVER_ONLY_PROMPT}

CANDIDATE BACKGROUND:
{cv_text}

JOB DESCRIPTION:
{job_description}

Return ONLY valid JSON."""
    return _parse_json(_call_gemini(prompt), "cover letter")


# ── LinkedIn Bio ─────────────────────────────────────────

LINKEDIN_PROMPT = """You are an expert LinkedIn profile writer. Write an optimized LinkedIn About section and headline for the candidate.

STRICT RULES:
- Sound human, not like a robot wrote it
- No clichés: "passionate", "results-driven", "dynamic", "synergy"
- Headline: short, specific, keyword-rich (max 15 words)
- About section: conversational, first person, 3-4 short paragraphs
- End the About section with a clear call to action
- Only use what's actually in their background — never invent

Return ONLY this JSON — no markdown, no preamble:
{
  "headline": "Your LinkedIn headline here",
  "about": "Full LinkedIn About section here as one string with paragraph breaks using \\n\\n"
}
"""

def generate_linkedin_bio(cv_text: str, target_role: str) -> dict:
    prompt = f"""{LINKEDIN_PROMPT}

CANDIDATE BACKGROUND:
{cv_text}

TARGET ROLE/INDUSTRY:
{target_role}

Return ONLY valid JSON."""
    return _parse_json(_call_gemini(prompt), "LinkedIn bio")


# ── Business Proposal ────────────────────────────────────

PROPOSAL_PROMPT = """You are an expert business proposal writer. Write a professional business proposal based on the details provided.

STRICT RULES:
- Professional but not stiff — clear and direct
- No filler phrases like "We are pleased to submit", "Please find herewith"
- Every section must be specific to what the user provided — no generic padding
- Sections must flow logically and build a convincing case

Return ONLY this JSON — no markdown, no preamble:
{
  "business_name": "Name of the business/sender",
  "client_name": "Name of the client/recipient",
  "date": "Day Month Year",
  "subject": "Clear proposal subject line",
  "sections": [
    { "title": "Executive Summary", "content": "..." },
    { "title": "The Problem / Opportunity", "content": "..." },
    { "title": "Our Solution", "content": "..." },
    { "title": "Scope of Work", "content": "..." },
    { "title": "Pricing", "content": "..." },
    { "title": "Why Us", "content": "..." },
    { "title": "Next Steps", "content": "..." }
  ]
}
"""

def generate_proposal(details: str) -> dict:
    prompt = f"""{PROPOSAL_PROMPT}

BUSINESS/PROJECT DETAILS PROVIDED BY USER:
{details}

Return ONLY valid JSON."""
    return _parse_json(_call_gemini(prompt), "proposal")


# ── Interview Prep ───────────────────────────────────────

INTERVIEW_PROMPT = """You are an expert interview coach. Generate likely interview questions and strong answers based on the job description and candidate background.

STRICT RULES:
- Questions must be specific to this role — not generic
- Answers must use the candidate's actual experience — never invent
- Answers should use the STAR format where appropriate (Situation, Task, Action, Result)
- No weak answers — every answer should be confident and specific
- Mix of technical, behavioural, and situational questions

Return ONLY this JSON — no markdown, no preamble:
{
  "role": "Job title being applied for",
  "questions": [
    {
      "question": "Interview question here",
      "answer": "Strong answer here"
    }
  ]
}

Generate exactly 10 questions.
"""

def generate_interview_prep(cv_text: str, job_description: str) -> dict:
    prompt = f"""{INTERVIEW_PROMPT}

CANDIDATE BACKGROUND:
{cv_text}

JOB DESCRIPTION:
{job_description}

Return ONLY valid JSON."""
    return _parse_json(_call_gemini(prompt), "interview prep")


# ── Business Permit Guide ────────────────────────────────

PERMIT_PROMPT = """You are an expert on Kenyan business regulations and licensing. Provide a clear, accurate step-by-step guide for registering and licensing the described business in Kenya.

STRICT RULES:
- Be specific to the business type and location described
- Include the actual government bodies involved (eCitizen, county government, KEBS, etc.)
- Include estimated costs in KES where known
- Include estimated timelines
- Be practical — tell them exactly what to do, in order
- If you are unsure of a specific fee, say "confirm current fee on eCitizen" rather than guessing

Return ONLY this JSON — no markdown, no preamble:
{
  "business_type": "Type of business described",
  "location": "County/location mentioned",
  "summary": "2 sentence overview of what they need",
  "steps": [
    {
      "step": 1,
      "title": "Step title",
      "description": "What to do",
      "where": "Which office or website",
      "cost": "Estimated cost in KES or 'Confirm on eCitizen'",
      "time": "Estimated time"
    }
  ],
  "important_notes": ["Note 1", "Note 2"]
}
"""

def generate_permit_guide(business_details: str) -> dict:
    prompt = f"""{PERMIT_PROMPT}

BUSINESS DETAILS:
{business_details}

Return ONLY valid JSON."""
    return _parse_json(_call_gemini(prompt), "permit guide")