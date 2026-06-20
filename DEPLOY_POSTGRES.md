# Production Postgres Cutover (Supabase)

Moves prod off the single-writer SQLite file (`/data/health_transform.db`) onto managed,
backed-up Postgres. Closes ARCHITECTURE_REVIEW #2 and #4. Migrations are already proven
Postgres-compatible on every PR (the `migrations-postgres` CI job).

**Why Supabase:** managed Postgres with automatic daily backups + point-in-time recovery,
TLS by default, generous free tier, and S3-compatible storage we can later use for durable
photo uploads (#7) — one vendor, two gaps closed.

## One-time setup (you do this — I can't provision your account)
1. Create a Supabase project → Project Settings → Database → copy the **connection string**
   (use the "Session"/direct 5432 string, not the pooler, for migrations).
2. Generate the two secrets:
   ```
   python -c "import secrets; print(secrets.token_urlsafe(48))"                       # JWT_SECRET
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # ENCRYPTION_KEY
   ```
3. Set these as **real secrets** on the host / deploy platform (not a `.env` shipped over scp);
   put deploy-time copies in GitHub Actions repo secrets if the pipeline needs them:
   - `DATABASE_URL=postgresql+psycopg2://postgres:<pw>@db.<ref>.supabase.co:5432/postgres?sslmode=require`
   - `ENVIRONMENT=production`
   - `JWT_SECRET=<from step 2>`
   - `ENCRYPTION_KEY=<from step 2>`
   - keep existing `TELEGRAM_BOT_TOKEN`, AI keys, `WEBAPP_URL`.

## Cutover
4. (Optional) migrate existing SQLite rows. The current prod data is small; simplest is a
   one-off export/import. If you want this automated, say so and I'll add a `scripts/` dumper
   (SQLite → Postgres) — otherwise we start clean and let users re-onboard.
5. Deploy. The container CMD runs `alembic upgrade head` against Postgres before gunicorn.
   With `ENVIRONMENT=production` the app now **skips `create_all`** (Alembic is the only
   schema source) and **refuses to boot on SQLite** — both guards are live.
6. Verify:
   ```
   curl https://<host>/health                       # {"status":"ok"}
   # register a throwaway account, then:
   curl -X POST https://<host>/api/v1/auth/register -H 'content-type: application/json' \
        -d '{"email":"smoke@example.com","password":"smoke-pass-123"}'
   ```
   Confirm Supabase dashboard shows the new row; confirm a backup snapshot exists.

## Rollback
Point `DATABASE_URL` back at the SQLite file and unset `ENVIRONMENT=production`, redeploy.
(Only valid before real Postgres-only data accumulates.)

## After cutover — removes the last operational debt
- Delete the server-only `docker-compose.override.yml` (`alembic upgrade heads`) and any
  stray local migration; the repo chain is linearized (single head), so plain `upgrade head`
  is correct.
