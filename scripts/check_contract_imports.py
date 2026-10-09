"""Verify common v1 ports import without optional domain applications."""

from __future__ import annotations

import importlib.abc
import sys


OPTIONAL_APPS = (
    "backend.apps.competition",
    "backend.apps.events",
    "backend.apps.judge",
    "backend.apps.problems",
    "backend.apps.submissions",
    "backend.apps.drafts",
)


class BlockOptionalApps(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if any(fullname == root or fullname.startswith(f"{root}.") for root in OPTIONAL_APPS):
            raise ModuleNotFoundError(f"optional app import blocked: {fullname}")
        return None


sys.meta_path.insert(0, BlockOptionalApps())

from backend.apps.common import contracts  # noqa: E402


required_contracts = (
    "AttemptReceipt",
    "CompetitionGatewayV1",
    "EventWriter",
    "InfrastructureFailureReceipt",
    "InfrastructureFailureSink",
    "JudgeInfrastructureError",
    "JudgeProvider",
    "JudgeResult",
    "LanguageRegistry",
    "LanguageDescriptor",
    "ProblemBundleV1",
    "ProblemCatalogV1",
    "ProblemSummaryV1",
    "PublicAccessV1",
    "PublicAccessContext",
    "ResultApplication",
    "ResultReceipt",
    "RunProblemSnapshot",
    "RunProblemSnapshotProvider",
    "TrustedJudgeJob",
    "WorkspaceContext",
)
missing = [name for name in required_contracts if not hasattr(contracts, name)]
if missing:
    raise SystemExit(f"Missing common contracts: {', '.join(missing)}")

print("common v1 contracts import without optional domain apps")
