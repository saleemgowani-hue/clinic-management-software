"""
billing.py
Razorpay Payment Links integration so clinics can pay to upgrade their plan
directly from inside the app. Uses plain REST calls (via `requests`) against
Razorpay's Payment Links API, so it doesn't require the separate `razorpay`
SDK package.

Docs: https://razorpay.com/docs/api/payments/payment-links/

SETUP (do this on your deployment, not needed to run the app without billing):
1. Create a Razorpay account and get your Key ID + Key Secret
   (Test mode keys are fine for trying this out).
2. Set them as environment variables before starting Streamlit:
     export RAZORPAY_KEY_ID="rzp_test_xxxxxxxx"
     export RAZORPAY_KEY_SECRET="your_key_secret"
   ...or add them to `.streamlit/secrets.toml`:
     RAZORPAY_KEY_ID = "rzp_test_xxxxxxxx"
     RAZORPAY_KEY_SECRET = "your_key_secret"
3. That's it - the "Billing & Upgrade" page will detect the keys and enable
   real payment links automatically. Without keys configured, that page
   shows setup instructions instead of crashing the app.
"""

import os
import base64

import requests

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"

# Monthly pricing in INR (edit these to your own pricing).
PLAN_PRICING = {
    "Basic": 999,
    "Pro": 2499,
    "Enterprise": 4999,
}


def _get_credentials():
    """Reads Razorpay keys from environment variables or Streamlit secrets."""
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        try:
            import streamlit as st
            key_id = key_id or st.secrets.get("RAZORPAY_KEY_ID")
            key_secret = key_secret or st.secrets.get("RAZORPAY_KEY_SECRET")
        except Exception:
            pass
    return key_id, key_secret


def is_configured() -> bool:
    key_id, key_secret = _get_credentials()
    return bool(key_id and key_secret)


def _auth_header():
    key_id, key_secret = _get_credentials()
    token = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def create_payment_link(amount_rupees: float, plan: str, clinic_name: str,
                         customer_name: str, customer_email: str = "",
                         customer_contact: str = "", center_id: int = None) -> dict:
    """
    Creates a Razorpay Payment Link for a plan upgrade.
    Returns {"id": ..., "short_url": ..., "status": ...} on success.
    Raises RuntimeError with a readable message on failure.
    """
    if not is_configured():
        raise RuntimeError("Razorpay keys are not configured on this server.")

    payload = {
        "amount": int(round(amount_rupees * 100)),  # paise
        "currency": "INR",
        "description": f"{plan} Plan subscription - {clinic_name}",
        "customer": {
            "name": customer_name,
            "email": customer_email or None,
            "contact": customer_contact or None,
        },
        "notify": {"sms": bool(customer_contact), "email": bool(customer_email)},
        "reminder_enable": True,
        "notes": {"center_id": str(center_id) if center_id else "", "plan": plan},
    }
    resp = requests.post(
        f"{RAZORPAY_API_BASE}/payment_links", json=payload, headers=_auth_header(), timeout=15
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Razorpay error ({resp.status_code}): {resp.text}")
    data = resp.json()
    return {"id": data["id"], "short_url": data["short_url"], "status": data["status"]}


def fetch_payment_link_status(link_id: str) -> str:
    """Returns one of: 'created', 'paid', 'cancelled', 'expired'."""
    if not is_configured():
        raise RuntimeError("Razorpay keys are not configured on this server.")

    resp = requests.get(
        f"{RAZORPAY_API_BASE}/payment_links/{link_id}", headers=_auth_header(), timeout=15
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Razorpay error ({resp.status_code}): {resp.text}")
    return resp.json().get("status", "created")
