import uuid
from dataclasses import asdict, dataclass, field

SEVERITIES = ["info", "low", "medium", "high", "critical"]
SEVERITY_BASE = {"info": 0, "low": 8, "medium": 22, "high": 45, "critical": 75}


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def downgrade(sev: str) -> str:
    return SEVERITIES[max(0, SEVERITIES.index(sev) - 1)]


def upgrade(sev: str) -> str:
    return SEVERITIES[min(len(SEVERITIES) - 1, SEVERITIES.index(sev) + 1)]


@dataclass
class Finding:
    rule_id: str
    title: str
    category: str
    severity: str
    confidence: float
    reason: str
    evidence: str = ""
    file: str | None = None
    line: int | None = None
    context: dict = field(default_factory=dict)
    id: str = field(default_factory=new_id)
    score: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FileRecord:
    path: str
    status: str  # identical | modified | package_only | repo_only | expected
    kind: str
    size: int = 0
    pkg_sha256: str | None = None
    repo_sha256: str | None = None
    repo_path: str | None = None
    expected_reason: str | None = None
    original_status: str | None = None
    normalized: bool = False
    risk_score: int = 0
    finding_count: int = 0
    has_detail: bool = False
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return asdict(self)
