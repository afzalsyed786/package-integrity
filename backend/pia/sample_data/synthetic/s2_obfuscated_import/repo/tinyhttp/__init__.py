"""tinyhttp — minimal HTTP helpers (PIA synthetic demo package)."""
from .client import get_json
from .utils import safe_math

__version__ = "0.9.1"
__all__ = ["get_json", "safe_math"]
