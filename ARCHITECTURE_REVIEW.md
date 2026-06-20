# Architecture Review — Weakest Points for the Multi-Platform / Scale Target

Scope: the gap between *what runs today* (single-box Telegram Mini App on SQLite) and
*where we're going* (web-open accounts + native iOS/Android + wearable aggregation + hybrid
AI, all on one versioned API). This is the input to Phase B. Each item: evidence, why it
hurts at the target, and the phase that closes it.

Ranked by blast radius. The first three are **launch-blocking** for anything beyond Telegram.

---

## 1. Identity is hard-coupled to `telegram_id` — BLOCKER
**Evidence:** `users.telegram_id` is `UNIQUE NOT NULL`; `get_or_create_user` keys on it; every
auth path (`backend/auth.py`), every notification, and payments all assume a Telegram id exists.
**Why it hurts:** "open to anyone via email/Apple/Google" is impossible while a Telegram id is
required to *exist as a user*. This is the single largest refactor and gates Phases C/E/F.
**Fix (Phase B):** make `telegram_id` nullable; add `email` + `password_hash`; introduce an
`auth_identity {account_id, provider, provider_uid}` table; issue JWT access+refresh. Telegram
becomes one linkable credential among many, not the primary key of a person.

## 2. SQLite in production, and the guard meant to stop it is disabled — BLOCKER
**Evidence:** prod DB is `/data/health_transform.db`. `backend/app.py:61` *does* guard
(`environment == "production" and database_url startswith sqlite → RuntimeError`) — but the box
boots without `environment=production`, so the guard never fires. A Postgres container is defined
in `docker-compose.yml` and sits **unused**.
**Why it hurts:** SQLite is single-writer; concurrent web+native+Telegram traffic will serialize
and lock. No managed backups/restore story. The guard giving false comfort is its own risk.
**Fix (Phase B):** cut over to the existing Postgres (managed + backed up), set
`environment=production`, make Alembic the single schema source (see #4), verify a backup restores.

## 3. Secrets live in `.env` on the host
**Evidence:** `backend/config.py` reads tokens/keys from env; deployment ships a `.env` to the box.
**Why it hurts:** App-Store / health-data posture and "fully legal" both assume secrets aren't
sitting in plaintext on a VM. Also blocks per-user encrypted AI keys (needs a real key custodian).
**Fix (Phase B):** move secrets to a real store/KMS; app-level encryption for sensitive health
fields and per-user AI keys; TLS in transit (have) + at-rest encryption.

---

## 4. App-startup `create_all` coexists with Alembic — drift engine
**Evidence:** `backend/app.py:66` calls `init_db` → `Base.metadata.create_all` (`database.py:621`)
on every boot, *in addition to* `alembic upgrade head` in the container CMD.
**Why it hurts:** `create_all` silently materializes whatever the ORM currently declares, so the
live schema can diverge from the migration chain without anyone noticing — exactly the class of
drift that produced the two-head incident and the missing-column 500s. The repo chain is now
linearized (single head, `alembic check` clean in CI), but `create_all` can still mask the next gap.
**Fix (Phase B):** retire `create_all` in production; Alembic is the only path that touches schema.
Keep `create_all` for ephemeral test DBs only.

## 5. Single worker + in-process scheduler — can't scale horizontally
**Evidence:** container runs `gunicorn --workers 1`; `backend/services/scheduler.py:23` is an
in-process `AsyncIOScheduler()`.
**Why it hurts:** one worker caps throughput; but you can't just raise `--workers` because each
worker would spin its own scheduler and **double-fire** weekly-plan generation and reminders
(no external lock/leader election). So the system is pinned at one instance.
**Fix (Phase B+):** move scheduled jobs behind a single leader (external scheduler, DB advisory
lock, or a dedicated worker process) so the API can scale to N workers safely.

## 6. Per-user timezone does not exist — "every day accurate" breaks for global users
**Evidence:** all day math uses `datetime.now(timezone.utc)` (heatmap, streaks, tasks). No
`User.timezone_offset`. This is the open D4 item.
**Why it hurts:** for users far from UTC, "today", streak rollover, and morning reminders fire on
the wrong local day. Fine for a UTC-ish cohort; wrong for a global launch. Calendar arithmetic
itself is now locked by `tests/test_date_accuracy.py` — the *missing input* is the user's zone.
**Fix (Phase B/D):** add `User.timezone_offset`; thread it through day-boundary + reminder logic;
extend the date tests with a per-zone dimension.

## 7. Uploads/processing assume local disk + single box
**Evidence:** `/uploads` is served from local disk (`backend/app.py:225`). Photo *analysis* is
in-memory and not persisted (`users.py:78`) — good — but any on-disk artifact is ephemeral across
redeploys and invisible to a second instance.
**Why it hurts:** the moment there's >1 instance or a fresh container, local-disk state is gone or
inconsistent. Blocks horizontal scale and durable media.
**Fix (Phase B+):** object storage (S3-compatible) for any durable media; keep transient analysis
in-memory.

## 8. Channels & payments are Telegram-shaped (seams exist, not yet used)
**Evidence:** notifications go through Telegram only (`notification_service`); payments are Stars.
**Good news:** `Subscription.provider`/`provider_sub_id` already model multiple providers, and the
AI layer (`ai_service.call_ai`) is already multi-provider with retry/validation.
**Why it hurts:** native + web need email/push channels and Stripe/Apple/Google IAP; coupling
blocks those surfaces.
**Fix (Phase B/D):** channel-agnostic notifications (`telegram|email|push`) with per-user prefs;
add Stripe + IAP alongside Stars on the existing seam.

---

## What is already solid (don't rebuild)
- Multi-provider AI with retry + Pydantic validation (`backend/services/ai_service.py`).
- GDPR export/delete already built (`/me/export`, `DELETE /me`).
- Payments/wearable seams present (`Subscription.provider`, `WearableSync`).
- `sync_token` is hashed + rotatable — a good precedent for token auth.
- Migration chain linearized, `alembic check` + smoke + calendar tests gating every PR in CI.
- A near-production native engine exists (`HealthOS`: HealthKit + WHOOP + HRV/recovery/sleep/strain).

## Outstanding prod hygiene (operational, do at next deploy)
- Remove the server-only `docker-compose.override.yml` (`upgrade heads`) and the stray
  `a3b4c5d6e7f8` migration file; `alembic stamp f8a9b0c1d2e3` so deploys use plain `upgrade head`.
  The repo is already linearized; this just reconciles the live box to it.

## Suggested Phase B order (highest leverage first)
1. Postgres cutover + retire prod `create_all` + set `environment=production` (#2, #4).
2. Identity refactor: nullable `telegram_id`, email/password, `auth_identity`, JWT (#1).
3. Secrets/KMS + at-rest + per-user-key encryption (#3).
4. Channel-agnostic notifications + `User.timezone_offset` (#6, #8).
5. Scale-out: scheduler leader-lock so API can run N workers (#5), object storage (#7).
