# Build-your-health — Full Codebase Audit

_Multi-agent audit, 9 subsystems, every correctness/security claim adversarially verified against the actual code. Findings below are the **confirmed** ones; refuted claims are listed at the end so they aren't re-investigated._

Date: 2026-06-19 · Branch: `main` · ~13k LOC backend (Python/FastAPI) + ~6k LOC frontend (vanilla JS) + bot + Docker/Fly.

---

## 1. What the project is

A **Telegram Mini App** AI fitness/health coach ("claudeGYM" / "Health Transform").

| Layer | Tech | Notes |
|---|---|---|
| Entry (dev) | `main.py` | uvicorn `reload=True` + spawns `bot.py` as subprocess |
| Entry (prod) | `Dockerfile` CMD | `alembic upgrade head && python bot.py & gunicorn` (1 uvicorn worker) |
| API | FastAPI | 16 routers in `backend/routers/`, 25 services in `backend/services/` |
| Auth | `backend/auth.py` | Telegram WebApp `initData` HMAC + dev-token + Apple-Watch `sync_token` |
| AI | Anthropic Claude (+ optional Gemini/OpenRouter fallback) | plans, coach replies, food-photo vision, weekly memory compression |
| DB | SQLAlchemy 2.x + Alembic (12 migrations) | SQLite (dev) / Postgres (prod); both `create_all` **and** Alembic are used |
| Frontend | 1 `index.html` (1636 lines) + `app.css` (3447) + 19 JS modules | served statically by FastAPI |
| Bot | `bot.py` (python-telegram-bot) | /start, /compete, /stats, /plan, /nutrition, /feedback, photo prompt, **Telegram Stars** "Pro" payments |
| Deploy | Docker / docker-compose / Fly.io; dev via Cloudflare/ngrok tunnel | |

Feature surface: daily tasks + streaks/XP/badges, AI weekly plans, gym/face/posture protocols, nutrition (USDA + Open Food Facts + barcode + Claude vision), body measurements, sleep/readiness/bio-age/cycle tracking, Apple-Watch sync, friend competitions, coach chat with PubMed citations, Pro paywall.

**Out of scope:** `.claude/worktrees/sharp-brown/` is a *separate* app (HealthOS Swift/iOS) sitting in a git worktree — ignored.

---

## 2. Confirmed findings by severity

### 🔴 CRITICAL — hard blocker

**C1. `BodyMeasurementLog` table is missing from every Alembic migration.**
`backend/models/database.py:580-596` defines the ORM table; `backend/routers/measurements.py:34-79` exposes 4 CRUD endpoints; the frontend ships a Measurements page + `measurements.js`. **No migration creates it.** Dev works (because `init_db()` `create_all`s), but **production runs `alembic upgrade head` only (`Dockerfile:23`)** → the table never exists → every `/api/measurements/*` call 500s in prod. 28 ORM tables, only 27 migrated.
→ Add a migration `add_body_measurement_logs` (table + FK + indexes on `(user_id,key)` and `(user_id,date)`).

---

### 🟠 HIGH — confirmed, fix before shipping

**H1. Age is collected on the frontend but never sent to the backend → every user's calorie targets are computed as age 30.**
`onboarding.js:142` collects age, `onboarding2.js:187-194` omits it from `API.register()`, `schemas.py` `RegistrationRequest` has no age field, so `nutrition_targets.compute_targets()` falls back to `DEFAULT_AGE=30` (`nutrition_targets.py:14,50`). Mifflin-St-Jeor BMR is systematically wrong for everyone not ~30; error compounds with activity + goal modifiers. Silent. **This is the single most impactful correctness bug** — the core nutrition number is wrong for most users.
→ Thread `age`/`date_of_birth` through registration → schema → `compute_targets`.

**H2. Docker healthcheck calls an auth-protected endpoint → container restart loop.**
`docker-compose.yml:13` health-checks `http://localhost:8000/api/users/me`, which requires `Authorization` and returns 401 → container marked unhealthy after ~120s → `restart: unless-stopped` thrashes it. A public `/health` already exists (`app.py:125`).
→ Point the healthcheck at `/health`.

**H3. Dockerfile CMD ordering serves traffic on a possibly-unmigrated schema.**
`Dockerfile:23`: `alembic upgrade head && python bot.py & gunicorn …`. Shell precedence is `(alembic && bot) & gunicorn` → **gunicorn starts immediately, not after migrations.** If migrations hang/lock, workers serve a stale schema; if migrations fail, the bot is skipped but gunicorn still runs.
→ Run migrations as a blocking step before gunicorn (init container or `sh -c 'alembic upgrade head && (python bot.py &) && gunicorn …'`).

**H4. `sync_token` is declared `unique=True` in the ORM but the migration omits the constraint.**
`database.py:41` vs `f2a3b4c5d6e7…py:28` (verified absent in the live SQLite schema). DB allows duplicate Apple-Watch tokens → auth collisions (one token matching multiple users via `auth.py:91`). Also: token is stored **plaintext, never expires, never rotates, no revocation** (`auth.py:83`), and is returned in JSON (`users.py:166`). DB breach = permanent wearable read/write per user.
→ Add the unique constraint in a migration; hash the token at rest; add expiry/rotation.

**H5. Weekly plan generation can leave orphan plans (no transaction boundary).**
`plans.py:118-142` commits the `UserPlan` (line 126) and commits again inside the per-day task loop (line 138) with no try/except. If `create_tasks_from_plan` or a later `add_all` fails, the plan exists with a partial/empty task set → broken streaks/metrics, no rollback.
→ Build all tasks, then single `add_all` + one commit; wrap in try/except with rollback.

**H6. AI calls have no retry on transient failure → users lose their weekly plan on any blip.**
`ai_service.py` `_call_*` (Gemini/OpenRouter/Anthropic) each catch-and-return-None; `call_ai()` only does cross-provider fallback, no within-provider retry on timeout/429/503. `claude_service.generate_plan()` has no exception handling and propagates into `scheduler.weekly_plan_generation` (line 154) which just logs.
→ Add exponential backoff (3-5 attempts) for timeouts/429/503.

**H7. `perfect_week` / perfect-day achievements are mathematically unobtainable.**
`progress.py:154` sets `perfect_days = 1 if today complete else 0` — a per-call local that never accumulates; the achievement check needs `perfect_days >= 7` (`progress.py:37`). Gamification silently broken. (Two parallel achievement systems also exist: `progress._check_achievements` and `badge_service` — neither tracks perfect-day streaks.)
→ Compute the consecutive-perfect-day streak from history; unify the two achievement paths.

**H8. Calorie-burn has two divergent formulas (~13% inconsistency) and misaligned seed data.**
`exercise_service.py:1641` (library path) = `calories_per_min*(weight/75)*minutes`; `:1652` (fallback) = `MET*weight*hours`. Same exercise yields different burns depending on path; the seed `calories_per_min` values don't equal `MET*75/60` despite the header comment. (Verifier corrected the original "60×" claim to ~13% + silent inconsistency.)
→ Pick one formula; regenerate seed `calories_per_min` from MET consistently; add a reference test.

**H9. Bio-age VO2max estimate has no physiological bounds.**
`bio_age_service.py:101-102`: `vo2max = 15.3*(220-age)/resting_hr` with RHR only filtered `>30` and HR bounds `0-300` (`health.py:189`). RHR=31 → VO2max≈94 (human max ≈85) → cardiovascular score saturates at 100 → bio-age underestimated by years → false fitness reassurance/overtraining risk.
→ Clamp VO2max to ~20-85; tighten RHR input bounds (40-100); flag implausible inputs.

**H10. Bio-age activity score double-counts the same wearable data.**
`bio_age_service.py:115-119` sums *both* steps→minutes *and* active_calories→minutes, but both come from the same daily wearable payload (`health.py:304-341`) → ~75% overestimate → sedentary users score 100 → bio-age inflated downward.
→ Use one source, or HR-zone intensity; stop adding steps and active-cal minutes together.

**H11. Cycle phase silently defaults to a 28-day cycle and validates nothing.**
`cycle_service.py:64` `cycle_length = row.cycle_length or 28`; no bounds on input (`health.py:51`, `database.py:557`). Short cycles (21d) make the follicular phase vanish; fertile-window predictions off by days. Medical implication for users relying on it.
→ Validate 21-35 (warn outside); require a logged length before predicting; don't silently persist 28.

**H12. N+1 + write-amplification in competition leaderboard.**
`competitions.py:245-269`: per-member `User` query + `_calc_member_score` (which re-queries User + DailyTask + Nutrition/Weight) → ~300-400 queries for a 100-member board; repeated in `get_highlights`. Worse: lines 257-269 **assign computed scores onto `CompetitionMember` and `db.commit()` on every GET** (the response uses the dict, not the row — the writes are pointless and lock rows).
→ Batch with `selectinload`/`IN`; remove the per-view commit; cache board with short TTL.

**H13. Race conditions on XP/task completion (no row locking).**
`exercise_sessions.py:124-133` (finish_session) and `tasks.py:638-641` (toggle) do read-modify-write on `user.xp` and task state with no `SELECT … FOR UPDATE` / atomic increment → double XP / lost updates on concurrent or double-submitted requests; `finish_session` also doesn't check `finished_at` for idempotency.
→ Atomic `UPDATE … xp = xp + :r`; idempotency guard on session finish.

**H14. Accessibility: missing alt/ARIA + failing contrast (WCAG AA).**
`index.html` photo-upload slots (574-589) and SVG icons have no `aria-label` (only 2 ARIA attrs across 48 SVGs); `exDetailImg` alt is the static string "Exercise". `--text-tertiary #42425A` on `--bg-primary #07070F` is ~2:1 (verifier recomputed — worse than the 4.19:1 first claimed) used on 40+ selectors at 11px.
→ Add alt/aria-label/landmarks; lift `--text-tertiary` to ≥4.5:1.

---

### 🟡 MEDIUM — confirmed

| ID | Finding | Location |
|---|---|---|
| M1 | `GET /api/exercises/admin/all` has **no auth** (other `/admin/*` do) — exercise-library disclosure | `exercises.py:222-252` |
| M2 | Food-photo vision endpoint is **not Pro-gated** and has no token metering (cost exposure) | `nutrition.py:396-453` |
| M3 | `/api/nutrition/search` `q` has `min_length` but **no `max_length`/charset** → external-API quota abuse | `nutrition.py:60` |
| M4 | XSS: competition `first_name`/highlight fields rendered via `innerHTML` unescaped (Telegram does not sanitize display names) | `ui.js:166-174`, `134-147` |
| M5 | XSS: `?invite=` URL param injected unescaped into an input `value="…"` attribute (verifier: payload in original was wrong, but the attribute-injection class is real) | `ui.js:288-294` ← `core.js:147` |
| M6 | In-memory rate limiter is per-process → bypassable / reset on restart (mitigated **only** by `--workers 1`) | `rate_limit.py:6` |
| M7 | Reminder delivery is check-then-act (TOCTOU) → duplicate sends under >1 worker | `scheduler.py:359-363` |
| M8 | Scheduler runs per-worker with no distributed lock → duplicate plans/notifications if ever scaled beyond 1 worker | `app.py:54-69`, `scheduler.py:23` |
| M9 | Prompt-injection: user-controlled exercise names → compressed memory → injected as **system prompt** in morning reminders | `scheduler.py:427-432`, `memory_service.py` |
| M10 | Frontend `loadDayTasks` has no `AbortController` → stale day's tasks can overwrite the newer selection | `tasks.js:34-42` |
| M11 | Sleep bedtime-consistency wraps midnight wrong → ~45-pt discontinuous score drop for normal/night-shift sleepers | `sleep_service.py:48-74` |
| M12 | AI JSON responses parsed without schema validation → missing keys silently degrade UI (no warning log) | `ai_service.py:48-72` |
| M13 | Heatmap "month summaries" iterate 30-day windows, dropping older partial months → silent data loss | `heatmap.py:73,107` |
| M14 | `UserResponse` omits `sex`/`date_of_birth`/`memory_json` → frontend uses extra calls/workarounds (ties to H1) | `schemas.py:16-32` |
| M15 | Dead **`Health Transform Onboarding.html`** — a complete second (React/CDN) onboarding, never served | project root |
| M16 | 129 inline event handlers in `index.html`; 2 spots interpolate API data into `onclick` with incomplete escaping; blocks any future CSP | `index.html` |
| M17 | XP toggle lost-update race (multi-tab/device) | `tasks.py:638-641` |

---

### 🟢 LOW / cleanup (confirmed or low-risk)

- `requirements.txt` uses `>=` only, no lockfile → non-reproducible builds.
- `secret_key="dev-secret-change-me"` is **dead config** (never used; auth keys off `bot_token`) — remove to avoid confusion.
- `dev_auth_enabled` defaults `True` (env=`production` is the real guard; still safer to default `False`).
- CORS `allow_methods/headers="*"` with `allow_credentials=True` (low risk: origins are restricted, auth is header-not-cookie).
- No `.env.example` (note: `.env` itself **is** correctly gitignored — the "secrets committed to git" claim was a false positive).
- `frontend/archive/` (6 files, ~1500 lines) is documented dead weight.
- Inconsistent script paths in `index.html` (mixed `js/…` and `/js/…`).
- Exercise-name lookups case-sensitive (`exercise_service.py:1546`); weight-history uses leading-wildcard `ILIKE` (`exercises.py:181`).
- Model IDs hardcoded in `claude_service.py` (137/142/211/286) — move to settings.
- `Feedback` ORM lacks a `user` relationship; `__pycache__`, root `txt`, and a committed `health_transform.db` are tree noise.

---

## 3. Strengths (don't regress these)

- **Telegram `initData` HMAC is correct**: proper `WebAppData`+token key derivation, sorted `data_check_string`, `hmac.compare_digest`, `auth_date` freshness/replay window.
- Ownership/IDOR checks are consistently present on user-scoped endpoints.
- SSRF-safe image proxy (host allowlist, no redirects) in `exercises.py`.
- Multi-provider AI fallback + sensible hardcoded defaults when all providers fail.
- Health math is mostly evidence-based (Mifflin-St-Jeor, HUNT VO2max, Schoenfeld volume landmarks, RPE-based load progression).
- Clean service/router separation; lifespan-managed scheduler; production SQLite guard; production `WEBAPP_URL` guard.
- Food-seed is idempotent & atomic; readiness scoring is robust (the div-by-zero and duplicate-seeding scares were **refuted**).

---

## 4. Refuted by verification (do NOT spend time on these)

Division-by-zero in readiness (sleep weight is unconditional) · "unbounded memory_json growth" (bounded to ~3 KB by design) · "60× calorie error" (actually ~13%) · duplicate food seeding (atomic + idempotent) · negative-carb VLCD (math error in the finding) · volume-deload mean (example was wrong) · onboarding.js/onboarding2.js "collision" (they're complementary by design) · swipe-handler memory leak (innerHTML GCs listeners) · 1636-line parse perf (data loads on demand) · `referrerpolicy` breaking images (backend proxies them) · DB session-factory thread-safety · API keys leaked in exception logs · `.env` committed with secrets (it's gitignored).

---

## 5. Suggested fix order

1. **C1** (missing migration) + **H2/H3** (Docker correctness) — otherwise prod is broken/looping.
2. **H1** (age→targets) — core data correctness for every user.
3. **H4/H5/H6/H7** (auth-token integrity, plan atomicity, AI retry, achievements).
4. **H8-H11** (health-math correctness — user-facing advice).
5. **H12/H13/M*** (perf, races, XSS, a11y).
6. Low/cleanup as you touch the files.
