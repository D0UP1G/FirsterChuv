import os
from dataclasses import replace

from django.test import TransactionTestCase, tag

from backend.apps.common.contracts import TrustedJudgeJob
from backend.apps.judge.provider import LocalJudge
from backend.apps.problems.bundle import parse_problem_bundle
from backend.apps.problems.catalog import DjangoProblemCatalog
from backend.apps.problems.compilers import COMPILERS
from backend.apps.problems.storage import store_bundle
from backend.apps.problems.tests.bundle_fixtures import make_bundle_archive
from backend.apps.judge.runner import DockerRunner

REAL_SMOKE_ENABLED = os.getenv("FIRSTERCHUV_REAL_JUDGE_SMOKE") == "1"
TEST_VERIFIED_COMPILERS = {"cpp20": replace(COMPILERS["cpp20"], verified=True)}


@tag("real_smoke")
class LocalJudgeDockerSmokeTests(TransactionTestCase):
    """Opt-in integration test; executes only through the actual Docker runner."""

    databases = {"default"}

    def test_programmatically_imported_bundle_gets_real_ok_verdict(self):
        bundle = parse_problem_bundle(make_bundle_archive())
        store_bundle(bundle, compiler_registry=TEST_VERIFIED_COMPILERS)
        catalog = DjangoProblemCatalog(compiler_registry=TEST_VERIFIED_COMPILERS)
        provider = LocalJudge(
            catalog,
            compiler_registry=TEST_VERIFIED_COMPILERS,
            sandbox=DockerRunner(),
        )
        result = provider.execute(
            TrustedJudgeJob(
                submission_id=bundle.problem_id,
                source=(
                    "#include <iostream>\n"
                    "int main() { int a, b; if (!(std::cin >> a >> b)) return 1; "
                    "std::cout << a + b << '\\n'; return 0; }\n"
                ),
                language_id="cpp20",
                problem_id=bundle.problem_id,
                problem_version=bundle.version,
                problem_checksum=bundle.checksum,
            )
        )
        self.assertEqual(result.verdict, "OK")


if not REAL_SMOKE_ENABLED:
    LocalJudgeDockerSmokeTests.__unittest_skip__ = True
    LocalJudgeDockerSmokeTests.__unittest_skip_why__ = (
        "set FIRSTERCHUV_REAL_JUDGE_SMOKE=1 after building the pinned sandbox image"
    )
