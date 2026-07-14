"""Standalone launcher for ITAM Enterprise.

Used both for local development (`python run_server.py`) and as the entry
point for the PyInstaller-built executable. Serves the app with Waitress
(a production-ready WSGI server with no extra system dependencies) and
stores the database, uploads, and backups in an `instance` folder placed
next to the running program — not in a temporary directory — so data
survives restarts and updates.
"""
import os
import socket
import sys
import threading
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


def main():
    base = _base_dir()
    instance_path = os.path.join(base, "instance")
    os.makedirs(instance_path, exist_ok=True)

    from itam import create_app
    app = create_app(instance_path=instance_path)

    port = int(os.environ.get("PORT", "8080"))
    ip = _local_ip()

    print("=" * 62)
    print("  ITAM Enterprise -- IT Asset Management System")
    print("=" * 62)
    print(f"  On this computer:   http://localhost:{port}")
    print(f"  On the network:     http://{ip}:{port}")
    print("  Share the network address with your team.")
    print("  First login: admin / admin123 (change it right away)")
    print(f"  Data is stored in:  {instance_path}")
    print("  Press Ctrl+C to stop.")
    print("=" * 62)

    if os.environ.get("ITAM_NO_BROWSER") != "1":
        threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    from waitress import serve
    serve(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
