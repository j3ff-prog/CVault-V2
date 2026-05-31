"""
api/index.py — Flask app entry point for Vercel serverless.
CV data travels through the browser's sessionStorage — no server-side session store.
"""
import os
import sys
import json
import requests as http_requests
from flask import Flask, request, jsonify, Response

# Ensure project root is on path so `services` can be found on Vercel
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.cv_extractor import extract_text
from services.gemini_service import generate_cv, generate_cover_letter

app = Flask(__name__)

# ── CORS — needed so mobile browsers can reach the API ──
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/{}"

PAYSTACK_LINKS = {
    "cv":       "https://paystack.shop/pay/pcxm8e88f2",
    "cv_cover": "https://paystack.shop/pay/6fjdv8zm65",
}


@app.route("/api/extract", methods=["POST", "OPTIONS"])
def extract():
    if request.method == "OPTIONS":
        return Response(status=200)

    if "cv_file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    f = request.files["cv_file"]
    if not f or not f.filename:
        return jsonify({"error": "Empty file upload."}), 400

    file_bytes = f.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        return jsonify({"error": "File too large. Please upload under 5MB."}), 400

    try:
        text = extract_text(file_bytes, f.filename)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"cv_text": text})


@app.route("/api/checkout", methods=["POST", "OPTIONS"])
def checkout():
    if request.method == "OPTIONS":
        return Response(status=200)

    data = request.get_json(silent=True) or {}

    cv_text         = (data.get("cv_text") or "").strip()
    job_description = (data.get("job_description") or "").strip()
    package         = (data.get("package") or "").strip()

    if not cv_text:
        return jsonify({"error": "CV text is missing."}), 400
    if not job_description:
        return jsonify({"error": "Please paste the job description."}), 400
    if package not in PAYSTACK_LINKS:
        return jsonify({"error": "Invalid package selected."}), 400

    return jsonify({"paystack_url": PAYSTACK_LINKS[package]})


@app.route("/api/generate", methods=["POST", "OPTIONS"])
def generate():
    if request.method == "OPTIONS":
        return Response(status=200)

    data = request.get_json(silent=True) or {}

    reference       = (data.get("reference") or "").strip()
    cv_text         = (data.get("cv_text") or "").strip()
    job_description = (data.get("job_description") or "").strip()
    package         = (data.get("package") or "cv").strip()

    if not reference:
        return jsonify({"error": "Missing payment reference."}), 400
    if not cv_text:
        return jsonify({"error": "CV data missing. Please go back and start again."}), 400
    if not job_description:
        return jsonify({"error": "Job description missing. Please go back and start again."}), 400

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
                     f"If you were charged, contact us with reference: {reference}"
        }), 402

    try:
        cv_data = generate_cv(cv_text, job_description)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    payload = {"cv_data": cv_data}

    if package == "cv_cover":
        try:
            payload["cover_letter_data"] = generate_cover_letter(cv_text, job_description)
        except RuntimeError as e:
            payload["cover_letter_error"] = str(e)

    return jsonify(payload)


# Vercel needs the app object exported as `app`
# (Vercel detects Flask apps automatically)
