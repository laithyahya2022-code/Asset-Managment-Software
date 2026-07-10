from datetime import datetime, timedelta

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)

from ..models import User, db
from ..security import login_required, new_token
from ..utils import log_activity, send_email

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        user = db.session.scalar(db.select(User).where(
            db.func.lower(User.username) == request.form["username"].strip().lower()))
        if user and user.active and user.check_password(request.form["password"]):
            session.clear()
            session["uid"] = user.id
            session.permanent = True
            user.last_login = datetime.utcnow()
            g.user = user
            log_activity("login", "user", user.id)
            db.session.commit()
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") else url_for("main.dashboard"))
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
    link = None
    if request.method == "POST":
        user = db.session.scalar(db.select(User).where(
            User.email == request.form["email"].strip().lower()))
        if user:
            user.reset_token = new_token()
            user.reset_expires = datetime.utcnow() + timedelta(hours=2)
            db.session.commit()
            link = url_for("auth.reset", token=user.reset_token, _external=True)
            if send_email("Password reset", f"Reset your password: {link}", to=user.email):
                flash("A reset link was emailed to you.", "success")
                link = None
            else:
                flash("Email is not configured — use the link below (valid 2 hours).", "success")
        else:
            flash("No account found with that email.", "error")
    return render_template("auth/forgot.html", link=link)


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
