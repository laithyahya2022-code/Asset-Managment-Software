from datetime import datetime, timedelta

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)

from ..models import User, db
from ..security import login_required, new_token
from ..utils import log_activity, send_email

bp = Blueprint("auth", __name__)


#: Failed sign-ins, keyed by username and by client address. The login form
#: accepted unlimited guesses, which is only survivable while the app is
#: unreachable from anywhere interesting. One process serves the whole school,
#: so in-memory is enough and costs nothing.
_FAILURES = {}
MAX_ATTEMPTS = 8            # per key, within the window
ATTEMPT_WINDOW = 300        # 5 minutes
LOCKOUT_SECONDS = 900       # 15 minutes


def _now():
    import time
    return time.monotonic()


def _locked_for(keys):
    """Seconds remaining before these keys may try again, 0 if they may now."""
    worst = 0
    for key in keys:
        entry = _FAILURES.get(key)
        if entry and entry["until"] > _now():
            worst = max(worst, int(entry["until"] - _now()))
    return worst


def _record_failure(keys):
    now = _now()
    for key in keys:
        entry = _FAILURES.get(key)
        if not entry or now - entry["first"] > ATTEMPT_WINDOW:
            entry = {"count": 0, "first": now, "until": 0}
        entry["count"] += 1
        if entry["count"] >= MAX_ATTEMPTS:
            entry["until"] = now + LOCKOUT_SECONDS
            entry["count"] = 0
            entry["first"] = now
        _FAILURES[key] = entry
    # Keep the table from growing without bound on a long-running server.
    if len(_FAILURES) > 5000:
        for key, entry in list(_FAILURES.items()):
            if entry["until"] < now and now - entry["first"] > ATTEMPT_WINDOW:
                _FAILURES.pop(key, None)


def _clear_failures(keys):
    for key in keys:
        _FAILURES.pop(key, None)


def _attempt_keys(username):
    return (f"u:{username}", f"ip:{request.remote_addr or '?'}")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        keys = _attempt_keys(username)
        wait = _locked_for(keys)
        if wait:
            flash(f"Too many failed sign-ins. Try again in {wait // 60 + 1} minute(s).",
                  "error")
            return render_template("auth/login.html")
        user = db.session.scalar(db.select(User).where(
            db.func.lower(User.username) == username))
        if user and user.active and user.check_password(request.form["password"]):
            _clear_failures(keys)
            session.clear()
            session["uid"] = user.id
            # A browser-session cookie (no expiry): closing the browser signs
            # the user out, so the next person on a shared device lands on the
            # welcome screen and must sign in again — not on the last session.
            session.permanent = False
            user.last_login = datetime.utcnow()
            g.user = user
            log_activity("login", "user", user.id)
            db.session.commit()
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") else url_for("main.dashboard"))
        _record_failure(keys)
        flash("Invalid username or password.", "error")
    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    log_activity("logout", "user", g.user.id)
    db.session.commit()
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    """Email a reset link. Never show one on screen.

    This used to print the link straight into the page whenever SMTP was not
    configured -- which is the default -- so anyone who could guess a staff
    email address could take over that account without knowing any password.
    It also said whether an account existed, which hands out a list of valid
    logins to anyone who asks.

    Both are fixed here: the reply is identical either way, and the link only
    ever leaves by email. With no SMTP set up, an administrator sets the
    password directly on the Users screen instead.
    """
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        keys = (f"forgot:{email}", f"ip:{request.remote_addr or '?'}")
        if not _locked_for(keys):
            user = db.session.scalar(db.select(User).where(User.email == email))
            if user and user.active:
                user.reset_token = new_token()
                user.reset_expires = datetime.utcnow() + timedelta(hours=2)
                db.session.commit()
                link = url_for("auth.reset", token=user.reset_token, _external=True)
                send_email("Password reset", f"Reset your password: {link}",
                           to=user.email)
            _record_failure(keys)      # rate-limit the probe either way
        flash("If that email address has an account, a reset link has been sent "
              "to it. If your school has no email server configured, ask an "
              "administrator to set your password.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html", link=None)


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    user = db.session.scalar(db.select(User).where(User.reset_token == token))
    if not user or not user.reset_expires or user.reset_expires < datetime.utcnow():
        flash("This reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        pw = request.form["password"]
        if len(pw) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif pw != request.form["confirm"]:
            flash("Passwords do not match.", "error")
        else:
            user.set_password(pw)
            user.reset_token = None
            log_activity("password_reset", "user", user.id)
            db.session.commit()
            flash("Password updated — log in with your new password.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", token=token)


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        if request.form.get("form") == "password":
            if not g.user.check_password(request.form["current"]):
                flash("Current password is incorrect.", "error")
            elif len(request.form["password"]) < 8:
                flash("New password must be at least 8 characters.", "error")
            elif request.form["password"] != request.form["confirm"]:
                flash("Passwords do not match.", "error")
            else:
                g.user.set_password(request.form["password"])
                log_activity("password_change", "user", g.user.id)
                db.session.commit()
                flash("Password changed.", "success")
        else:
            g.user.name = request.form["name"].strip()
            g.user.email = request.form["email"].strip().lower()
            db.session.commit()
            flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html")
