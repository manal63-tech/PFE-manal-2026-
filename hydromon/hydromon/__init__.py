"""Hydromon — hydroponic monitoring application package.

Exposes an application factory (:func:`create_app`) that wires together
configuration, the database, migrations and the route blueprints.
"""
from flask import Flask

from .config import Config
from .extensions import db, migrate


def create_app(config_class: type[Config] = Config) -> Flask:
    """Application factory.

    Heavy modules (pandas / scikit-learn / the ML bundle) are intentionally
    imported lazily inside the request path so that lightweight tooling such
    as ``flask db`` migration commands can import the app without those
    dependencies installed.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialise extensions.
    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so that they are registered with SQLAlchemy / Alembic.
    from . import db_models  # noqa: F401

    # Register blueprints.
    from .routes.dashboard import dashboard_bp
    from .routes.api import api_bp
    from .services import start_export_scheduler

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)

    if app.config.get("ENABLE_EXPORT_SCHEDULER", True):
        start_export_scheduler(app)

    return app
