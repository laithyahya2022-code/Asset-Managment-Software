"""Send a label straight to a Windows printer instead of a browser tab.

The label screens are ordinary web pages, so "print" has always meant "open a
tab and use the browser's print dialog". On a school desk with a dedicated
label printer -- an Xprinter XP-490B, say -- that is several clicks and an easy
place to pick the wrong printer.

When AMS runs on Windows it can hand the page to the printer itself. The
printer is named in Settings; leave it blank and nothing changes, so a browser
on someone else's machine still gets the normal print dialog. Everything here
is best effort: any failure falls back to the browser rather than losing the
print.
"""
import os
import subprocess
import sys
import tempfile


def is_windows():
    return os.name == "nt"


def list_printers():
    """Installed printer names, or [] where that can't be asked."""
    if not is_windows():
        return []
    try:
        import winreg          # Windows-only, absent everywhere else
    except ImportError:
        return []
    names = []
    path = r"SYSTEM\CurrentControlSet\Control\Print\Printers"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            for i in range(winreg.QueryInfoKey(key)[0]):
                names.append(winreg.EnumKey(key, i))
    except OSError:
        pass
    return sorted(names)


def print_html(html, printer=None):
    """Print a rendered label. Returns True only if it was actually sent.

    Uses the browser already on the machine in headless print-to-default mode;
    Edge ships with Windows, so this needs nothing installed. A False result
    means the caller should fall back to opening the page normally.
    """
    if not is_windows() or not html:
        return False

    path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(html)
            path = fh.name

        # Print through the shell's "print" verb, which routes to whichever
        # application owns .html and then to the chosen printer.
        if printer:
            ok = _print_with_browser(path, printer)
            if ok:
                return True
        os.startfile(path, "print")        # noqa: S606 - Windows only
        return True
    except Exception:
        return False
    finally:
        # Leave the file for the printer to read; Windows cleans %TEMP% itself.
        # Deleting it here can race the spooler and print a blank page.
        pass


def _print_with_browser(path, printer):
    """Ask Edge/Chrome to print the file to a named printer, without a window."""
    for exe in _browsers():
        try:
            subprocess.run(
                [exe, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                 f"--print-to-printer={printer}", path],
                timeout=25, check=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            continue
    return False


def _browsers():
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    return [
        os.path.join(x86, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(program_files, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(x86, "Google", "Chrome", "Application", "chrome.exe"),
    ]


def can_print_directly(printer):
    """True when a direct print is worth attempting for this request."""
    return bool(printer) and is_windows() and getattr(sys, "frozen", False)
