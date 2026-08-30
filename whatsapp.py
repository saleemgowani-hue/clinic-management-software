"""
whatsapp.py
Builds a "Click to WhatsApp" link (wa.me) pre-filled with a fixed-format
appointment confirmation message, so staff can send it to the patient
with one click after booking — opens WhatsApp Web/Desktop/App with the
patient's number and the message already typed in; staff just presses
Send inside WhatsApp themselves.

No API keys, no account setup, no approval process, and no per-message
cost — this uses WhatsApp's official "click to chat" deep link
(https://wa.me/), the same mechanism "Chat with us on WhatsApp" buttons
on websites use. The message is not sent automatically by the app; the
staff member reviews it and taps Send inside WhatsApp, which keeps it
fully within WhatsApp's normal personal/business usage terms.
"""

from urllib.parse import quote

# Default country code used when a patient's mobile number is stored
# without one (e.g. "9876543210" -> "919876543210"). Change if most of
# your clinics are outside India.
DEFAULT_COUNTRY_CODE = "91"


def format_mobile(mobile: str) -> str:
    """
    Normalizes a stored mobile number into the digits-only international
    format wa.me expects (e.g. "9876543210" -> "919876543210",
    "+91 98765 43210" -> "919876543210"). No leading "+".
    """
    digits = "".join(ch for ch in (mobile or "") if ch.isdigit())
    if not digits:
        return ""
    if len(digits) == 10:
        return f"{DEFAULT_COUNTRY_CODE}{digits}"
    return digits


def build_appointment_message(patient_name, clinic_name, doctor_name, appt_date, appt_time) -> str:
    """Fixed-format appointment confirmation text."""
    return (
        f"Hello {patient_name}, your appointment is confirmed.\n"
        f"Clinic: {clinic_name}\n"
        f"Doctor: {doctor_name or 'To be assigned'}\n"
        f"Date: {appt_date}\n"
        f"Time: {appt_time}\n"
        f"Please arrive 10 minutes early. Thank you!"
    )


def build_whatsapp_link(mobile, patient_name, clinic_name, doctor_name, appt_date, appt_time):
    """
    Returns (link: str|None, message: str). If the mobile number is
    missing/invalid, link is None and message explains why — callers
    should show that as a soft note instead of a button.
    """
    to_number = format_mobile(mobile)
    if not to_number or len(to_number) < 8:
        return None, "Patient's mobile number looks invalid, so no WhatsApp link could be created."

    text = build_appointment_message(patient_name, clinic_name, doctor_name, appt_date, appt_time)
    link = f"https://wa.me/{to_number}?text={quote(text)}"
    return link, "WhatsApp message ready — click below to review and send it."
