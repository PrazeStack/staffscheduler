from flask import render_template
from flask_login import login_required
from . import main_bp

@main_bp.route("/debug/db")
def debug_db():
    from flask import current_app
    return current_app.config["SQLALCHEMY_DATABASE_URI"]

@main_bp.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html")