from flask import Flask
from flask_migrate import Migrate
from flask_login import LoginManager
import os

from .extensions import db
from .models import Admin


def create_app():
    app = Flask(__name__)

    # ------------------
    # Config
    # ------------------
    db_url = os.getenv("DATABASE_URL", "").strip()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url or "sqlite:///staff_scheduler.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")

    # ------------------
    # Extensions
    # ------------------
    db.init_app(app)
    Migrate(app, db)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return Admin.query.get(int(user_id))

    # ------------------
    # Blueprints
    # ------------------
    from .auth import auth_bp
    from .main import main_bp
    from .staff import staff_bp
    from .units import units_bp
    from .assignments import assignments_bp
    from .requests import requests_bp
    from .schedule import schedule_bp
    from .recurring_requests import recurring_requests_bp
    from .recurring_assignments import recurring_assignments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(units_bp)
    app.register_blueprint(assignments_bp)
    app.register_blueprint(requests_bp)
    app.register_blueprint(schedule_bp, url_prefix="/schedule")
    app.register_blueprint(recurring_requests_bp)
    app.register_blueprint(recurring_assignments_bp)

    # ------------------
    # CLI Commands (ADMIN ONLY)
    # ------------------
    from .cli import create_admin
    app.cli.add_command(create_admin)

    return app