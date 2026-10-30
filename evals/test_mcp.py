# -*- coding: utf-8 -*-
"""
End-to-end test suite for SewaSetu Citizen and Officer MCP servers.
Tests Streamable HTTP endpoints (GET/POST /mcp), tools/list, initialize, and error handling.
"""

import sys
import os
import json

# Add mcp-citizen and mcp-officer to path
sys.path.insert(0, os.path.abspath("mcp-citizen"))
import server as citizen_server

sys.path.insert(0, os.path.abspath("mcp-officer"))
import server as officer_server


def test_citizen_mcp():
    print("=== Testing Citizen MCP Server ===")
    client = citizen_server.app.test_client()

    # 1. Health check
    res = client.get("/health")
    assert res.status_code == 200, f"Health check failed: {res.status_code}"
    print("[PASS] Citizen /health -> 200 OK:", res.get_json())

    # 2. SSE endpoint (GET /mcp)
    res = client.get("/mcp")
    assert res.status_code == 200, f"SSE failed: {res.status_code}"
    assert "text/event-stream" in res.content_type
    assert b"event: endpoint" in res.data
    print("[PASS] Citizen GET /mcp (SSE stream) -> 200 OK")

    # 3. JSON-RPC Initialize
    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"}
        }
    }
    res = client.post("/mcp", json=init_payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["result"]["serverInfo"]["name"] == "sewasetu-citizen-mcp"
    print("[PASS] Citizen POST /mcp (initialize) -> serverInfo:", data["result"]["serverInfo"])

    # 4. JSON-RPC tools/list
    list_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    res = client.post("/mcp", json=list_payload)
    assert res.status_code == 200
    data = res.get_json()
    tool_names = [t["name"] for t in data["result"]["tools"]]
    print("[PASS] Citizen tools/list ->", tool_names)
    assert "check_eligibility" in tool_names
    assert "submit_application" in tool_names
    assert "approve_application" not in tool_names  # Security check: no officer tools!
    print("[PASS] Security isolation verified: No officer tools in citizen server.")

    # 5. Tool call without token (must return 401)
    call_payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "check_eligibility", "arguments": {}}
    }
    res = client.post("/mcp", json=call_payload)
    assert res.status_code == 401
    print("[PASS] Citizen unauthenticated tool call correctly rejected -> 401 Unauthorized")


def test_officer_mcp():
    print("\n=== Testing Officer MCP Server ===")
    client = officer_server.app.test_client()

    # 1. Health check
    res = client.get("/health")
    assert res.status_code == 200
    print("[PASS] Officer /health -> 200 OK:", res.get_json())

    # 2. SSE endpoint (GET /mcp)
    res = client.get("/mcp")
    assert res.status_code == 200
    assert "text/event-stream" in res.content_type
    print("[PASS] Officer GET /mcp (SSE stream) -> 200 OK")

    # 3. JSON-RPC tools/list
    list_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    res = client.post("/mcp", json=list_payload)
    assert res.status_code == 200
    data = res.get_json()
    tool_names = [t["name"] for t in data["result"]["tools"]]
    print("[PASS] Officer tools/list ->", tool_names)
    assert "approve_application" in tool_names
    assert "reject_application" in tool_names
    assert "dashboard_stats" in tool_names
    assert "submit_application" not in tool_names  # Security check: no citizen tools!
    print("[PASS] Security isolation verified: No citizen tools in officer server.")

    # 4. Tool call without token (must return 401)
    call_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "dashboard_stats", "arguments": {}}
    }
    res = client.post("/mcp", json=call_payload)
    assert res.status_code == 401
    print("[PASS] Officer unauthenticated tool call correctly rejected -> 401 Unauthorized")


if __name__ == "__main__":
    test_citizen_mcp()
    test_officer_mcp()
    print("\nALL MCP TESTS PASSED SUCCESSFULLY!")
