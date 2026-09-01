"""Release-contract static tests for the Task 19 Docker deployment.

These tests parse the tracked Dockerfile, Compose file, and dependency lock
as plain files (no daemon, no build).  They freeze the judge-facing release
contract from docs/superpowers/specs/2026-08-24-docker-judge-deployment-design.md
Sections 3.1-3.5 and the Task 19.D implementation plan.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = (REPO_ROOT / "docker/Dockerfile").read_text(encoding="utf-8")
COMPOSE_TEXT = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
COMPOSE = yaml.safe_load(COMPOSE_TEXT)
_REQUIREMENTS_IN_PATH = REPO_ROOT / "docker/requirements.in"
REQUIREMENTS_IN = (
    _REQUIREMENTS_IN_PATH.read_text(encoding="utf-8")
    if _REQUIREMENTS_IN_PATH.exists()
    else ""
)

NODE_BASE = (
    "node:20.19.5-bookworm-slim@"
    "sha256:9e70124bd00f47dd023e349cd587132ae61892acc0e47ed641416c3e18f401c3"
)
PYTHON_BASE = (
    "python:3.12.13-slim-bookworm@"
    "sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2"
)
INVOCATION_LABEL = "io.challengecup.task19.invocation"
INVOCATION_DEFAULT = "${TASK19_INVOCATION_ID:-manual}"


def _from_lines() -> list[str]:
    return [
        line.strip()
        for line in DOCKERFILE.splitlines()
        if line.strip().upper().startswith("FROM ")
    ]


def test_from_lines_use_immutable_amd64_bases() -> None:
    from_lines = _from_lines()
    assert len(from_lines) == 3, from_lines
    for line in from_lines:
        assert line.startswith("FROM --platform=linux/amd64 "), line
    assert sum(NODE_BASE in line for line in from_lines) == 1
    assert sum(PYTHON_BASE in line for line in from_lines) == 2


def test_web_builder_stage_uses_committed_lockfile() -> None:
    web_stage = DOCKERFILE.split("AS web-builder", 1)[1]
    builder_end = re.search(r"^FROM ", web_stage, re.M)
    assert builder_end is not None
    web_stage = web_stage[: builder_end.start()]
    assert "COPY web/package.json web/package-lock.json ./" in web_stage
    npm_ci = re.search(r"^RUN npm ci(?: [^\n]*)?$", web_stage, re.M)
    assert npm_ci is not None, "web builder must run npm ci"
    assert web_stage.index("web/package-lock.json") < npm_ci.start()
    assert re.search(r"^RUN npm run build$", web_stage, re.M)


def test_python_install_requires_hashes_and_wheels_only() -> None:
    assert re.search(
        r"^RUN pip install --require-hashes --only-binary :all: "
        r"-r docker/requirements\.lock$",
        DOCKERFILE,
        re.M,
    ), "python install must pin hashes and binary wheels from the lock"


def test_sumo_build_gates_pin_1_27_1() -> None:
    runtime_stage = DOCKERFILE.split("AS runtime", 1)[1]
    assert re.search(r"sumo --version", runtime_stage)
    assert re.search(r"sumo-gui --version", runtime_stage)
    assert re.search(r"1\.27\.1", runtime_stage)
    for package in ("eclipse-sumo", "traci", "sumolib"):
        assert f'"{package}"' in runtime_stage or f"'{package}'" in runtime_stage
    # The wheel-built binaries dynamically link X11/GL (not vendored by the
    # manylinux wheel and absent from slim-bookworm); the loader libs must be
    # installed before the version gates, or every gate and run aborts.
    run_blocks = list(
        re.finditer(
            r"^RUN (.+?)(?=^RUN |^USER |^EXPOSE )", runtime_stage, re.M | re.S
        )
    )
    apt_match = next(
        (
            match
            for match in run_blocks
            if "apt-get install" in match.group(1)
            and "libx11-6 libxext6 libxrender1 libgl1" in match.group(1)
        ),
        None,
    )
    assert apt_match is not None, "runtime must install the X11/GL loader libraries"
    # Reproducibility: system packages resolve from the frozen Bookworm snapshot.
    assert "snapshot.debian.org/archive/debian/20260824T000000Z" in runtime_stage
    assert "check-valid-until=no" in runtime_stage
    gate = re.search(
        r"^RUN set -eux;(.+?)(?=^RUN |^USER |^EXPOSE )",
        runtime_stage,
        re.M | re.S,
    )
    assert gate is not None, "sumo verification RUN block not found"
    assert apt_match.start() < gate.start(), (
        "X11/GL loader install must precede the sumo version gates"
    )
    gate_body = gate.group(1)
    assert re.search(r"sumo --version\s*\|\s*grep -F", gate_body), gate_body
    assert re.search(r"sumo-gui --version\s*\|\s*grep -F", gate_body), gate_body
    assert "version('eclipse-sumo') == '1.27.1'" in gate_body
    assert "version('traci') == '1.27.1'" in gate_body
    assert "version('sumolib') == '1.27.1'" in gate_body


def test_runtime_env_and_user_contract() -> None:
    assert "EXPOSE 8000" in DOCKERFILE
    assert "PYTHONDONTWRITEBYTECODE=1" in DOCKERFILE
    assert "PYTHONUNBUFFERED=1" in DOCKERFILE
    assert "TMPDIR=/tmp" in DOCKERFILE
    assert "SUMO_HOME=/opt/sumo" in DOCKERFILE
    assert re.search(r"^RUN groupadd .*-g 10001", DOCKERFILE, re.M)
    assert re.search(r"^RUN useradd .*-u 10001", DOCKERFILE, re.M)
    assert re.search(r"^USER judge$", DOCKERFILE, re.M)
    assert DOCKERFILE.rindex("USER judge") < DOCKERFILE.rindex(
        'ENTRYPOINT ["python", "scripts/run_judge.py"]'
    )


def test_launcher_default_command_is_strict_headless() -> None:
    assert 'ENTRYPOINT ["python", "scripts/run_judge.py"]' in DOCKERFILE
    assert (
        'CMD ["--host", "0.0.0.0", "--port", "8000", '
        '"--port-attempts", "1", "--no-browser", '
        '"--gui-mode", "headless", '
        '"--diagnostics", "/app/output/evidence/docker/launcher.json"]'
    ) in DOCKERFILE


def test_runtime_web_assets_come_from_the_node_builder() -> None:
    assert re.search(
        r"^COPY --from=web-builder \S*api/static/dist \./api/static/dist$",
        DOCKERFILE,
        re.M,
    ), "runtime web assets must come from the web-builder stage"
    for line in DOCKERFILE.splitlines():
        if "api/static/dist" not in line or line.strip().startswith("#"):
            continue
        if line.strip().startswith(("COPY --from=web-builder", "RUN", "ENV")):
            continue
        pytest.fail(f"host web assets must not enter the image: {line!r}")


def test_runtime_copies_only_required_paths() -> None:
    required = [
        "algorithms/",
        "api/",
        "cloud/",
        "core/",
        "engine/",
        "experiments/",
        "ml/",
        "scenes/",
        "scripts/",
        "visualization/",
        "config/",
        "data/intersection_data",
        "pyproject.toml",
    ]
    for entry in required:
        assert f"COPY {entry}" in DOCKERFILE, f"missing runtime copy: {entry}"
    for entry in ["docs/", "tests/", ".superpowers", "output/"]:
        assert not re.search(
            rf"^COPY (?:--chown=\S+ )?{re.escape(entry)}", DOCKERFILE, re.M
        ), f"forbidden runtime copy: {entry}"


def test_invocation_arg_and_label_declared_in_final_stage() -> None:
    runtime_stage = DOCKERFILE.split("AS runtime", 1)[1]
    assert re.search(r"^ARG TASK19_INVOCATION_ID=manual$", runtime_stage, re.M)
    assert re.search(
        rf"^LABEL {INVOCATION_LABEL}=\$TASK19_INVOCATION_ID$",
        runtime_stage,
        re.M,
    )


def test_compose_default_service_contract() -> None:
    services = COMPOSE["services"]
    assert list(services) == ["judge", "judge-gui"]
    judge = services["judge"]
    assert judge["image"] == "${JUDGE_IMAGE:-ca-mp:latest}"
    assert judge["platform"] == "linux/amd64"
    assert judge["build"]["dockerfile"] == "docker/Dockerfile"
    assert judge["build"]["args"]["TASK19_INVOCATION_ID"] == INVOCATION_DEFAULT
    assert judge["init"] is True
    assert judge["read_only"] is True
    assert judge["restart"] == "no"
    assert judge["tmpfs"] == ["/tmp"]
    grace = judge["stop_grace_period"]
    match = re.fullmatch(r"(\d+)s", grace)
    assert match is not None and 0 < int(match.group(1)) <= 60, grace
    assert judge["volumes"] == ["judge-output:/app/output"]
    assert judge["ports"] == ["${JUDGE_HOST:-127.0.0.1}:8000:8000"]


def test_compose_healthcheck_is_exact_json() -> None:
    healthcheck = COMPOSE["services"]["judge"]["healthcheck"]
    test_cmd = " ".join(healthcheck["test"])
    assert "api/health" in test_cmd
    assert '{"run_workers": 1, "status": "ok"}' in test_cmd
    assert healthcheck["timeout"]
    assert healthcheck["retries"] >= 1
    assert healthcheck["start_period"]


def test_invocation_label_covers_service_network_and_volume() -> None:
    judge = COMPOSE["services"]["judge"]
    assert judge["labels"][INVOCATION_LABEL] == INVOCATION_DEFAULT
    default_network = COMPOSE["networks"]["default"]
    assert default_network["labels"][INVOCATION_LABEL] == INVOCATION_DEFAULT
    volume = COMPOSE["volumes"]["judge-output"]
    assert volume["labels"][INVOCATION_LABEL] == INVOCATION_DEFAULT


def test_requirements_in_freezes_exact_sumo_pins() -> None:
    lines = [
        line.strip()
        for line in REQUIREMENTS_IN.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert lines, "docker/requirements.in must exist and be non-empty"
    assert lines[0] == "-r ../requirements.txt"
    assert lines[1:] == [
        "eclipse-sumo==1.27.1",
        "traci==1.27.1",
        "sumolib==1.27.1",
    ]


def test_requirements_lock_is_hash_pinned_and_covers_runtime() -> None:
    lock_path = REPO_ROOT / "docker/requirements.lock"
    assert lock_path.exists(), "docker/requirements.lock must be committed"
    lock = lock_path.read_text(encoding="utf-8")
    for pin in ("eclipse-sumo==1.27.1", "traci==1.27.1", "sumolib==1.27.1"):
        assert re.search(rf"^{re.escape(pin)}\b", lock, re.M), pin
    hash_lines = re.findall(r"^    --hash=sha256:[0-9a-f]{64}$", lock, re.M)
    pin_lines = [
        line
        for line in lock.splitlines()
        if line and not line.startswith(("#", " ", "-"))
    ]
    assert len(hash_lines) >= len(pin_lines), (
        "every pinned artifact must carry at least one hash"
    )
    for line in lock.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "--", "-r")):
            continue
        assert "==" in stripped or stripped.startswith("--hash="), stripped
        assert " @" not in stripped and "file://" not in stripped
    # Every runtime dependency of requirements.txt must be locked by name.
    runtime_req = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    for line in runtime_req.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name = re.split(r"[\[<>=!~;]", stripped, 1)[0].strip().lower()
        assert name and re.search(
            rf"^{re.escape(name)}==", lock, re.M | re.I
        ), f"runtime dependency missing from lock: {name}"


DOCKERFILE_GUI_PATH = REPO_ROOT / "docker/Dockerfile.gui"
DOCKERFILE_GUI = (
    DOCKERFILE_GUI_PATH.read_text(encoding="utf-8")
    if DOCKERFILE_GUI_PATH.exists()
    else ""
)
DOCKERIGNORE = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
GUI_SNAPSHOT = "https://snapshot.debian.org/archive/debian/20260824T000000Z"


def test_gui_dockerfile_depends_on_judge_base_context() -> None:
    assert DOCKERFILE_GUI, "docker/Dockerfile.gui must exist"
    first_from = next(
        line.strip() for line in DOCKERFILE_GUI.splitlines() if line.strip().upper().startswith("FROM ")
    )
    assert first_from == "FROM --platform=linux/amd64 judge_base", first_from
    # No mutable release tag: the GUI image is built from the judge service
    # context, never from a floating registry reference.  The GUI stage has
    # exactly one FROM and it is the judge_base context.
    gui_from_lines = [
        line.strip()
        for line in DOCKERFILE_GUI.splitlines()
        if line.strip().upper().startswith("FROM ")
    ]
    assert gui_from_lines == ["FROM --platform=linux/amd64 judge_base"], gui_from_lines
    assert re.search(r"^ARG TASK19_INVOCATION_ID=manual$", DOCKERFILE_GUI, re.M)
    assert re.search(
        rf"^LABEL {INVOCATION_LABEL}=\$TASK19_INVOCATION_ID$", DOCKERFILE_GUI, re.M
    )
    label_pos = DOCKERFILE_GUI.index(f"LABEL {INVOCATION_LABEL}")
    from_pos = DOCKERFILE_GUI.upper().index("FROM ")
    assert from_pos < label_pos, "GUI image must reset the invocation label itself"


def test_gui_dockerfile_pins_frozen_bookworm_snapshot() -> None:
    snapshot_base = "https://snapshot.debian.org/archive"
    sources = re.findall(r"deb \[[^\]]+\] (\S+) (\S+) main", DOCKERFILE_GUI)
    assert len(sources) == 3, sources
    for url, suite in sources:
        assert url in (
            f"{snapshot_base}/debian/{GUI_SNAPSHOT.split('/')[-1]}",
            f"{snapshot_base}/debian-security/{GUI_SNAPSHOT.split('/')[-1]}",
        ), url
        assert suite.startswith("bookworm"), suite
    assert "bookworm-security" in DOCKERFILE_GUI
    assert "bookworm-updates" in DOCKERFILE_GUI
    assert DOCKERFILE_GUI.count("20260824T000000Z") >= 3
    assert "Acquire::Check-Valid-Until=false" in DOCKERFILE_GUI
    assert "rm -f /etc/apt/sources.list.d/debian.sources" in DOCKERFILE_GUI
    # Every frozen source line must itself carry check-valid-until=no.
    brackets = re.findall(r"deb \[([^\]]*)\] (\S+) (\S+) main", DOCKERFILE_GUI)
    assert len(brackets) == 3
    for options, _url, _suite in brackets:
        assert "check-valid-until=no" in options, options


def test_gui_dockerfile_pins_exact_x11_packages() -> None:
    assert "xvfb=2:21.1.7-3+deb12u12" in DOCKERFILE_GUI
    assert "xauth=1:1.1.2-1" in DOCKERFILE_GUI
    assert "libglu1-mesa=9.0.2-1.1" in DOCKERFILE_GUI
    assert "--no-install-recommends" in DOCKERFILE_GUI


def test_gui_dockerfile_fails_on_missing_libraries() -> None:
    assert re.search(r"command -v sumo-gui", DOCKERFILE_GUI)
    assert re.search(r"ldd \"\$\(cat /tmp/sumo-gui-path\.txt\)\"", DOCKERFILE_GUI)
    assert re.search(r"!\s*grep -F 'not found' /tmp/sumo-gui-ldd\.txt", DOCKERFILE_GUI)


def test_gui_entrypoint_runs_xvfb_container_gui() -> None:
    assert (
        'ENTRYPOINT ["xvfb-run", "-a", "python", "scripts/run_judge.py"]'
        in DOCKERFILE_GUI
    )
    assert (
        'CMD ["--host", "0.0.0.0", "--port", "8000", '
        '"--port-attempts", "1", "--no-browser", '
        '"--gui-mode", "container-gui", '
        '"--diagnostics", "/app/output/evidence/docker/launcher.json"]'
    ) in DOCKERFILE_GUI
    assert re.search(r"^USER judge$", DOCKERFILE_GUI, re.M)
    # Design 3.6: software GL is mandatory so frames do not depend on a GPU.
    assert re.search(
        r"^ENV LIBGL_ALWAYS_SOFTWARE=1$", DOCKERFILE_GUI, re.M
    )


def test_compose_gui_profile_contract() -> None:
    gui = COMPOSE["services"]["judge-gui"]
    assert gui["profiles"] == ["gui"]
    assert gui["build"]["dockerfile"] == "docker/Dockerfile.gui"
    assert gui["build"]["additional_contexts"] == {"judge_base": "service:judge"}
    assert gui["build"]["args"]["TASK19_INVOCATION_ID"] == INVOCATION_DEFAULT
    assert gui["image"] == "${JUDGE_GUI_IMAGE:-ca-mp-gui:latest}"
    assert gui["platform"] == "linux/amd64"
    assert gui["ports"] == ["127.0.0.1:8001:8000"]
    assert gui["volumes"] == ["judge-gui-output:/app/output"]
    assert gui["read_only"] is True and gui["init"] is True
    assert gui["restart"] == "no" and gui["tmpfs"] == ["/tmp"]
    assert gui["labels"][INVOCATION_LABEL] == INVOCATION_DEFAULT
    gui_volume = COMPOSE["volumes"]["judge-gui-output"]
    assert gui_volume["labels"][INVOCATION_LABEL] == INVOCATION_DEFAULT
    judge_volume = COMPOSE["volumes"]["judge-output"]
    assert judge_volume["labels"][INVOCATION_LABEL] == INVOCATION_DEFAULT


def test_dockerignore_excludes_protected_and_generated() -> None:
    required_exclusions = [
        "赛题资料.7z",
        "web/node_modules",
        "api/static/dist",
        ".superpowers",
        ".agents",
        ".worktrees",
        "output",
        ".git",
        ".venv",
        "__pycache__",
        ".env",
        ".7z",
        ".pem",
        "playwright-report",
        "test-results",
    ]
    for exclusion in required_exclusions:
        assert exclusion in DOCKERIGNORE, f"missing .dockerignore rule: {exclusion}"


def test_dockerignore_permits_runtime_inputs() -> None:
    rules = [
        line.strip()
        for line in DOCKERIGNORE.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    banned_exact = {
        "data",
        "data/",
        "data/intersection_data",
        "data/intersection_data/",
        "engine",
        "engine/configs",
        "web",
        "web/src",
        "web/package.json",
        "web/package-lock.json",
        "scripts",
        "config",
        "scenes",
        "algorithms",
        "core",
        "*.xml",
        "*.yaml",
        "*.py",
    }
    assert not (banned_exact & set(rules)), sorted(banned_exact & set(rules))
    # Prefix or glob exclusions that would swallow runtime trees or inputs.
    for rule in rules:
        for prefix in (
            "data", "scripts", "scenes", "engine", "config", "web/s", "web/p",
            "algorithms", "core", "ml", "experiments", "visualization",
            "cloud",
        ):
            assert not rule.startswith(prefix), rule
        # api is special: only the host-built dist may be excluded (the
        # runtime dist is built inside the image); nothing else under api/.
        if rule.startswith("api"):
            assert rule in {"api/static/dist", "/api/static/dist"}, rule
        assert not rule.endswith((".py", ".xml", ".yaml")), rule


def test_operator_docs_carry_required_terms() -> None:
    docs = [
        (REPO_ROOT / "docker/README.md").read_text(encoding="utf-8"),
        (REPO_ROOT / "docs/deployment.md").read_text(encoding="utf-8"),
    ]
    combined = "\n".join(docs)
    for term in (
        "docker_cli_unavailable",
        "not_run",
        "--execute-live",
        "container-gui",
        "linux/amd64",
        "8001",
        "compose cp",
    ):
        assert term in combined, f"operator docs missing required term: {term}"
    for forbidden_claim in (
        "Docker live verification: pass",
        "gui_smoke: pass",
        "save_load: pass",
    ):
        assert forbidden_claim not in combined, forbidden_claim
    # A direct Dockerfile.gui build must supply the judge_base named context;
    # a bare `docker build -f docker/Dockerfile.gui` cannot resolve it.
    for doc in docs:
        if "docker/Dockerfile.gui" not in doc:
            continue
        # Multiline-aware: PowerShell continuation blocks span several lines,
        # so the per-command regex alone would be vacuous for those docs.
        assert "--build-context judge_base=" in doc, (
            "GUI direct-build route must supply the judge_base context"
        )
        for match in re.finditer(r"docker build[^\n]*docker/Dockerfile\.gui", doc):
            command = match.group(0)
            assert "--build-context judge_base=" in command, command
