import os
from dataclasses import dataclass, field, replace
from pathlib import Path

PIA_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(PIA_ROOT / ".env")
except ImportError:
    pass


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


MB = 1024 * 1024


@dataclass(frozen=True)
class Limits:
    max_download_bytes: int = _int("PIA_MAX_DOWNLOAD_MB", 60) * MB
    max_repo_download_bytes: int = _int("PIA_MAX_REPO_DOWNLOAD_MB", 120) * MB
    max_extract_bytes: int = _int("PIA_MAX_EXTRACT_MB", 300) * MB
    max_file_bytes: int = _int("PIA_MAX_FILE_MB", 25) * MB
    max_files: int = _int("PIA_MAX_FILES", 20000)
    max_compression_ratio: int = 120
    max_metadata_bytes: int = 40 * MB
    max_text_analysis_bytes: int = 2 * MB
    http_timeout: int = _int("PIA_HTTP_TIMEOUT", 30)
    git_timeout: int = _int("PIA_GIT_TIMEOUT", 40)


@dataclass(frozen=True)
class Settings:
    limits: Limits = field(default_factory=Limits)
    http_retries: int = 3
    min_request_interval: float = 0.25
    user_agent: str = "PIA-PackageIntegrityAnalyzer/1.0 (+security research; read-only)"
    ai_provider: str = os.environ.get("PIA_AI_PROVIDER", "groq").lower()
    ai_model: str = os.environ.get("PIA_AI_MODEL", "")
    groq_api_key: str = os.environ.get("GROQ_API_KEY", "")
    openrouter_api_key: str = os.environ.get("OPENROUTER_API_KEY", "")
    ai_timeout: int = 45
    sqlite_path: str = os.environ.get("PIA_SQLITE_PATH", str(PIA_ROOT / "pia.sqlite3"))
    samples_dir: Path = PIA_ROOT / "sample_data"

    def with_limits(self, **kw) -> "Settings":
        return replace(self, limits=replace(self.limits, **kw))


def get_settings() -> Settings:
    return Settings()
