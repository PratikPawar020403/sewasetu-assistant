# -*- coding: utf-8 -*-
"""
MCP tools for the Citizen assistant.

Each tool calls the portal's REST API with the citizen's OAuth token.
Tools available:
  - check_eligibility: Is this citizen eligible to apply?
  - submit_application: Submit a new pension application
  - check_status: Check status of existing applications
  - withdraw_application: Withdraw a pending application
"""

import logging
import requests

logger = logging.getLogger(__name__)


def _headers(token):
    return {"Authorization": "Bearer %s" % token, "Content-Type": "application/json"}


def check_eligibility(portal_url, token):
    """Check if the authenticated citizen is eligible to apply for pension.

    Returns eligibility information including:
    - Whether they are eligible
    - Whether they have an existing active application
    - Whether the scheme window is open
    - Minimum age requirement
    """
    try:
        resp = requests.get(
            "%s/api/eligibility" % portal_url,
            headers=_headers(token),
            timeout=15
        )
        return resp.json()
    except requests.RequestException as e:
        logger.error("check_eligibility failed: %s", e)
        return {"error": "connection_failed", "detail": str(e)}


def submit_application(portal_url, token, application_data):
    """Submit a new pension application.

    application_data should include:
    - applicant_name: Full name of the applicant
    - dob: Date of birth in DD/MM/YYYY format
    - gender: Male/Female/Other
    - marital_status: Married/Unmarried/Widow/Widower
    - husband_name: (if applicable)
    - village: Village name
    - block: One of: Sonari, Rajapara, Dhemaji Pathar, Borgaon, Namti, Khelua
    - bank_account: 9-18 digit bank account number
    - ifsc: 11-character IFSC code (e.g., SBIN0003077)
    """
    try:
        resp = requests.post(
            "%s/api/applications" % portal_url,
            json=application_data,
            headers=_headers(token),
            timeout=15
        )
        return resp.json()
    except requests.RequestException as e:
        logger.error("submit_application failed: %s", e)
        return {"error": "connection_failed", "detail": str(e)}


def check_status(portal_url, token):
    """Check status of all applications for the authenticated citizen.

    Returns a list of all applications associated with their mobile number,
    including status, submitted date, and decision details if decided.
    """
    try:
        resp = requests.get(
            "%s/api/applications/status" % portal_url,
            headers=_headers(token),
            timeout=15
        )
        return resp.json()
    except requests.RequestException as e:
        logger.error("check_status failed: %s", e)
        return {"error": "connection_failed", "detail": str(e)}


def withdraw_application(portal_url, token, application_id):
    """Withdraw a pending application.

    Only pending applications can be withdrawn. After withdrawal,
    the citizen can submit a new application.

    Args:
        application_id: The numeric ID of the application to withdraw.
    """
    try:
        resp = requests.post(
            "%s/api/applications/%s/withdraw" % (portal_url, application_id),
            headers=_headers(token),
            timeout=15
        )
        return resp.json()
    except requests.RequestException as e:
        logger.error("withdraw_application failed: %s", e)
        return {"error": "connection_failed", "detail": str(e)}
