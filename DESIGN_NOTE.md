# Sewa Setu AI Assistant &mdash; Design Note

**Project:** Sewa Setu Old Age Pension AI Layer  
**Department:** Department of Social Welfare, Government of Purvanchal  
**Architecture:** Dual Role-Isolated MCP Servers over Streamable HTTP with OAuth 2.1  

---

## 1. Executive Summary
The Sewa Setu portal manages Old Age Pension delivery across 6 administrative blocks, serving elderly citizens through shared devices and block development officers (BDOs). To introduce agentic AI capabilities safely into this public digital infrastructure, we built two separate Model Context Protocol (MCP) servers over streamable HTTP, backed by the portal's native OAuth 2.1 authorization server, and an evaluation suite with 9 diverse personas and ground-truth database assertions.

---

## 2. The Three Decisions That Mattered Most

### Decision 1: Physical Endpoint & Capability Isolation (Two Distinct MCP Servers)
* **The Choice:** We deployed two completely separate HTTP services—`mcp-citizen` (Port 8001, scope `citizen`) and `mcp-officer` (Port 8002, scope `officer`)—rather than a single unified server with dynamic tool filtering.
* **Why It Mattered:** In public systems, prompt injection and capability hallucination are primary security risks. If an officer tool (`approve_application`) exists in the tool schema of an assistant serving a citizen, prompt injection or model confusion could trigger unauthorized state mutations. By hosting separate streamable HTTP endpoints, an applicant's assistant **cannot even discover** administrative tools during `tools/list`. The separation is enforced physically at the transport and discovery layer.

### Decision 2: The Portal as the Inviolable System of Record (Zero Shadow State)
* **The Choice:** Neither MCP server maintains an independent database or shadow state. Every tool invocation maps directly to authenticated REST endpoints on the portal, which in turn enforce the state machine, deduplication rules (active status locks), and statutory audit logging.
* **Why It Mattered:** Welfare delivery relies on statutory compliance (such as the 15-day deemed approval rule under the Purvanchal Right to Public Services Act). Any out-of-band updates or detached memory would corrupt audit trails. By keeping the portal as the sole authority, all AI actions leave verifiable audit rows with actor attribution (`citizen:<mobile>` or `officer:<username>`) and participate seamlessly in the nightly deemed approval cron job.

### Decision 3: Persona-Centric Evals with Post-Conversation Database Assertions
* **The Choice:** Rather than relying on LLM-as-a-judge for surface dialogue fluency, our evaluation suite defines 9 specific human personas (varying ages, dialects, villages, and intent) and validates **database state assertions** after the conversation ends.
* **Why It Mattered:** An assistant can sound extremely persuasive while failing to persist data or violating statutory rules. Our assertions directly verify PostgreSQL state: checking that an underage 55-year-old left 0 applications, that an approved applicant was blocked from duplicate filing, and that an officer's approval recorded the mandatory audit explanation.

---

## 3. The One Decision We Would Make Differently with More Time

### Direct S3/Blob Presigned Document Ingestion vs. Container Path Uploads
* **What We Did:** For citizen age-proof verification, the portal requires a physical document upload (`doc_path`). Within the MCP tools, we implemented standard file path passing and synthetic placeholder creation for automated workflows.
* **What We Would Do Differently:** In rural Assam/Purvanchal, elderly applicants often interact via community kiosks or voice/chat agents on low-bandwidth networks. With more time, we would implement **presigned direct upload URLs** coupled with an asynchronous OCR tool in the citizen MCP. This would allow an assistant to take a photo of an elector photo identity card (EPIC) or birth certificate, upload it directly to cloud object storage, and automatically extract and cross-verify the DOB before submitting the application.

---

## 4. Verification & Submission Checklist
- [x] Portal running with ~100k seed records and SMS gateway integration
- [x] Citizen MCP Server running on `http://<host>:8001/mcp` (Streamable HTTP / SSE)
- [x] Officer MCP Server running on `http://<host>:8002/mcp` (Streamable HTTP / SSE)
- [x] OAuth 2.1 token validation with JWKS and role-based scope enforcement
- [x] Evaluation dashboard live at `/eval-dashboard` with 100% assertion pass rate
- [x] 1-page design note (`DESIGN_NOTE.md`)
