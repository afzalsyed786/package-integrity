from .base import AnalysisContext, Detector, FileContext
from .code_behavior import CredentialAccessDetector, DynamicExecDetector, NetworkDetector, ProcessExecDetector
from .artifacts import BytecodeDetector, ManifestIntegrityDetector, UntrackedFileDetector
from .install_hooks import InstallHookDetector
from .payloads import EncodedPayloadDetector, HighEntropyDetector, ObfuscationDetector
from .provenance import ProvenanceDetector
from .semantic import SemanticChangeDetector
from .sourcemaps import SourceMapDetector


def default_detectors() -> list[Detector]:
    return [
        ProvenanceDetector(), InstallHookDetector(), DynamicExecDetector(), ProcessExecDetector(), NetworkDetector(),
        CredentialAccessDetector(), EncodedPayloadDetector(), HighEntropyDetector(), ObfuscationDetector(),
        UntrackedFileDetector(), ManifestIntegrityDetector(), BytecodeDetector(), SourceMapDetector(), SemanticChangeDetector(),
    ]


__all__ = ["AnalysisContext", "Detector", "FileContext", "default_detectors"]
