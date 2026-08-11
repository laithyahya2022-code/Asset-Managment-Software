"""Self-update for the packaged Windows build.

Talks only to the GitHub Releases API — no other service is involved and no
account or subscription is needed beyond access to the repository itself.

How an update lands:

1. On startup the app asks GitHub for the latest release and reads the version
   it advertises. The download link is deliberately a fixed tag (v1.0.0) so it
   never expires, which means the tag carries no version — the workflow ships a
   ``version.txt`` asset next to the executable instead.
2. If that version is newer, the new executable is downloaded *beside* the
   running one as ``AMS.exe.new``. Nothing is replaced yet.
3. Windows will not let a running executable be overwritten, but it will let it
   be *renamed*. So on the next start the old file is renamed aside, the
   downloaded one takes its place, and the app relaunches itself.

The ``instance`` folder — the SQLite database, uploads and backups — is never
read, written, moved or deleted here. An update only ever touches the three
executable files next to it.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

#: Asset names published by .github/workflows/release.yml.
EXE_ASSET = "AMS.exe"
VERSION_ASSET = "version.txt"

#: Written next to the running executable. Deliberately siblings of the exe and
#: never inside instance/.
PENDING_SUFFIX = ".new"
RETIRED_SUFFIX = ".old"

API = "https://api.github.com/repos/{repo}/releases/latest"
TIMEOUT = 8


def parse_version(text):
    """"2026.07.19" or "v1.2.3" -> (2026, 7, 19) / (1, 2, 3); None if unusable."""
    if not text:
        return None
    numbers = re.findall(r"\d+", str(text))
    return tuple(int(n) for n in numbers) if numbers else None


def is_newer(remote, local):
    """True when `remote` is a strictly higher version than `local`.

    Unparseable input is treated as "not newer", so a malformed release can
    never trigger a download. Versions of different lengths are compared by
    padding the shorter one with zeros: 2026.08.01.1 really is newer than
    2026.08.01. Refusing to compare them instead — as this used to — meant
    that adding a hotfix component to the scheme would silently freeze every
    installed copy on its current build, with nothing logged anywhere.
    """
    r, l = parse_version(remote), parse_version(local)
    if not r or not l:
        return False
    width = max(len(r), len(l))
    return r + (0,) * (width - len(r)) > l + (0,) * (width - len(l))


def _request(url, token=None, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={
        "Accept": accept,
        "User-Agent": "AMS-updater",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def latest_release(repo, token=None):
    """The latest release as a dict, or None if it can't be reached.

    Returns None rather than raising for every failure mode there is — no
    network, DNS failure, proxy, rate limit, 404 on a private repo without a
    token — because a failed update check must never disturb the app.
    """
    try:
        with _request(API.format(repo=repo), token) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError,
            ValueError, TimeoutError):
        return None


def _asset(release, name):
    for asset in (release or {}).get("assets") or []:
        if asset.get("name") == name:
            return asset
    return None


def remote_version(release, token=None):
    """The version a release advertises.

    Prefers the ``version.txt`` asset; falls back to trailing digits in the
    release title. The tag is ignored on purpose — it is pinned to v1.0.0 so
    the download URL stays permanent, so it never changes.
    """
    asset = _asset(release, VERSION_ASSET)
    if asset and asset.get("browser_download_url"):
        try:
            with _request(asset["browser_download_url"], token,
                          accept="application/octet-stream") as resp:
                text = resp.read(64).decode("utf-8", "replace").strip()
            if parse_version(text):
                return text
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                TimeoutError):
            pass
    name = (release or {}).get("name") or ""
    match = re.search(r"(\d+(?:[._]\d+)+)", name)
    return match.group(1) if match else None


def exe_path(base_dir):
    """The executable this app runs as, or None when running from source."""
    if not getattr(sys, "frozen", False):
        return None
    return os.path.join(base_dir, os.path.basename(sys.executable))


def pending_path(base_dir, exe=None):
    return (exe or os.path.join(base_dir, EXE_ASSET)) + PENDING_SUFFIX


def pending_update(base_dir, exe=None):
    """True when a downloaded update is waiting to be applied on restart."""
    return os.path.exists(pending_path(base_dir, exe))


def download_update(release, base_dir, exe=None, token=None):
    """Fetch the new executable to <exe>.new. Returns True on success.

    Downloads to a temporary name first and renames into place, so a connection
    that drops halfway can never leave a half-written file that the next start
    would treat as a valid update.
    """
    asset = _asset(release, EXE_ASSET)
    if not asset or not asset.get("browser_download_url"):
        return False
    target = pending_path(base_dir, exe)
    partial = target + ".part"
    try:
        with _request(asset["browser_download_url"], token,
                      accept="application/octet-stream") as resp, \
                open(partial, "wb") as fh:
            shutil.copyfileobj(resp, fh)
        if os.path.getsize(partial) < 1_000_000:      # a real build is ~27 MB
            os.remove(partial)
            return False
        os.replace(partial, target)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError,
            TimeoutError):
        for path in (partial,):
            try:
                os.remove(path)
            except OSError:
                pass
        return False


def check_for_update(repo, current_version, base_dir, exe=None, token=None):
    """Look for a newer build and download it. Never raises.

    Returns one of: "downloaded", "pending" (one was already waiting),
    "up-to-date", "unavailable" (offline / private repo / no release).
    """
    if pending_update(base_dir, exe):
        return "pending"
    release = latest_release(repo, token)
    if not release:
        return "unavailable"
    version = remote_version(release, token)
    if not is_newer(version, current_version):
        return "up-to-date"
    return "downloaded" if download_update(release, base_dir, exe, token) \
        else "unavailable"


def apply_pending_update(base_dir, exe=None):
    """Swap in a downloaded update. Returns True if the app should relaunch.

    Windows refuses to overwrite a running executable but allows renaming one,
    so the running file is moved aside and the downloaded file takes its place.
    Only ever touches these three sibling files — never instance/.
    """
    exe = exe or exe_path(base_dir)
    if not exe or not os.path.exists(exe):
        return False
    new = exe + PENDING_SUFFIX
    if not os.path.exists(new):
        return False
    retired = exe + RETIRED_SUFFIX
    try:
        if os.path.exists(retired):
            os.remove(retired)                 # left over from a past update
    except OSError:
        pass
    try:
        os.rename(exe, retired)                # allowed while running
    except OSError:
        return False                           # locked; try again next start
    try:
        os.replace(new, exe)
    except OSError:
        os.rename(retired, exe)                # put things back, stay on old
        return False
    return True


def _child_env(**extra):
    """Environment for relaunching ourselves.

    A PyInstaller one-file app extracts itself to a _MEI… temp folder and
    records that in the environment. A child launched with the parent's
    environment latches onto the dying parent's folder, which then can't be
    removed — the "Failed to remove temporary directory" popup. Strip those
    markers and tell the bootloader to start clean.
    """
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("_MEI", "_PYI"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    env.update(extra)
    return env


def relaunch(exe):
    """Start the freshly installed executable and let this process finish."""
    try:
        subprocess.Popen([exe], close_fds=True, env=_child_env(),
                         cwd=os.path.dirname(exe) or None,
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        return True
    except OSError:
        return False


def _close_app_windows():
    """Destroy any pywebview window before the hard exit.

    The window's embedded browser engine (WebView2) runs as child processes
    holding files inside the PyInstaller _MEI temp folder. Exiting without
    closing the window leaves them alive for a moment, the folder can't be
    removed, and Windows pops up "Failed to remove temporary directory".
    """
    try:
        import webview
        for w in list(getattr(webview, "windows", [])):
            try:
                w.destroy()
            except Exception:
                pass
        import time
        time.sleep(1.0)          # let the browser children shut down
    except Exception:
        pass                     # headless server: nothing to close


def restart_into_update(base_dir, exe=None):
    """Swap in the pending update and hand this process over to the new build.

    On success this call DOES NOT RETURN: the freshly installed executable is
    started (with AMS_TAKEOVER so it waits for our port) and this process
    exits. Returns False when there is nothing to apply or the swap failed,
    in which case the caller keeps serving on the old build.
    """
    exe = exe or exe_path(base_dir)
    if not apply_pending_update(base_dir, exe):
        return False
    _close_app_windows()
    try:
        subprocess.Popen([exe], close_fds=True, env=_child_env(AMS_TAKEOVER="1"),
                         cwd=os.path.dirname(exe) or None,
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    except OSError:
        return False        # swap already happened; the next start runs it
    os._exit(0)


def cleanup_retired(base_dir, exe=None):
    """Remove the previous executable once the new one is running."""
    exe = exe or exe_path(base_dir)
    if not exe:
        return
    try:
        os.remove(exe + RETIRED_SUFFIX)
    except OSError:
        pass
