"""Real loopback API smoke on disposable SQLite; not full M0 acceptance."""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime, timedelta
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPCookieProcessor,
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)
from uuid import uuid4
from wsgiref.simple_server import WSGIRequestHandler, make_server

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASE_IDS = tuple(f"T{number:02d}" for number in range(1, 22))
GATE_REASONS = {
    "G01": "Не проверены полный one-command runtime и normalized import.",
    "G02": "Проверены auth/invite/bracket slices; run config и private submit access не проверялись.",
    "G03": "Production worker, isolated verdict и durable result/failure chain не запускались.",
    "G04": "Clock, draft, live score, winner и browser path не проверялись.",
    "G05": "Полный hostile/restart/privacy gate не запускался; sandbox probe только synthetic.",
    "G06": "Public spectator snapshot и SSE не проверялись.",
}


class SmokeFailure(Exception):
    def __init__(
        self,
        code: str,
        *,
        check_id: str | None = None,
        status: int | None = None,
        api_code: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.check_id = check_id
        self.status = status
        self.api_code = api_code


class ApiResponse:
    def __init__(self, status: int, payload: Any, headers: dict[str, str]) -> None:
        self.status = status
        self.payload = payload
        self.headers = headers


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class QuietHandler(WSGIRequestHandler):
    """Invitation URLs contain bearer tokens, so never log request paths."""

    def log_message(self, format: str, *args: Any) -> None:
        return


class Session:
    def __init__(self, base_url: str) -> None:
        opener = build_opener(
            ProxyHandler({}),
            HTTPCookieProcessor(CookieJar()),
            NoRedirect(),
        )
        self._open = opener.open
        self.base_url = base_url
        self.csrf_token: str | None = None

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        csrf: bool = False,
    ) -> ApiResponse:
        if not path.startswith("/") or path.startswith("//"):
            raise SmokeFailure("invalid_local_route")
        headers = {"Accept": "application/json"}
        payload = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body, separators=(",", ":")).encode()
        if csrf:
            if self.csrf_token is None:
                raise SmokeFailure("csrf_token_missing")
            headers["X-CSRFToken"] = self.csrf_token
        request = Request(
            f"{self.base_url}{path}",
            data=payload,
            headers=headers,
            method=method,
        )
        try:
            with self._open(request, timeout=4) as response:
                status, data = response.status, response.read()
                response_headers = dict(response.headers.items())
        except HTTPError as response:
            status, data = response.code, response.read()
            response_headers = dict(response.headers.items())
        except (OSError, URLError, TimeoutError):
            raise SmokeFailure("loopback_http_unreachable") from None
        try:
            parsed = json.loads(data) if data else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
        return ApiResponse(status, parsed, response_headers)

    def fetch_csrf(self) -> None:
        response = self.request("GET", "/api/v1/auth/csrf")
        payload = response.payload
        token = payload.get("csrfToken") if isinstance(payload, dict) else None
        if response.status != 200 or not isinstance(token, str) or not token:
            raise SmokeFailure("csrf_bootstrap_failed", status=response.status)
        self.csrf_token = token


def api_error_code(response: ApiResponse) -> str | None:
    payload = response.payload
    error = payload.get("error") if isinstance(payload, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    if isinstance(code, str) and re.fullmatch(r"[a-z0-9_]{1,48}", code):
        return code
    return None


def require_status(
    response: ApiResponse,
    expected: int | tuple[int, ...],
    check_id: str,
) -> dict[str, Any]:
    expected_statuses = (expected,) if isinstance(expected, int) else expected
    if response.status not in expected_statuses:
        raise SmokeFailure(
            "unexpected_http_status",
            check_id=check_id,
            status=response.status,
            api_code=api_error_code(response),
        )
    if not isinstance(response.payload, dict):
        raise SmokeFailure("unexpected_json_shape", check_id=check_id, status=response.status)
    return response.payload


def require(condition: bool, check_id: str, code: str) -> None:
    if not condition:
        raise SmokeFailure(check_id=check_id, code=code)


def passed(checks: list[dict[str, Any]], check_id: str, evidence: str) -> None:
    checks.append({"id": check_id, "status": "PASS", "evidence": evidence})


def api_scenario(
    base_url: str,
    checks: list[dict[str, Any]],
    admin_email: str,
    password: str,
) -> None:
    run_id = uuid4().hex
    probe = Session(base_url)
    probe.fetch_csrf()
    registration = {
        "email": f"csrf-{run_id}@example.test",
        "password": password,
        "displayName": "Disposable CSRF Probe",
    }

    require_status(
        probe.request("POST", "/api/v1/auth/register", body=registration),
        403,
        "api.registration_requires_csrf",
    )
    passed(checks, "api.registration_requires_csrf", "registration без CSRF отклонён (403)")

    probe.fetch_csrf()
    require_status(
        probe.request(
            "POST",
            "/api/v1/auth/register",
            body={**registration, "role": "admin"},
            csrf=True,
        ),
        400,
        "api.registration_rejects_role_assignment",
    )
    require_status(
        probe.request(
            "POST",
            "/api/v1/auth/login",
            body={"email": registration["email"], "password": password},
            csrf=True,
        ),
        401,
        "api.registration_rejects_role_assignment",
    )
    passed(
        checks,
        "api.registration_rejects_role_assignment",
        "role=admin отклонён; такой identity не проходит login",
    )

    admin = Session(base_url)
    admin.fetch_csrf()
    login = require_status(
        admin.request(
            "POST",
            "/api/v1/auth/login",
            body={"email": admin_email, "password": password},
            csrf=True,
        ),
        200,
        "api.disposable_admin_login",
    )
    require(login.get("role") == "admin", "api.disposable_admin_login", "admin_role_mismatch")
    require(
        isinstance(login.get("csrfToken"), str),
        "api.disposable_admin_login",
        "csrf_token_missing",
    )
    admin.csrf_token = login["csrfToken"]
    passed(checks, "api.disposable_admin_login", "временный application admin вошёл по HTTP")

    now = datetime.now(UTC).replace(microsecond=0)
    tournament = require_status(
        admin.request(
            "POST",
            "/api/v1/tournaments",
            csrf=True,
            body={
                "title": f"Acceptance {run_id[:12]}",
                "description": "Disposable acceptance data",
                "startsAt": now.isoformat().replace("+00:00", "Z"),
                "endsAt": (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
                "format": "single_elimination",
                "participantLimit": 2,
                "visibility": "public",
                "matchDurationSec": 600,
                "startMode": "manual",
            },
        ),
        201,
        "api.admin_creates_tournament",
    )
    tournament_id = tournament.get("id")
    require(
        isinstance(tournament_id, str) and tournament.get("status") == "draft",
        "api.admin_creates_tournament",
        "tournament_response_mismatch",
    )
    passed(checks, "api.admin_creates_tournament", "application admin создал disposable турнир")

    invite = require_status(
        admin.request(
            "POST",
            f"/api/v1/tournaments/{tournament_id}/invites",
            csrf=True,
            body={
                "expiresAt": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                "maxUses": 2,
            },
        ),
        201,
        "api.admin_creates_bounded_invite",
    )
    token = invite.get("token")
    require(isinstance(token, str) and token, "api.admin_creates_bounded_invite", "token_missing")
    passed(
        checks,
        "api.admin_creates_bounded_invite",
        "ограниченный invite создан; bearer token используется только в памяти",
    )

    preview = Session(base_url).request("GET", f"/api/v1/invites/{token}")
    preview_body = require_status(preview, 200, "api.invite_preview_is_public_minimal")
    require(
        preview_body.get("valid") is True
        and set(preview_body) == {"tournament", "valid", "expiresAt"}
        and "no-store" in preview.headers.get("Cache-Control", "").lower()
        and preview.headers.get("Referrer-Policy", "").lower() == "no-referrer",
        "api.invite_preview_is_public_minimal",
        "preview_projection_or_headers_mismatch",
    )
    passed(
        checks,
        "api.invite_preview_is_public_minimal",
        "анонимный preview содержит только allowlisted поля и private headers",
    )

    participants: list[Session] = []
    for index in (1, 2):
        session = Session(base_url)
        email = f"participant-{index}-{run_id}@example.test"
        session.fetch_csrf()
        created = require_status(
            session.request(
                "POST",
                "/api/v1/auth/register",
                csrf=True,
                body={
                    "email": email,
                    "password": password,
                    "displayName": f"Disposable Player {index}",
                },
            ),
            201,
            "api.two_participant_sessions",
        )
        require(
            created.get("role") == "participant" and "password" not in created,
            "api.two_participant_sessions",
            "participant_registration_projection_mismatch",
        )
        session.fetch_csrf()
        login = require_status(
            session.request(
                "POST",
                "/api/v1/auth/login",
                csrf=True,
                body={"email": email, "password": password},
            ),
            200,
            "api.two_participant_sessions",
        )
        require(login.get("role") == "participant", "api.two_participant_sessions", "role_mismatch")
        session.csrf_token = login.get("csrfToken")
        require(bool(session.csrf_token), "api.two_participant_sessions", "csrf_token_missing")
        participants.append(session)
    require(participants[0] is not participants[1], "api.two_participant_sessions", "session_reused")
    passed(checks, "api.two_participant_sessions", "две participant identity вошли через отдельные sessions")

    for check_id, session in (
        ("api.participant_admin_write_denied", participants[0]),
        ("api.anonymous_admin_write_denied", probe),
    ):
        response = session.request("POST", "/api/v1/tournaments", body={}, csrf=True)
        require_status(response, (401, 403), check_id)
        evidence = (
            "participant не может создать tournament через admin API"
            if session is participants[0]
            else "анонимный клиент не может создать tournament"
        )
        passed(checks, check_id, evidence)

    accept_path = f"/api/v1/invites/{token}/accept"
    first = require_status(
        participants[0].request("POST", accept_path, body={}, csrf=True),
        200,
        "api.invite_accept_is_idempotent",
    )
    repeat = require_status(
        participants[0].request("POST", accept_path, body={}, csrf=True),
        200,
        "api.invite_accept_is_idempotent",
    )
    second = require_status(
        participants[1].request("POST", accept_path, body={}, csrf=True),
        200,
        "api.invite_accept_is_idempotent",
    )
    require(first == repeat and first != second, "api.invite_accept_is_idempotent", "join_mismatch")
    passed(checks, "api.invite_accept_is_idempotent", "повтор первого join не создал второй membership")

    bracket = require_status(
        admin.request(
            "POST",
            f"/api/v1/tournaments/{tournament_id}/bracket/generate",
            body={"seedingMode": "manual"},
            csrf=True,
        ),
        200,
        "api.two_player_bracket_generation",
    )
    matches = bracket.get("matches")
    require(
        bracket.get("bracketSize") == 2 and isinstance(matches, list) and len(matches) == 1,
        "api.two_player_bracket_generation",
        "bracket_shape_mismatch",
    )
    slots = matches[0].get("slots") if isinstance(matches[0], dict) else None
    entries = [slot.get("participant") for slot in slots if isinstance(slot, dict)] if isinstance(slots, list) else []
    require(
        len(entries) == 2
        and all(isinstance(entry, dict) for entry in entries)
        and entries[0].get("userId") != entries[1].get("userId"),
        "api.two_player_bracket_generation",
        "bracket_roster_mismatch",
    )
    passed(checks, "api.two_player_bracket_generation", "два участника получили один реальный bracket match")

    joined_bracket = require_status(
        participants[0].request("GET", f"/api/v1/tournaments/{tournament_id}/bracket"),
        200,
        "api.joined_participant_reads_bracket",
    )
    require(
        isinstance(joined_bracket.get("matches"), list)
        and len(joined_bracket["matches"]) == 1,
        "api.joined_participant_reads_bracket",
        "bracket_response_mismatch",
    )
    passed(checks, "api.joined_participant_reads_bracket", "joined participant прочитал bracket через HTTP")

    outsider = Session(base_url)
    outsider_email = f"outsider-{run_id}@example.test"
    outsider.fetch_csrf()
    require_status(
        outsider.request(
            "POST",
            "/api/v1/auth/register",
            body={
                "email": outsider_email,
                "password": password,
                "displayName": "Disposable Outsider",
            },
            csrf=True,
        ),
        201,
        "api.outsider_cannot_read_bracket",
    )
    outsider.fetch_csrf()
    outsider_login = require_status(
        outsider.request(
            "POST",
            "/api/v1/auth/login",
            body={"email": outsider_email, "password": password},
            csrf=True,
        ),
        200,
        "api.outsider_cannot_read_bracket",
    )
    outsider.csrf_token = outsider_login.get("csrfToken")
    require(bool(outsider.csrf_token), "api.outsider_cannot_read_bracket", "csrf_token_missing")
    require_status(
        outsider.request("GET", f"/api/v1/tournaments/{tournament_id}/bracket"),
        404,
        "api.outsider_cannot_read_bracket",
    )
    passed(checks, "api.outsider_cannot_read_bracket", "неучаствующий participant получил 404")


def repository_facts() -> dict[str, Any]:
    def git(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout.strip()

    return {
        "commitSha": git("rev-parse", "HEAD"),
        "baseSha": git("merge-base", "HEAD", "origin/develop"),
        "branch": git("branch", "--show-current"),
        "worktreeClean": git("status", "--porcelain", "--untracked-files=normal") == "",
    }


def new_report() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "taskId": "P4-08",
        "recordedAt": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": repository_facts(),
        "scope": "disposable-loopback-http-api-smoke",
        "smokeResult": "NOT_RUN",
        "checks": [],
        "sandboxProbe": {"status": "NOT_RUN", "reason": "Не запрошено."},
        "m0": {
            "status": "NOT_ACCEPTED",
            "gates": {
                gate: {"status": "NOT_RUN", "reason": GATE_REASONS[gate]}
                for gate in GATE_REASONS
            },
        },
        "fullCaseAcceptance": {
            case_id: {"status": "NOT_RUN"} for case_id in CASE_IDS
        },
    }


def temporary_environment(db_path: Path) -> dict[str, str | None]:
    values = {
        "DJANGO_SETTINGS_MODULE": "backend.config.settings",
        "DJANGO_DEBUG": "true",
        "DJANGO_REQUIRE_SECRET_KEY": "false",
        "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost",
        "CSRF_TRUSTED_ORIGINS": "http://127.0.0.1",
        "SQLITE_PATH": str(db_path),
        "SQLITE_TIMEOUT": "2",
    }
    previous = {key: os.environ.get(key) for key in (*values, "DJANGO_ADMIN_PASSWORD")}
    os.environ.update(values)
    return previous


def restore_environment(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def disposable_api(checks: list[dict[str, Any]]) -> None:
    with tempfile.TemporaryDirectory(prefix="firsterchuv-acceptance-") as directory:
        previous_env = temporary_environment(Path(directory) / "acceptance.sqlite3")
        previous_logging = logging.root.manager.disable
        server = thread = connections = None
        try:
            logging.disable(logging.CRITICAL)
            import django

            django.setup()
            from django.core.management import call_command
            from django.db import connections as db_connections

            connections = db_connections
            call_command("ensure_sqlite_wal", verbosity=0, stdout=io.StringIO())
            call_command("migrate", interactive=False, verbosity=0, stdout=io.StringIO())
            admin_email = f"admin-{uuid4().hex}@example.test"
            admin_password = f"{uuid4().hex}{uuid4().hex}A!"
            os.environ["DJANGO_ADMIN_PASSWORD"] = admin_password
            call_command(
                "create_admin",
                email=admin_email,
                display_name="Disposable Admin",
                stdout=io.StringIO(),
            )
            os.environ.pop("DJANGO_ADMIN_PASSWORD", None)

            from backend.config.wsgi import application

            server = make_server("127.0.0.1", 0, application, handler_class=QuietHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            deadline = time.monotonic() + 10
            while True:
                try:
                    if Session(base_url).request("GET", "/health").status == 200:
                        break
                except SmokeFailure:
                    pass
                if time.monotonic() >= deadline:
                    raise SmokeFailure("disposable_api_start_timeout")
                time.sleep(0.05)
            api_scenario(base_url, checks, admin_email, admin_password)
        finally:
            try:
                if server is not None:
                    server.shutdown()
                    server.server_close()
                if thread is not None:
                    thread.join(timeout=2)
                if connections is not None:
                    connections.close_all()
            finally:
                logging.disable(previous_logging)
                restore_environment(previous_env)


def sandbox_probe(requested: bool) -> dict[str, Any]:
    if not requested:
        return {"status": "NOT_RUN", "reason": "Не запрошено; используйте --sandbox."}
    docker = shutil.which("docker")
    if docker is None:
        return {"status": "NOT_RUN", "reason": "Docker CLI отсутствует."}
    try:
        engine = subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {"status": "NOT_RUN", "reason": "Docker Engine недоступен или не ответил за 5 секунд."}
    if engine.returncode != 0:
        return {"status": "NOT_RUN", "reason": "Docker Engine недоступен."}
    try:
        result = subprocess.run(
            [sys.executable, "sandbox/smoke.py", "--case", "all"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {"status": "FAIL", "reason": "Sandbox smoke не завершился в ограниченное время."}
    return {
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "reason": (
            "Только synthetic runner fixtures; это не full T18/T20 acceptance."
            if result.returncode == 0
            else "sandbox/smoke.py завершился с ошибкой; вывод не включён в evidence."
        ),
        "exitCode": result.returncode,
    }


def emit_report(report: dict[str, Any], output: Path | None) -> bool:
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if output is None:
        sys.stdout.write(rendered)
        return True
    destination = output if output.is_absolute() else ROOT / output
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(rendered, encoding="utf-8")
        try:
            os.link(temporary, destination)
        except FileExistsError:
            return False
    finally:
        temporary.unlink(missing_ok=True)
    sys.stdout.write(
        json.dumps(
            {
                "smokeResult": report["smokeResult"],
                "checks": len(report["checks"]),
                "output": str(destination),
                "fullAcceptance": "NOT_RUN",
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="JSON evidence path; default is stdout.")
    parser.add_argument(
        "--sandbox",
        action="store_true",
        help="If Docker Engine is available, run bounded synthetic runner smoke.",
    )
    args = parser.parse_args(argv)
    report = new_report()
    failure: SmokeFailure | None = None
    try:
        disposable_api(report["checks"])
    except SmokeFailure as error:
        failure = error
    except Exception as error:  # noqa: BLE001 - exception text may contain private request data.
        report["smokeResult"] = "FAIL"
        report["failureCode"] = f"setup_failed_{type(error).__name__}"

    report["sandboxProbe"] = sandbox_probe(args.sandbox)
    if failure is not None:
        report["smokeResult"] = "FAIL"
        report["failureCode"] = failure.code
        if failure.check_id is not None:
            report["checks"].append(
                {
                    "id": failure.check_id,
                    "status": "FAIL",
                    "failureCode": failure.code,
                    "httpStatus": failure.status,
                    "apiErrorCode": failure.api_code,
                }
            )
    elif report["sandboxProbe"]["status"] == "FAIL":
        report["smokeResult"] = "FAIL"
    elif report["smokeResult"] != "FAIL":
        report["smokeResult"] = "PASS"

    if not emit_report(report, args.output):
        sys.stderr.write("evidence file already exists; choose a new output path\n")
        return 2
    return int(report["smokeResult"] == "FAIL")


if __name__ == "__main__":
    raise SystemExit(main())
