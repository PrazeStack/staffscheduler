from flask import Blueprint

recurring_requests_bp = Blueprint("recurring_requests", __name__, url_prefix="/recurring-requests")

from . import routes  # noqa: F401