# Working on AMS in Visual Studio Code

How to open this project on your own computer, run it, make changes, and
publish updates to GitHub — where the school server picks them up.

## One-time setup (about 10 minutes)

1. **Install the free tools**
   - [Visual Studio Code](https://code.visualstudio.com)
   - [Git for Windows](https://git-scm.com/download/win)
   - [Python 3.12](https://www.python.org/downloads/) — tick
     **"Add python.exe to PATH"** during install.

2. **Get the project**
   - Open VS Code → press **Ctrl+Shift+P** → type `Git: Clone` → Enter
   - Paste: `https://github.com/laithyahya2022-code/IT-Asset-Management-System-.git`
   - Pick a folder, then click **Open** when it finishes.
   - VS Code will suggest the Python extension — click **Install**.

3. **Install the project's dependencies**
   Open the terminal (**Ctrl+`**) and run:
   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   flask --app app seed
   ```
   (When VS Code asks "select this environment?", say yes.)

## Daily use

- **Run the app:** press **F5** (or Run → Start Debugging) →
  open http://127.0.0.1:5000 → log in with `admin / admin123`.
  Edit any file, save, refresh the browser — you see your change instantly.
- **Run the tests:** in the terminal, `pytest` — all green means safe to publish.

## Publishing an update (Edit → Commit → Push)

1. Make your change and check it works (F5 + browser, then `pytest`).
2. Click the **Source Control** icon in the left bar (the branching symbol).
3. Type a short message describing the change, e.g. `Fix warranty date on report`.
4. Click **✓ Commit**, then **Sync Changes** (this pushes to GitHub).

Your update is now the official version on GitHub.

## Getting updates onto the school server

On the server (from DEPLOYMENT.md):
```bash
git pull
pip install -r requirements.txt   # only needed if requirements changed
# restart the itam service / scheduled task
```

## Getting other people's updates onto your computer

Click **Source Control → … → Pull** (or run `git pull`). Do this before you
start editing so you're working on the latest version.

## Golden rules

- **Pull before you edit, test before you push.**
- Never edit files directly on the server — always change them here,
  push to GitHub, and pull on the server. GitHub stays the single source
  of truth, and every version can be restored.
