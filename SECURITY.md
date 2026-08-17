# Security Policy & Operational Hardening Guide

This document outlines the security architecture, credentials management, safety mechanisms, and access control policies for the **AI Digital Marketing Command Center**.

---

## 1. Secrets Storage & Configuration

- **Environment Variables**: All external API keys, service credentials, database passwords, and cryptographic secrets are strictly loaded via `.env` files and system environment variables (`os.getenv`).
- **File Exclusions (`.gitignore`)**:
  - Root `.env`, `blog-agent/.env`, and `corporate-cars-social-agent/.env` are strictly excluded from source control.
  - Service account files (`gsc-service-account.json`, `credentials*.json`, `client_secret*.json`, `*.pem`, `*.key`) are completely ignored.
- **Provider Vault**:
  - AI API keys (Anthropic, Gemini, OpenAI, DeepSeek, Groq) can be configured at runtime and are masked before any client-side transmission (e.g. `sk-ant-••••••••2022`).
  - Raw secret values are **never** returned in API responses, logs, or dashboard templates.

---

## 2. Automated Log & Error Redaction

- **Centralized Redacting Formatter (`core/logging/logger.py`)**:
  - Every log entry written to disk (`logs/agents/*.log`, `logs/command_center.log`) or streamed to `stdout` passes through regex scrubbing filters.
  - Automatically redacts:
    - Bearer and Basic authentication headers: `Bearer [REDACTED]`
    - Anthropic Claude keys (`sk-ant-*` -> `sk-ant-[REDACTED]`)
    - OpenAI keys (`sk-*` -> `sk-[REDACTED]`)
    - Google API keys (`AIza*` -> `AIza[REDACTED]`)
    - Private keys and PEM certificates (`[REDACTED PRIVATE KEY]`)
    - Key-value credentials in JSON or strings (`password`, `token`, `api_key`, `secret`, `wp_app_password` -> `[REDACTED]`)
    - Database connection strings containing user credentials (`postgres://user:***@host`)
- **Exception Sanitization**:
  - Unhandled exceptions and task error tracebacks are automatically scrubbed via `redact_sensitive_text()` before assignment to `task.error_message`.

---

## 3. Role-Based Access Control (RBAC) & Authentication

- **Dual Access Tiers**:
  1. **Public Read-Only Viewer**:
     - Can inspect telemetry, status cards, scheduled queue timelines, and generated reports.
     - Blocked from mutating tasks, toggling agents, adding topics/keywords, or changing configurations (HTTP 403).
     - Badge display: `👁️ Read-Only Mode (Only Admin Can Run & Create Tasks)` (Administrator email is hidden).
  2. **Authenticated Super Admin**:
     - Requires valid HMAC-SHA256 bearer token issued via `POST /api/auth/login`.
     - Full execution privileges across all 19 sub-agents and administrative endpoints.
     - Badge display: `👑 Super Admin (Full Control)`.
- **Protected Endpoints**:
  - All mutating POST endpoints enforce `require_admin` FastAPI dependency.

---

## 4. Paid Ads Safety Guard (`ADS_LIVE_EXECUTION_ENABLED=false`)

- **Hard Protection Constraint**:
  - Google Ads Agent (`agents/google_ads_monitoring_agent.py`) and Meta Ads Agent (`agents/meta_ads_monitoring_agent.py`) enforce `ADS_LIVE_EXECUTION_ENABLED=false` by default.
  - Any live mutation request (e.g. campaign creation, budget adjustment, ad group pausing) is blocked server-side and redirected into simulated telemetry.
  - Zero unintended live ad spend is guaranteed.

---

## 5. High-Risk Action Gatekeeping & Approval Matrix

| Operation Category | Risk Level | Authorization / Gatekeeper | Execution Behavior |
| :--- | :--- | :--- | :--- |
| **Blog Post Publishing** | Standard / Normal | Automated Schedule | Posts to WordPress at configured cron time. |
| **Social Media Posting** | Standard / Normal | Automated Schedule | Posts via API to IG/FB/LinkedIn at scheduled time. |
| **Keyword & Content Briefs** | Low / Read-Only | Public / Admin | Generates SEO recommendations in sandbox. |
| **Review & Lead Follow-ups**| Medium | Human Approval | Drafts response; requires manual approval before sending. |
| **Ads Budget / Live Changes**| Critical | Hard Blocked (`ADS_LIVE_EXECUTION_ENABLED=false`) | Simulation only; live mutations prohibited. |
| **API Key / Config Updates** | High | Super Admin Only (`require_admin`) | Verified server-side and encrypted in vault. |
| **Multi-Website Creation** | High | Super Admin Only (`require_admin`) | Verified profile registration. |

---

## 6. Audit Trail & Traceability

- **`AuditTrail` (`core/orchestrator/audit.py`)**:
  - Records every critical event: `TASK_CREATED`, `TASK_RUNNING`, `TASK_APPROVED`, `TASK_REJECTED`, `TASK_COMPLETED`, `TASK_FAILED`, `TASK_RETRY`.
  - Captures: `timestamp`, `agent_id`, `action`, `details`, `user_id`.
  - Recursive key and text scrubbing ensures secrets are stripped from `details` before persisting.

---

## 7. Credential Rotation & Emergency Procedures

If any API key or credential is suspected of compromise:
1. **Rotate the Key** with the external provider (Anthropic Console, Google Cloud Console, OpenAI Platform, Meta Business Manager, WordPress Admin).
2. **Update Environment**:
   - In Dashboard: Navigate to **Settings -> AI Model Vault** and update the key under Super Admin mode.
   - Or on Host: Update `ANTHROPIC_API_KEY` or target variable in `.env` / Render Environment Variables.
3. **Restart Service**: The system automatically refreshes the in-memory `ModelRouter` upon update.
