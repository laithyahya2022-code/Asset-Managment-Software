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


# ------------------------------------------------- native label printing
#
# Browsers print labels through the Windows driver's page pipeline, and some
# label drivers rotate or scale whatever arrives to fit their stock, no
# matter what the dialogs say. Thermal label printers (Xprinter, TSC, ...)
# also speak TSPL, a tiny command language with the sticker size, gap
# registration and rotation built in - so AMS talks to them directly and the
# driver never gets a chance to "help".

DOTS_PER_MM = 8          # 203 dpi print head


def _ascii(text, limit=None):
    """TSPL built-in fonts are ASCII; anything else becomes '?'."""
    s = "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in str(text or ""))
    s = s.replace('"', "'")
    return s[:limit] if limit else s


def label_tspl(width_mm, height_mm, org, tag, rows, flip=False, gap_mm=3):
    """One asset label as a TSPL program.

    rows: [(field label, value)] — e.g. [("Branch", "Mada 3"), ...].
    flip reuses the rotate setting: it turns the print 180° for rolls loaded
    the other way round.
    """
    w = int(width_mm * DOTS_PER_MM)
    h = int(height_mm * DOTS_PER_MM)
    pad = max(int(w * 0.03), 8)
    tag_a = _ascii(tag, 20)
    # Header: the organisation alone, centred and uppercase, in the biggest
    # built-in font that spans the width, over a strong rule. The tag is not
    # repeated here -- it already sits under the barcode. A frame box round
    # the whole sticker matches the on-screen design.
    org_a = _ascii(org, 40).upper()
    for font, cw, ch in (("5", 32, 48), ("4", 24, 32), ("3", 16, 24), ("2", 12, 20)):
        if len(org_a) * cw <= w - 2 * pad:
            break
    out = [
        f"SIZE {width_mm} mm,{height_mm} mm",
        f"GAP {gap_mm} mm,0 mm",
        f"DIRECTION {0 if flip else 1}",
        "REFERENCE 0,0",
        "CLS",
        f"BOX 1,1,{w - 2},{h - 2},4",
        f'TEXT {max(pad, (w - len(org_a) * cw) // 2)},{pad},"{font}",0,1,1,"{org_a}"',
        f"BAR {pad},{pad + ch + 6},{w - 2 * pad},4",
    ]
    y = pad + ch + 22
    for field, value in rows:
        out.append(f'TEXT {pad},{y},"2",0,1,1,"{_ascii(field, 8).upper()}"')
        out.append(f'TEXT {pad + 100},{y},"2",0,1,1,"{_ascii(value, 26)}"')
        y += 28
    # Code 128 across the bottom with the tag centred beneath it.
    bc_h = max(int(h * 0.26), 40)
    bc_y = h - pad - 22 - bc_h
    modules = 11 * (len(tag_a) + 3) + 2          # start+check+stop+quiet
    narrow = 2 if modules * 2 <= w - 2 * pad else 1
    bc_x = max(pad, (w - modules * narrow) // 2)
    out.append(f'BARCODE {bc_x},{bc_y},"128",{bc_h},0,0,{narrow},{narrow * 2},"{tag_a}"')
    out.append(f'TEXT {max(pad, (w - len(tag_a) * 12) // 2)},{bc_y + bc_h + 4},"2",0,1,1,"{tag_a}"')
    out.append("PRINT 1,1")
    return "\r\n".join(out) + "\r\n"


def print_raw(printer, data):
    """Send raw bytes (a TSPL program) to a Windows printer's spooler."""
    if not is_windows() or not printer or not data:
        return False
    if isinstance(data, str):
        data = data.encode("ascii", "replace")
    try:
        import ctypes
        from ctypes import wintypes

        winspool = ctypes.WinDLL("winspool.drv")

        class DOC_INFO_1(ctypes.Structure):
            _fields_ = [("pDocName", wintypes.LPWSTR),
                        ("pOutputFile", wintypes.LPWSTR),
                        ("pDatatype", wintypes.LPWSTR)]

        handle = wintypes.HANDLE()
        if not winspool.OpenPrinterW(printer, ctypes.byref(handle), None):
            return False
        try:
            info = DOC_INFO_1("AMS label", None, "RAW")
            if winspool.StartDocPrinterW(handle, 1, ctypes.byref(info)) == 0:
                return False
            winspool.StartPagePrinter(handle)
            written = wintypes.DWORD(0)
            winspool.WritePrinter(handle, data, len(data), ctypes.byref(written))
            winspool.EndPagePrinter(handle)
            winspool.EndDocPrinter(handle)
            return written.value == len(data)
        finally:
            winspool.ClosePrinter(handle)
    except Exception:
        return False


LOCAL_ADDRESSES = {"127.0.0.1", "::1", "localhost"}


def can_print_directly(printer, client_address=None):
    """True when a direct print is worth attempting for this request.

    The last condition is the one that matters once AMS is installed on a
    server: printing happens on the machine running AMS, not on the machine
    of whoever clicked. A member of staff at their own desk pressing "Print
    label" would otherwise be told the label was sent while it came out of a
    printer in the server room. So a direct print is only attempted when the
    request came from the same machine -- which is always true for the
    desktop app, and true at the server's own console. Everyone else gets the
    browser's print dialog and their own printer, which is what they want.
    """
    if not printer or not is_windows() or not getattr(sys, "frozen", False):
        return False
    return client_address is None or client_address in LOCAL_ADDRESSES
