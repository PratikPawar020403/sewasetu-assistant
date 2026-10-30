# -*- coding: utf-8 -*-
"""
Officer MCP Server — Streamable HTTP transport.

Exposes tools that a block officer's AI assistant can use:
  - dashboard_stats
  - list_applications
  - view_application
  - approve_application
  - reject_application

The server validates OAuth 2.1 JWT access tokens with scope 'officer'.
Transport: Streamable HTTP (SSE-based MCP protocol over HTTP).
"""

import os
import json
import logging

from flask import Flask, request, jsonify, Response

from auth import validate_token
import tools

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s [officer-mcp] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

PORTAL_URL = os.environ.get("PORTAL_URL", "http://app:8000")
MCP_SERVER_NAME = "sewasetu-officer-mcp"
MCP_SERVER_VERSION = "1.0.0"

MCP_PROTOCOL_VERSION = "2025-03-26"

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "dashboard_stats",
        "description": (
            "Get dashboard statistics for the pension portal. Returns counts "
            "by status (PENDING, APPROVED, DEEMED_APPROVED, REJECTED, WITHDRAWN), "
            "overdue pending applications (past SLA), and pending counts by block."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_applications",
        "description": (
            "List and filter pension applications. Can filter by status, block, "
            "mobile number, and date range. Returns paginated results. "
            "Blocks: Sonari, Rajapara, Dhemaji Pathar, Borgaon, Namti, Khelua. "
            "Statuses: PENDING, APPROVED, DEEMED_APPROVED, REJECTED, WITHDRAWN."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["PENDING", "APPROVED", "DEEMED_APPROVED", "REJECTED", "WITHDRAWN"],
                    "description": "Filter by application status (default: PENDING)",
                },
                "block": {
                    "type": "string",
                    "enum": ["Sonari", "Rajapara", "Dhemaji Pathar", "Borgaon", "Namti", "Khelua"],
                    "description": "Filter by block",
                },
                "mobile": {
                    "type": "string",
                    "description": "Search by mobile number",
                },
                "date_from": {
                    "type": "string",
                    "description": "Filter applications submitted from this date (YYYY-MM-DD)",
                },
                "date_to": {
                    "type": "string",
                    "description": "Filter applications submitted until this date (YYYY-MM-DD)",
                },
                "page": {
                    "type": "integer",
                    "description": "Page number (default: 1)",
                },
                "per_page": {
                    "type": "integer",
                    "description": "Items per page (default: 50, max: 100)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "view_application",
        "description": (
            "View the full detail of a specific pension application, including "
            "personal details, address, bank information, current status, and "
            "the complete audit trail (who did what and when)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "integer",
                    "description": "The numeric ID of the application to view",
                },
            },
            "required": ["application_id"],
        },
    },
    {
        "name": "approve_application",
        "description": (
            "Approve a pending pension application. Only PENDING applications "
            "can be approved. Include an optional note for the audit trail."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "integer",
                    "description": "The numeric ID of the application to approve",
                },
                "note": {
                    "type": "string",
                    "description": "Optional audit note (e.g., 'Verified documents and age proof')",
                },
            },
            "required": ["application_id"],
        },
    },
    {
        "name": "reject_application",
        "description": (
            "Reject a pending pension application with a mandatory reason. "
            "Only PENDING applications can be rejected. The reason is recorded "
            "in the audit trail."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "application_id": {
                    "type": "integer",
                    "description": "The numeric ID of the application to reject",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for rejection (required)",
                },
                "note": {
                    "type": "string",
                    "description": "Optional additional audit note",
                },
            },
            "required": ["application_id", "reason"],
        },
    },
]


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------

def _get_bearer_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def _require_officer_token():
    token = _get_bearer_token()
    if not token:
        return None, token, (jsonify({
            "jsonrpc": "2.0",
            "error": {"code": -32000, "message": "Bearer token required"},
            "id": None,
        }), 401)

    claims, err = validate_token(token, PORTAL_URL, required_scope="officer")
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
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": TOOLS,
        },
    }


def handle_tools_call(req_id, params, token):
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    if tool_name == "dashboard_stats":
        result = tools.dashboard_stats(PORTAL_URL, token)

    elif tool_name == "list_applications":
        result = tools.list_applications(PORTAL_URL, token, filters=arguments)

    elif tool_name == "view_application":
        app_id = arguments.get("application_id")
        if not app_id:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({
                        "error": "missing_parameter", "detail": "application_id is required"
                    })}],
                    "isError": True,
                },
            }
        result = tools.view_application(PORTAL_URL, token, app_id)

    elif tool_name == "approve_application":
        app_id = arguments.get("application_id")
        note = arguments.get("note", "")
        if not app_id:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({
                        "error": "missing_parameter", "detail": "application_id is required"
                    })}],
                    "isError": True,
                },
            }
        result = tools.approve_application(PORTAL_URL, token, app_id, note)

    elif tool_name == "reject_application":
        app_id = arguments.get("application_id")
        reason = arguments.get("reason", "")
        note = arguments.get("note", "")
        if not app_id:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({
                        "error": "missing_parameter", "detail": "application_id is required"
                    })}],
                    "isError": True,
                },
            }
        if not reason:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({
                        "error": "missing_parameter", "detail": "reason is required for rejection"
                    })}],
                    "isError": True,
                },
            }
        result = tools.reject_application(PORTAL_URL, token, app_id, reason, note)

    else:
        return {
            "jsonrpc": "2.0", "id": req_id,
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

    if method == "notifications/initialized":
        return "", 204

    if method == "initialize":
        return jsonify(handle_initialize(req_id, params))

    if method == "tools/list":
        return jsonify(handle_tools_list(req_id, params))

    if method == "tools/call":
        claims, token, err_resp = _require_officer_token()
        if err_resp:
            return err_resp
        return jsonify(handle_tools_call(req_id, params, token))

    if method == "ping":
        return jsonify({"jsonrpc": "2.0", "id": req_id, "result": {}})

    return jsonify({
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": "Method not found: %s" % method},
    }), 404


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "server": MCP_SERVER_NAME, "version": MCP_SERVER_VERSION})


@app.route("/mcp", methods=["GET"])
def mcp_sse():
    def generate():
        yield "event: endpoint\ndata: /mcp\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    })


@app.route("/mcp", methods=["OPTIONS"])
def mcp_options():
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
    port = int(os.environ.get("PORT", 8002))
    logger.info("Starting Officer MCP server on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False)
