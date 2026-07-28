"""Standalone launcher for the Mada Asset Management System (AMS).

Used both for local development (`python run_server.py`) and as the entry
point for the PyInstaller-built executable. Serves the app with Waitress
(a production-ready WSGI server with no extra system dependencies) and
stores the database, uploads, and backups in an `instance` folder placed
next to the running program — not in a temporary directory — so data
survives restarts and updates.

When run as the packaged Windows app it opens in its own desktop window
(no console window, no browser tab). It still serves on the network so
other devices can open the same shared database in their browser.
"""
import os
import socket
import sys
import threading
import time
import webbrowser


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _wait_until_up(port, timeout=15):
    """Block until the web server is accepting connections (or timeout)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def _open_app_window(url, title):
    """Show the app in its own desktop window. Returns True if a window was
    opened and closed (meaning we should exit), False if we couldn't and the
    caller should fall back to another method."""
    # 1) Native window via pywebview (uses the built-in Edge WebView2 on Windows)
    try:
        import webview
        webview.create_window(title, url, width=1280, height=840)
        webview.start()      # blocks until the window is closed
        return True
    except Exception:
        pass
    # 2) A clean "app mode" window in Edge or Chrome (no tabs, no address bar)
    for exe in _browser_app_candidates():
        try:
            import subprocess
            subprocess.Popen([exe, f"--app={url}"])
            return False     # window opened, but its lifetime is independent
        except Exception:
            continue
    return False


def _browser_app_candidates():
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pfx86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    return [
        os.path.join(pfx86, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(pfx86, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
    ]


def main():
    base = _base_dir()
    instance_path = os.path.join(base, "instance")
    os.makedirs(instance_path, exist_ok=True)

    from itam import create_app
    app = create_app(instance_path=instance_path)

    port = int(os.environ.get("PORT", "8080"))
    ip = _local_ip()
    url = f"http://localhost:{port}"

    banner = (
        "=" * 62 + "\n"
        "  Mada Asset Management System (AMS)\n" +
        "=" * 62 + "\n"
        f"  On this computer:   {url}\n"
        f"  On the network:     http://{ip}:{port}\n"
        "  Open the network address on phones/other PCs to share data.\n"
        "  First login: admin / admin123 (change it right away)\n"
        f"  Data is stored in:  {instance_path}\n"
    )
    print(banner)
    # In windowed mode there is no console, so leave the access details in a
    # text file next to the program for whoever sets it up.
    try:
        with open(os.path.join(base, "AMS - open on other devices.txt"),
                  "w", encoding="utf-8") as fh:
            fh.write(banner)
    except OSError:
        pass

    # Serve in a background thread so the main thread can own the app window.
    from waitress import serve
    server = threading.Thread(
        target=lambda: serve(app, host="0.0.0.0", port=port), daemon=True)
    server.start()
    _wait_until_up(port)

    # ITAM_NO_BROWSER is the pre-rename spelling, still honoured so existing
    # server installs and scheduled tasks keep running headless.
    if "1" in (os.environ.get("AMS_NO_BROWSER"), os.environ.get("ITAM_NO_BROWSER")):
        server.join()        # headless (e.g. CI smoke test / server install)
        return

    title = f"Mada AMS  —  network: http://{ip}:{port}"
    if _open_app_window(url, title):
        return               # the app window was closed -> quit
    # Last resort: default browser, then keep serving in the background.
    try:
        webbrowser.open(url)
    except Exception:
        pass
    server.join()


if __name__ == "__main__":
    main()
