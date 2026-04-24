# Commercial Trading — Business Model (PRD)

## Original Problem Statement
Continuation of existing Commercial Trading / Business Model app (FastAPI + React + MongoDB).
GitHub: https://github.com/Chixalatedpeese/Business_Model.git

Phase 5 focused on restoring **accounting integrity, returns correctness, invoice credit-note
linkage, historical settlement, and reporting truth**, plus a production-grade forgot-password
flow and Dark/Light theming.

## User Personas
1. **Business owner / admin** — seeds customers, products, orders, invoices, tracks profit.
2. **Accountant / back-office** — reconciles payments, settles historical invoices, processes returns.
3. **Operator** — records daily payments, generates invoices from orders.

## Core Requirements (static)
- FastAPI backend on :8001, MongoDB local, React frontend on :3000 (via supervisor).
- JWT cookie-based auth. Seeded admin user.
- All business entities (customers, suppliers, products, orders, purchases, invoices, payments, returns, returned_stock) as separate routes.

## What's Been Implemented (cumulative)

### Phase 1-4 (pre-existing in repo)
- Full CRUD for customers, suppliers, products, orders, purchases, invoices, payments.
- Returns + returned stock pool (sellable in future orders without supplier payable).
- Multi-cheque payments, payment allocations, per-supplier/per-order purchase generation.
- Analytics (sales/purchases/profit), reports (customer-outstanding, supplier-payable, payments).
- Basic auth w/ OTP reset (inline — dev only).

### Phase 5 — 2026-04-24 (this session)
1. **Payment outstanding integrity** — `recalc_invoice_status` now considers payments + returns + manual settlement. Edit/delete recompute across old AND new allocations; no double counting or orphan state.
2. **Historical invoice settlement** — new endpoint `POST /api/invoices/{id}/settle` with optional amount (null = full outstanding) and note. Stored as `manual_settled_amount` + embedded `manual_settle_history`. Status auto-recomputes.
3. **Profit correctness with returns** — Dashboard & financial-summary now subtract both **returns revenue** and **returns cost** (using the snapshotted `cost_price` stored on each return item). Profit reflects only items that stayed sold.
4. **Hybrid invoice numbering** — `/api/invoices/from-order/{id}` and `/api/invoices` accept optional `invoice_number`; validates uniqueness, else auto-generates `INV-NNNN`. Exposed in Orders → Generate Invoice dialog (`manual-invoice-number-input` + backdated `manual-invoice-date-input`).
5. **Credit note system** — every Return now also carries `credit_note_number` (`CN-NNNN`). Invoice GET returns `credit_notes` array + `net_payable` + `balance`. UI shows `Subtotal / - Credit Note CN-xxxx / Paid / Manually Settled / Total Due` in the invoice view.
6. **Forgot-password via real email (Resend)** — `/api/auth/forgot-password` now sends HTML OTP email via Resend when `RESEND_API_KEY` is set; falls back to inline OTP (with `email_sent:false`) when empty. LoginPage shows "email sent" banner or inline OTP accordingly.
7. **Returns → Opening Stock form layout** — cleaner grid, proper spacing, responsive dialog, helper hints.
8. **Dark / Light theme toggle** — `ThemeContext` with `localStorage` persistence (`ctb.theme`). Toggle button in top bar (Sun/Moon). Theme-aware CSS vars + dark overrides for hardcoded slate/emerald/amber palettes.

### Test Results (Phase 5)
- Backend: **12 / 12 pytest cases pass** (`/app/backend/tests/test_phase5.py`).
- Frontend: Login, theme toggle + persistence, Orders→Generate Invoice hybrid dialog, Invoices View + Settle, Returns CN column, Opening Stock layout, Forgot-Password fallback — all verified.

## Backlog / Future

### P0 — Before production ship
- **Set `RESEND_API_KEY`** in /app/backend/.env (user to provide) and verify sender domain/email in Resend. Until then, inline-OTP fallback is a minor info leak risk.

### P1
- Gate inline-OTP fallback behind an explicit `DEV_MODE=true` env flag so prod never returns the OTP.
- `/forgot-password` deep-linkable route.
- Audit-log collection for manual settlements (compliance trail beyond embedded history).

### P2
- Batch/$lookup for dashboard profit (current impl does N*M product lookups — slow at scale).
- Composite index on `invoices.customer_id + status`.
- ISO-date validation on reports `date_from`/`date_to`.
- Replace native date inputs on Migration page with shadcn Calendar.

## Architecture Notes
- **Credit Note = Return** (1:1): `returns.credit_note_number` = `CN-{seq:04d}` from the shared `returns` counter; invoice view pulls them via `/api/invoices/{id}`.
- **Invoice status** is derived from: `total_amount` vs (sum of allocated customer payments) + (sum of return items) + `manual_settled_amount`.
- **Manual Settlement** does NOT create a payment row — it's a flag on the invoice (amount + history). Use for legacy money collected outside the system.
- **Theming** applies the `dark` class on `<html>`; Tailwind `@media dark` not used — only CSS vars + explicit `.dark .foo` overrides for hardcoded hex/slate classes still present in the codebase.

## Environment
- Backend `.env`: `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `CORS_ORIGINS`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `RESEND_API_KEY` (empty), `SENDER_EMAIL=admincta22@gmail.com`, `SENDER_NAME`, `APP_NAME`.
- Frontend `.env`: `REACT_APP_BACKEND_URL`.
