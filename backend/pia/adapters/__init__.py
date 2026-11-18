"""Adapter registry. Register a new ecosystem by adding an EcosystemAdapter subclass to ADAPTER_CLASSES."""
from .base import AnalysisInputError, EcosystemAdapter, ReleaseInfo
from .npm import NpmAdapter
from .pypi import PyPIAdapter
from .synthetic import SyntheticAdapter

ADAPTER_CLASSES = {"pypi": PyPIAdapter, "npm": NpmAdapter}


def build_adapters(http, settings) -> dict[str, EcosystemAdapter]:
    adapters = {name: cls(http, settings) for name, cls in ADAPTER_CLASSES.items()}
    adapters["synthetic"] = SyntheticAdapter(http, settings, delegates=dict(adapters))
    return adapters


__all__ = ["AnalysisInputError", "EcosystemAdapter", "ReleaseInfo", "build_adapters", "ADAPTER_CLASSES"]
