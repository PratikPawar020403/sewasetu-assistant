# -*- coding: utf-8 -*-
"""
Citizen MCP Server — Streamable HTTP transport.

Exposes tools that a citizen's AI assistant can use to interact with the
Sewa Setu Old Age Pension Portal:
  - check_eligibility
  - submit_application
  - check_status
  - withdraw_application

The server validates OAuth 2.1 JWT access tokens with scope 'citizen'.
Transport: Streamable HTTP (SSE-based MCP protocol over HTTP).
"""

import os
import json
import uuid
import logging
from datetime import datetime

from flask import Flask, request, jsonify, Response

from auth import validate_token
import tools

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s [citizen-mcp] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

PORTAL_URL = os.environ.get("PORTAL_URL", "http://app:8000")
MCP_SERVER_NAME = "sewasetu-citizen-mcp"
MCP_SERVER_VERSION = "1.0.0"

# MCP Protocol version
MCP_PROTOCOL_VERSION = "2025-03-26"

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "check_eligibility",
        "description": (
            "Check if the authenticated citizen is eligible to apply for the "
            "Old Age Pension scheme. Returns eligibility status, whether the scheme "
            "window is open, whether there is an existing active application, "
            "and the minimum age requirement (60 years)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "submit_application",
        "description": (
            "Submit a new pension application for the authenticated citizen. "
            "Requires personal details, address, and bank information. "
            "The applicant must be 60 years or older, must not have an existing "
            "active application, and the scheme window must be open. "
            "Blocks: Sonari, Rajapara, Dhemaji Pathar, Borgaon, Namti, Khelua."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "applicant_name": {
                    "type": "string",
                    "description": "Full name of the applicant",
                },
                "dob": {
                    "type": "string",
                    "description": "Date of birth in DD/MM/YYYY format",
                },
                "gender": {
                    "type": "string",
                    "enum": ["Male", "Female", "Other"],
                    "description": "Gender of the applicant",
                },
                "marital_status": {
                    "type": "string",
                    "enum": ["Married", "Unmarried", "Widow", "Widower"],
                    "description": "Marital status",
                },
                "husband_name": {
                    "type": "string",
                    "description": "Husband's name (if applicable)",
                },
                "village": {
                    "type": "string",
                    "description": "Village name",
                },
                "block": {
                    "type": "string",
                    "enum": ["Sonari", "Rajapara", "Dhemaji Pathar", "Borgaon", "Namti", "Khelua"],
                    "description": "Block name",
                },
                "bank_account": {
                    "type": "string",
                    "description": "Bank account number (9-18 digits)",
                },
                "ifsc": {
                    "type": "string",
                    "description": "IFSC code (11 characters, e.g. SBIN0003077)",
                },
            },
            "required": [
                "applicant_name", "dob", "gender", "village",
                "block", "bank_account", "ifsc",
            ],
        },
    },
    {
        "name": "check_status",
        "description": (
            "Check the status of all pension applications for the authenticated "
            "citizen. Returns application details including application number, "
            "status (PENDING, APPROVED, DEEMED_APPROVED, REJECTED, WITHDRAWN), "
            "submission date, and decision details."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "withdraw_application",
        "description": (
            "Withdraw a pending pension application. Only PENDING applications "
            "can be withdrawn. After withdrawal, the citizen may submit a new "
            "application. Use check_status first to find the application ID."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "integer",
                    "description": "The numeric ID of the application to withdraw",
                },
            },
            "required": ["application_id"],
        },
    },
]


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------

def _get_bearer_token():
    """Extract Bearer token from the request."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def _require_citizen_token():
    """Validate and return claims from a citizen-scoped token, or (None, error_response)."""
    token = _get_bearer_token()
    if not token:
        return None, token, (jsonify({
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": "Bearer token required"},
            "id": None,
        }), 401)

    claims, err = validate_token(token, PORTAL_URL, required_scope="citizen")
    if err:
        return None, token, (jsonify({
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": "Authentication failed: %s" % err},
            "id": None,
        }), 401)

    return claims, token, None


# ---------------------------------------------------------------------------
# MCP JSON-RPC handler
# ---------------------------------------------------------------------------

def handle_initialize(req_id, params):
    """Handle the initialize request."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": MCP_SERVER_NAME,
                "version": MCP_SERVER_VERSION,
            },
        },
    }


def handle_tools_list(req_id, params):
    """Handle tools/list request."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": TOOLS,
        },
    }


def handle_tools_call(req_id, params, token):
    """Handle tools/call request."""
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    if tool_name == "check_eligibility":
        result = tools.check_eligibility(PORTAL_URL, token)

    elif tool_name == "submit_application":
        result = tools.submit_application(PORTAL_URL, token, arguments)

    elif tool_name == "check_status":
        result = tools.check_status(PORTAL_URL, token)

    elif tool_name == "withdraw_application":
        app_id = arguments.get("application_id")
        if not app_id:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({
                        "error": "missing_parameter",
                        "detail": "application_id is required",
                    })}],
                    "isError": True,
                },
            }
        result = tools.withdraw_application(PORTAL_URL, token, app_id)

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": "Unknown tool: %s" % tool_name},
        }

    is_error = "error" in result
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "content": [{"type": "text", "text": json.dumps(result, default=str)}],
            "isError": is_error,
        },
    }


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

@app.route("/mcp", methods=["POST"])
def mcp_endpoint():
    """Streamable HTTP MCP endpoint.

    Accepts JSON-RPC messages and returns JSON-RPC responses.
    For simplicity, this implementation handles one request at a time
    (no SSE streaming for this initial version).
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": "Parse error"},
            "id": None,
        }), 400

    method = body.get("method", "")
    req_id = body.get("id")
    params = body.get("params", {})

    # Handle notifications (no id)
    if method == "notifications/initialized":
        return "", 204

    if method == "initialize":
        return jsonify(handle_initialize(req_id, params))

    if method == "tools/list":
        return jsonify(handle_tools_list(req_id, params))

    if method == "tools/call":
        # Require authentication for tool calls
        claims, token, err_resp = _require_citizen_token()
        if err_resp:
            return err_resp
        return jsonify(handle_tools_call(req_id, params, token))

    if method == "ping":
        return jsonify({"jsonrpc": "2.0", "id": req_id, "result": {}})

    return jsonify({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": "Method not found: %s" % method},
    }), 404


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "server": MCP_SERVER_NAME, "version": MCP_SERVER_VERSION})


# ---------------------------------------------------------------------------
# SSE endpoint for Streamable HTTP transport
# ---------------------------------------------------------------------------

@app.route("/mcp", methods=["GET"])
def mcp_sse():
    """SSE endpoint for the Streamable HTTP MCP transport.

    Returns a Server-Sent Events stream. The client can use this to
    receive server-initiated messages.
    """
    def generate():
        # Send an initial keepalive
        yield "event: endpoint\ndata: /mcp\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    })


@app.route("/mcp", methods=["OPTIONS"])
def mcp_options():
    """CORS preflight for the MCP endpoint."""
    return "", 204, {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept",
    }


@app.after_request
def cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    logger.info("Starting Citizen MCP server on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False)
