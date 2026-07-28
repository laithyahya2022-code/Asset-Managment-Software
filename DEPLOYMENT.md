# Server Installation Guide (School / On-Premises)

This guide takes a fresh server to a running, shared AMS website in about
15 minutes. Cost: **$0** — everything used here is free software.

After setup, everyone in the school opens the site in their browser at
`http://SERVER-IP:8080` (or a friendly name like `http://itam.school.local`),
logs in, and works on **one shared database**.

Pick the section for your server:

- [A. Windows — ready-made AMS.exe (no Python needed)](#a-windows--ready-made-itamexe-easiest)
- [B. Windows Server (from source)](#b-windows-server-from-source)
- [C. Linux server (Ubuntu/Debian)](#c-linux-server-ubuntudebian)
- [D. Docker (any OS, with PostgreSQL)](#d-docker-any-os)
- [After installation](#after-installation) — first login, backups, updates

---

## A. Windows — ready-made AMS.exe (easiest)

Every update to this project automatically builds a Windows executable —
no Python, no `pip install`, no command line. This is the fastest way to
get the system onto a Windows server or PC.

1. Open the repository on GitHub → the **Actions** tab →
   **Build Windows executable** → click the newest successful run (green ✓).
2. Under **Artifacts**, download **AMS-windows-exe** (a small zip)
   and extract it — you get **`AMS.exe`**.
3. Copy `AMS.exe` to a folder on the server, e.g. `C:\AMS\AMS.exe`.
4. Double-click it. A console window opens showing:
   ```
   On this computer:   http://localhost:8080
   On the network:     http://192.168.1.50:8080
   ```
   Your browser opens automatically. Share the **network** address with
   your team — that's the shared link everyone on the school network uses.
5. The database, uploads, and backups are created automatically in an
   `instance` folder next to `AMS.exe`. Keep that folder — it **is** your
   data. Back up that folder the same way you'd back up any important file.

**To start it automatically on boot:** put a shortcut to `AMS.exe` in the
Windows **Startup** folder (`Win+R` → `shell:startup`), or set it up as a
scheduled task the same way as the "start on boot" step in Section B below,
just pointing at `AMS.exe` instead of a `.bat` file.

**Updating:** download the newest `AMS.exe` from Actions the same way and
replace the old file — your `instance` folder (all your data) is untouched.

**Windows SmartScreen:** since the file isn't code-signed, Windows may show
a blue "protected your PC" warning the first time. Click **More info → Run
anyway**. This is normal for any small, unsigned program and does not mean
anything is wrong.

---

## B. Windows Server (from source)

### 1. Install Python (once)
Download Python 3.12 from https://www.python.org/downloads/ and run the
installer. **Tick "Add python.exe to PATH"** on the first screen.

### 2. Get the code
Either `git clone` the repository, or on GitHub click **Code → Download ZIP**
and extract it to `C:\itam`.

### 3. Install and start (Command Prompt)
```bat
cd C:\itam
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

rem optional sample data to explore first:
flask --app app seed

rem start the website (waitress = production server for Windows):
.venv\Scripts\waitress-serve --host=0.0.0.0 --port=8080 app:app
```

The site is now live at `http://localhost:8080` on the server and
`http://SERVER-IP:8080` from every other device.

### 4. Open the firewall port (once, as Administrator)
```bat
netsh advfirewall firewall add rule name="AMS" dir=in action=allow protocol=TCP localport=8080
```

### 5. Start automatically with Windows
Simplest reliable way — Task Scheduler:
1. Create `C:\itam\start-ams.bat` containing:
   ```bat
   cd /d C:\itam
   .venv\Scripts\waitress-serve --host=0.0.0.0 --port=8080 app:app
   ```
2. Open **Task Scheduler → Create Task**:
   - General: "Run whether user is logged on or not"
   - Triggers: **At startup**
   - Actions: Start a program → `C:\itam\start-ams.bat`
3. Reboot once to confirm the site comes back by itself.

---

## C. Linux server (Ubuntu/Debian)

### 1. Install and start
```bash
sudo apt update && sudo apt install -y python3-venv git
sudo git clone https://github.com/laithyahya2022-code/IT-Asset-Management-System-.git /opt/itam
cd /opt/itam
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.txt
sudo .venv/bin/flask --app app seed        # optional sample data
```

### 2. Run as a system service (starts on boot)
```bash
sudo tee /etc/systemd/system/itam.service > /dev/null <<'EOF'
[Unit]
Description=Mada AMS
After=network.target

[Service]
WorkingDirectory=/opt/itam
Environment=SECRET_KEY=CHANGE-THIS-TO-A-LONG-RANDOM-STRING
ExecStart=/opt/itam/.venv/bin/gunicorn --bind 0.0.0.0:8080 --workers 3 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now itam
```

Check it: `systemctl status itam` → the site is at `http://SERVER-IP:8080`.

---

## D. Docker (any OS)

If the server already runs Docker, this is the shortest path and uses
PostgreSQL (better for many simultaneous users):

```bash
git clone https://github.com/laithyahya2022-code/IT-Asset-Management-System-.git
cd IT-Asset-Management-System-
cp .env.example .env          # edit: set SECRET_KEY and DB_PASSWORD
docker compose up -d
```

Site: `http://SERVER-IP:8000`. Data survives restarts (named volumes).

---

## After installation

### First login — do this immediately
1. Open the site and log in: **admin / admin123**
2. Go to **Profile → Change password** and set a strong password.
3. **Users → + New user** — create accounts for your team. Give most people
   the `technician` or `viewer` role; keep `admin` for 1–2 people.
4. **Settings** — set your school's name, and (optionally) SMTP email for
   alert notifications.

### Shared data — how it works
All data lives in one database **on the server**
(`instance/itam.sqlite`, or PostgreSQL under Docker). Every browser session
reads and writes that same database — when one person checks out a laptop,
everyone sees it instantly. Nothing is stored on users' devices.

### Backups
- In the app: **Settings → Backups → Create backup now**, then Download and
  keep a copy on a different machine. Restore from the same page.
- Or copy the file `instance/itam.sqlite` while the service is stopped.
- Docker/PostgreSQL: `docker compose exec db pg_dump -U itam itam > backup.sql`

### Updating to a new version
```bash
cd /opt/itam            # or C:\itam
git pull
.venv/bin/pip install -r requirements.txt    # Windows: .venv\Scripts\pip
sudo systemctl restart itam                  # Windows: restart the scheduled task
```

### Friendly address (optional, still free)
Ask whoever manages the school DNS to point a name like `itam.school.local`
at the server's IP — then everyone uses `http://itam.school.local:8080`.

### Phones and tablets
The site is responsive and installable: open it in Chrome/Safari on a phone
→ menu → **Add to Home Screen** → it behaves like an app, same shared data.
