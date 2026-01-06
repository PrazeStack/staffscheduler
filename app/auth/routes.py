from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from . import auth_bp
from ..models import Admin

@auth_bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("auth/login.html")

@auth_bp.post("/login")
def login_post():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    admin = Admin.query.filter_by(email=email, is_active=True).first()
    if not admin or not admin.check_password(password):
        flash("Invalid email or password.", "danger")
        return redirect(url_for("auth.login"))

    login_user(admin)
    return redirect(url_for("main.dashboard"))

@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))