# Build-your-health — Launch Roadmap

Goal: take the current Telegram Mini App from "works on my tunnel" to a **launch-ready product**, fix every confirmed defect in [AUDIT.md](AUDIT.md), build value on top, and keep the backend ready for a **native app (phase 5)**.

Strategy chosen: **ship the Mini App first, native later** · **do everything** (fix + harden + build).

---

## Systemic gaps that shape every phase
These are root causes, not single bugs — addressing them prevents whole classes of the audit findings:
1. **Schema duality** — both `init_db()` `create_all` (dev) and Alembic (prod) manage the schema → drift (caused the C1 production blocker). Pick Alembic as the single source of truth in prod.
2. **No automated tests** in the main app (the only tests live in the unrelated HealthOS worktree). Every fix below should land with a test.
3. **No observability** — Sentry is wired but optional; no structured logging, no metrics, no CI.
4. **Single-process assumptions** — in-memory rate limiter + per-worker scheduler mean the app is silently pinned to `--workers 1`. A shared store (Redis) unlocks scaling.
5. **No legal/privacy layer** — an AI app giving health/nutrition advice + taking payments needs a medical disclaimer, privacy policy, and data-handling/GDPR story before public launch.

---

## Phase 0 — Make it actually run in production  *(deploy blockers, ~1–2 days)*
- [ ] **C1**: add Alembic migration for `body_measurement_logs` (table + FK + 2 indexes). Verify `alembic upgrade head` on a clean DB creates all 28 tables.
- [ ] **H2**: point `docker-compose.yml` healthcheck at `/health` (unauthenticated).
- [ ] **H3**: fix `Dockerfile` CMD so migrations **block** before gunicorn; bot in background.
- [ ] Add a `scripts/check_drift` step (or `alembic check`) to CI so ORM↔migration drift can't recur.
- [ ] `.env.example` (documented keys) + pin deps via a lockfile (`pip-tools`/`uv`).
- **Exit:** a clean Postgres comes up healthy from `docker compose up`, all routers respond, no restart loop.

## Phase 1 — Correct the core promises (health math & data)  *(the advice must be right)*
- [ ] **H1**: capture `age`/`date_of_birth` in onboarding → schema → registration → `compute_targets` (fixes everyone's calorie targets).
- [ ] **H7**: real perfect-day streak from history; unify the two achievement systems.
- [ ] **H8**: one calorie-burn formula; regenerate seed `calories_per_min` consistently; reference test.
- [ ] **H9**: clamp VO2max (≈20–85) + tighten RHR input bounds.
- [ ] **H10**: stop double-counting steps + active-calories in bio-age activity score.
- [ ] **H11**: validate cycle length; don't silently default to 28.
- [ ] **M11** sleep midnight-wrap, **M13** heatmap month aggregation, **M14** expose `sex`/`dob` in `UserResponse`.
- **Exit:** golden-value tests for BMR/TDEE/macros, calorie burn, bio-age, readiness, cycle phases.

## Phase 2 — Integrity, security, reliability
- [ ] **H4**: `sync_token` unique constraint (migration) + hash-at-rest + expiry/rotation/revoke.
- [ ] **H5**: atomic plan generation (build-all → one commit, rollback on failure).
- [ ] **H6**: AI retry w/ exponential backoff on timeout/429/503; **M12** validate AI JSON via Pydantic.
- [ ] **H12**: batch leaderboard (`selectinload`/`IN`), drop the per-view commit, add short-TTL cache.
- [ ] **H13/M17**: atomic XP increments + idempotent session finish (row locks / `UPDATE … +`).
- [ ] **M1** auth the `/admin/all` endpoint · **M2** Pro-gate + meter vision · **M3** input bounds on search.
- [ ] **M4/M5**: escape all server/user/URL data before `innerHTML`; fix `?invite=` attribute injection.
- [ ] **M6/M7/M8/M9**: introduce **Redis** → shared rate limiter + distributed scheduler lock + reminder de-dup; treat user-derived memory as untrusted (move out of system prompt).
- **Exit:** the app is safe to run with >1 worker; security checklist passes.

## Phase 3 — Launch readiness (turn it into a *product*)
- [ ] **Testing**: pytest suite (services + routers + auth) + a couple of frontend smoke tests; target the critical paths.
- [ ] **Observability**: enable Sentry, structured JSON logging, request IDs, basic metrics/healthz.
- [ ] **CI/CD**: lint + test + migration-check + build on push; one-command deploy (Fly.io) with secrets via platform store.
- [ ] **UX polish**: loading skeletons, empty/error states, **a11y (H14: alt/ARIA/contrast)**, onboarding tightening.
- [ ] **Payments**: harden Telegram Stars flow (idempotent activation, failure/refund handling, trial anti-abuse from M-list).
- [ ] **Reminders/notifications** reliability under the new scheduler; per-user timezone correctness.
- [ ] **Legal/trust**: medical disclaimer ("not medical advice"), privacy policy, data export/delete, GDPR basics.
- [ ] **Cleanup**: delete `Health Transform Onboarding.html`, `frontend/archive/`, committed `health_transform.db`, root `txt`, `__pycache__`; remove dead `secret_key`; de-inline `index.html` handlers (enables CSP).
- [ ] **Store/BotFather**: menu button, app name/short-description/icon, deep links, About/ToS links.
- **Exit:** a stranger can install from the bot, onboard, get correct plans, pay, and we can see errors in Sentry.

## Phase 4 — Build on top (growth / "best product")
Candidate features (prioritize with you): adaptive auto-progression coaching, richer AI weekly review with PubMed-cited insights, exercise GIF/library polish, habit/streak depth, social/competition expansion, push re-engagement, referral loop, deeper wearable sync (Apple Health/Google Fit), nutrition barcode UX, and a paywall/conversion pass.

## Phase 5 — Native app (later, reuses this backend)
- [ ] Stabilize + version the API (`/api/v1`), document it (OpenAPI is already there).
- [ ] **Auth portability**: today auth is Telegram-`initData` only. Native needs a real session-token exchange (issue our own JWT after an initial trusted handshake).
- [ ] Decide native stack (extend the HealthOS Swift base vs. cross-platform). Build iOS first; backend stays shared.

---

## Open decisions (need your call as we hit them)
- **Hosting**: Fly.io (current references) vs other? Managed Postgres + Redis there?
- **Redis**: introduce in Phase 2 (recommended) — unblocks scaling, rate limiting, scheduler.
- **Tests/CI**: pytest + GitHub Actions assumed unless you prefer otherwise.
- **Native stack** (Phase 5): reuse Swift HealthOS vs. React Native/Flutter.
