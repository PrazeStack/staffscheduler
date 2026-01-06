from flask import Blueprint

main_bp = Blueprint("main", __name__)

from . import routes  # IMPORTANT: loads routes so endpoint exists