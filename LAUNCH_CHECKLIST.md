# What I Need From You to Finish & Launch

Everything is grouped by milestone. Each item says **what to get**, **where it goes**, **cost**,
and **what I do with it**. Start at Milestone 1 — it's the closest (all code is built and tested).

Legend: 🔴 required to ship that milestone · 🟡 strongly recommended · ⚪ optional/later.

---

## Milestone 1 — Web app live in production (closest; days, not weeks)

Everything for this is already built and tested. It needs accounts/secrets only.

| # | What to get | Where it goes | Cost | What I do |
|---|---|---|---|---|
| 🔴 1 | **Supabase project** → copy the direct (5432) DB connection string | `DATABASE_URL` secret | Free tier | Run the migration + cut prod over from SQLite |
| 🔴 2 | Generate **`JWT_SECRET`** and **`ENCRYPTION_KEY`** (commands in `DEPLOY_POSTGRES.md`) | host secrets | — | Account logins + PII encryption use them |
| 🔴 3 | Confirm **where the app runs** (your existing Oracle Cloud VM, or a managed host like Fly/Render) | — | $0–10/mo | Deploy there; set `ENVIRONMENT=production` |
| 🔴 4 | A **domain + HTTPS** (Telegram and web both require https). Do you have one, or want me to use a tunnel for now? | `WEBAPP_URL` | ~$12/yr | Point the app + Telegram Mini App at it |
| 🔴 5 | At least **one AI key**: Anthropic **or** Gemini **or** OpenRouter | `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `OPENROUTER_API_KEY` | usage-based | Powers coaching, plans, photo/meal analysis |
| 🔴 6 | **Telegram bot token** (you have it) + set the Mini App URL in @BotFather | `TELEGRAM_BOT_TOKEN` | Free | Telegram entry + initData auth |
| 🟡 7 | **SMTP / email provider** (Resend, Postmark, SendGrid…) + a sending domain | SMTP secrets | Free tier | Email verification + password reset (not built yet — needs this to build) |
| 🟡 8 | **Sentry DSN** | `SENTRY_DSN` | Free tier | Production error tracking (already wired) |
| ⚪ 9 | **USDA API key** | `USDA_API_KEY` | Free | Better nutrition search (falls back to a demo key) |

**After 1–6 I can put the web app live and you can test it at your URL.** 7 unlocks me building
"forgot password" / email verification.

---

## Milestone 2 — iOS native app (App Store)

| # | What to get | Cost | What I do |
|---|---|---|---|
| 🔴 1 | **Apple Developer Program** membership | $99/yr | Required to build/sign/submit |
| 🔴 2 | A **Mac with Xcode** (yours, or a cloud Mac) | — | Build the app (on the existing HealthOS engine) |
| 🔴 3 | **App Store Connect** app record (name, bundle id) | — | App metadata + TestFlight + submission |
| 🔴 4 | **Sign in with Apple**: a Services ID + key (.p8) | — | Apple login (required if any social login exists) |
| 🔴 5 | **HealthKit** entitlement enabled on the App ID | — | Read Apple Health / Apple Watch data |
| 🔴 6 | **APNs auth key** (.p8) | — | Push notifications to iPhone |
| 🔴 7 | A **hosted privacy policy + support URL** | ~$0 | Store requirement (I'll draft the policy) |
| 🟡 8 | A **test iPhone** (or simulator) + your Apple ID for TestFlight | — | You test the build before submission |

---

## Milestone 3 — Android native app (Play Store)

| # | What to get | Cost | What I do |
|---|---|---|---|
| 🔴 1 | **Google Play Developer** account | $25 once | Required to publish |
| 🔴 2 | **Google Cloud project** + OAuth client IDs (web + android) | Free | Google sign-in |
| 🔴 3 | **Firebase / FCM** project | Free | Android push |
| 🔴 4 | **Health Connect** access (Samsung/Google/Fitbit aggregation) | Free | Read wearable data |
| 🟡 5 | A **test Android device** | — | You test the build |

---

## Milestone 4 — Full features (wearables, web payments, social login on web)

| # | What to get | Cost | What I do |
|---|---|---|---|
| ⚪ 1 | **WHOOP developer app** (client id + secret) | Free | WHOOP cloud sync (recovery/HRV/sleep/strain) |
| ⚪ 2 | **Stripe account** (test + live keys) | usage % | Web subscriptions (alongside Telegram Stars, already supported) |
| ⚪ 3 | **Google + Apple OAuth** (from M2/M3) reused on web | — | Web "Sign in with Apple/Google" |
| ⚪ 4 | The **competitor / reference docs** you mentioned | — | I extract the best ideas into concrete issues |

---

## Decisions only you can make

- **Final app/brand name** for the stores (currently shows "claudeGYM" / "Health Transform").
- **Hosting**: stay on Oracle Cloud, or move to a managed host?
- **Pricing / subscription tiers** (free vs Pro features).
- **Primary AI provider** (cost vs quality) — or keep the automatic fallback chain.
- **Business/legal entity** for store + payments accounts (and which country).

---

## How we test each layer

| Layer | How it's tested | Needs from you |
|---|---|---|
| Backend logic | 108 automated unit tests on every PR | nothing |
| DB migrations | run on SQLite **and** Postgres in CI | nothing |
| Web "every button" | Playwright browser E2E in CI (already catching real bugs) | nothing |
| **Live production** | I run smoke + you click through the live URL | the deployed URL (after M1) |
| **AI features** | real coaching/plan/photo calls | a valid AI key (M1 #5) |
| **Payments** | test-mode keys first, then a real small purchase | Stripe/Stars/IAP test keys |
| **Native (iOS/Android)** | TestFlight / internal track on a real device | dev accounts + a device (M2/M3) |
| **Wearables** | connect a real WHOOP/Apple Watch and verify sync | the device + its account |

---

## The single fastest path to "live and testable"

Do **Milestone 1, items 1–6** (Supabase + 2 generated secrets + host + domain + 1 AI key +
the Telegram token you already have). That puts the full app — Telegram **and** open-web with
email/password accounts — live on real infrastructure, and you can test every feature end to end.
Everything else layers on top.
