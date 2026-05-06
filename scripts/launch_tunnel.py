"""
Start the FastAPI app + Cloudflare quick tunnel, print the public HTTPS URL, then keep running.

If trycloudflare URLs always 404 in the browser, use ngrok instead:
  python scripts/launch_ngrok.py
  See docs/NGROK_TUNNEL.md

Usage (from project root):
  python scripts/launch_tunnel.py

If you already run `python main.py` in another terminal, port 8000 is taken: the inner
uvicorn would exit immediately, this script would end, and the tunnel would die (404).
In that case use:
  python scripts/launch_tunnel.py --tunnel-only

Stop with Ctrl+C (terminates uvicorn and cloudflared).
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import threading
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
# Set to 1 to skip patching .env WEBAPP_URL (default: keep .env in sync with tunnel)
SKIP_ENV_SYNC = os.getenv("HEALTH_TRANSFORM_SKIP_ENV_SYNC", "").strip() in ("1", "true", "yes")
# Optional: set CLOUDFLARE_TUNNEL_REGION=us if your firewall only allows US edge IPs
CF_TUNNEL_REGION = os.getenv("CLOUDFLARE_TUNNEL_REGION", "").strip()
# Edge transport: http2 = TCP (works through most firewalls). quic = UDP (often blocked; log can show "Registered" but browsers get 404).
CF_TUNNEL_PROTOCOL = os.getenv("CLOUDFLARE_TUNNEL_PROTOCOL", "http2").strip().lower()
if CF_TUNNEL_PROTOCOL not in ("auto", "http2", "quic"):
    CF_TUNNEL_PROTOCOL = "http2"

CF_CANDIDATES = [
    "cloudflared",
    os.path.join(os.environ.get("ProgramFiles(x86)", ""), "cloudflared", "cloudflared.exe"),
    os.path.join(os.environ.get("ProgramFiles", ""), "cloudflared", "cloudflared.exe"),
]


def _sync_webapp_url_to_env(env_path: str, public_base: str) -> None:
    """Set WEBAPP_URL in .env so you don't paste the wrong trycloudflare hostname."""
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


def _which_cloudflared() -> str | None:
    for c in CF_CANDIDATES:
        if not c:
            continue
        if c == "cloudflared":
            from shutil import which

            w = which("cloudflared")
            if w:
                return w
            continue
        if os.path.isfile(c):
            return c
    return None


def _wait_health(timeout_sec: int = 90) -> bool:
    deadline = time.time() + timeout_sec
    url = f"http://127.0.0.1:{PORT}/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(0.5)
    return False


def _wait_health_while_uvicorn_running(uv: subprocess.Popen, timeout_sec: int = 90) -> bool:
    """Wait for /health, but fail if *our* uvicorn child dies (e.g. port already in use)."""
    deadline = time.time() + timeout_sec
    url = f"http://127.0.0.1:{PORT}/health"
    while time.time() < deadline:
        code = uv.poll()
        if code is not None:
            # Child exited — if something still answers /health, another process owns the port
            try:
                with urllib.request.urlopen(url, timeout=2) as r:
                    if r.status == 200:
                        print("", file=sys.stderr)
                        print(
                            "ERROR: Uvicorn could not bind to port %s (already in use)."
                            % PORT,
                            file=sys.stderr,
                        )
                        print(
                            "  Fix: stop the other server (e.g. close the `python main.py` window), "
                            "then run this script again.",
                            file=sys.stderr,
                        )
                        print(
                            "  Or: keep `python main.py` running and use:",
                            file=sys.stderr,
                        )
                        print(
                            "       python scripts/launch_tunnel.py --tunnel-only",
                            file=sys.stderr,
                        )
                        print("", file=sys.stderr)
                        return False
            except (urllib.error.URLError, OSError, TimeoutError):
                pass
            print(
                "ERROR: Uvicorn exited before the API became ready (port %s)." % PORT,
                file=sys.stderr,
            )
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(0.5)
    return False


def _verify_public_health(base_url: str, attempts: int = 15, delay_sec: float = 4.0) -> bool:
    """Confirm Cloudflare edge actually routes HTTP to this tunnel (not only 'registered' in the log)."""
    base = base_url.rstrip("/")
    health = f"{base}/health"
    req = urllib.request.Request(health, headers={"User-Agent": "HealthTransformTunnelCheck/1"})
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(delay_sec)
    return False


def main() -> int:
    tunnel_only = "--tunnel-only" in sys.argv

    # Kill stale cloudflared from previous runs (quick tunnels are ephemeral anyway)
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/IM", "cloudflared.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)

    cf = _which_cloudflared()
    if not cf:
        print("cloudflared not found. Install: winget install Cloudflare.cloudflared", file=sys.stderr)
        return 1

    uv: subprocess.Popen | None = None
    if tunnel_only:
        print("Tunnel-only mode: expecting API already running (e.g. python main.py).", flush=True)
        if not _wait_health():
            print(
                f"Nothing answered http://127.0.0.1:{PORT}/health — start `python main.py` first.",
                file=sys.stderr,
            )
            return 1
    else:
        _uv_kw: dict = {
            "cwd": ROOT,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            _uv_kw["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

        uv = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.app:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(PORT),
            ],
            **_uv_kw,
        )

        if not _wait_health_while_uvicorn_running(uv):
            try:
                uv.terminate()
                uv.wait(timeout=10)
            except OSError:
                pass
            return 1

    # Do NOT use subprocess.PIPE (buffer can fill on Windows). Do NOT use cmd.exe shell redirects:
    # spawn cloudflared as a direct child and log to a file. Edge 404 + Server: cloudflare means
    # the connector was not actually routing HTTP yet.
    log_path = os.path.join(ROOT, ".cloudflared.log")
    # Use an empty config so cloudflared ignores ~/.cloudflared/config.yml
    # (that file may have ingress rules for a named tunnel that return http_status:404 for all other hosts)
    empty_cfg = os.path.join(ROOT, ".cloudflared-empty.yml")
    if not os.path.isfile(empty_cfg):
        with open(empty_cfg, "wb") as f:
            f.write(b"# empty config\n")
    cf_args: list[str] = [
        cf,
        "--config",
        empty_cfg,
        "--edge-ip-version",
        "4",
    ]
    if CF_TUNNEL_REGION:
        cf_args.extend(["--region", CF_TUNNEL_REGION])
    cf_args.extend(
        [
            "tunnel",
            "--url",
            f"http://127.0.0.1:{PORT}",
            "--protocol",
            CF_TUNNEL_PROTOCOL,
        ]
    )

    logf = open(log_path, "w", encoding="utf-8", newline="\n", buffering=1)
    _popen_kw: dict = {
        "cwd": ROOT,
        "stdout": logf,
        "stderr": subprocess.STDOUT,
    }
    # Do NOT use CREATE_NO_WINDOW — it can break cloudflared's console handling on Windows.
    # Do NOT close logf after Popen — cloudflared writes to this fd for its entire lifetime.
    # Closing it prematurely invalidates the handle and kills the tunnel connection.
    p = subprocess.Popen(cf_args, **_popen_kw)

    url = None
    pat = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    deadline = time.time() + 120
    while time.time() < deadline and p.poll() is None:
        try:
            with open(log_path, encoding="utf-8", errors="replace") as rf:
                text = rf.read()
        except OSError:
            text = ""
        m = pat.search(text)
        if m:
            url = m.group(0)
            break
        time.sleep(0.25)

    if not url:
        print("Could not read tunnel URL from cloudflared log.", file=sys.stderr)
        try:
            with open(log_path, encoding="utf-8", errors="replace") as rf:
                tail = rf.read()[-6000:]
            if tail.strip():
                print("--- .cloudflared.log (tail) ---\n", tail, file=sys.stderr)
        except OSError:
            pass
        p.terminate()
        try:
            logf.close()
        except OSError:
            pass
        if uv is not None:
            uv.terminate()
        return 1

    if not _verify_public_health(url):
        print("", file=sys.stderr)
        print(
            "WARNING: Cloudflare edge did not return 200 from /health on the public URL yet.",
            file=sys.stderr,
        )
        print(
            "  Edge may still be propagating, or UDP (QUIC) was blocked — default is now --protocol http2.",
            file=sys.stderr,
        )
        print(
            "  Wait 60s, retry browser. Or set CLOUDFLARE_TUNNEL_REGION=us in .env. See docs/TELEGRAM_MINI_APP_RUNBOOK.md",
            file=sys.stderr,
        )
        print(
            "  See .cloudflared.log for errors. Run: scripts\\stop-stack.ps1 then start tunnel again.",
            file=sys.stderr,
        )
        print("", file=sys.stderr)

    print()
    print("=" * 60)
    print("  Mini App URL (set WEBAPP_URL in .env to this):")
    print(f"  {url}/")
    print("=" * 60)
    print("  Server + tunnel running. Press Ctrl+C to stop.")
    print("  If the first browser load fails, wait 10-20s (tunnel registration) and retry.")
    print()
    try:
        with open(os.path.join(ROOT, ".tunnel_url"), "w", encoding="utf-8") as tf:
            tf.write(f"{url}/\n")
        print("  (saved to .tunnel_url)", flush=True)
    except OSError:
        pass

    env_path = os.path.join(ROOT, ".env")
    if not SKIP_ENV_SYNC:
        try:
            _sync_webapp_url_to_env(env_path, url)
            print("  (updated WEBAPP_URL in .env - restart bot.py if it is already running)", flush=True)
        except OSError as e:
            print(f"  (could not update .env: {e})", file=sys.stderr, flush=True)
    print()

    def _terminate_all(*_a):
        try:
            p.terminate()
        except OSError:
            pass
        if uv is not None:
            try:
                uv.terminate()
            except OSError:
                pass
        try:
            logf.close()
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, _terminate_all)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _terminate_all)

    def _wait_tunnel():
        p.wait()

    if uv is not None:
        threading.Thread(target=_wait_tunnel, daemon=True).start()

    try:
        if uv is not None:
            uv.wait()
        else:
            p.wait()
    except KeyboardInterrupt:
        _terminate_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
