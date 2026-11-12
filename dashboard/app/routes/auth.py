"""Login, registration and logout."""

from __future__ import annotations

from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User, utcnow
from ..validators import ValidationError, validate_registration

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _safe_next(target: str | None) -> str:
    """Only allow relative redirects to prevent open-redirect attacks."""
    if target and urlparse(target).netloc == "" and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("main.dashboard")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        identifier = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier.lower())
        ).first()
        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get("remember")))
            user.last_login_at = utcnow()
            db.session.commit()
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(_safe_next(request.args.get("next")))
        flash("Invalid username/email or password.", "danger")
        return render_template("auth/login.html", username=identifier), 401

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    errors: dict[str, str] = {}
    if request.method == "POST":
        try:
            data = validate_registration(request.form)
            if User.query.filter_by(username=data["username"]).first():
                errors["username"] = "This username is already taken."
            if User.query.filter_by(email=data["email"]).first():
                errors["email"] = "An account with this email already exists."
            if not errors:
                user = User(username=data["username"], email=data["email"])
                user.set_password(data["password"])
                db.session.add(user)
                db.session.commit()
                flash("Account created. You can sign in now.", "success")
                return redirect(url_for("auth.login"))
        except ValidationError as exc:
            errors = exc.errors
        return render_template("auth/register.html", errors=errors, form=request.form), 400

    return render_template("auth/register.html", errors=errors, form={})


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
