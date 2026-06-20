"""Web-open browser E2E: the app boots in a plain browser, account auth works, and the primary
navigation renders without console errors. Locks in the Phase C web-open + responsive work."""
import uuid

from conftest import mark_registered, register_account

# 402 = intentional Pro-gating (the app shows a paywall); not a defect for a free test account.
_BENIGN = ("Telegram", "favicon", "manifest", "ServiceWorker", "402", "Payment Required")


def _collect_errors(page):
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    return errors


def _real(errors):
    return [e for e in errors if not any(b in e for b in _BENIGN)]


def test_login_screen_shown_without_telegram(live_server, page):
    page.goto(live_server)
    page.wait_for_selector("#webAuthOverlay:not([hidden])", timeout=15000)
    assert page.is_visible("#webAuthEmail")
    assert page.is_visible("#webAuthPassword")
    assert "Welcome back" in page.inner_text("#webAuthTitle")


def test_register_via_ui_logs_in(live_server, page):
    errors = _collect_errors(page)
    page.goto(live_server)
    page.wait_for_selector("#webAuthOverlay:not([hidden])", timeout=15000)
    page.click("#webAuthToggle")  # switch to register mode
    page.fill("#webAuthEmail", f"web-{uuid.uuid4().hex[:8]}@example.com")
    page.fill("#webAuthPassword", "e2epass1234")
    page.click("#webAuthSubmit")
    # On success the overlay is gone (page reloads into the app / registration wizard).
    page.wait_for_selector("#webAuthOverlay", state="hidden", timeout=20000)
    assert page.evaluate("() => !!localStorage.getItem('bh_access_token')")
    assert not _real(errors), f"console errors during register: {_real(errors)}"


def test_primary_tabs_render(live_server, page):
    token, uid = register_account(live_server, f"nav-{uuid.uuid4().hex[:8]}@example.com")
    mark_registered(uid)
    errors = _collect_errors(page)
    page.goto(live_server)
    page.evaluate("(t) => localStorage.setItem('bh_access_token', t)", token)
    page.reload()
    page.wait_for_selector("#bottomTabs", state="visible", timeout=20000)
    # Drive the nav via the app's switchPage() (each bottom tab calls it) rather than physical
    # clicks — a non-Pro account can surface a paywall sheet that would intercept clicks. This
    # still exercises every primary view's render path and catches load-time console errors.
    for key in ["today", "assistant", "nutrition", "progress", "settings"]:
        page.evaluate(f"switchPage('{key}')")
        page.wait_for_timeout(400)
        active = page.get_attribute(".page.active", "id")
        assert active, f"no active page after switchPage('{key}')"
    assert not _real(errors), f"console errors navigating tabs: {_real(errors)}"
