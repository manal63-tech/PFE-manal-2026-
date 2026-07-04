"""Machine-learning artifact loading.

Wraps the trained scaler / isolation-forest and the persisted feature metadata
in a small bundle that is loaded lazily on first use. Lazy loading keeps the
heavy joblib / scikit-learn import out of the application-factory import path
(so migrations can run without those dependencies installed).
"""
import joblib

from .config import Config


class ModelBundle:
    """Container for the trained ML artifacts."""

    def __init__(self, model_dir):
        self.scaler = joblib.load(model_dir / "scaler.pkl")
        self.iso_model = joblib.load(model_dir / "isolation_forest.pkl")
        self.temp_col = joblib.load(model_dir / "temp_col.pkl")
        self.features = joblib.load(model_dir / "features.pkl")


_bundle = None


def get_bundle():
    """Return the process-wide :class:`ModelBundle`, loading it on first call."""
    global _bundle
    if _bundle is None:
        _bundle = ModelBundle(Config.MODEL_DIR)
    return _bundle
