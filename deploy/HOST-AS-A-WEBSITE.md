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

## 1. Run AMS as a background service (no window)

On the server, run AMS headless so it just serves and never opens a window:

- **Windows:** create a file `start-ams.bat` next to `AMS.exe`:
  ```bat
  set AMS_NO_BROWSER=1
  set PORT=8080
  set SECRET_KEY=change-this-to-a-long-random-string
  AMS.exe
  ```
  Run it, or install it as a service with NSSM so it starts on boot
  (`nssm install AMS "C:\ams\start-ams.bat"`).

- **Linux:** run `AMS_NO_BROWSER=1 PORT=8080 python run_server.py` under
  systemd or `pm2` so it restarts automatically.

AMS now answers on `http://SERVER-IP:8080`. That already works for every
device on the network — this is the whole point: **only the server runs the
program, everyone else just opens the address.**

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
- [ ] `SECRET_KEY` set to a long random value
- [ ] Admin password changed from the default
- [ ] Backups: the `instance/backups` folder is copied off-site regularly
