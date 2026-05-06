# Cloudflare Tunnel (Quick Tunnel) for Telegram Mini App

Telegram Mini Apps require **HTTPS**. A **Quick Tunnel** gives you a temporary `https://….trycloudflare.com` URL that forwards to your local server—no domain or Cloudflare account required.

## Prerequisites

- **cloudflared** installed ([winget](https://winget.run/pkg/Cloudflare/cloudflared): `winget install Cloudflare.cloudflared`)
- App running locally (`python main.py`)

## One command (API + tunnel)

From the project folder:

```powershell
python scripts/launch_tunnel.py
```

This starts **uvicorn** (no reload) and **cloudflared**, prints the **`https://….trycloudflare.com/`** URL, then keeps running until you press **Ctrl+C**. The URL is also written to **`.tunnel_url`** in the project folder. Copy it into **`WEBAPP_URL`** in `.env` and restart **`python bot.py`**.

**Important:** Each `trycloudflare.com` hostname works **only while that `cloudflared` process is running**. If you stop the tunnel or start a new one, you get a **new** URL — update `.env` and BotFather. A URL from an old session (or from a script that already exited) will show **404** in Telegram.

## Steps (manual)

### 1. Start the API

From the project folder:

```powershell
python main.py
```

Note the port (default **8000**, or whatever you set in `.env` as `PORT=`).

### 2. Start the tunnel (second terminal)

```powershell
cd "c:\Users\HP\Documents\Health app"
.\scripts\start-tunnel.ps1
```

Or manually:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Change `8000` if your app uses another port (e.g. `8080`).

### 3. Copy the HTTPS URL

`cloudflared` prints a line like:

```text
https://something-random.trycloudflare.com
```

### 4. Set `WEBAPP_URL` in `.env`

Use the **root** of your app (FastAPI serves the mini app at `/`):

```env
WEBAPP_URL=https://something-random.trycloudflare.com/
```

No `/frontend/index.html` path—your server already returns the mini app at `/`.

### 5. BotFather + bot

- In [@BotFather](https://t.me/BotFather), set the **Menu Button** / **Web App URL** to the same HTTPS origin (or full URL as above).
- Restart the bot: `python bot.py`

### 6. Open in Telegram

Use your bot’s **Open app** / menu button. The tunnel must stay running while you test.

---

## Notes

| Topic | Detail |
|--------|--------|
| **URL changes** | Quick Tunnel URLs change each time you restart `cloudflared`. Update `.env` and BotFather when they change. |
| **Production** | For a stable URL, use a [named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/) and a domain on Cloudflare. |
| **Firewall** | Tunnel is outbound-only; you usually don’t open router ports. |

---

## Troubleshooting: “HTTP ERROR 404” in Telegram

This almost always means the **tunnel is not forwarding to your FastAPI app** (or nothing is listening on that port).

1. **Start order** — In one terminal: `python main.py`. Wait until you see the server URL. **Then** in another terminal: `.\scripts\start-tunnel.ps1`.  
   The script now checks `http://127.0.0.1:<PORT>/health` before starting; if that fails, start the API first.

2. **Same port** — The tunnel uses `PORT` from `.env` (default `8000`). Your app must listen on **that** port. If you changed `PORT` (e.g. to `8080`), restart `python main.py` and run the tunnel script again.

3. **Another program on 8000** — If something else is bound to that port, the tunnel may hit the wrong service (often **404**). Check:  
   `netstat -ano | findstr :8000`  
   Stop the other process or pick a free `PORT` in `.env` and use it for both `main.py` and the tunnel.

4. **Test in a normal browser** — Open the `https://….trycloudflare.com` URL in Chrome/Edge. You should see your app (not a 404). If the browser shows 404, fix the local server/port before testing in Telegram.

5. **No spaces in `WEBAPP_URL`** — Use `WEBAPP_URL=https://your-host.trycloudflare.com` with **no trailing spaces** after the URL (spaces break the Mini App link).

6. **Wait a few seconds** after the tunnel prints “Visit it at …” — the hostname can take a short time to work everywhere.
