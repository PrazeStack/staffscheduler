import click
from werkzeug.security import generate_password_hash
from flask.cli import with_appcontext

from .extensions import db
from .models import Admin


@click.command("create-admin")
@click.argument("email")
@click.argument("full_name")
@click.password_option()
@with_appcontext
def create_admin(email, full_name, password):
    """Create an admin user."""
    existing = Admin.query.filter_by(email=email).first()
    if existing:
        click.echo("Admin already exists.")
        return

    admin = Admin(
        email=email,
        full_name=full_name,
        password_hash=generate_password_hash(password),
    )
    db.session.add(admin)
    db.session.commit()
    click.echo(f"Admin created: {email}")


@click.command("set-admin-password")
@click.argument("email")
@click.password_option()
@with_appcontext
def set_admin_password(email, password):
    """Reset an admin password."""
    admin = Admin.query.filter_by(email=email).first()
    if not admin:
        click.echo("Admin not found.")
        return

    admin.password_hash = generate_password_hash(password)
    db.session.commit()
    click.echo("Password updated.")