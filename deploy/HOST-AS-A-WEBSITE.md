# Host AMS as a website on your own server

Goal: people open a **name** in their browser — like `https://itam.madaacademy.edu.jo`
or `http://itam` — and sign in. Everything stays on **your own on-premise
server**; no cloud, no monthly app fee.

There are three layers. Pick the depth you need.

```
   Staff device                      Your server (on-prem)
   ┌───────────┐   types a name   ┌──────────────────────────┐
   │  browser  │ ───────────────► │  Caddy / IIS (name+HTTPS) │
   │  or phone │                  │            │              │
   └───────────┘                  │            ▼              │
                                  │   AMS app on :8080        │
                                  │   (one shared database)   │
                                  └──────────────────────────┘
```

---

## 1. Install it on the server (one command, five minutes)

Download **AMS-Server-Setup.zip** from the releases page onto the server,
unzip it, then right-click **Install-AMS.bat** and choose *Run as
administrator*.

That is the whole installation. It:

- installs to `C:\AMS` — a fixed location, never a Downloads folder;
- registers a scheduled task so AMS **starts automatically at boot**, with no
  window and nobody logged in;
- opens the Windows firewall for port 8080 on domain and private networks;
- restarts AMS by itself if it ever stops;
- prints the one address everyone else uses, and saves it to
  `C:\AMS\AMS - open on other devices.txt`.

```
  Done.

  Everyone opens:  http://192.168.100.204:8080
  First login:     admin / admin123  (change it immediately)
  Data folder:     C:\AMS\instance
```

**Upgrading:** download the new zip and run `Install-AMS.bat` again. It stops
the service, swaps the executable and starts it back up. Your `instance`
folder — database, uploads, backups, session key — is never written to.

**Removing it:** `Uninstall-AMS.ps1` removes the service, firewall rule and
program, and deliberately **leaves your data** in `C:\AMS\instance` so an
uninstall can never lose it.

> **Back up `C:\AMS\instance`.** That folder is the entire system. Everything
> else is replaceable in one download.

### The one rule

**One installation = one database.** Copying `AMS.exe` to a second computer
does not copy your data — it creates a second, empty system, and the two never
merge. Only the server runs the program; everyone else opens the address in a
browser. That includes phones for QR scanning.

### Doing it by hand instead

If you'd rather not use the installer, run AMS headless yourself:

```bat
set AMS_NO_BROWSER=1
set PORT=8080
AMS.exe
```

and start that at boot however you prefer (Task Scheduler, NSSM). On Linux:
`AMS_NO_BROWSER=1 PORT=8080 python run_server.py` under systemd.

AMS answers on `http://SERVER-IP:8080` either way.

## 2. Give it a name people type

**A. Inside the school only (free, no internet needed)**
Add a record in your **internal DNS** (or every device's hosts file)
pointing a name at the server's LAN IP:

```
itam.madaacademy.edu.jo   →   192.168.100.204
```

Now staff type `http://itam.madaacademy.edu.jo:8080`. To drop the `:8080`, put Caddy
in front (step 3) and proxy port 80/443 to 8080.

**B. A public domain you own (reachable off-campus)**
In your domain's DNS, add an **A record**:

```
itam.madaacademy.edu.jo   →   <your school's public IP>
```

On the router/firewall, **forward ports 80 and 443** to the server. Then use
Caddy (step 3) for automatic HTTPS.

## 3. Add the name + HTTPS with Caddy (recommended)

[Caddy](https://caddyserver.com/download) is a single free file and gets a
trusted HTTPS certificate automatically.

1. Put the `Caddyfile` from this folder next to `caddy.exe`, edit the domain.
2. Keep AMS running from step 1 on `127.0.0.1:8080`.
3. Run `caddy run` (or install it as a service).

Staff now open `https://itam.madaacademy.edu.jo` and sign in. Done.

> AMS already trusts the proxy's forwarded headers (`AMS_BEHIND_PROXY=1`
> by default), so links and redirects use the right `https://name` address.

## 4. "Install as an app" (PWA)

Once the site loads over the name, any device can add it as an app:

- **Android / Chrome / Edge:** a browser prompt offers **Install AMS**, or use
  the ⋮ menu → *Install app / Add to Home screen*.
- **iPhone / Safari:** Share → **Add to Home Screen**.
- **Windows / Edge:** address-bar **Install** icon.

It gets the green AMS icon and opens full-screen straight to the sign-in
page — a real app, backed by your on-prem server.

---

### Checklist
- [ ] AMS runs as a service on the server (`AMS_NO_BROWSER=1`)
- [ ] A DNS name points at the server (internal or public)
- [ ] Ports forwarded (only if public) and Caddy running for HTTPS
- [x] Session key — generated automatically per installation and kept in
      `instance/secret_key`. Nothing to set. (Override with a `SECRET_KEY`
      environment variable only if you manage secrets centrally.)
- [ ] Admin password changed from the default
- [ ] Backups: the `instance/backups` folder is copied off-site regularly
