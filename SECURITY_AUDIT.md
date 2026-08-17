# Security Audit & Hardening Plan

## Executive Summary
This document provides a comprehensive security audit of the AI Digital Marketing Operating System & Command Center. The system orchestrates 19 specialized marketing agents (including the production Corporate Cars Blog Agent, Corporate Cars Social Media Posting Agent, and 17 AI/SEO/Ads sub-agents), FastAPI dashboard, SQLite/CSV databases, and third-party APIs (Anthropic, Gemini, OpenAI, DeepSeek, Groq, WordPress REST API, Meta Graph API, LinkedIn API).

The objective is **Security Hardening Only** without modifying any existing agent logic, prompts, content generation, publishing behavior, or scheduling.

---

## 1. Project Inventory & Architecture Analysis

### 1.1 Existing Agents
1. **Corporate Cars Blog Agent (`blog-agent/`)**: Autonomous SEO blog generator and WordPress publisher for chauffeur websites (`ccm`, `opal`).
2. **Corporate Cars Social Media Posting Agent (`corporate-cars-social-agent/`)**: Autonomous social content generator and multi-platform scheduler/publisher for Instagram, Facebook, and LinkedIn.
3. **SEO Keyword Research Agent (`seo-keyword-agent`)**: Keyword discovery, clustering, search volume estimation, intent classification.
4. **Competitor Analysis Agent (`competitor-analysis-agent`)**: Competitive intelligence, content gap analysis, SERP benchmarking.
5. **SEO Content Brief Agent (`seo-content-brief-agent`)**: Detailed editorial briefs, heading hierarchy, target keywords.
6. **Internal Linking Agent (`internal-linking-agent`)**: Internal linking discovery and anchor text optimization.
7. **SEO Technical Audit Agent (`seo-audit-agent`)**: Technical SEO auditing, schema.org validation, meta tags inspection.
8. **Google Search Console Agent (`gsc-agent`)**: Organic search metrics, query performance, quick-win identification.
9. **GA4 Reporting Agent (`ga4-reporting-agent`)**: Traffic, conversions, user acquisition channels, engagement metrics.
10. **Google Ads Monitoring Agent (`google-ads-monitoring-agent`)**: Read-only ad telemetry, search terms, CTR/CPA tracking. *(Hard safety guard active: Zero live mutation).*
11. **Google Ads Optimization Agent (`google-ads-optimization-agent`)**: Bid optimization recommendations and negative keyword proposals. *(Requires approval).*
12. **Meta Ads Monitoring Agent (`meta-ads-monitoring-agent`)**: Read-only Meta ad telemetry and placement breakdown. *(Hard safety guard active: Zero live mutation).*
13. **Social Media Analytics Agent (`social-analytics-agent`)**: Multi-platform reach, impressions, follower growth, engagement.
14. **Review & Reputation Agent (`reputation-agent`)**: Google/Trustpilot review monitoring and response drafting. *(Draft-first approval).*
15. **Lead Management & CRM Agent (`lead-management-agent`)**: Inbound inquiry scoring, high-value chauffeur lead routing, email drafting. *(Draft-first approval).*
16. **Monthly Executive Report Agent (`monthly-report-agent`)**: Cross-channel performance reporting and C-level executive summaries.
17. **External Link Building Agent (`external-link-building-agent`)**: Niche citation discovery, automated email outreach drafting, tier-1 directories.
18. **Competitor Ad Spy Agent (`competitor-ad-spy-agent`)**: Competitor ad copy extraction, value propositions, hook analysis.
19. **Page Optimizer Agent (`page-optimizer-agent`)**: Live URL auditing against Google E-E-A-T and Helpful Content updates.

### 1.2 Existing APIs & Endpoints
- **Public Read-Only Endpoints**: `/health`, `/api/system-health`, `/api/overview`, `/api/agents`, `/api/tasks`, `/api/websites`, `/api/schedules`, `/api/settings`, `/api/approvals`, `/api/audit-logs`, `/api/agents/{agent_id}/report`.
- **Protected Admin Endpoints (RBAC Enforced)**: `/api/auth/login`, `/api/auth/session`, `/api/auth/logout`, `/api/tasks/create`, `/api/tasks/execute/{task_id}`, `/api/agents/toggle`, `/api/agents/blog-agent/topics/add`, `/api/agents/social-agent/campaign/add`, `/api/websites`, `/api/approvals/approve`, `/api/approvals/reject`, `/api/ai/providers/save-key`, `/api/ai/providers/set-primary`, `/api/agents/external-link/custom-outreach`, `/api/agents/external-link/daily-batch`, `/api/agents/ad-spy/analyze`, `/api/agents/page-optimizer/audit`.

---

## 2. Identified Security Risks & Vulnerabilities

| Risk ID | Category | Severity | Description & Potential Impact |
| :--- | :--- | :--- | :--- |
| **SEC-01** | **Logging Exposure** | High | Log formatters in `core/logging/logger.py` do not scrub sensitive patterns (Bearer tokens, API keys, basic auth, passwords) before writing to log files and stdout. |
| **SEC-02** | **Audit Trail Scrubbing** | Medium | The `AuditTrail.record()` method in `core/orchestrator/audit.py` accepts arbitrary `details` dictionaries that could inadvertently record credentials, authorization headers, or private keys. |
| **SEC-03** | **Error Message Leaks** | Medium | Unhandled exceptions or external API error responses could bubble up containing API keys or full authorization headers in `error_message` fields of `AgentTask`. |
| **SEC-04** | **Ads Safety Assurance** | High | Verification that `ADS_LIVE_EXECUTION_ENABLED=false` is enforced as an unbypassable constraint across both Google Ads and Meta Ads agent modules. |
| **SEC-05** | **Error Isolation** | Medium | If an individual agent encounters a network timeout or provider outage, ensuring failure is strictly isolated and does not disrupt background schedulers or unrelated agents. |
| **SEC-06** | **Credential Storage** | Low | Ensuring all `.env` files across root, `blog-agent/`, and `corporate-cars-social-agent/` remain ignored by Git and never committed. |

---

## 3. Scope of Modifications

### 3.1 Files That Need Changes (Security Layer Only)
1. **`core/logging/logger.py`**:
   - Add a `SensitiveDataFilter` / `RedactingFormatter` to automatically redact API keys (`sk-ant-*`, `sk-*`, `AIza*`), Bearer tokens, passwords, authorization headers, and private keys across all loggers (`agent.*` and `command_center`).
2. **`core/orchestrator/audit.py`**:
   - Add automated recursive dictionary sanitizer to `record()` so that all audit events have sensitive keys (`api_key`, `token`, `password`, `secret`, `authorization`, `x-admin-token`, etc.) automatically redacted.
3. **`core/models/task.py` / `core/orchestrator/master.py`**:
   - Ensure exception strings and task input/output payloads sanitize any sensitive credential patterns before setting `error_message` or writing to history.
4. **`SECURITY.md`**:
   - Create comprehensive documentation covering secrets storage, rotation, approval mechanisms, ads safety, and logging redaction.
5. **`tests/test_security_hardening.py`**:
   - Add automated test suite verifying secret redaction, audit trail sanitization, ads live execution guard, error isolation, and frontend protection.

### 3.2 Files That Should NOT Be Changed
- **`blog-agent/blog_agent.py`**: Must preserve 100% existing CLI commands, prompts, content generation, WordPress REST API publishing, and Yoast SEO metadata.
- **`blog-agent/config.yaml`**, **`blog-agent/topics.csv`**, **`blog-agent/content_rules.md`**: Preserve existing queue and rules.
- **`corporate-cars-social-agent/cli.py`**, **`corporate-cars-social-agent/content_generator.py`**, **`corporate-cars-social-agent/publishing.py`**, **`corporate-cars-social-agent/scheduler.py`**: Must preserve 100% existing CLI, APScheduler, platform publishers, and SQLite schema.
- **`core/ai_layer/router.py`**: Preserve existing model routing, fallback mechanisms, and token cost tracking.
- **`dashboard/static/app.js`**, **`dashboard/static/index.html`**, **`dashboard/static/styles.css`**: Preserve existing dashboard layout, components, and user experience.

---

## 4. Proposed Security Changes

1. **Reusable Secret Redaction Filter (`core/logging/logger.py`)**:
   - Intercepts all logging records.
   - Regex patterns for:
     - `Bearer [a-zA-Z0-9_\-\.]{10,}` -> `Bearer [REDACTED]`
     - `sk-ant-[a-zA-Z0-9_\-]{10,}` -> `sk-ant-[REDACTED]`
     - `sk-[a-zA-Z0-9_\-]{20,}` -> `sk-[REDACTED]`
     - `AIza[0-9A-Za-z\-_]{20,}` -> `AIza[REDACTED]`
     - `-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----` -> `[REDACTED PRIVATE KEY]`
     - `(password|token|secret|api_key|access_token|auth_token|wp_app_password)\s*[:=]\s*['"]?([^'",\s\\]+)` -> `\1: [REDACTED]`
     - `Authorization:\s*[^\r\n]+` -> `Authorization: [REDACTED]`
     - `x-admin-token:\s*[^\r\n]+` -> `x-admin-token: [REDACTED]`
2. **Audit Trail Sanitizer (`core/orchestrator/audit.py`)**:
   - Recursive dictionary scrubber masking sensitive key names and token values before storing in `AuditEvent`.
3. **Task Error Message Sanitizer (`core/orchestrator/master.py`)**:
   - Redacts credentials from exception tracebacks before recording to `task.error_message`.
4. **Ads Safety Constraint Verification**:
   - Confirms `ADS_LIVE_EXECUTION_ENABLED=false` hard constraint in `google_ads_monitoring_agent.py` and `meta_ads_monitoring_agent.py`.
5. **Comprehensive Security Test Suite**:
   - Verification across 10+ security vectors.
