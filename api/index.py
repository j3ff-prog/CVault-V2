"""
api/index.py — Flask app entry point for Vercel serverless.
All routes live here. No in-memory session store needed —
CV data travels through the browser's sessionStorage instead.
"""
import os
import sys
import json
import requests as http_requests
from flask import Flask, request, jsonify

# Ensure the project root is on the path so `services` can be imported
# whether running locally or on Vercel
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.cv_extractor import extract_text
from services.gemini_service import generate_cv, generate_cover_letter

app = Flask(__name__)

PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/{}"

# ── Paystack payment links (pre-created by Jeff) ──
PAYSTACK_LINKS = {
    "cv":       "https://paystack.shop/pay/pcxm8e88f2",
    "cv_cover": "https://paystack.shop/pay/6fjdv8zm65",
}


# ─────────────────────────────────────────────────────────
# POST /api/extract
# Accepts a CV file upload, returns extracted plain text.
# The frontend stores this text in sessionStorage.
# ─────────────────────────────────────────────────────────
@app.route("/api/extract", methods=["POST"])
def extract():
    if "cv_file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    f = request.files["cv_file"]
    if not f or not f.filename:
        return jsonify({"error": "Empty file upload."}), 400

    # 5MB limit
    file_bytes = f.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        return jsonify({"error": "File is too large. Please upload a file under 5MB."}), 400

    try:
        text = extract_text(file_bytes, f.filename)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"cv_text": text})


# ─────────────────────────────────────────────────────────
# POST /api/checkout
# Validates inputs, returns the correct Paystack payment URL.
# No data is stored server-side — frontend keeps cv_text + jd.
# ─────────────────────────────────────────────────────────
@app.route("/api/checkout", methods=["POST"])
def checkout():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided."}), 400

    cv_text = (data.get("cv_text") or "").strip()
    job_description = (data.get("job_description") or "").strip()
    package = (data.get("package") or "").strip()

    if not cv_text:
        return jsonify({"error": "CV text is missing."}), 400
    if not job_description:
        return jsonify({"error": "Please paste the job description."}), 400
    if package not in PAYSTACK_LINKS:
        return jsonify({"error": "Invalid package selected."}), 400

    return jsonify({"paystack_url": PAYSTACK_LINKS[package]})


# ─────────────────────────────────────────────────────────
# POST /api/generate
# Called by the payment-success page.
# Body: { reference, cv_text, job_description, package }
# Verifies payment with Paystack, then runs Gemini.
# ─────────────────────────────────────────────────────────
@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided."}), 400

    reference     = (data.get("reference") or "").strip()
    cv_text       = (data.get("cv_text") or "").strip()
    job_description = (data.get("job_description") or "").strip()
    package       = (data.get("package") or "cv").strip()

    if not reference:
        return jsonify({"error": "Missing payment reference."}), 400
    if not cv_text:
        return jsonify({"error": "CV data missing. Please go back and start again."}), 400
    if not job_description:
        return jsonify({"error": "Job description missing. Please go back and start again."}), 400

    # ── 1. Verify payment with Paystack ──
    secret_key = os.getenv("PAYSTACK_SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "Payment system not configured."}), 500

    try:
        resp = http_requests.get(
            PAYSTACK_VERIFY_URL.format(reference),
            headers={"Authorization": f"Bearer {secret_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()
    except http_requests.RequestException as e:
        return jsonify({"error": f"Could not reach payment server: {str(e)}"}), 502

    tx_data = result.get("data", {})
    if not result.get("status") or tx_data.get("status") != "success":
        return jsonify({
            "error": f"Payment not confirmed (status: {tx_data.get('status', 'unknown')}). "
                     f"If you were charged, contact support with reference: {reference}"
        }), 402

    # ── 2. Generate with Gemini ──
    try:
        cv_data = generate_cv(cv_text, job_description)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    response_payload = {"cv_data": cv_data}

    if package == "cv_cover":
        try:
            cover_data = generate_cover_letter(cv_text, job_description)
            response_payload["cover_letter_data"] = cover_data
        except RuntimeError as e:
            # Don't fail the whole request — CV is already generated
            response_payload["cover_letter_error"] = str(e)

    return jsonify(response_payload)


# Vercel needs the app object exported as `app`
# (Vercel detects Flask apps automatically)
