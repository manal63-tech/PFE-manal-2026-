"""Dashboard (HTML) routes."""
from flask import Blueprint, render_template

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/", methods=["GET"])
def dashboard():
    return render_template("index.html")
