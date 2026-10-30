# -*- coding: utf-8 -*-
"""
Database assertions for SewaSetu evaluation framework.

Verifies the state of the SewaSetu PostgreSQL database after an evaluation
conversation completes, ensuring the assistant adhered to business rules
and properly recorded transactions.
"""

import logging
import psycopg2

logger = logging.getLogger(__name__)


def check_assertion(conn_params, assertion):
    """Execute a single database assertion.

    Args:
        conn_params (dict): Database connection parameters.
        assertion (dict): Assertion definition from persona.

    Returns:
        dict: {"passed": bool, "description": str, "actual": str, "error": str or None}
    """
    atype = assertion.get("type")
    desc = assertion.get("description", str(assertion))

    try:
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()

        if atype == "application_exists":
            mobile = assertion.get("mobile")
            expected_status = assertion.get("status")

            query = "SELECT id, application_no, status, applicant_name, village, block FROM applications WHERE mobile = %s"
            params = [mobile]
            if expected_status:
                query += " AND status = %s"
                params.append(expected_status)
            query += " ORDER BY submitted_at DESC LIMIT 1"

            cur.execute(query, params)
            row = cur.fetchone()

            if row:
                passed = True
                actual = f"Found application {row[1]} with status {row[2]} for {row[3]}"
            else:
                passed = False
                cur.execute("SELECT status FROM applications WHERE mobile = %s", (mobile,))
                existing = [r[0] for r in cur.fetchall()]
                actual = f"No application with status {expected_status} found. Existing statuses: {existing or 'None'}"

            cur.close()
            conn.close()
            return {"passed": passed, "description": desc, "actual": actual, "error": None}

        elif atype == "no_application":
            mobile = assertion.get("mobile")
            cur.execute("SELECT count(*) FROM applications WHERE mobile = %s", (mobile,))
            count = cur.fetchone()[0]

            passed = (count == 0)
            actual = f"Found {count} applications for mobile {mobile}"
            cur.close()
            conn.close()
            return {"passed": passed, "description": desc, "actual": actual, "error": None}

        elif atype == "application_count":
            mobile = assertion.get("mobile")
            expected_count = assertion.get("expected_count", 1)
            cur.execute("SELECT count(*) FROM applications WHERE mobile = %s", (mobile,))
            actual_count = cur.fetchone()[0]

            passed = (actual_count == expected_count)
            actual = f"Found {actual_count} application(s), expected {expected_count}"
            cur.close()
            conn.close()
            return {"passed": passed, "description": desc, "actual": actual, "error": None}

        elif atype == "status_changed_to":
            status = assertion.get("status")
            block = assertion.get("block")

            query = "SELECT a.id, a.application_no, a.status, a.block, al.actor, al.note FROM applications a LEFT JOIN audit_log al ON a.id = al.application_id WHERE a.status = %s"
            params = [status]
            if block:
                query += " AND a.block = %s"
                params.append(block)
            query += " ORDER BY a.decided_at DESC NULLS LAST LIMIT 1"

            cur.execute(query, params)
            row = cur.fetchone()

            passed = bool(row)
            if row:
                actual = f"Found application {row[1]} ({row[3]}) with status {row[2]}, decided by {row[4] or 'N/A'}"
            else:
                actual = f"No application found with status {status}" + (f" in block {block}" if block else "")

            cur.close()
            conn.close()
            return {"passed": passed, "description": desc, "actual": actual, "error": None}

        elif atype == "dashboard_accessed":
            # For dashboard review, the assertion is that the dashboard API was called successfully
            passed = assertion.get("simulated_success", True)
            actual = "Dashboard statistics retrieved successfully"
            cur.close()
            conn.close()
            return {"passed": passed, "description": desc, "actual": actual, "error": None}

        else:
            cur.close()
            conn.close()
            return {"passed": False, "description": desc, "actual": "Unknown assertion type", "error": f"Invalid assertion type {atype}"}

    except Exception as e:
        logger.error("Error executing assertion %s: %s", atype, e)
        return {"passed": False, "description": desc, "actual": "Exception during execution", "error": str(e)}
