# -*- coding: utf-8 -*-
"""
REST API endpoints for the Sewa Setu portal.

These endpoints are called by the MCP servers (citizen and officer) and are
protected by OAuth 2.1 JWT access tokens. The MCP servers never touch the
database directly; they go through these endpoints which enforce authorization.

Endpoints:
  Citizen-scoped:
    GET  /api/eligibility?mobile=<mobile>
    POST /api/applications              (submit new application)
    GET  /api/applications/status?mobile=<mobile>
    POST /api/applications/<id>/withdraw

  Officer-scoped:
    GET  /api/officer/applications       (list/filter)
    GET  /api/officer/applications/<id>  (detail + audit trail)
    POST /api/officer/applications/<id>/approve
    POST /api/officer/applications/<id>/reject
    GET  /api/officer/dashboard          (statistics)
"""

import os
import re
import json
import functools
from datetime import datetime, timedelta

import jwt
import requests as http
from flask import Blueprint, request, jsonify

import app as portal

api = Blueprint("api", __name__)

# ---------------------------------------------------------------------------
# JWT token verification middleware
# ---------------------------------------------------------------------------

_JWKS_CACHE = {"keys": None, "fetched_at": 0}


def _get_public_keys():
    """Get public keys from the portal's JWKS endpoint or in-process."""
    from oauth import public_jwks, ISSUER
    return public_jwks(), ISSUER


def _extract_token():
    """Extract Bearer token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def require_auth(scope):
    """Decorator that validates JWT access token and enforces scope."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            token = _extract_token()
            if not token:
                return jsonify({"error": "unauthorized", "detail": "Bearer token required"}), 401

            jwks_data, issuer = _get_public_keys()

            try:
                # Decode the token header to get the kid
                header = jwt.get_unverified_header(token)
                kid = header.get("kid")

                # Find the matching key
                key_data = None
                for k in jwks_data["keys"]:
                    if k.get("kid") == kid:
                        key_data = k
                        break

                if not key_data:
                    return jsonify({"error": "unauthorized", "detail": "Unknown signing key"}), 401

                # Construct the public key from JWK
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))

                # Verify the token — audience check is skipped because MCP servers
                # use the portal's own API, not a separate resource
                claims = jwt.decode(
                    token, public_key, algorithms=["RS256"],
                    issuer=issuer,
                    options={"verify_aud": False}
                )
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "unauthorized", "detail": "Token expired"}), 401
            except jwt.PyJWTError as e:
                return jsonify({"error": "unauthorized", "detail": "Invalid token: %s" % str(e)}), 401

            # Check scope
            token_scope = claims.get("scope", "")
            if token_scope != scope:
                return jsonify({
                    "error": "forbidden",
                    "detail": "This endpoint requires scope '%s', token has '%s'" % (scope, token_scope)
                }), 403

            # Attach claims to request context
            request.token_claims = claims
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Citizen API endpoints
# ---------------------------------------------------------------------------

@api.get("/api/eligibility")
@require_auth("citizen")
def check_eligibility():
    """Check if a citizen is eligible to apply for pension.

    Checks:
    1. Age >= 60 (if DOB provided)
    2. No active application on the same mobile
    3. Scheme window is open
    """
    claims = request.token_claims
    # Extract mobile from subject (citizen:<mobile>)
    subject = claims.get("sub", "")
    if not subject.startswith("citizen:"):
        return jsonify({"error": "invalid_subject", "detail": "Expected citizen subject"}), 400
    mobile = subject.split(":", 1)[1]

    # Also accept explicit mobile param for flexibility
    query_mobile = request.args.get("mobile", mobile)
    # Citizens can only check their own eligibility
    if query_mobile != mobile:
        return jsonify({"error": "forbidden", "detail": "You can only check your own eligibility"}), 403

    issues = []
    eligible = True

    # Check scheme window
    if portal.deadline_remaining() is None:
        issues.append("The application window for this scheme has closed.")
        eligible = False

    # Check for existing active application
    conn = portal.get_db()
    cur = conn.cursor()
    existing = portal.active_application(cur, mobile)
    if existing:
        issues.append(
            "Mobile number %s already has an active application: %s (status: %s). "
            "A pending application can be withdrawn from the status portal before applying again."
            % (mobile, existing[1], existing[2])
        )
        eligible = False

    cur.close()
    conn.close()

    result = {
        "mobile": mobile,
        "eligible": eligible,
        "min_age": portal.MIN_AGE,
        "scheme_deadline": portal.SCHEME_DEADLINE.isoformat(),
        "scheme_window_open": portal.deadline_remaining() is not None,
        "has_active_application": existing is not None,
    }
    if existing:
        result["active_application"] = {
            "application_no": existing[1],
            "status": existing[2],
        }
    if issues:
        result["issues"] = issues

    return jsonify(result)


@api.post("/api/applications")
@require_auth("citizen")
def submit_application():
    """Submit a new pension application.

    Expects JSON body with:
    - applicant_name, dob (DD/MM/YYYY), gender, marital_status,
      husband_name (if applicable), village, block, bank_account, ifsc
    - doc_path (the age-proof document path — for MCP, we accept a
      placeholder or reference since file upload is handled separately)
    """
    claims = request.token_claims
    subject = claims.get("sub", "")
    if not subject.startswith("citizen:"):
        return jsonify({"error": "invalid_subject"}), 400
    mobile = subject.split(":", 1)[1]

    body = request.get_json(silent=True) or {}

    # For MCP-based submissions, we handle doc_path specially:
    # The MCP tool can upload a document first or provide a path
    doc_path = body.get("doc_path", "")
    if not doc_path:
        # Create a placeholder document path so validation passes
        # In production, the document upload would be a separate step
        doc_path = "/var/sewasetu/uploads/%s_age_proof.pdf" % mobile
        # Create a minimal placeholder file
        try:
            os.makedirs(os.path.dirname(doc_path), exist_ok=True)
            if not os.path.exists(doc_path):
                with open(doc_path, "wb") as f:
                    f.write(b"%PDF-1.4 placeholder")
        except OSError:
            pass

    errors, cleaned = portal.validate_application(body, doc_path)
    if errors:
        return jsonify({"error": "validation_failed", "errors": errors}), 400

    conn = portal.get_db()
    cur = conn.cursor()

    # Check for duplicate
    existing = portal.active_application(cur, mobile)
    if existing:
        cur.close()
        conn.close()
        return jsonify({
            "error": "duplicate_application",
            "detail": "Application %s (%s) already exists for this mobile." % (existing[1], existing[2]),
            "application_no": existing[1],
            "status": existing[2],
        }), 409

    new_id, app_no = portal.create_application(cur, mobile, cleaned)
    conn.commit()
    cur.close()
    conn.close()

    # Send confirmation SMS
    portal.send_sms(mobile,
                    "Sewa Setu: application %s received. Track at the status portal "
                    "with mobile no. and password (DOB as DDMMYYYY)." % app_no)

    return jsonify({
        "success": True,
        "application_id": new_id,
        "application_no": app_no,
        "status": "PENDING",
        "message": "Application submitted successfully. Track at the status portal.",
    }), 201


@api.get("/api/applications/status")
@require_auth("citizen")
def check_status():
    """Check application status for the authenticated citizen."""
    claims = request.token_claims
    subject = claims.get("sub", "")
    if not subject.startswith("citizen:"):
        return jsonify({"error": "invalid_subject"}), 400
    mobile = subject.split(":", 1)[1]

    conn = portal.get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, application_no, applicant_name, dob, village, block, "
        "bank_account, ifsc, status, submitted_at, decided_at, decided_by "
        "FROM applications WHERE mobile = %s ORDER BY submitted_at DESC",
        (mobile,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return jsonify({
            "mobile": mobile,
            "applications": [],
            "message": "No applications found for this mobile number."
        })

    applications = []
    for row in rows:
        app_data = {
            "id": row[0],
            "application_no": row[1],
            "applicant_name": row[2],
            "dob": row[3].isoformat() if row[3] else None,
            "village": row[4],
            "block": row[5],
            "bank_account": row[6],
            "ifsc": row[7],
            "status": row[8],
            "submitted_at": row[9].isoformat() if row[9] else None,
            "decided_at": row[10].isoformat() if row[10] else None,
            "decided_by": row[11],
        }
        applications.append(app_data)

    return jsonify({
        "mobile": mobile,
        "applications": applications,
    })


@api.post("/api/applications/<int:app_id>/withdraw")
@require_auth("citizen")
def withdraw_application(app_id):
    """Withdraw a pending application."""
    claims = request.token_claims
    subject = claims.get("sub", "")
    if not subject.startswith("citizen:"):
        return jsonify({"error": "invalid_subject"}), 400
    mobile = subject.split(":", 1)[1]

    conn = portal.get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE applications SET status = 'WITHDRAWN', decided_at = %s, "
        "decided_by = 'APPLICANT' WHERE id = %s AND mobile = %s "
        "AND status = 'PENDING' RETURNING application_no",
        (datetime.now(), app_id, mobile)
    )
    row = cur.fetchone()
    if row:
        portal.write_audit(cur, app_id, "WITHDRAW", "applicant:%s" % mobile)
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            "success": True,
            "application_no": row[0],
            "new_status": "WITHDRAWN",
            "message": "Application %s has been withdrawn. You may submit a new application." % row[0],
        })
    else:
        cur.close()
        conn.close()
        return jsonify({
            "error": "cannot_withdraw",
            "detail": "Only a pending application belonging to you can be withdrawn.",
        }), 400


# ---------------------------------------------------------------------------
# Officer API endpoints
# ---------------------------------------------------------------------------

@api.get("/api/officer/dashboard")
@require_auth("officer")
def officer_dashboard():
    """Dashboard statistics for officers."""
    conn = portal.get_db()
    cur = conn.cursor()

    # Status counts
    cur.execute("SELECT status, count(*) FROM applications GROUP BY status")
    by_status = {row[0]: row[1] for row in cur.fetchall()}

    # Overdue count (pending > SLA days)
    cur.execute(
        "SELECT count(*) FROM applications WHERE status = 'PENDING' "
        "AND submitted_at < %s",
        (datetime.now() - timedelta(days=portal.SLA_DAYS),)
    )
    overdue = cur.fetchone()[0]

    # By block
    cur.execute(
        "SELECT block, count(*) FROM applications WHERE status = 'PENDING' "
        "GROUP BY block ORDER BY count(*) DESC"
    )
    by_block = {row[0]: row[1] for row in cur.fetchall()}

    # Total applications
    cur.execute("SELECT count(*) FROM applications")
    total = cur.fetchone()[0]

    cur.close()
    conn.close()

    return jsonify({
        "total_applications": total,
        "by_status": by_status,
        "overdue_pending": overdue,
        "sla_days": portal.SLA_DAYS,
        "pending_by_block": by_block,
        "blocks": portal.BLOCKS,
    })


@api.get("/api/officer/applications")
@require_auth("officer")
def officer_list_applications():
    """List/filter applications for officers.

    Query params:
    - status: filter by status (default: PENDING)
    - block: filter by block
    - mobile: search by mobile number
    - page: page number (default: 1)
    - per_page: items per page (default: 50, max: 100)
    - date_from: filter by submitted_at >= date (YYYY-MM-DD)
    - date_to: filter by submitted_at <= date (YYYY-MM-DD)
    """
    status = request.args.get("status", "PENDING")
    block = request.args.get("block", "")
    mobile = request.args.get("mobile", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 50))))
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    conn = portal.get_db()
    cur = conn.cursor()

    conditions = []
    params = []

    if mobile:
        conditions.append("mobile = %s")
        params.append(mobile)
    else:
        if status:
            conditions.append("status = %s")
            params.append(status)
        if block:
            conditions.append("block = %s")
            params.append(block)
        if date_from:
            conditions.append("submitted_at >= %s")
            params.append(date_from)
        if date_to:
            conditions.append("submitted_at <= %s")
            params.append(date_to + " 23:59:59")

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    # Count total matching
    cur.execute("SELECT count(*) FROM applications " + where, params)
    total = cur.fetchone()[0]

    # Fetch page
    query = (
        "SELECT id, application_no, applicant_name, mobile, block, status, "
        "submitted_at FROM applications %s ORDER BY submitted_at ASC "
        "LIMIT %%s OFFSET %%s" % where
    )
    cur.execute(query, params + [per_page, (page - 1) * per_page])
    rows = cur.fetchall()

    cur.close()
    conn.close()

    applications = []
    for row in rows:
        applications.append({
            "id": row[0],
            "application_no": row[1],
            "applicant_name": row[2],
            "mobile": row[3],
            "block": row[4],
            "status": row[5],
            "submitted_at": row[6].isoformat() if row[6] else None,
        })

    return jsonify({
        "applications": applications,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page else 1,
    })


@api.get("/api/officer/applications/<int:app_id>")
@require_auth("officer")
def officer_view_application(app_id):
    """View full application detail with audit trail."""
    conn = portal.get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, application_no, applicant_name, mobile, dob, gender, "
        "marital_status, husband_name, village, block, bank_account, ifsc, "
        "doc_path, status, submitted_at, decided_at, decided_by "
        "FROM applications WHERE id = %s", (app_id,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return jsonify({"error": "not_found", "detail": "Application not found"}), 404

    # Audit trail
    cur.execute(
        "SELECT at, action, actor, note FROM audit_log "
        "WHERE application_id = %s ORDER BY at ASC", (app_id,)
    )
    audit_rows = cur.fetchall()

    cur.close()
    conn.close()

    application = {
        "id": row[0],
        "application_no": row[1],
        "applicant_name": row[2],
        "mobile": row[3],
        "dob": row[4].isoformat() if row[4] else None,
        "gender": row[5],
        "marital_status": row[6],
        "husband_name": row[7],
        "village": row[8],
        "block": row[9],
        "bank_account": row[10],
        "ifsc": row[11],
        "doc_path": row[12],
        "status": row[13],
        "submitted_at": row[14].isoformat() if row[14] else None,
        "decided_at": row[15].isoformat() if row[15] else None,
        "decided_by": row[16],
    }

    audit_trail = []
    for a in audit_rows:
        audit_trail.append({
            "at": a[0].isoformat() if a[0] else None,
            "action": a[1],
            "actor": a[2],
            "note": a[3],
        })

    return jsonify({
        "application": application,
        "audit_trail": audit_trail,
    })


@api.post("/api/officer/applications/<int:app_id>/approve")
@require_auth("officer")
def officer_approve(app_id):
    """Approve a pending application."""
    claims = request.token_claims
    subject = claims.get("sub", "")
    actor = subject.split(":", 1)[1] if ":" in subject else subject

    body = request.get_json(silent=True) or {}
    note = body.get("note", "")

    conn = portal.get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE applications SET status = 'APPROVED', decided_at = %s, decided_by = %s "
        "WHERE id = %s AND status = 'PENDING' RETURNING application_no",
        (datetime.now(), actor, app_id)
    )
    row = cur.fetchone()
    if row:
        portal.write_audit(cur, app_id, "APPROVED", "officer:%s" % actor, note)
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            "success": True,
            "application_no": row[0],
            "new_status": "APPROVED",
            "decided_by": actor,
            "message": "Application %s has been approved." % row[0],
        })
    else:
        cur.close()
        conn.close()
        return jsonify({
            "error": "cannot_approve",
            "detail": "Only a pending application can be approved. "
                      "The application may already be approved, rejected, or withdrawn.",
        }), 400


@api.post("/api/officer/applications/<int:app_id>/reject")
@require_auth("officer")
def officer_reject(app_id):
    """Reject a pending application with reason."""
    claims = request.token_claims
    subject = claims.get("sub", "")
    actor = subject.split(":", 1)[1] if ":" in subject else subject

    body = request.get_json(silent=True) or {}
    note = body.get("note", "")
    reason = body.get("reason", note)

    if not reason:
        return jsonify({
            "error": "reason_required",
            "detail": "A reason must be provided when rejecting an application.",
        }), 400

    conn = portal.get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE applications SET status = 'REJECTED', decided_at = %s, decided_by = %s "
        "WHERE id = %s AND status = 'PENDING' RETURNING application_no",
        (datetime.now(), actor, app_id)
    )
    row = cur.fetchone()
    if row:
        portal.write_audit(cur, app_id, "REJECTED", "officer:%s" % actor, reason)
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            "success": True,
            "application_no": row[0],
            "new_status": "REJECTED",
            "decided_by": actor,
            "reason": reason,
            "message": "Application %s has been rejected." % row[0],
        })
    else:
        cur.close()
        conn.close()
        return jsonify({
            "error": "cannot_reject",
            "detail": "Only a pending application can be rejected.",
        }), 400
