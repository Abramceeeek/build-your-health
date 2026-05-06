"""
Expose the local API (python main.py) over HTTPS using ngrok — often works when trycloudflare.com does not.

Prerequisites:
  1. Install ngrok:  winget install ngrok.ngrok
  2. One-time auth (free account):  ngrok config add-authtoken <token from https://dashboard.ngrok.com/get-started/your-authtoken
  3. Keep `python main.py` running on PORT (default 8000).

Usage:
  python scripts/launch_ngrok.py

Then set WEBAPP_URL to the printed https URL and restart python bot.py
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT + "/.env")

PORT = int(os.getenv("PORT", "8000"))
SKIP_ENV_SYNC = os.getenv("HEALTH_TRANSFORM_SKIP_ENV_SYNC", "").strip() in ("1", "true", "yes")

NGROK_API = "http://127.0.0.1:4040/api/tunnels"


def _sync_webapp_url_to_env(env_path: str, public_base: str) -> None:
    public_base = public_base.rstrip("/") + "/"
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        lines = f.readlines()
    new_lines: list[str] = []
    replaced = False
    for line in lines:
        s = line.lstrip()
        if s.startswith("WEBAPP_URL=") and not s.startswith("#"):
            new_lines.append(f"WEBAPP_URL={public_base}\n")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"WEBAPP_URL={public_base}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def _which_ngrok() -> str | None:
    from shutil import which

    w = which("ngrok")
    if w:
        return w
    local = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ngrok", "ngrok.exe")
    if os.path.isfile(local):
        return local
    return None


def _wait_health() -> bool:
    deadline = time.time() + 60
    url = f"http://127.0.0.1:{PORT}/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(0.4)
    return False


def _poll_ngrok_https_url(timeout_sec: int = 90) -> str | None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(NGROK_API, timeout=3) as r:
                data = json.load(r)
            for t in data.get("tunnels", []):
                pub = t.get("public_url") or ""
                if pub.startswith("https://"):
                    return pub.rstrip("/")
        except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, KeyError, ValueError):
            pass
        time.sleep(0.5)
    return None


def _verify_public_health(base: str) -> bool:
    health = f"{base.rstrip('/')}/health"
    req = urllib.request.Request(health, headers={"User-Agent": "HealthTransformNgrokCheck/1"})
    for _ in range(12):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(2)
    return False


def main() -> int:
    ng = _which_ngrok()
    if not ng:
        print("ngrok not found. Install:", file=sys.stderr)
        print("  winget install ngrok.ngrok", file=sys.stderr)
        print("Then add your authtoken: https://dashboard.ngrok.com/get-started/your-authtoken", file=sys.stderr)
        return 1

    print("Expecting API on http://127.0.0.1:%s (start: python main.py)" % PORT, flush=True)
    if not _wait_health():
        print("Nothing on /health — start `python main.py` first.", file=sys.stderr)
        return 1

    # ngrok: avoid hiding window so first-time errors are visible
    p = subprocess.Popen(
        [ng, "http", str(PORT)],
        cwd=ROOT,
    )

    public = _poll_ngrok_https_url()
    if not public:
        print("Could not read public URL from ngrok API (http://127.0.0.1:4040).", file=sys.stderr)
        print("Is ngrok logged in? Run: ngrok config add-authtoken <token>", file=sys.stderr)
        try:
            p.terminate()
            p.wait(timeout=5)
        except OSError:
            pass
        return 1

    if not _verify_public_health(public):
        print("WARNING: public /health did not return 200 yet — try again in browser in ~10s.", file=sys.stderr)

    print()
    print("=" * 60)
    print("  Mini App URL (set WEBAPP_URL in .env):")
    print(f"  {public}/")
    print("=" * 60)
    print("  ngrok running. Press Ctrl+C to stop.")
    print("  First visit may show ngrok interstitial — click Continue.")
    print()

    try:
        with open(os.path.join(ROOT, ".tunnel_url"), "w", encoding="utf-8") as tf:
            tf.write(f"{public}/\n")
        print("  (saved to .tunnel_url)", flush=True)
    except OSError:
        pass

    env_path = os.path.join(ROOT, ".env")
    if not SKIP_ENV_SYNC:
        try:
            _sync_webapp_url_to_env(env_path, public)
            print("  (updated WEBAPP_URL in .env — restart bot.py)", flush=True)
        except OSError as e:
            print(f"  (could not update .env: {e})", file=sys.stderr)

    def _stop(*_a):
        try:
            p.terminate()
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    try:
        p.wait()
    except KeyboardInterrupt:
        _stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
