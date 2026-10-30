# -*- coding: utf-8 -*-
"""
MCP tools for the Officer assistant.

Each tool calls the portal's REST API with the officer's OAuth token.
Tools available:
  - list_applications: List/filter pending applications
  - view_application: View full application detail with audit trail
  - approve_application: Approve a pending application
  - reject_application: Reject a pending application with reason
  - dashboard_stats: Get dashboard statistics
"""

import logging
import requests

logger = logging.getLogger(__name__)


def _headers(token):
    return {"Authorization": "Bearer %s" % token, "Content-Type": "application/json"}


def dashboard_stats(portal_url, token):
    """Get dashboard statistics: status counts, overdue, by block."""
    try:
        resp = requests.get(
            "%s/api/officer/dashboard" % portal_url,
            headers=_headers(token),
            timeout=15
        )
        return resp.json()
    except requests.RequestException as e:
        logger.error("dashboard_stats failed: %s", e)
        return {"error": "connection_failed", "detail": str(e)}


def list_applications(portal_url, token, filters=None):
    """List/filter applications.

    Supported filters:
    - status: PENDING, APPROVED, DEEMED_APPROVED, REJECTED, WITHDRAWN
    - block: one of the 6 blocks
    - mobile: search by mobile number
    - date_from, date_to: date range (YYYY-MM-DD)
    - page, per_page: pagination
    """
    try:
        params = filters or {}
        resp = requests.get(
            "%s/api/officer/applications" % portal_url,
            params=params,
            headers=_headers(token),
            timeout=15
        )
        return resp.json()
    except requests.RequestException as e:
        logger.error("list_applications failed: %s", e)
        return {"error": "connection_failed", "detail": str(e)}


def view_application(portal_url, token, application_id):
    """View full application detail with audit trail."""
    try:
        resp = requests.get(
            "%s/api/officer/applications/%s" % (portal_url, application_id),
            headers=_headers(token),
            timeout=15
        )
        return resp.json()
    except requests.RequestException as e:
        logger.error("view_application failed: %s", e)
        return {"error": "connection_failed", "detail": str(e)}


def approve_application(portal_url, token, application_id, note=""):
    """Approve a pending application with an optional audit note."""
    try:
        resp = requests.post(
            "%s/api/officer/applications/%s/approve" % (portal_url, application_id),
            json={"note": note},
            headers=_headers(token),
            timeout=15
        )
        return resp.json()
    except requests.RequestException as e:
        logger.error("approve_application failed: %s", e)
        return {"error": "connection_failed", "detail": str(e)}


def reject_application(portal_url, token, application_id, reason="", note=""):
    """Reject a pending application with reason and optional audit note."""
    try:
        resp = requests.post(
            "%s/api/officer/applications/%s/reject" % (portal_url, application_id),
            json={"reason": reason, "note": note or reason},
            headers=_headers(token),
            timeout=15
        )
        return resp.json()
    except requests.RequestException as e:
        logger.error("reject_application failed: %s", e)
        return {"error": "connection_failed", "detail": str(e)}
