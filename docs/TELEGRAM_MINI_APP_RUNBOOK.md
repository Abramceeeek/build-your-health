# Run everything for Telegram Mini App (full guide)

Use this after you **close all terminals** and want a **clean start** with a **new tunnel**.

### If `*.trycloudflare.com` **always** returns 404

Stop fighting Cloudflare quick tunnels on your network. Use **ngrok** instead — see **`docs/NGROK_TUNNEL.md`** and run **`python scripts/launch_ngrok.py`** (with `python main.py` already running). Many developers switch to ngrok when QUIC/edge routing fails.

---

## What has to run (three pieces)

| # | What | Why |
|---|------|-----|
| **1** | **FastAPI app** (`backend.app`) | Serves the web UI (`/`), CSS/JS, and `/api/*`. Telegram opens this over HTTPS. |
| **2** | **Cloudflare quick tunnel** (`cloudflared`) | Gives a public **`https://….trycloudflare.com`** URL and forwards it to your PC (`127.0.0.1:PORT`). |
| **3** | **Telegram bot** (`bot.py`) | Talks to Telegram; menu button / Web App button uses **`WEBAPP_URL`** from `.env`. |

Telegram’s client only loads **HTTPS** pages. The tunnel provides that. **If 1 or 2 stops, the Mini App link breaks (404 / connection errors).**

---

## One-time setup (BotFather)

Do this once (or when you change the public URL permanently):

1. Open [@BotFather](https://t.me/BotFather).
2. Select your bot → **Bot Settings** → **Menu Button** (or **Configure Mini App** / **Web App URL**, depending on BotFather’s wording).
3. Set the URL to the **same HTTPS origin** you use in **`WEBAPP_URL`** (e.g. `https://something-random.trycloudflare.com/`).

Your **`bot.py`** also calls `setChatMenuButton` on startup using **`WEBAPP_URL`**, so keeping **`.env` correct** is usually enough after the first setup.

---

## Fresh start: recommended flow (2 terminals + edit `.env`)

### Terminal A — API + tunnel (one command)

From the project folder:

```powershell
cd "c:\Users\HP\Documents\Health app"
python scripts\launch_tunnel.py
```

- Starts **uvicorn** (no hot-reload) + **cloudflared**.
- Prints a line like: **`https://WORD-WORD-WORD.trycloudflare.com/`**
- Also writes the same URL to **`.tunnel_url`**.
- **Leave this window open.** Closing it **stops** the tunnel and the API started by this script.

### Update `.env`

If you use **`python scripts\launch_tunnel.py`**, it **automatically sets `WEBAPP_URL`** in `.env` to match the tunnel (unless you set `HEALTH_TRANSFORM_SKIP_ENV_SYNC=1`). You only need to **restart the bot** (next step).

If you use **`start-tunnel.ps1` manually**, copy the printed URL into **`WEBAPP_URL`** yourself:

```env
WEBAPP_URL=https://WORD-WORD-WORD.trycloudflare.com/
```

### Terminal B — bot

Open a **second** terminal:

```powershell
cd "c:\Users\HP\Documents\Health app"
python bot.py
```

- Needs **`TELEGRAM_BOT_TOKEN`** (and other vars) in `.env`.
- **Restart** this after **`launch_tunnel.py`** updates **`WEBAPP_URL`** (or restart once after tunnel is up).

### Windows shortcut (three windows)

From Explorer, double-click **`scripts\start-stack.cmd`**. It opens:

1. **`python main.py`** (API)
2. **`python scripts\launch_tunnel.py --tunnel-only`** (public HTTPS — does **not** start a second server on port 8000)
3. **`python bot.py`**

**Leave all three open.**  

**Why `--tunnel-only`?** If you run `launch_tunnel.py` **while `main.py` is already using port 8000**, the script used to start a *second* uvicorn, which **fails to bind**, exits immediately, and the whole launcher **quits** — the tunnel dies and you get **404**. Tunnel-only only runs `cloudflared` and forwards to the API you already started.

### Why it “stops working” when you close terminals

The **`trycloudflare.com` URL only works while `cloudflared` is running** in some terminal. If you close that window or stop the process, that hostname is dead until you start a **new** tunnel (new random name). **`launch_tunnel.py` now patches `.env` automatically** so the hostname in `.env` matches the running tunnel — you still must **restart `bot.py`** after starting a new tunnel if the bot was already running.

### Check before Telegram

1. In **Chrome/Edge**, open the **same** `https://….trycloudflare.com/` URL → you should see your app, not 404.
2. Then open the Mini App from the bot in Telegram.

---

## Alternative: 3 terminals (manual)

Use this if you prefer **`python main.py`** (with reload) for development.

### Terminal A — API

```powershell
cd "c:\Users\HP\Documents\Health app"
python main.py
```

Uses **`PORT`** from `.env` (default **8000**).

### Terminal B — tunnel

```powershell
cd "c:\Users\HP\Documents\Health app"
.\scripts\start-tunnel.ps1
```

The script checks **`http://127.0.0.1:<PORT>/health`** before starting `cloudflared`.  
Copy the **`https://….trycloudflare.com`** line from the output into **`WEBAPP_URL`**.

### Terminal C — bot

```powershell
cd "c:\Users\HP\Documents\Health app"
python bot.py
```

Same rule: **after every new tunnel URL**, update **`.env`** and **restart** `bot.py`.

---

## Every time you start a **new** tunnel

Quick tunnels get a **new random hostname** each time you run `cloudflared` (unless you use a **named tunnel** + your own domain later).

1. Copy the new **`https://….trycloudflare.com/`** URL.
2. Put it in **`WEBAPP_URL`** in `.env`.
3. **Restart** `python bot.py`.
4. Optionally confirm **BotFather** still matches (often already OK if you only change subdomain on the same pattern).

If you skip step 2–3, Telegram will still open an **old** URL → **404**.

---

## `.env` checklist (for Telegram)

| Variable | Role |
|----------|------|
| **`TELEGRAM_BOT_TOKEN`** | Required for `bot.py` and for validating Mini App `initData` on the API. |
| **`WEBAPP_URL`** | **Public HTTPS URL** of the Mini App = current tunnel URL + `/`. |
| **`PORT`** | Must match where the API listens (**8000** unless you changed it). Tunnel must point to the **same** port. |
| **`SECRET_KEY`** | Used by the app for signing; change from default for anything serious. |

---

## Troubleshooting (short)

| Symptom | Likely cause |
|--------|----------------|
| **404** on `trycloudflare.com` | Tunnel process stopped, or **`WEBAPP_URL`** doesn’t match the **running** tunnel. |
| **404** while the tunnel window is still open | If **`Server: cloudflare`** in DevTools, the **edge** is not routing HTTP to your PC. Common fix: **`CLOUDFLARE_TUNNEL_PROTOCOL=http2`** (TCP) — **`launch_tunnel.py` defaults to this** because **QUIC (UDP)** is often blocked by ISPs/firewalls while logs still say “Registered”. Try **`CLOUDFLARE_TUNNEL_REGION=us`** if your firewall only allows US edge IPs. Kill stray **`cloudflared.exe`**: **`scripts\stop-stack.ps1`**. |
| **502 / bad gateway** | API not running on the port the tunnel uses. |
| **Works in browser, fails in Telegram** | Rare caching; confirm **`WEBAPP_URL`** and restart bot. |
| **Blank / API errors** | Bot token / `initData` issues; check server logs in the API terminal. |

---

## Summary diagram

```
Telegram app  --HTTPS-->  trycloudflare.com  --tunnel-->  127.0.0.1:PORT  --HTTP-->  FastAPI (your app)
                              ^
                              |
                    cloudflared (must stay running)

bot.py  --HTTPS-->  api.telegram.org  (polling; separate from the Mini App page)
```

**Remember:** three processes for a working Mini App session — **API + tunnel + bot** — and **`WEBAPP_URL`** must always match the **current** tunnel URL.
