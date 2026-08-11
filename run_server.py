"""Standalone launcher for the Mada Asset Management System (AMS).

Used both for local development (`python run_server.py`) and as the entry
point for the PyInstaller-built executable. Serves the app with Waitress
(a production-ready WSGI server with no extra system dependencies) and
stores the database, uploads, and backups in an `instance` folder placed
next to the running program — not in a temporary directory — so data
survives restarts and updates.

When run as the packaged Windows app it opens in its own desktop window
(no console window, no browser tab). It still serves on the network so
other devices can open the same shared database in their browser — and
closing the window does not stop the website: the server keeps running
in the background so other devices stay connected. Launching AMS.exe
again while the server is up just reopens the window on the running site.
"""
import os
import shutil
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


def _port_in_use(port):
    """True when something is already serving on this port locally."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


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


#: _open_app_window outcomes.
WINDOW_CLOSED = "closed"      # we owned the window and the user shut it -> quit
WINDOW_DETACHED = "detached"  # a window is up but we don't own its lifetime
WINDOW_NONE = "none"          # nothing opened -> caller should fall back


def _open_app_window(url, title):
    """Show the app in its own desktop window."""
    # 1) Native window via pywebview (uses the built-in Edge WebView2 on Windows)
    try:
        import webview
        # WebView2 cancels every download unless this is on, which silently
        # breaks the Excel/CSV exports and the backup download inside the
        # packaged app. Older pywebview builds have no such setting.
        try:
            webview.settings["ALLOW_DOWNLOADS"] = True
        except (AttributeError, KeyError, TypeError):
            pass
        # Fill the screen. maximized=True on its own is not enough: it resizes
        # the frame but leaves the embedded browser control at whatever
        # width/height the window was created with, so the page ends up drawn
        # in a 1280x840 box with dead space to its right. Create the window at
        # the real screen size, then maximize again once it is up so the
        # control gets a resize it actually acts on.
        width, height = _primary_screen_size(webview, 1280, 840)
        window = webview.create_window(title, url, width=width, height=height,
                                       maximized=True)
    except Exception:
        window = None
    if window is not None:
        # Past this point a window exists. Never fall through to the browser
        # fallback from here, or a failure would leave the user with two.
        def _fill_screen(win):
            try:
                win.maximize()
            except Exception:
                pass         # older pywebview, or a platform without maximize

        try:
            webview.start(_fill_screen, window)   # blocks until it is closed
        except Exception:
            try:
                webview.start()                   # no callback: still our window
            except Exception:
                pass
        return WINDOW_CLOSED
    # 2) A clean "app mode" window in Edge or Chrome (no tabs, no address bar)
    for exe in _browser_app_candidates():
        try:
            import subprocess
            subprocess.Popen([exe, f"--app={url}", "--start-maximized"])
            return WINDOW_DETACHED
        except Exception:
            continue
    return WINDOW_NONE


def _primary_screen_size(webview, fallback_w, fallback_h):
    """Usable size of the main monitor, or the fallback if it can't be read.

    pywebview only exposes webview.screens once its GUI backend has loaded,
    and older builds don't expose it at all, so every step here is optional.
    """
    try:
        screen = webview.screens[0]
        width, height = int(screen.width), int(screen.height)
        if width > 0 and height > 0:
            return width, height
    except Exception:
        pass
    return fallback_w, fallback_h


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


def _apply_update_if_ready(base):
    """Swap in a downloaded update before anything else starts.

    Windows will not overwrite a running executable, so the swap happens here,
    at the very start of the next run, and the app relaunches itself. The
    instance folder is never involved: only the executable is replaced.
    """
    if not getattr(sys, "frozen", False):
        return False
    from itam import updater
    exe = updater.exe_path(base)
    updater.cleanup_retired(base, exe)          # tidy the previous update
    if not updater.pending_update(base, exe):
        return False
    if not updater.apply_pending_update(base, exe):
        return False
    print("Update applied — restarting…")
    return updater.relaunch(exe)


def _count_assets(db_path):
    """Assets in a candidate database, read-only; -1 when unreadable."""
    import sqlite3
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1)
        try:
            return int(con.execute("SELECT COUNT(*) FROM asset").fetchone()[0])
        finally:
            con.close()
    except Exception:
        return -1


def _db_healthy(db_path):
    """True when SQLite's own quick_check passes on the file."""
    import sqlite3
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)
        try:
            return con.execute("PRAGMA quick_check(1)").fetchone()[0] == "ok"
        finally:
            con.close()
    except Exception:
        return False


def _copy_database(src_db, dst_db):
    """Copy a SQLite database with the backup API.

    A plain file copy of a database another process is writing to can produce
    a corrupt copy; the backup API takes a consistent snapshot even then.
    """
    import sqlite3
    src = sqlite3.connect(f"file:{src_db}?mode=ro", uri=True, timeout=5)
    try:
        dst = sqlite3.connect(dst_db)
        try:
            with dst:
                src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _best_existing_instance(candidates):
    """The candidate instance folder holding the most assets (newest wins
    ties) — i.e. the database with the most work in it."""
    best, key = None, None
    for inst in candidates:
        db = os.path.join(inst, "itam.sqlite")
        if not os.path.isfile(db):
            continue
        k = (_count_assets(db), os.path.getmtime(db))
        if key is None or k > key:
            best, key = inst, k
    return best


def _adopt_existing_data(base, inst):
    """One-time rescue into the fixed data folder.

    People end up with several AMS folders (Downloads, "AMS (1)", C:\\AMS …),
    each with its own database, and whichever exe they double-click looks like
    it "lost" the data. On the first run with an empty fixed folder, find the
    database with the most assets among the known past locations and copy that
    whole instance (database, uploads, backups, secret key) in. Originals are
    never modified or deleted. Once a database exists here, never adopt again.
    """
    target = os.path.join(inst, "itam.sqlite")
    if os.path.exists(target):
        if _db_healthy(target):
            return None
        # A broken copy (e.g. adopted from a live database with a plain file
        # copy) would 500 on every page forever. Move it aside — kept, never
        # deleted — and adopt again properly.
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for suffix in ("", "-wal", "-shm"):
            try:
                os.replace(target + suffix,
                           target + suffix + f".corrupt-{stamp}")
            except OSError:
                pass
    candidates = [os.path.join(base, "instance")]
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    candidates.append(os.path.join(downloads, "instance"))
    try:
        candidates += [os.path.join(downloads, d, "instance")
                       for d in sorted(os.listdir(downloads))
                       if os.path.isdir(os.path.join(downloads, d))]
    except OSError:
        pass
    candidates.append(r"C:\AMS\instance")
    src = _best_existing_instance(dict.fromkeys(candidates))
    if not src or os.path.abspath(src) == os.path.abspath(inst):
        return None
    try:
        # Files first (uploads, backups, secret key), then a consistent
        # snapshot of the database itself via SQLite's backup API.
        shutil.copytree(src, inst, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("itam.sqlite*"))
        _copy_database(os.path.join(src, "itam.sqlite"), target)
    except Exception:
        try:
            os.remove(target)          # half-written copy: retry next start
        except OSError:
            pass
        return None
    return src


def _data_root(base):
    """Where the data lives: one fixed folder for the whole machine.

    Data used to sit next to the exe, so every re-downloaded or moved copy
    of AMS.exe started a fresh, empty database. The packaged app now keeps
    everything in ProgramData\\AMS\\instance — the same data no matter where
    AMS.exe is run from. Running from source keeps the old repo-local path.
    """
    if not getattr(sys, "frozen", False):
        return os.path.join(base, "instance"), None
    root = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "AMS")
    inst = os.path.join(root, "instance")
    try:
        os.makedirs(inst, exist_ok=True)
        probe = os.path.join(inst, ".write-test")
        open(probe, "w").close()
        os.remove(probe)
    except OSError:
        return os.path.join(base, "instance"), None   # locked down: stay local
    return inst, _adopt_existing_data(base, inst)


def main():
    base = _base_dir()
    port = int(os.environ.get("PORT", "8080"))
    # Apply a downloaded update only when no server is running: the running
    # server installs its own updates at a quiet moment, and a double-click
    # while one is waiting must open a window, not eat the click on a swap.
    if not _port_in_use(port) and _apply_update_if_ready(base):
        return                                   # the new build takes over
    instance_path, adopted_from = _data_root(base)
    os.makedirs(instance_path, exist_ok=True)

    ip = _local_ip()
    url = f"http://localhost:{port}"

    # Relaunched by "Update now": the old build is still letting go of the
    # port, so wait for it rather than concluding another server is running.
    takeover = os.environ.get("AMS_TAKEOVER") == "1"
    if takeover:
        deadline = time.time() + 30
        while time.time() < deadline and _port_in_use(port):
            time.sleep(0.3)

    # If AMS is already serving on this machine, this launch is just someone
    # double-clicking the program again: reopen the window on the running
    # site instead of fighting over the port (and the database).
    serving = not _port_in_use(port)

    banner = (
        "=" * 62 + "\n"
        "  Mada Asset Management System (AMS)\n" +
        "=" * 62 + "\n"
        f"  On this computer:   {url}\n"
        f"  On the network:     http://{ip}:{port}\n"
        f"  By name:            http://{socket.gethostname().lower()}:{port}\n"
        f"      (phones/tablets: http://{socket.gethostname().lower()}.local:{port})\n"
        "  Open the network address on phones/other PCs to share data.\n"
        "  First login: admin / admin123 (change it right away)\n"
        f"  Data is stored in:  {instance_path}\n"
        + (f"  (your data was found in {adopted_from} and moved here"
           " automatically; the old folder was left untouched)\n"
           if adopted_from else "") +
        "\n"
        "  Closing the AMS window does NOT stop the website - it keeps\n"
        "  running in the background for other devices. Double-click\n"
        "  AMS.exe to reopen the window. To stop the website completely,\n"
        "  end AMS.exe in Task Manager or restart the computer.\n"
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
    server = None
    if serving:
        from itam import create_app
        app = create_app(instance_path=instance_path)
        from waitress import serve
        server = threading.Thread(
            target=lambda: serve(app, host="0.0.0.0", port=port), daemon=True)
        server.start()
        _wait_until_up(port)

    # ITAM_NO_BROWSER is the pre-rename spelling, still honoured so existing
    # server installs and scheduled tasks keep running headless.
    # An update restart (AMS_TAKEOVER) is headless too: popping a fresh window
    # and grabbing focus after every self-update reads as lag and clutter —
    # the site just comes back quietly, and the next double-click of AMS.exe
    # opens a window on it. Only when this process actually took the port
    # over, though: a takeover launch that found another server already up
    # is effectively a viewer and should still show a window.
    if ("1" in (os.environ.get("AMS_NO_BROWSER"), os.environ.get("ITAM_NO_BROWSER"))
            or (takeover and serving)):
        if server is not None:
            server.join()    # headless (e.g. CI smoke test / server install)
        return               # already running elsewhere: nothing to do

    # The window title is visible to everyone; the network address stays in
    # the console banner and the access-info text file instead.
    title = "Mada Asset Management System"
    outcome = _open_app_window(url, title)
    if outcome == WINDOW_NONE:
        # Last resort: default browser. Only when nothing else opened, so an
        # app-mode window doesn't get a duplicate tab piled on top of it.
        try:
            webbrowser.open(url)
        except Exception:
            pass
    # The website must survive its window: other devices are using it. When
    # this process owns the server, keep serving after the window closes;
    # when another AMS.exe owns it, this launch was only a viewer and exits.
    if server is not None:
        server.join()


if __name__ == "__main__":
    main()
