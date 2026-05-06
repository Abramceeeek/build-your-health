# Ngrok tunnel (recommended if trycloudflare.com always shows 404)

Cloudflare **quick tunnels** (`*.trycloudflare.com`) often fail on some networks (UDP/QUIC, ISP, country, or firewall). **ngrok** uses a stable TCP tunnel and usually “just works” for local development.

## 1. Install ngrok (Windows)

```powershell
winget install ngrok.ngrok
```

Restart the terminal, then:

```powershell
ngrok version
```

## 2. One-time login (free)

1. Create a free account at [ngrok.com](https://ngrok.com/).
2. Copy your **authtoken** from the [dashboard](https://dashboard.ngrok.com/get-started/your-authtoken).
3. Run:

```powershell
ngrok config add-authtoken YOUR_TOKEN_HERE
```

## 3. Run the app + ngrok + bot

**Terminal 1 — API**

```powershell
cd "C:\Users\HP\Documents\Health app"
python main.py
```

**Terminal 2 — ngrok**

```powershell
cd "C:\Users\HP\Documents\Health app"
python scripts\launch_ngrok.py
```

Copy the printed **`https://….ngrok-free.app/`** URL into **`WEBAPP_URL`** in `.env` (the script updates it automatically unless you disabled sync).

**Terminal 3 — bot**

```powershell
python bot.py
```

## 4. Browser / Telegram notes

- The first open of an ngrok URL may show an **ngrok interstitial** page — click **Continue** (Telegram’s WebView may show it once).
- **`WEBAPP_URL`** must match the **current** ngrok URL; it changes if you restart ngrok (paid plans can fix a domain).

## 5. Optional script

Double-click **`scripts\start-stack-ngrok.cmd`** (starts three windows: API → ngrok → bot).
