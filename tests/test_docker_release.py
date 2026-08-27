"""Behavioral tests for non-mutating Docker release evidence."""

from __future__ import annotations

import copy
import base64
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import io
import struct
import time
import tarfile
from datetime import datetime, timedelta, timezone
import urllib.request
import zlib
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from core.run_models import RunStatus
from core.types import MetricSummary
from engine.artifacts import RunArtifacts
from engine.events import EVENT_FIELDS
from experiments.evidence import (
    EvidenceReader,
    EvidenceWriter,
    RunManifest,
    canonical_mapping_sha256,
)
from scripts.release import docker_status, docker_verify


class _VerifierFakeRunner:
    """Strict injected Docker boundary used by verifier-only unit tests."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.inventory_result: list[dict[str, object]] = []

    def __call__(
        self,
        argv: list[str],
        _cwd: Path,
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del env
        self.calls.append(list(argv))
        if argv[:2] == ["docker", "inspect"]:
            matches = [
                item
                for item in self.inventory_result
                if item.get("name") == argv[-1]
            ]
            return _completed(
                list(argv),
                returncode=0 if matches else 1,
                stdout=json.dumps(matches),
            )
        return _completed(list(argv))


class _LiveVerifierRunner:
    """Stateful Docker substitute that models only Task 19.C boundaries."""

    _PNG_ONE = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05"
        b"\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    _PNG_TWO = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc`\xf8\xcf\xf0\x1f\x00\x04\x01"
        b"\x01\xffq\xebG\xe5\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    def __init__(
        self,
        *,
        fail_at: str | None = None,
        interrupt_at: str | None = None,
        cleanup_wrong_label: bool = False,
        cleanup_fail: bool = False,
        retain_after_cleanup: bool = False,
        semantic_mismatch_at: str | None = None,
        base_exception_at: str | None = None,
    ) -> None:
        self.fail_at = fail_at
        self.interrupt_at = interrupt_at
        self.cleanup_wrong_label = cleanup_wrong_label
        self.cleanup_fail = cleanup_fail
        self.retain_after_cleanup = retain_after_cleanup
        self.semantic_mismatch_at = semantic_mismatch_at
        self.base_exception_at = base_exception_at
        self.events: list[str] = []
        self.calls: list[list[str]] = []
        self.envs: list[dict[str, str]] = []
        self.resources: dict[str, dict[str, object]] = {}
        self.mutation_started = False
        self.final_inventory_seen = False
        self.compose_env: dict[str, str] = {}
        self.image_identity_seen = False
        self.container_runs: dict[str, Path] = {}
        self.container_proofs: dict[str, dict[str, object]] = {}

    @staticmethod
    def _proof(container: str, image: str, run_id: str) -> dict[str, object]:
        match = re.search(r"ca-mp-task19-([0-9a-f]{12})", container)
        if match is None:
            raise AssertionError("fake API container is not invocation-scoped")
        resources = docker_verify.InvocationResources.from_id(match.group(1))
        scope = (
            "gui"
            if "judge-gui" in container
            else "imported" if "imported" in container else "headless"
        )
        return _binding1_api_proof(
            resources, scope=scope, run_id=run_id
        )

    def _event(
        self, name: str, argv: list[str]
    ) -> subprocess.CompletedProcess[str]:
        self.events.append(name)
        if self.base_exception_at == name:
            raise BaseException(name)
        if self.interrupt_at == name:
            raise KeyboardInterrupt(name)
        if self.fail_at == name or (
            self.cleanup_fail and name == "cleanup_rm"
        ):
            return _completed(argv, returncode=19, stderr=f"{name} failed")
        return _completed(argv)

    def __call__(
        self,
        argv: list[str],
        _cwd: Path,
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = list(argv)
        self.calls.append(command)
        if env:
            self.compose_env = dict(env)
        variables = dict(env or self.compose_env)
        self.envs.append(dict(env or {}))
        project = variables.get("COMPOSE_PROJECT_NAME", "")
        invocation_id = variables.get("TASK19_INVOCATION_ID", "")
        owner = {"io.challengecup.task19.invocation": invocation_id}
        headless = variables.get("JUDGE_IMAGE", "")
        gui = variables.get("JUDGE_GUI_IMAGE", "")
        imported = f"{project}-imported:local" if project else ""

        if command == ["docker", "--version"]:
            result = self._event("cli", command)
            result.stdout = "Docker version 27.0.0, build unit-test"
            return result
        if command[:2] == ["docker", "info"]:
            result = self._event("daemon", command)
            result.stdout = '"27.0.0"'
            return result
        typed_inspect = (
            len(command) == 4
            and command[0] == "docker"
            and command[1] in {"container", "network", "volume", "image"}
            and command[2] == "inspect"
        )
        project_inventory = (
            len(command) >= 7
            and command[0] == "docker"
            and command[1] in {"container", "network", "volume", "image"}
            and command[2] == "ls"
            and "--filter" in command
            and "--format" in command
        )
        if project_inventory:
            return _completed(command)
        if (
            command[:2] == ["docker", "inspect"] and "--format" not in command
        ) or typed_inspect:
            name = command[-1]
            self.events.append(
                "final_inventory"
                if self.mutation_started and not self.resources
                else (
                    "collision_inventory"
                    if not self.mutation_started
                    else "cleanup_inventory"
                )
            )
            if self.mutation_started and not self.resources:
                self.final_inventory_seen = True
            item = self.resources.get(name)
            if (
                item is not None
                and self.cleanup_wrong_label
                and self.mutation_started
            ):
                item = {**item, "labels": {"other": "foreign"}}
            if (
                item is not None
                and typed_inspect
                and command[1] == "image"
                and not self.image_identity_seen
                and self.mutation_started
                and name.endswith("-headless:local")
            ):
                self.image_identity_seen = True
                identity_result = self._event("image_identity", command)
                if identity_result.returncode != 0:
                    return identity_result
            if item is not None and typed_inspect and command[1] == "image":
                config_bytes = json.dumps(
                    {
                        "architecture": "amd64",
                        "os": "linux",
                        "rootfs": {
                            "type": "layers",
                            "diff_ids": ["sha256:" + "b" * 64],
                        },
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
                digest = hashlib.sha256(config_bytes).hexdigest()
                item = {
                    "Id": f"sha256:{digest}",
                    "RepoTags": [name],
                    "RepoDigests": (
                        []
                        if self.semantic_mismatch_at == "image_identity"
                        else [f"local@sha256:{digest}"]
                    ),
                    "Config": {"Labels": item["labels"]},
                    "Os": "linux",
                    "Architecture": "amd64",
                    "RootFS": {
                        "Type": "layers",
                        "Layers": ["sha256:" + "b" * 64],
                    },
                }
            elif item is not None and typed_inspect:
                item = (
                    {
                        "Name": "/" + name,
                        "Config": {"Labels": item["labels"]},
                    }
                    if command[1] == "container"
                    else {"Name": name, "Labels": item["labels"]}
                )
            return _completed(
                command,
                returncode=0 if item else 1,
                stdout=json.dumps([item] if item else []),
                stderr=(
                    ""
                    if item
                    else f"Error: No such {command[1]}: {name}"
                ),
            )
        if "config" in command and "--quiet" in command:
            return self._event("config_quiet", command)
        if "config" in command and "--format" in command:
            result = self._event("config_json", command)
            services = {
                "judge": {
                    "profiles": [],
                    "image": headless,
                    "platform": "linux/amd64",
                    "labels": owner,
                    "build": {"additional_contexts": {}},
                }
            }
            if "--profile" in command:
                services["judge-gui"] = {
                    "profiles": ["gui"],
                    "image": gui,
                    "platform": "linux/amd64",
                    "labels": owner,
                    "build": {
                        "additional_contexts": {"judge_base": "service:judge"}
                    },
                }
            result.stdout = json.dumps({"name": project, "services": services})
            if self.semantic_mismatch_at == "config_json":
                result.stdout = json.dumps({"name": project, "services": {}})
            return result
        if "build" in command:
            event = "gui_build" if "judge-gui" in command else "build"
            self.mutation_started = True
            result = self._event(event, command)
            if result.returncode == 0:
                image = gui if event == "gui_build" else headless
                self.resources[image] = {
                    "kind": "image",
                    "name": image,
                    "labels": owner,
                }
            return result
        if "compose" in command and "up" in command:
            event = "gui_start" if "judge-gui" in command else "start"
            result = self._event(event, command)
            if result.returncode == 0:
                container = (
                    f"{project}-judge-gui-1"
                    if event == "gui_start"
                    else f"{project}-judge-1"
                )
                volume = (
                    f"{project}_judge-gui-output"
                    if event == "gui_start"
                    else f"{project}_judge-output"
                )
                for kind, name in (
                    ("container", container),
                    ("network", f"{project}_default"),
                    ("volume", volume),
                ):
                    self.resources[name] = {
                        "kind": kind,
                        "name": name,
                        "labels": owner,
                    }
            return result
        if command[:3] == ["docker", "inspect", "--format"]:
            event = (
                "gui_health"
                if "judge-gui" in command[-1]
                else (
                    "imported_health"
                    if "imported" in command[-1]
                    else "health"
                )
            )
            result = self._event(event, command)
            result.stdout = (
                "starting\n"
                if self.semantic_mismatch_at == event
                else "healthy\n" if result.returncode == 0 else ""
            )
            return result
        if command[:2] == ["docker", "exec"] and "api-health" in command:
            container = command[2]
            event = (
                "gui_api_health"
                if "judge-gui" in container
                else (
                    "imported_api_health"
                    if "imported" in container
                    else "api_health"
                )
            )
            result = self._event(event, command)
            if result.returncode == 0:
                result.stdout = (
                    '{"status":"wrong"}\n'
                    if self.semantic_mismatch_at == event
                    else '{"run_workers":1,"status":"ok"}\n'
                )
            return result
        if command[:2] == ["docker", "exec"] and "api-smoke" in command:
            container = command[2]
            event = (
                "gui_smoke"
                if "judge-gui" in container
                else (
                    "imported_smoke"
                    if "imported" in container
                    else "quick_smoke"
                )
            )
            result = self._event(event, command)
            if result.returncode == 0:
                run_id = {
                    "quick_smoke": "111111111111",
                    "imported_smoke": "222222222222",
                    "gui_smoke": "333333333333",
                }[event]
                image = (
                    gui
                    if event == "gui_smoke"
                    else imported if event == "imported_smoke" else headless
                )
                proof = self._proof(container, image, run_id)
                run_path = str(proof["output"]["path"])
                scope = (
                    "gui"
                    if event == "gui_smoke"
                    else "imported" if event == "imported_smoke" else "headless"
                )
                run_dir = _write_binding1_sealed_run(
                    Path(_cwd) / ".fake-container" / scope / "runs",
                    run_id=run_id,
                )
                proof["observed_completion"] = (
                    docker_verify._read_observed_completion(
                        run_dir,
                        run_id=run_id,
                        run_path=run_path,
                    )
                )
                self.container_runs[container] = run_dir
                self.container_proofs[container] = proof
                result.stdout = json.dumps(proof)
                if self.semantic_mismatch_at == event:
                    proof["terminal_status"] = "failed"
                    result.stdout = json.dumps(proof)
            return result
        if command[:3] == ["docker", "container", "stop"]:
            return self._event("stop", command)
        if command[:3] == ["docker", "image", "save"]:
            result = self._event("save", command)
            if result.returncode == 0:
                output = Path(_cwd) / command[command.index("--output") + 1]
                _write_docker_save_tar(
                    output,
                    tag=headless,
                    rootfs_layers=["sha256:" + "b" * 64],
                )
            return result
        if command[:3] == ["docker", "image", "load"]:
            return self._event("load", command)
        if command[:3] == ["docker", "image", "tag"]:
            result = self._event("retag", command)
            if result.returncode == 0:
                self.resources[imported] = {
                    "kind": "image",
                    "name": imported,
                    "labels": owner,
                }
            return result
        if command[:3] == ["docker", "container", "create"]:
            result = self._event("imported_create", command)
            if result.returncode == 0:
                name = command[command.index("--name") + 1]
                self.resources[name] = {
                    "kind": "container",
                    "name": name,
                    "labels": owner,
                }
            return result
        if command[:3] == ["docker", "container", "start"]:
            return self._event("imported_start", command)
        if command[:2] == ["docker", "cp"]:
            result = self._event("export", command)
            if result.returncode != 0:
                return result
            source, destination = command[2:]
            target = Path(_cwd) / destination
            for container, proof in self.container_proofs.items():
                run_path = str(proof["output"]["path"])
                if source == f"{container}:/app/output/{run_path}/.":
                    shutil.copytree(self.container_runs[container], target)
                    return result
                if source == (
                    f"{container}:/app/output/evidence/docker/launcher.json"
                ):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(
                        json.dumps(
                            {"container": container, "run_id": proof["run_id"]},
                            sort_keys=True,
                        ).encode()
                    )
                    return result
            return result
        if command[:2] == ["docker", "exec"] and "gui-frames" in command:
            result = self._event("gui_frames", command)
            if result.returncode == 0:
                container = command[2]
                run_id = "333333333333"
                proof = self._proof(container, gui, run_id)
                run_path = str(proof["output"]["path"])
                run_dir = _write_binding1_sealed_run(
                    Path(_cwd) / ".fake-container" / "gui" / "runs",
                    run_id=run_id,
                )
                proof["observed_completion"] = (
                    docker_verify._read_observed_completion(
                        run_dir,
                        run_id=run_id,
                        run_path=run_path,
                    )
                )
                self.container_runs[container] = run_dir
                self.container_proofs[container] = proof
                frames = [
                    {
                        "path": "gui/frames/frame-0001.png",
                        "sequence": 1,
                        "simulation_time": 1.0,
                        "png_base64": base64.b64encode(
                            self._PNG_ONE
                        ).decode(),
                    },
                    {
                        "path": "gui/frames/frame-0002.png",
                        "sequence": 2,
                        "simulation_time": 2.0,
                        "png_base64": base64.b64encode(
                            self._PNG_TWO
                        ).decode(),
                    },
                ]
                if self.semantic_mismatch_at == "gui_frames":
                    frames = [
                        {
                            "path": "gui/frames/frame-0001.png",
                            "sequence": 1,
                            "simulation_time": 1.0,
                            "png_base64": base64.b64encode(
                                b"not-png"
                            ).decode(),
                        },
                        {
                            "path": "gui/frames/frame-0002.png",
                            "sequence": 2,
                            "simulation_time": 2.0,
                            "png_base64": base64.b64encode(
                                self._PNG_TWO
                            ).decode(),
                        },
                    ]
                result.stdout = json.dumps(
                    {
                        "api_proof": proof,
                        "active_observation": {
                            "method": "GET",
                            "path": f"/api/runs/{run_id}",
                            "status": 200,
                            "run_id": run_id,
                            "state": "running",
                            "run_dir": f"/app/output/{run_path}",
                            "body_sha256": _canonical_json_hash(
                                {
                                    "run_id": run_id,
                                    "run_dir": f"/app/output/{run_path}",
                                    "status": "running",
                                }
                            ),
                        },
                        "frames": frames,
                    }
                )
            return result
        if (
            len(command) == 4
            and command[:1] == ["docker"]
            and command[2] == "rm"
        ):
            result = self._event("cleanup_rm", command)
            name = command[-1]
            if result.returncode == 0 and not self.retain_after_cleanup:
                self.resources.pop(name, None)
            return result
        raise AssertionError(f"unexpected verifier command: {command}")


@pytest.fixture
def verifier_fake_runner() -> _VerifierFakeRunner:
    return _VerifierFakeRunner()


def test_invocation_resources_are_unique_and_namespaced() -> None:
    first = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    second = docker_verify.InvocationResources.from_id("001122334455")

    assert first.compose_project == "ca-mp-task19-a1b2c3d4e5f6"
    assert first.label == "io.challengecup.task19.invocation=a1b2c3d4e5f6"
    assert first.headless_image != second.headless_image
    assert first.imported_image.endswith("-imported:local")


def test_collision_preflight_rejects_same_name_with_wrong_label(
    verifier_fake_runner: _VerifierFakeRunner,
) -> None:
    verifier_fake_runner.inventory_result = [
        {"kind": "container", "name": "expected", "labels": {}}
    ]

    with pytest.raises(docker_verify.SafetyError, match="collision"):
        docker_verify.assert_no_name_collisions(
            verifier_fake_runner, expected={"expected"}
        )


def test_fix4_public_collision_permission_lookalike_is_not_absence() -> None:
    """A generic ``not found`` substring cannot suppress a command failure."""
    name = "ca-mp-task19-a1b2c3d4e5f6-judge-1"

    def runner(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        assert argv == ["docker", "inspect", name]
        return subprocess.CompletedProcess(
            argv, 17, stdout=b"[]", stderr=b"permission helper not found"
        )

    with pytest.raises(docker_verify.SafetyError, match="inventory command"):
        docker_verify.assert_no_name_collisions(runner, expected={name})


def test_fix4_public_collision_accepts_exact_object_absence() -> None:
    """The bounded generic inspect absence for the queried name is empty."""
    name = "ca-mp-task19-a1b2c3d4e5f6-judge-1"

    def runner(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        assert argv == ["docker", "inspect", name]
        return subprocess.CompletedProcess(
            argv,
            1,
            stdout=b"[]",
            stderr=f"Error: No such object: {name}".encode("utf-8"),
        )

    assert docker_verify.assert_no_name_collisions(runner, expected={name}) == []


def test_fix4_public_collision_rejects_foreign_object_absence() -> None:
    """A real Docker absence for another name cannot answer this query."""
    name = "ca-mp-task19-a1b2c3d4e5f6-judge-1"

    def runner(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        assert argv == ["docker", "inspect", name]
        return subprocess.CompletedProcess(
            argv,
            1,
            stdout=b"[]",
            stderr=b"Error: No such object: a-different-name",
        )

    with pytest.raises(docker_verify.SafetyError, match="inventory command"):
        docker_verify.assert_no_name_collisions(runner, expected={name})


@pytest.mark.parametrize(
    ("response", "semantic"),
    [
        ("wrong-kind-absence", False),
        ("wrong-returned-name", True),
    ],
    ids=["wrong-kind-absence", "wrong-returned-name"],
)
def test_fix4_typed_inventory_rejects_wrong_kind_or_name(
    tmp_path: Path,
    response: str,
    semantic: bool,
) -> None:
    """Typed inspect binds both the requested kind and returned identity."""
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    target = resources.containers[0]

    def runner(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        assert argv == ["docker", "container", "inspect", target]
        if response == "wrong-kind-absence":
            return subprocess.CompletedProcess(
                argv,
                1,
                stdout=b"[]",
                stderr=f"Error: No such network: {target}".encode("utf-8"),
            )
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(
                [{"Name": "/a-different-name", "Config": {"Labels": {}}}]
            ).encode("utf-8"),
            stderr=b"",
        )

    with pytest.raises(docker_verify._InventoryFailure) as caught:
        docker_verify._inventory(runner, resources, tmp_path)
    assert caught.value.argv == ["docker", "container", "inspect", target]
    assert caught.value.semantic is semantic


def test_cleanup_requires_exact_name_and_invocation_label() -> None:
    candidate = {"name": "expected", "labels": {"other": "value"}}

    assert (
        docker_verify.is_owned(
            candidate,
            name="expected",
            invocation_id="a1b2c3d4e5f6",
        )
        is False
    )


@pytest.mark.parametrize("argv", [[], ["--repo-root", "."]])
def test_verifier_cli_requires_execute_live_before_runner_or_writer(
    argv: list[str],
) -> None:
    def unexpected(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("ungated verifier reached a mutation dependency")

    code = docker_verify.main(
        argv,
        command_runner=unexpected,
        evidence_writer=unexpected,
    )

    assert code != 0


def test_verifier_script_ungated_exit_has_no_import_traceback() -> None:
    result = subprocess.run(
        [
            os.fspath(Path(os.sys.executable)),
            os.fspath(
                Path(__file__).parents[1]
                / "scripts"
                / "release"
                / "docker_verify.py"
            ),
            "--repo-root",
            ".",
        ],
        cwd=Path(__file__).parents[1],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_task19c_r5_public_verifier_rejects_direct_live_execution(
    tmp_path: Path,
) -> None:
    """The public interface cannot bypass the CLI's --execute-live gate."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner()
    public_verify = docker_verify.verify_live

    with pytest.raises(docker_verify.SafetyError, match="--execute-live"):
        public_verify(
            tmp_path,
            Path("output/evidence/docker/live"),
            command_runner=runner,
            invocation_id="a1b2c3d4e5f6",
            expected_root=tmp_path,
        )

    assert runner.calls == []
    assert not (tmp_path / "output").exists()


def test_binding1_dispatch_rejects_unknown_and_stripped_contract() -> None:
    legacy = docker_status.new_evidence()
    docker_status.validate_evidence(legacy)

    strict = copy.deepcopy(legacy)
    strict["producer_contract"] = docker_status.LIVE_VERIFIER_CONTRACT
    docker_status.validate_live_verifier_evidence(strict)
    docker_status.validate_evidence(strict)

    unknown = copy.deepcopy(strict)
    unknown["producer_contract"] = "task19.c.live-verifier.unknown"
    with pytest.raises(ValueError, match="producer contract"):
        docker_status.validate_evidence(unknown)

    stripped = copy.deepcopy(strict)
    stripped.pop("producer_contract")
    with pytest.raises(ValueError, match="producer contract"):
        docker_status.validate_live_verifier_evidence(stripped)


def test_fix4_present_null_producer_contract_cannot_select_legacy() -> None:
    """Key presence, not a truthy value, selects the strict profile."""
    legacy = docker_status.new_evidence()
    docker_status.validate_evidence(legacy)

    present_null = copy.deepcopy(legacy)
    present_null["producer_contract"] = None
    with pytest.raises(ValueError, match="producer contract"):
        docker_status.validate_evidence(present_null)

    strict = copy.deepcopy(legacy)
    strict["producer_contract"] = docker_status.LIVE_VERIFIER_CONTRACT
    docker_status.validate_evidence(strict)


@pytest.mark.parametrize(
    "carrier",
    [
        "internal_error",
        "command_exception",
    ],
    ids=["internal-error", "command-exception"],
)
def test_fix5_absent_contract_rejects_strict_only_failure_carriers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    carrier: str,
) -> None:
    """A real strict failure carrier cannot be downgraded into legacy data."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    runner = _LiveVerifierRunner()

    def injected_runner(
        argv: list[str],
        cwd: Path,
        *,
        env: dict[str, str] | None = None,
    ) -> object:
        if "config" in argv and "--quiet" in argv:
            if carrier == "internal_error":
                raise RuntimeError("injected verifier failure")
            raise subprocess.TimeoutExpired(
                argv, 10, output=b"", stderr=b""
            )
        return runner(argv, cwd, env=env)

    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=injected_runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", validator
    )
    validator(payload)
    record = payload["static_contract"]
    assert record["execution"] == carrier
    assert record["boundary"] == "compose_contract"
    if carrier == "internal_error":
        assert record["argv"] == []
        assert record["failure_proof"] == {"kind": "internal_error"}
    else:
        assert record["argv"] == [
            "docker",
            "compose",
            "--project-name",
            "ca-mp-task19-a1b2c3d4e5f6",
            "config",
            "--quiet",
        ]
        assert record["failure_proof"] == {
            "kind": "command_exception",
            "exception_kind": "timeout",
        }

    downgraded = copy.deepcopy(payload)
    downgraded.pop("producer_contract")
    assert "producer_contract" not in downgraded
    with pytest.raises(ValueError, match="boundary|execution|field"):
        docker_status.validate_evidence(downgraded)


def test_binding1_verifier_marks_even_early_capability_evidence(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner(fail_at="cli")

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert payload["producer_contract"] == (
        "task19.c.live-verifier.binding-1"
    )
    docker_status.validate_live_verifier_evidence(payload)


def test_binding1_failure_cannot_strip_boundary_into_legacy(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at="build"),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    payload["headless_build"].pop("boundary")

    with pytest.raises(ValueError, match="boundary"):
        docker_status.validate_evidence(payload)


def _real_image_inspect(
    *, repo_digests: list[str], labels: dict[str, str] | None = None
) -> dict[str, object]:
    project = "ca-mp-task19-a1b2c3d4e5f6"
    digest = "a" * 64
    return {
        "Id": f"sha256:{digest}",
        "RepoTags": [f"{project}-headless:local"],
        "RepoDigests": repo_digests,
        "Os": "linux",
        "Architecture": "amd64",
        "Config": {
            "Labels": labels
            or {docker_status.OWNERSHIP_LABEL_KEY: "a1b2c3d4e5f6"}
        },
        "RootFS": {
            "Type": "layers",
            "Layers": ["sha256:" + "b" * 64, "sha256:" + "c" * 64],
        },
    }


@pytest.mark.parametrize(
    ("repo_digests", "expected_repository_digest"),
    [
        ([], None),
        (["foreign/repo@sha256:" + "d" * 64], None),
        (
            [
                "ca-mp-task19-a1b2c3d4e5f6-headless@sha256:"
                + "d" * 64
            ],
            "sha256:" + "d" * 64,
        ),
    ],
)
def test_binding1_local_image_identity_uses_only_real_sources(
    repo_digests: list[str],
    expected_repository_digest: str | None,
) -> None:
    identity = docker_verify._parse_image_identity(
        _real_image_inspect(repo_digests=repo_digests),
        expected_tag=(
            "ca-mp-task19-a1b2c3d4e5f6-headless:local"
        ),
        invocation_id="a1b2c3d4e5f6",
    )

    assert identity["headless_image_id"] == "sha256:" + "a" * 64
    assert identity.get("repository_digest") == expected_repository_digest
    assert identity["rootfs_layers"] == [
        "sha256:" + "b" * 64,
        "sha256:" + "c" * 64,
    ]
    assert "config_digest" not in identity
    assert "content_digest" not in identity


def test_binding1_local_image_identity_rejects_conflicting_exact_digests(
) -> None:
    exact = "ca-mp-task19-a1b2c3d4e5f6-headless@sha256:"
    with pytest.raises(docker_verify.SafetyError, match="conflicting"):
        docker_verify._parse_image_identity(
            _real_image_inspect(
                repo_digests=[exact + "d" * 64, exact + "e" * 64]
            ),
            expected_tag=(
                "ca-mp-task19-a1b2c3d4e5f6-headless:local"
            ),
            invocation_id="a1b2c3d4e5f6",
        )


def test_binding1_real_inventory_shapes_and_private_label_projection() -> None:
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    private_labels = {
        docker_status.OWNERSHIP_LABEL_KEY: "a1b2c3d4e5f6",
        "com.docker.compose.project.working_dir": "C:/private/worktree",
        "secret.custom": "must-not-serialize",
    }
    shapes = {
        ("container", resources.containers[0]): {
            "Name": "/" + resources.containers[0],
            "Config": {"Labels": private_labels},
        },
        ("network", resources.networks[0]): {
            "Name": resources.networks[0],
            "Labels": private_labels,
        },
        ("volume", resources.volumes[0]): {
            "Name": resources.volumes[0],
            "Labels": private_labels,
        },
        ("image", resources.headless_image): {
            **_real_image_inspect(repo_digests=[]),
            "Config": {"Labels": private_labels},
        },
    }

    def runner(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        item = shapes.get((argv[1], argv[3]))
        if item is None:
            return subprocess.CompletedProcess(
                argv,
                1,
                stdout=b"[]",
                stderr=f"Error: No such {argv[1]}: {argv[3]}".encode(),
            )
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps([item]).encode(), stderr=b""
        )

    all_entries, owned = docker_verify._inventory(
        runner, resources, Path(".")
    )

    assert {(item["kind"], item["name"]) for item in all_entries} == set(
        shapes
    )
    assert owned == all_entries
    assert all(
        item["labels"]
        == {docker_status.OWNERSHIP_LABEL_KEY: "a1b2c3d4e5f6"}
        for item in all_entries
    )
    assert "private" not in json.dumps(all_entries)
    assert "must-not-serialize" not in json.dumps(all_entries)


def test_binding1_post_identity_failure_requires_only_observed_image_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at="start"),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    for field in ("repository_digest", "config_digest", "content_digest"):
        payload["invocation"].pop(field, None)

    docker_status.validate_live_verifier_evidence(payload)


def test_binding1_runner_uses_allowlisted_env_and_raw_byte_streams(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TASK19_PRIVATE_SECRET", "must-not-inherit")
    received: dict[str, object] = {}

    def fake_run(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        received["args"] = args
        received.update(kwargs)
        return subprocess.CompletedProcess(
            args[0], 0, stdout=b"\xffraw-out", stderr=b"\x80raw-err"
        )

    monkeypatch.setattr(docker_verify.subprocess, "run", fake_run)
    result = docker_verify.run_command(
        ["docker", "compose", "config"],
        tmp_path,
        env={
            "COMPOSE_PROJECT_NAME": "ca-mp-task19-a1b2c3d4e5f6",
            "JUDGE_IMAGE": "headless:local",
            "JUDGE_GUI_IMAGE": "gui:local",
            "TASK19_INVOCATION_ID": "a1b2c3d4e5f6",
        },
    )
    record = docker_verify._command_record(
        "pass", "raw byte proof", ["docker", "compose", "config"],
        result, tmp_path,
    )

    assert received["text"] is False
    assert received["shell"] is False
    process_env = received["env"]
    assert "TASK19_PRIVATE_SECRET" not in process_env
    assert set(process_env).issubset(
        docker_verify._HOST_ENV_ALLOWLIST
        | {
            "COMPOSE_PROJECT_NAME",
            "JUDGE_IMAGE",
            "JUDGE_GUI_IMAGE",
            "TASK19_INVOCATION_ID",
        }
    )
    assert record["stdout_sha256"] == hashlib.sha256(b"\xffraw-out").hexdigest()
    assert record["stderr_sha256"] == hashlib.sha256(b"\x80raw-err").hexdigest()


def test_binding1_runner_uses_exact_logical_host_env_allowlist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    allowed = {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "TEMP",
        "TMP",
        "TMPDIR",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_CONFIG",
        "DOCKER_API_VERSION",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    }
    overlays = {
        "COMPOSE_PROJECT_NAME": "ca-mp-task19-a1b2c3d4e5f6",
        "JUDGE_IMAGE": "headless:local",
        "JUDGE_GUI_IMAGE": "gui:local",
        "TASK19_INVOCATION_ID": "a1b2c3d4e5f6",
    }
    for key in allowed:
        monkeypatch.setenv(key, "controlled-" + key.casefold())
    for key in (
        "HOME",
        "USERPROFILE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "COMPOSE_FILE",
        "COMPOSE_PROFILES",
        "COMPOSE_ENV_FILES",
        "COMPOSE_PROJECT_DIR",
        "TASK19_PRIVATE_SECRET",
    ):
        monkeypatch.setenv(key, "must-not-inherit")
    received: dict[str, object] = {}

    def fake_run(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        received.update(kwargs)
        return subprocess.CompletedProcess(args[0], 0, b"", b"")

    monkeypatch.setattr(docker_verify.subprocess, "run", fake_run)
    docker_verify.run_command(
        ["docker", "info"], tmp_path, env=overlays
    )

    process_env = received["env"]
    assert set(process_env) == allowed | set(overlays)
    assert all(process_env[key] == value for key, value in overlays.items())
    assert not any("must-not-inherit" in value for value in process_env.values())


def test_binding1_every_live_command_receives_exact_task19_overlays(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner()
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    expected = {
        "COMPOSE_PROJECT_NAME": "ca-mp-task19-a1b2c3d4e5f6",
        "JUDGE_IMAGE": "ca-mp-task19-a1b2c3d4e5f6-headless:local",
        "JUDGE_GUI_IMAGE": "ca-mp-task19-a1b2c3d4e5f6-gui:local",
        "TASK19_INVOCATION_ID": "a1b2c3d4e5f6",
    }
    assert runner.calls
    assert len(runner.calls) == len(runner.envs)
    assert all(env == expected for env in runner.envs)


def _binding1_raw_compose_config(
    resources: docker_verify.InvocationResources, *, include_gui: bool
) -> dict[str, object]:
    owner = {docker_status.OWNERSHIP_LABEL_KEY: resources.invocation_id}
    services: dict[str, object] = {
        "judge": {
            "profiles": [],
            "image": resources.headless_image,
            "platform": "linux/amd64",
            "labels": owner,
            "build": {"additional_contexts": {}},
        }
    }
    if include_gui:
        services["judge-gui"] = {
            "profiles": ["gui"],
            "image": resources.gui_image,
            "platform": "linux/amd64",
            "labels": owner,
            "build": {
                "additional_contexts": {"judge_base": "service:judge"}
            },
        }
    return {"name": resources.compose_project, "services": services}


@pytest.mark.parametrize("include_gui", [False, True], ids=["headless", "gui"])
def test_binding1_compose_facts_are_exact_raw_topology_projection(
    include_gui: bool,
) -> None:
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    raw = _binding1_raw_compose_config(resources, include_gui=include_gui)

    facts = docker_verify._selected_render_facts(
        raw, resources, include_gui
    )

    assert facts["project"] == raw["name"]
    assert facts["profiles"] == (["gui"] if include_gui else [])
    assert [service["name"] for service in facts["services"]] == [
        "judge",
        *(["judge-gui"] if include_gui else []),
    ]
    assert [service["profiles"] for service in facts["services"]] == [
        [],
        *([["gui"]] if include_gui else []),
    ]


@pytest.mark.parametrize(
    "defect",
    [
        "foreign-project",
        "extra-service",
        "headless-profile",
        "gui-missing-profile",
        "gui-extra-profile",
        "foreign-label",
    ],
)
def test_binding1_compose_projection_rejects_raw_topology_drift(
    defect: str,
) -> None:
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    include_gui = defect.startswith("gui-")
    raw = _binding1_raw_compose_config(resources, include_gui=include_gui)
    services = raw["services"]
    if defect == "foreign-project":
        raw["name"] = "foreign-project"
    elif defect == "extra-service":
        services["unreviewed"] = dict(services["judge"])
    elif defect == "headless-profile":
        services["judge"]["profiles"] = ["gui"]
    elif defect == "gui-missing-profile":
        services["judge-gui"]["profiles"] = []
    elif defect == "gui-extra-profile":
        services["judge-gui"]["profiles"] = ["gui", "other"]
    else:
        services["judge"]["labels"] = {
            docker_status.OWNERSHIP_LABEL_KEY: resources.invocation_id,
            "private.compose.label": "must-not-project",
        }

    with pytest.raises(docker_verify.SafetyError, match="Compose"):
        docker_verify._selected_render_facts(raw, resources, include_gui)


@pytest.mark.parametrize(
    "case",
    [
        "extra-selected-fact",
        "extra-service-field",
        "missing-service-profiles",
        "incorrect-service-profiles",
    ],
)
def test_fix5_strict_compose_render_facts_are_recursively_exact(
    tmp_path: Path,
    case: str,
) -> None:
    """Strict producer facts enforce exact nested keys and profiles."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at="build"),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    docker_status.validate_live_verifier_evidence(payload)
    facts = payload["static_contract"]["render_proof"]["selected_facts"]
    service = facts["services"][0]
    assert service["name"] == "judge"
    assert service["profiles"] == []
    if case == "extra-selected-fact":
        facts["unexpected"] = "value"
    elif case == "extra-service-field":
        service["unexpected"] = "value"
    elif case == "missing-service-profiles":
        service.pop("profiles")
    else:
        service["profiles"] = ["gui"]

    with pytest.raises(ValueError, match="render selected"):
        docker_status.validate_live_verifier_evidence(payload)


def _binding1_png(
    *,
    scanlines: bytes = b"\x00\xff\x00\x00\xff",
    interlace: int = 0,
    compressed_suffix: bytes = b"",
) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, interlace)
    compressed = zlib.compress(scanlines) + compressed_suffix
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


def test_binding1_png_validator_accepts_complete_rgba_frame() -> None:
    docker_verify._validate_png_bytes(_binding1_png())


@pytest.mark.parametrize(
    "defect",
    [
        "crc",
        "truncated",
        "trailing",
        "filter",
        "scanline-length",
        "zlib-trailing",
        "interlaced",
    ],
)
def test_binding1_png_validator_rejects_structural_corruption(
    defect: str,
) -> None:
    data = _binding1_png()
    if defect == "crc":
        offset = data.index(b"IDAT") + 4
        data = data[:offset] + bytes([data[offset] ^ 1]) + data[offset + 1 :]
    elif defect == "truncated":
        data = data[:-3]
    elif defect == "trailing":
        data += b"trailing"
    elif defect == "filter":
        data = _binding1_png(scanlines=b"\x05\xff\x00\x00\xff")
    elif defect == "scanline-length":
        data = _binding1_png(scanlines=b"\x00\xff\x00\x00")
    elif defect == "zlib-trailing":
        data = _binding1_png(compressed_suffix=b"junk")
    else:
        data = _binding1_png(interlace=1)

    with pytest.raises(docker_verify.SafetyError, match="PNG"):
        docker_verify._validate_png_bytes(data)


def test_binding1_gui_probe_is_one_interleaved_post_frames_terminal_flow(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import sys
    import urllib.request

    run_id = "333333333333"
    run_dir = "/app/output/runs/i1/fixed_time/x1/s42/" + run_id
    calls: list[tuple[str, str]] = []

    class Headers(dict[str, str]):
        def get_content_type(self) -> str:
            return self["Content-Type"]

    class Response:
        def __init__(
            self,
            status: int,
            data: bytes,
            headers: dict[str, str] | None = None,
        ) -> None:
            self.status = status
            self.data = data
            self.headers = Headers(headers or {})

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return self.data

    expected = [
        ("POST", "http://127.0.0.1:8000/api/runs"),
        ("GET", f"http://127.0.0.1:8000/api/runs/{run_id}"),
        ("GET", f"http://127.0.0.1:8000/api/runs/{run_id}/frame"),
        (
            "GET",
            f"http://127.0.0.1:8000/api/runs/{run_id}/frame?sequence=4",
        ),
        ("GET", f"http://127.0.0.1:8000/api/runs/{run_id}"),
    ]

    def fake_urlopen(
        target: object, timeout: int,
    ) -> Response:
        del timeout
        if isinstance(target, urllib.request.Request):
            call = (target.get_method(), target.full_url)
        else:
            call = ("GET", str(target))
        calls.append(call)
        assert call == expected[len(calls) - 1]
        if len(calls) == 1:
            return Response(
                202,
                json.dumps({"run_id": run_id, "run_dir": run_dir}).encode(),
            )
        if len(calls) == 2:
            return Response(
                200,
                json.dumps(
                    {"run_id": run_id, "run_dir": run_dir, "status": "running"}
                ).encode(),
            )
        if len(calls) in {3, 4}:
            sequence = 4 if len(calls) == 3 else 5
            return Response(
                200,
                _binding1_png(),
                {
                    "Content-Type": "image/png",
                    "X-Run-Id": run_id,
                    "X-Frame-Sequence": str(sequence),
                    "X-Simulation-Time": str(float(sequence)),
                },
            )
        return Response(
            200,
            json.dumps(
                {"run_id": run_id, "run_dir": run_dir, "status": "completed"}
            ).encode(),
        )

    monotonic = iter([10.0, 10.1, 10.2])
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    expected_completion = _binding1_api_proof(
        resources, scope="gui", run_id=run_id
    )["observed_completion"]

    def fake_completion(
        path: Path, *, run_id: str, run_path: str
    ) -> dict[str, object]:
        calls.append(("READ", path.as_posix()))
        assert run_id == "333333333333"
        assert run_path == "runs/i1/fixed_time/x1/s42/333333333333"
        return expected_completion

    monkeypatch.setattr(
        docker_verify, "_read_observed_completion", fake_completion
    )
    monkeypatch.setattr("time.monotonic", lambda: next(monotonic))
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    monkeypatch.setattr(
        sys, "argv", ["gui-probe", "container-name", "image-name"]
    )

    namespace = {"__name__": "__main__"}
    exec(
        compile(docker_verify._GUI_FRAMES_SCRIPT, "<gui-probe>", "exec"),
        namespace,
        namespace,
    )

    output = json.loads(capsys.readouterr().out)
    assert calls == [
        *expected,
        ("READ", "/app/output/runs/i1/fixed_time/x1/s42/333333333333"),
    ]
    assert output["api_proof"]["run_id"] == run_id
    assert output["api_proof"]["observed_completion"] == expected_completion
    assert output["active_observation"]["state"] == "running"
    assert [frame["sequence"] for frame in output["frames"]] == [4, 5]


def _binding1_api_proof(
    resources: docker_verify.InvocationResources,
    *,
    scope: str = "headless",
    run_id: str = "111111111111",
) -> dict[str, object]:
    container_index = {"headless": 0, "imported": 2, "gui": 1}[scope]
    image = {
        "headless": resources.headless_image,
        "imported": resources.imported_image,
        "gui": resources.gui_image,
    }[scope]
    run_path = f"runs/i1/fixed_time/x1/s42/{run_id}"
    run_dir = "/app/output/" + run_path
    body = {
        "intersection_id": "1",
        "algorithm": "fixed_time",
        "steps": 100,
    }
    response_body = {"status": 202, "run_id": run_id, "run_dir": run_dir}
    terminal_body = {
        "status": "completed",
        "run_id": run_id,
        "run_dir": run_dir,
    }
    return {
        "requested_steps": 100,
        "run_id": run_id,
        "terminal_status": "completed",
        "output": {"root": "app/output", "path": run_path, "run_id": run_id},
        "container": resources.containers[container_index],
        "image": image,
        "request": {
            "method": "POST",
            "path": "/api/runs",
            "body": body,
            "body_sha256": _canonical_json_hash(body),
        },
        "response": {
            "status": 202,
            "run_id": run_id,
            "run_dir": run_dir,
            "body_sha256": _canonical_json_hash(response_body),
        },
        "terminal": {
            "method": "GET",
            "path": f"/api/runs/{run_id}",
            "status": 200,
            "run_id": run_id,
            "state": "completed",
            "run_dir": run_dir,
            "body_sha256": _canonical_json_hash(terminal_body),
        },
        "observed_completion": {
            "source": "sealed_simulation_log.v1",
            "run_id": run_id,
            "run_path": run_path,
            "requested_steps": 100,
            "observed_step_count": 100,
            "observed_step_indices": list(range(100)),
            "step_log_path": "simulation_log.csv",
            "step_log_sha256": "d" * 64,
            "hashes_path": "hashes.json",
            "hashes_sha256": "e" * 64,
        },
    }


def test_binding1_api_parser_accepts_exact_sealed_completion() -> None:
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    proof = _binding1_api_proof(resources)
    result = _completed(["docker", "exec"], stdout=json.dumps(proof))

    assert docker_verify._parse_api_proof(result, resources) == proof


@pytest.mark.parametrize(
    "defect",
    [
        "synthetic-completed-steps",
        "wrong-output-path",
        "wrong-created-dir",
        "wrong-terminal-dir",
        "missing-completion",
        "wrong-step-index",
        "foreign-container",
    ],
)
def test_binding1_api_parser_rejects_unsealed_or_unbound_completion(
    defect: str,
) -> None:
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    proof = _binding1_api_proof(resources)
    if defect == "synthetic-completed-steps":
        proof["completed_steps"] = list(range(1, 101))
    elif defect == "wrong-output-path":
        proof["output"]["path"] = "runs/" + proof["run_id"]
    elif defect == "wrong-created-dir":
        proof["response"]["run_dir"] = "/app/output/runs/foreign"
    elif defect == "wrong-terminal-dir":
        proof["terminal"]["run_dir"] = "/app/output/runs/foreign"
    elif defect == "missing-completion":
        del proof["observed_completion"]
    elif defect == "wrong-step-index":
        proof["observed_completion"]["observed_step_indices"][50] = 49
    else:
        proof["container"] = "foreign-container"

    result = _completed(["docker", "exec"], stdout=json.dumps(proof))
    with pytest.raises(docker_verify.SafetyError):
        docker_verify._parse_api_proof(result, resources)


def _write_binding1_completion_files(
    run_dir: Path, *, run_id: str = "111111111111"
) -> None:
    run_dir.mkdir(parents=True)
    step_log = (
        "step,value\n"
        + "".join(f"{index},{index * 2}\n" for index in range(100))
    ).encode()
    for name, value in (
        ("manifest.json", {"run_id": run_id}),
        ("status.json", {"run_id": run_id, "status": "completed"}),
        (
            "run_metadata.json",
            {"run_id": run_id, "status": "completed", "requested_steps": 100},
        ),
    ):
        (run_dir / name).write_bytes(json.dumps(value).encode())
    (run_dir / "simulation_log.csv").write_bytes(step_log)
    hashes = {
        "run_id": run_id,
        "files": {"simulation_log.csv": hashlib.sha256(step_log).hexdigest()},
    }
    (run_dir / "hashes.json").write_bytes(json.dumps(hashes).encode())


def _write_binding1_sealed_run(root: Path, *, run_id: str) -> Path:
    artifacts = RunArtifacts.create(
        root,
        "1",
        "fixed_time",
        1.0,
        42,
        run_id=run_id,
    )
    writer = EvidenceWriter(artifacts.run_dir)
    source_hashes = {"net": "c" * 64, "sumocfg": "d" * 64}
    writer.begin(
        RunManifest(
            run_id=run_id,
            code_commit="a" * 40,
            scene_manifest_sha256=canonical_mapping_sha256(source_hashes),
            algorithm="fixed_time",
            parameters={"plan_source": "official"},
            flow_multiplier=1.0,
            seed=42,
            duration_seconds=100.0,
            warmup_seconds=0.0,
            derived_steps=100,
            sumo_version="1.27.1",
            python_version="3.12.13",
            prediction_enabled=False,
            scene_id="1",
            scene_source_sha256=source_hashes,
            step_length=1.0,
            requested_seconds=100.0,
        )
    )
    artifacts.tripinfo.write_text(
        "<tripinfos>"
        '<tripinfo id="done" depart="0" arrival="100" duration="100" '
        'timeLoss="0" waitingCount="0">'
        '<emissions fuel_abs="1" CO2_abs="1"/>'
        "</tripinfo></tripinfos>",
        encoding="utf-8",
    )
    artifacts.metrics.write_text(
        "step,timestamp,avg_queue_length,max_queue_length\n"
        + "".join(f"{step},{step + 1},0,0\n" for step in range(100)),
        encoding="utf-8",
    )
    with artifacts.events.open("w", newline="", encoding="utf-8") as output:
        csv.DictWriter(output, fieldnames=list(EVENT_FIELDS)).writeheader()
    artifacts.step_log.write_text(
        "step,timestamp,current_phase\n"
        + "".join(f"{step},{step + 1},0\n" for step in range(100)),
        encoding="utf-8",
    )
    artifacts.stats.write_text(
        '<summary><step time="100"/></summary>', encoding="utf-8"
    )
    artifacts.trajectory.write_text(
        '<fcd-export><timestep time="100"/></fcd-export>', encoding="utf-8"
    )
    artifacts.collisions.write_text("<collisions/>", encoding="utf-8")
    summary = MetricSummary.from_raw_outputs(
        artifacts.run_dir, warmup_seconds=0
    )
    writer.finalize(RunStatus.COMPLETED, summary)
    artifacts.write_status("queued", "")
    artifacts.write_status("starting", "")
    artifacts.write_status("running", "")
    artifacts.write_metadata(
        RunStatus.COMPLETED.value,
        "",
        [path for path in artifacts.run_dir.iterdir() if path.is_file()],
        started_at="2026-08-24T00:00:00+00:00",
        ended_at="2026-08-24T00:01:40+00:00",
        sumo_version="1.27.1",
        requested_steps=100,
        requested_seconds=100.0,
        warmup_seconds=0.0,
        final_simulation_time=100.0,
        step_length=1.0,
    )
    writer.seal()
    issues = EvidenceReader.validate(artifacts.run_dir)
    assert issues == [], issues
    return artifacts.run_dir


def test_binding1_source_completion_reads_real_sealed_bytes(
    tmp_path: Path,
) -> None:
    run_id = "111111111111"
    run_path = f"runs/i1/fixed_time/x1/s42/{run_id}"
    run_dir = tmp_path / run_path
    _write_binding1_completion_files(run_dir, run_id=run_id)

    completion = docker_verify._read_observed_completion(
        run_dir,
        run_id=run_id,
        run_path=run_path,
        evidence_validator=lambda _path: [],
    )

    step_raw = (run_dir / "simulation_log.csv").read_bytes()
    hashes_raw = (run_dir / "hashes.json").read_bytes()
    assert completion == {
        "source": "sealed_simulation_log.v1",
        "run_id": run_id,
        "run_path": run_path,
        "requested_steps": 100,
        "observed_step_count": 100,
        "observed_step_indices": list(range(100)),
        "step_log_path": "simulation_log.csv",
        "step_log_sha256": hashlib.sha256(step_raw).hexdigest(),
        "hashes_path": "hashes.json",
        "hashes_sha256": hashlib.sha256(hashes_raw).hexdigest(),
    }


@pytest.mark.parametrize(
    "defect", ["reader-issue", "run-id", "requested-steps", "hash", "rows"]
)
def test_binding1_source_completion_rejects_unsealed_bytes(
    tmp_path: Path,
    defect: str,
) -> None:
    run_id = "111111111111"
    run_path = f"runs/i1/fixed_time/x1/s42/{run_id}"
    run_dir = tmp_path / run_path
    _write_binding1_completion_files(run_dir, run_id=run_id)

    def validator(_path: Path) -> list[str]:
        return ["issue"] if defect == "reader-issue" else []
    if defect == "run-id":
        metadata = json.loads((run_dir / "run_metadata.json").read_text())
        metadata["run_id"] = "222222222222"
        (run_dir / "run_metadata.json").write_text(json.dumps(metadata))
    elif defect == "requested-steps":
        metadata = json.loads((run_dir / "run_metadata.json").read_text())
        metadata["requested_steps"] = 99
        (run_dir / "run_metadata.json").write_text(json.dumps(metadata))
    elif defect == "hash":
        hashes = json.loads((run_dir / "hashes.json").read_text())
        hashes["files"]["simulation_log.csv"] = "f" * 64
        (run_dir / "hashes.json").write_text(json.dumps(hashes))
    elif defect == "rows":
        (run_dir / "simulation_log.csv").write_text("step,value\n0,0\n")

    with pytest.raises(docker_verify.SafetyError):
        docker_verify._read_observed_completion(
            run_dir,
            run_id=run_id,
            run_path=run_path,
            evidence_validator=validator,
        )


def test_binding1_api_probe_reads_completion_after_terminal(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import sys
    import urllib.request

    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    run_id = "111111111111"
    run_path = f"runs/i1/fixed_time/x1/s42/{run_id}"
    run_dir = "/app/output/" + run_path
    calls: list[str] = []

    class Response:
        def __init__(self, status: int, data: object) -> None:
            self.status = status
            self.data = json.dumps(data).encode()

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return self.data

    def fake_urlopen(target: object, timeout: int) -> Response:
        del timeout
        if isinstance(target, urllib.request.Request):
            calls.append("post")
            return Response(202, {"run_id": run_id, "run_dir": run_dir})
        calls.append("terminal")
        return Response(
            200,
            {"run_id": run_id, "run_dir": run_dir, "status": "completed"},
        )

    expected_completion = _binding1_api_proof(resources)[
        "observed_completion"
    ]

    def fake_completion(
        path: Path, *, run_id: str, run_path: str
    ) -> dict[str, object]:
        calls.append("completion")
        assert path.as_posix() == "/app/output/" + run_path
        assert run_id == "111111111111"
        return expected_completion

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        docker_verify, "_read_observed_completion", fake_completion
    )
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "api-probe",
            resources.containers[0],
            resources.headless_image,
            "ignored-requested-id",
        ],
    )
    namespace = {"__name__": "__main__"}
    exec(
        compile(docker_verify._API_SMOKE_SCRIPT, "<api-probe>", "exec"),
        namespace,
        namespace,
    )

    output = json.loads(capsys.readouterr().out)
    assert calls == ["post", "terminal", "completion"]
    assert output["observed_completion"] == expected_completion
    assert "completed_steps" not in output


def test_binding1_host_uses_one_combined_gui_probe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)

    class CombinedGuiRunner(_LiveVerifierRunner):
        def __call__(
            self,
            argv: list[str],
            cwd: Path,
            *,
            env: dict[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
            if (
                argv[:2] == ["docker", "exec"]
                and "api-smoke" in argv
                and "judge-gui" in argv[2]
            ):
                raise AssertionError("GUI must not use a separate API probe")
            if argv[:2] == ["docker", "exec"] and "gui-frames" in argv:
                self.calls.append(list(argv))
                self.envs.append(dict(env or {}))
                self.events.append("gui_frames")
                resources = docker_verify.InvocationResources.from_id(
                    "a1b2c3d4e5f6"
                )
                proof = _binding1_api_proof(
                    resources,
                    scope="gui",
                    run_id="333333333333",
                )
                run_path = str(proof["output"]["path"])
                run_dir = _write_binding1_sealed_run(
                    Path(cwd) / ".fake-container" / "gui" / "runs",
                    run_id="333333333333",
                )
                proof["observed_completion"] = (
                    docker_verify._read_observed_completion(
                        run_dir,
                        run_id="333333333333",
                        run_path=run_path,
                    )
                )
                self.container_runs[resources.containers[1]] = run_dir
                self.container_proofs[resources.containers[1]] = proof
                return _completed(
                    argv,
                    stdout=json.dumps(
                        {
                            "api_proof": proof,
                            "active_observation": {
                                "method": "GET",
                                "path": "/api/runs/333333333333",
                                "status": 200,
                                "run_id": "333333333333",
                                "state": "running",
                                "run_dir": (
                                    "/app/output/"
                                    + run_path
                                ),
                                "body_sha256": _canonical_json_hash(
                                    {
                                        "run_id": "333333333333",
                                        "run_dir": "/app/output/" + run_path,
                                        "status": "running",
                                    }
                                ),
                            },
                            "frames": [
                                {
                                    "path": "gui/frames/frame-0001.png",
                                    "sequence": 4,
                                    "simulation_time": 4.0,
                                    "png_base64": base64.b64encode(
                                        self._PNG_ONE
                                    ).decode(),
                                },
                                {
                                    "path": "gui/frames/frame-0002.png",
                                    "sequence": 5,
                                    "simulation_time": 5.0,
                                    "png_base64": base64.b64encode(
                                        self._PNG_TWO
                                    ).decode(),
                                },
                            ],
                        }
                    ),
                )
            return super().__call__(argv, cwd, env=env)

    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    runner = CombinedGuiRunner()
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        include_gui=True,
        expected_root=tmp_path,
    )

    assert payload["status"] == "pass", (
        payload["reason"],
        payload["gui_smoke"].get("execution"),
        payload["gui_smoke"].get("failure_proof"),
        runner.events,
    )
    assert "gui_smoke" not in runner.events
    assert runner.events.count("gui_frames") == 1
    assert payload["gui_smoke"]["api_proof"]["run_id"] == "333333333333"


def test_binding1_save_load_has_exact_nine_stage_ledger(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    proof = payload["save_load_proof"]
    stages = [
        "controlled_stop",
        "image_save",
        "image_load",
        "image_retag",
        "imported_container_create",
        "imported_container_start",
        "imported_docker_health",
        "imported_api_health",
        "imported_api_smoke",
    ]
    assert list(proof) == [
        "tar_path",
        "tar_sha256",
        "tar_byte_length",
        "imported_image",
        "imported_container",
        *stages,
    ]
    assert all(proof[stage]["status"] == "pass" for stage in stages)
    assert payload["save_load"] == proof["image_save"]
    tar_file = (
        tmp_path
        / "output/evidence/docker/live/a1b2c3d4e5f6/headless-image.tar"
    )
    tar_bytes = tar_file.read_bytes()
    assert proof["tar_sha256"] == hashlib.sha256(tar_bytes).hexdigest()
    assert proof["tar_byte_length"] == len(tar_bytes) > 0
    assert payload["invocation"]["config_digest"] == payload["invocation"][
        "headless_image_id"
    ]
    assert "content_digest" not in payload["invocation"]


@pytest.mark.parametrize(
    ("fail_at", "selected"),
    [
        ("stop", "controlled_stop"),
        ("save", "image_save"),
        ("load", "image_load"),
        ("retag", "image_retag"),
        ("imported_create", "imported_container_create"),
        ("imported_start", "imported_container_start"),
        ("imported_health", "imported_docker_health"),
        ("imported_api_health", "imported_api_health"),
        ("imported_smoke", "imported_api_smoke"),
    ],
)
def test_binding1_save_load_failure_is_exact_stage_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fail_at: str,
    selected: str,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at=fail_at),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    stages = [
        "controlled_stop",
        "image_save",
        "image_load",
        "image_retag",
        "imported_container_create",
        "imported_container_start",
        "imported_docker_health",
        "imported_api_health",
        "imported_api_smoke",
    ]
    selected_index = stages.index(selected)
    proof = payload["save_load_proof"]
    assert [proof[stage]["status"] for stage in stages] == [
        *("pass" for _ in stages[:selected_index]),
        "fail",
        *("not_run" for _ in stages[selected_index + 1 :]),
    ]
    assert proof[selected]["boundary"] == selected
    assert payload["save_load"] == proof[selected]
    has_tar_identity = selected_index > stages.index("image_save")
    assert ("tar_sha256" in proof) is has_tar_identity
    assert ("tar_byte_length" in proof) is has_tar_identity


@pytest.mark.parametrize(
    ("raised", "execution", "failure_proof"),
    [
        (
            subprocess.TimeoutExpired(
                ["docker", "image", "load"],
                3,
                output=b"partial-out",
                stderr=b"partial-err",
            ),
            "command_exception",
            {"kind": "command_exception", "exception_kind": "timeout"},
        ),
        (
            OSError("private host detail"),
            "command_exception",
            {"kind": "command_exception", "exception_kind": "os_error"},
        ),
        (
            RuntimeError("private host detail"),
            "internal_error",
            {"kind": "internal_error"},
        ),
    ],
)
def test_binding1_save_load_exception_union_keeps_stage_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    raised: Exception,
    execution: str,
    failure_proof: dict[str, str],
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner()

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv[:3] == ["docker", "image", "load"]:
            raise raised
        return delegate(argv, root, **kwargs)

    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    proof = payload["save_load_proof"]
    failed = proof["image_load"]
    assert failed["status"] == "fail"
    assert failed["boundary"] == "image_load"
    assert failed["execution"] == execution
    assert failed["failure_proof"] == failure_proof
    assert payload["save_load"] == failed
    assert proof["controlled_stop"]["status"] == "pass"
    assert proof["image_save"]["status"] == "pass"
    assert proof["image_retag"]["status"] == "not_run"


def test_binding1_archive_read_failure_is_local_image_save_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)

    class CorruptArchiveRunner(_LiveVerifierRunner):
        def __call__(
            self,
            argv: list[str],
            cwd: Path,
            *,
            env: dict[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
            result = super().__call__(argv, cwd, env=env)
            if argv[:3] == ["docker", "image", "save"]:
                target = Path(cwd) / argv[argv.index("--output") + 1]
                target.write_bytes(b"not-a-tar")
            return result

    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=CorruptArchiveRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    proof = payload["save_load_proof"]
    failed = proof["image_save"]
    assert failed["execution"] == "local_operation"
    assert failed["boundary"] == "image_save"
    assert failed["argv"][:3] == ["docker", "image", "save"]
    assert failed["exit_code"] == 0
    assert failed["failure_proof"] == {
        "kind": "local_operation",
        "operation": "read_saved_image_archive",
    }
    assert payload["save_load"] == failed
    assert "tar_sha256" not in proof
    assert "tar_byte_length" not in proof
    assert "config_digest" not in payload["invocation"]


def test_binding1_export_walker_hashes_actual_stable_regular_files(
    tmp_path: Path,
) -> None:
    root = tmp_path / "export"
    (root / "scope/run").mkdir(parents=True)
    (root / "scope/run/a.txt").write_bytes(b"alpha")
    (root / "scope/run/b.bin").write_bytes(b"\x00\xff")

    contents = docker_verify._walk_exported_regular_files(root)

    assert contents == [
        {
            "path": "scope/run/a.txt",
            "byte_length": 5,
            "sha256": hashlib.sha256(b"alpha").hexdigest(),
        },
        {
            "path": "scope/run/b.bin",
            "byte_length": 2,
            "sha256": hashlib.sha256(b"\x00\xff").hexdigest(),
        },
    ]


def test_binding1_export_walker_rejects_links_and_case_aliases(
    tmp_path: Path,
) -> None:
    root = tmp_path / "export"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"private")
    link = root / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation unavailable")

    with pytest.raises(docker_verify.SafetyError, match="export"):
        docker_verify._walk_exported_regular_files(root)


def test_binding1_export_seals_actual_run_trees_and_launcher_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    runner = _LiveVerifierRunner()

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert payload["status"] == "pass", (
        payload.get("reason"),
        payload.get("headless_smoke"),
        payload.get("save_load_proof"),
    )
    assert "exported_evidence" in payload, payload
    exported = payload["exported_evidence"]
    invocation = (
        tmp_path / "output/evidence/docker/live/a1b2c3d4e5f6"
    )
    actual_contents = []
    for path in sorted(
        (candidate for candidate in invocation.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(invocation).as_posix(),
    ):
        raw = path.read_bytes()
        actual_contents.append(
            {
                "path": path.relative_to(invocation).as_posix(),
                "byte_length": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    assert exported["status"] == "pass"
    assert exported["path"] == (
        "output/evidence/docker/live/a1b2c3d4e5f6"
    )
    assert exported["contents"] == actual_contents
    assert not list(invocation.glob("*-smoke.json"))

    headless_path = "runs/i1/fixed_time/x1/s42/111111111111"
    imported_path = "runs/i1/fixed_time/x1/s42/222222222222"
    expected_units = [
        (
            "saved_image_tar",
            "shared",
            "headless-image.tar",
            "headless-image.tar",
        ),
        (
            "run_tree",
            "headless",
            (
                "ca-mp-task19-a1b2c3d4e5f6-judge-1:"
                f"/app/output/{headless_path}/."
            ),
            f"headless/{headless_path}",
        ),
        (
            "launcher_diagnostics",
            "headless",
            (
                "ca-mp-task19-a1b2c3d4e5f6-judge-1:"
                "/app/output/evidence/docker/launcher.json"
            ),
            "headless/diagnostics/launcher.json",
        ),
        (
            "run_tree",
            "imported",
            (
                "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1:"
                f"/app/output/{imported_path}/."
            ),
            f"imported/{imported_path}",
        ),
        (
            "launcher_diagnostics",
            "imported",
            (
                "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1:"
                "/app/output/evidence/docker/launcher.json"
            ),
            "imported/diagnostics/launcher.json",
        ),
    ]
    units = exported["export_units"]
    assert [
        (unit["kind"], unit["scope"], unit["source"], unit["destination"])
        for unit in units
    ] == expected_units
    assert all(unit["status"] == "pass" for unit in units)
    assert set(units[0]) == {
        "kind",
        "scope",
        "status",
        "source",
        "destination",
        "content_paths",
    }
    assert units[0]["content_paths"] == ["headless-image.tar"]
    base_copy_keys = {
        "kind",
        "scope",
        "status",
        "source",
        "destination",
        "content_paths",
        "record",
    }
    assert set(units[1]) == base_copy_keys
    assert set(units[3]) == base_copy_keys
    assert all(
        set(unit) == base_copy_keys | {"observed_content"}
        for unit in (units[2], units[4])
    )
    assert all(
        unit["observed_content"]
        == next(
            entry
            for entry in actual_contents
            if entry["path"] == unit["destination"]
        )
        for unit in (units[2], units[4])
    )
    assert [unit["record"]["argv"] for unit in units[1:]] == [
        ["docker", "cp", source, f"{exported['path']}/{destination}"]
        for _kind, _scope, source, destination in expected_units[1:]
    ]

    assert exported["run_exports"] == [
        {
            "scope": "headless",
            "container": "ca-mp-task19-a1b2c3d4e5f6-judge-1",
            "image": "ca-mp-task19-a1b2c3d4e5f6-headless:local",
            "run_id": "111111111111",
            "output_path": headless_path,
            "host_prefix": f"headless/{headless_path}",
            "sealed": True,
        },
        {
            "scope": "imported",
            "container": "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1",
            "image": "ca-mp-task19-a1b2c3d4e5f6-imported:local",
            "run_id": "222222222222",
            "output_path": imported_path,
            "host_prefix": f"imported/{imported_path}",
            "sealed": True,
        },
    ]
    by_path = {entry["path"]: entry for entry in actual_contents}
    for scope, phase in (
        ("headless", payload["headless_smoke"]),
        ("imported", payload["save_load_proof"]["imported_api_smoke"]),
    ):
        completion = phase["api_proof"]["observed_completion"]
        prefix = next(
            item["host_prefix"]
            for item in exported["run_exports"]
            if item["scope"] == scope
        )
        assert by_path[f"{prefix}/simulation_log.csv"]["sha256"] == (
            completion["step_log_sha256"]
        )
        assert by_path[f"{prefix}/hashes.json"]["sha256"] == (
            completion["hashes_sha256"]
        )


def test_binding1_gui_export_appends_run_diagnostics_and_exact_frames(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        include_gui=True,
        expected_root=tmp_path,
    )

    assert payload["status"] == "pass", payload.get("reason")
    exported = payload["exported_evidence"]
    assert [
        (unit["kind"], unit["scope"], unit["destination"])
        for unit in exported["export_units"]
    ] == [
        ("saved_image_tar", "shared", "headless-image.tar"),
        (
            "run_tree",
            "headless",
            "headless/runs/i1/fixed_time/x1/s42/111111111111",
        ),
        (
            "launcher_diagnostics",
            "headless",
            "headless/diagnostics/launcher.json",
        ),
        (
            "run_tree",
            "imported",
            "imported/runs/i1/fixed_time/x1/s42/222222222222",
        ),
        (
            "launcher_diagnostics",
            "imported",
            "imported/diagnostics/launcher.json",
        ),
        (
            "run_tree",
            "gui",
            "gui/runs/i1/fixed_time/x1/s42/333333333333",
        ),
        (
            "launcher_diagnostics",
            "gui",
            "gui/diagnostics/launcher.json",
        ),
        ("gui_frame", "gui", "gui/frames/frame-0001.png"),
        ("gui_frame", "gui", "gui/frames/frame-0002.png"),
    ]
    assert [unit["source"] for unit in exported["export_units"][-2:]] == [
        "captured_gui_frame_0",
        "captured_gui_frame_1",
    ]
    assert [item["scope"] for item in exported["run_exports"]] == [
        "headless",
        "imported",
        "gui",
    ]
    assert [frame["path"] for frame in payload["gui_frame_proof"]["frames"]] == [
        "gui/frames/frame-0001.png",
        "gui/frames/frame-0002.png",
    ]


def test_binding1_export_failure_retains_only_actual_first_incomplete_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at="export"),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert payload["status"] == "fail"
    assert payload["reason"] == "evidence_export_failed"
    exported = payload["exported_evidence"]
    assert set(exported) == {
        "status",
        "path",
        "contents",
        "run_exports",
        "export_units",
        "attempt",
    }
    assert exported["status"] == "fail"
    assert exported["run_exports"] == []
    assert exported["export_units"] == [
        {
            "kind": "saved_image_tar",
            "scope": "shared",
            "status": "pass",
            "source": "headless-image.tar",
            "destination": "headless-image.tar",
            "content_paths": ["headless-image.tar"],
        }
    ]
    tar_raw = (
        tmp_path
        / "output/evidence/docker/live/a1b2c3d4e5f6/headless-image.tar"
    ).read_bytes()
    assert exported["contents"] == [
        {
            "path": "headless-image.tar",
            "byte_length": len(tar_raw),
            "sha256": hashlib.sha256(tar_raw).hexdigest(),
        }
    ]
    attempt = exported["attempt"]
    assert attempt["status"] == "fail"
    assert attempt["boundary"] == "evidence_export"
    assert attempt["execution"] == "command"
    assert attempt["argv"] == [
        "docker",
        "cp",
        (
            "ca-mp-task19-a1b2c3d4e5f6-judge-1:"
            "/app/output/runs/i1/fixed_time/x1/s42/111111111111/."
        ),
        (
            "output/evidence/docker/live/a1b2c3d4e5f6/"
            "headless/runs/i1/fixed_time/x1/s42/111111111111"
        ),
    ]


def test_binding1_export_command_exception_retains_safe_partial_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    delegate = _LiveVerifierRunner()
    injected = False

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal injected
        if argv[:2] == ["docker", "cp"] and not injected:
            injected = True
            destination = root / argv[3]
            destination.mkdir(parents=True)
            (destination / "partial.txt").write_bytes(b"partial")
            raise subprocess.TimeoutExpired(
                argv, 3, output=b"copy-out", stderr=b"copy-err"
            )
        return delegate(argv, root, **kwargs)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert payload["status"] == "fail"
    assert payload["reason"] == "evidence_export_failed"
    exported = payload["exported_evidence"]
    attempt = exported["attempt"]
    assert attempt["execution"] == "command_exception"
    assert attempt["boundary"] == "evidence_export"
    assert attempt["failure_proof"] == {
        "kind": "command_exception",
        "exception_kind": "timeout",
    }
    assert attempt["stdout_sha256"] == hashlib.sha256(b"copy-out").hexdigest()
    assert attempt["stderr_sha256"] == hashlib.sha256(b"copy-err").hexdigest()
    assert exported["export_units"] == [
        {
            "kind": "saved_image_tar",
            "scope": "shared",
            "status": "pass",
            "source": "headless-image.tar",
            "destination": "headless-image.tar",
            "content_paths": ["headless-image.tar"],
        }
    ]
    assert [entry["path"] for entry in exported["contents"]] == [
        "headless-image.tar",
        (
            "headless/runs/i1/fixed_time/x1/s42/111111111111/"
            "partial.txt"
        ),
    ]
    assert payload["cleanup"]["status"] == "pass"


def test_binding1_cleanup_pass_proves_complete_inventories_and_action_projection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    owned = payload["owned_resources"]
    assert set(owned) == {
        "before_cleanup",
        "before_cleanup_complete",
        "after_cleanup",
        "after_cleanup_complete",
        "cleanup_actions",
    }
    assert owned["before_cleanup_complete"] is True
    assert owned["after_cleanup_complete"] is True
    assert owned["before_cleanup"]
    assert owned["after_cleanup"] == []
    actions = owned["cleanup_actions"]
    removals = [
        action for action in actions if action["action_kind"] == "remove"
    ]
    observations = [
        action for action in actions if action["action_kind"] == "inventory"
    ]
    assert len(removals) == len(owned["before_cleanup"])
    assert observations
    assert all(
        set(action)
        == {
            "status",
            "execution",
            "action_kind",
            "resource_kind",
            "resource_name",
            "required_label",
            "argv",
            "exit_code",
            "stdout_sha256",
            "stderr_sha256",
        }
        for action in removals
    )
    assert all(
        action["status"] == "pass"
        and action["execution"] == "command"
        and action["action_kind"] == "remove"
        and action["argv"]
        == [
            "docker",
            action["resource_kind"],
            "rm",
            action["resource_name"],
        ]
        and action["exit_code"] == 0
        for action in removals
    )
    for removal in removals:
        identity = (removal["resource_kind"], removal["resource_name"])
        assert any(
            action["inventory_stage"] == "post_remove"
            and action["observed_present"] is False
            and (action["resource_kind"], action["resource_name"]) == identity
            for action in observations
        )
        if removal["resource_kind"] == "container":
            assert any(
                action["inventory_stage"] == "requery"
                and action["observed_present"] is True
                and isinstance(action["observed_running"], bool)
                and (action["resource_kind"], action["resource_name"]) == identity
                for action in observations
            )
    common = {
        "status",
        "execution",
        "action_kind",
        "resource_kind",
        "resource_name",
        "required_label",
        "argv",
        "exit_code",
        "stdout_sha256",
        "stderr_sha256",
        "inventory_stage",
        "failure_proof",
        "boundary",
    }
    cleanup = payload["cleanup"]
    projected_action = next(
        action for action in reversed(actions) if action["action_kind"] != "inventory"
    )
    assert {
        key: cleanup[key] for key in common if key in cleanup
    } == {
        key: projected_action[key]
        for key in common
        if key in projected_action
    }
    assert set(cleanup) == {
        "status",
        "started_at",
        "finished_at",
        "detail",
        *set(projected_action),
    }


@pytest.mark.parametrize(
    ("raised", "execution", "failure_proof", "expected_argv"),
    [
        (
            subprocess.TimeoutExpired(
                ["docker", "container", "inspect", "name"],
                3,
                output=b"partial-out",
                stderr=b"partial-err",
            ),
            "command_exception",
            {"kind": "command_exception", "exception_kind": "timeout"},
            True,
        ),
        (
            OSError("private path"),
            "command_exception",
            {"kind": "command_exception", "exception_kind": "os_error"},
            True,
        ),
        (
            RuntimeError("private path"),
            "internal_error",
            {"kind": "internal_error"},
            False,
        ),
        (
            KeyboardInterrupt("stop"),
            "interruption",
            {
                "kind": "interruption",
                "interruption_kind": "keyboard_interrupt",
                "phase": "cleanup",
            },
            False,
        ),
        (
            BaseException("stop"),
            "interruption",
            {
                "kind": "interruption",
                "interruption_kind": "base_exception",
                "phase": "cleanup",
            },
            False,
        ),
    ],
)
def test_binding1_cleanup_initial_inventory_exception_has_closed_terminal_action(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    raised: BaseException,
    execution: str,
    failure_proof: dict[str, object],
    expected_argv: bool,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    delegate = _LiveVerifierRunner()
    injected = False

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal injected
        typed_inspect = (
            len(argv) == 4
            and argv[0] == "docker"
            and argv[1] in {"container", "network", "volume", "image"}
            and argv[2] == "inspect"
        )
        if (
            not injected
            and typed_inspect
            and "export" in delegate.events
        ):
            injected = True
            raise raised
        return delegate(argv, root, **kwargs)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert payload["status"] == "fail"
    assert payload["reason"] == "cleanup_failed"
    owned = payload["owned_resources"]
    assert owned["before_cleanup_complete"] is False
    assert owned["after_cleanup_complete"] is False
    assert owned["before_cleanup"] == owned["after_cleanup"] == []
    assert len(owned["cleanup_actions"]) == 1
    action = owned["cleanup_actions"][0]
    assert action["status"] == "fail"
    assert action["execution"] == execution
    assert action["action_kind"] == "inventory"
    assert action["inventory_stage"] == "initial"
    assert action["boundary"] == "cleanup"
    assert action["failure_proof"] == failure_proof
    assert bool(action["argv"]) is expected_argv
    if execution == "command_exception" and failure_proof["exception_kind"] == "timeout":
        assert action["stdout_sha256"] == hashlib.sha256(b"partial-out").hexdigest()
        assert action["stderr_sha256"] == hashlib.sha256(b"partial-err").hexdigest()
    common = {
        "status",
        "execution",
        "action_kind",
        "resource_kind",
        "resource_name",
        "required_label",
        "argv",
        "exit_code",
        "stdout_sha256",
        "stderr_sha256",
        "inventory_stage",
        "failure_proof",
        "boundary",
    }
    assert {
        key: payload["cleanup"][key]
        for key in common
        if key in payload["cleanup"]
    } == {key: action[key] for key in common if key in action}


@pytest.mark.parametrize(
    "stage",
    ["requery", "remove", "post_remove", "final"],
)
def test_binding1_cleanup_base_exception_is_terminal_at_every_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stage: str,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    delegate = _LiveVerifierRunner()
    cleanup_inspects = 0
    removal_seen = False
    empty_inspects = 0
    injected = False

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal cleanup_inspects, removal_seen, empty_inspects, injected
        typed_inspect = (
            len(argv) == 4
            and argv[0] == "docker"
            and argv[1] in {"container", "network", "volume", "image"}
            and argv[2] == "inspect"
        )
        cleanup_started = "export" in delegate.events
        if cleanup_started and typed_inspect:
            cleanup_inspects += 1
            if not delegate.resources:
                empty_inspects += 1
        should_raise = (
            not injected
            and cleanup_started
            and (
                (stage == "requery" and typed_inspect and cleanup_inspects == 10)
                or (stage == "remove" and len(argv) == 4 and argv[2] == "rm")
                or (stage == "post_remove" and typed_inspect and removal_seen)
                or (stage == "final" and typed_inspect and empty_inspects == 10)
            )
        )
        if should_raise:
            injected = True
            raise BaseException("private cleanup failure")
        result = delegate(argv, root, **kwargs)
        if cleanup_started and len(argv) == 4 and argv[2] == "rm":
            removal_seen = True
        return result

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert injected is True
    assert payload["status"] == "fail"
    assert payload["reason"] == "cleanup_failed"
    action = next(
        candidate
        for candidate in payload["owned_resources"]["cleanup_actions"]
        if candidate.get("failure_proof")
        == {
            "kind": "interruption",
            "interruption_kind": "base_exception",
            "phase": "cleanup",
        }
    )
    assert action["status"] == "fail"
    assert action["execution"] == "interruption"
    assert action["boundary"] == "cleanup"
    assert action["failure_proof"] == {
        "kind": "interruption",
        "interruption_kind": "base_exception",
        "phase": "cleanup",
    }
    assert payload["owned_resources"]["before_cleanup_complete"] is True
    assert payload["owned_resources"]["after_cleanup_complete"] is (
        stage == "remove"
    )
    if stage != "remove":
        assert action["action_kind"] == "inventory"
        assert action["inventory_stage"] == stage


@pytest.mark.parametrize(
    "defect",
    [
        "save-command",
        "cleanup-completeness",
        "cleanup-summary",
        "api-run-dir",
        "export-attempt-command",
    ],
)
def test_binding1_strict_validator_rejects_cross_record_mutations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    defect: str,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    runner = _LiveVerifierRunner(
        fail_at="export" if defect == "export-attempt-command" else None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    if defect == "save-command":
        payload["save_load_proof"]["image_load"]["argv"] = [
            "docker",
            "info",
        ]
    elif defect == "cleanup-completeness":
        payload["owned_resources"]["after_cleanup_complete"] = False
    elif defect == "cleanup-summary":
        payload["cleanup"]["resource_name"] = payload["invocation"][
            "headless_image"
        ]
    elif defect == "api-run-dir":
        payload["headless_smoke"]["api_proof"]["terminal"]["run_dir"] = (
            "/app/output/runs/foreign"
        )
    else:
        payload["exported_evidence"]["attempt"]["argv"] = [
            "docker",
            "info",
        ]

    with pytest.raises(ValueError):
        validator(payload)


def test_binding1_strict_validator_rejects_gui_frame_projection_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        include_gui=True,
        expected_root=tmp_path,
    )
    payload["gui_frame_proof"]["frames"][1]["sha256"] = "f" * 64

    with pytest.raises(ValueError):
        validator(payload)


@pytest.mark.parametrize(
    ("raised", "execution", "proof_kind"),
    [
        (
            subprocess.TimeoutExpired(
                ["docker", "exec"], 3,
                output=b"partial-out", stderr=b"partial-err",
            ),
            "command_exception",
            "timeout",
        ),
        (OSError("private host path"), "command_exception", "os_error"),
        (RuntimeError("unexpected private host path"), "internal_error", "internal_error"),
    ],
)
def test_binding1_runner_exceptions_have_closed_honest_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    raised: BaseException,
    execution: str,
    proof_kind: str,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    delegate = _LiveVerifierRunner()

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["docker", "exec"] and "api-smoke" in argv:
            raise raised
        return delegate(argv, root, **kwargs)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    failure = payload["headless_smoke"]
    assert payload["reason"] == "primary_api_run_failed"
    assert failure["execution"] == execution
    assert failure["exit_code"] is None
    if execution == "command_exception":
        assert failure["failure_proof"] == {
            "kind": "command_exception",
            "exception_kind": proof_kind,
        }
    else:
        assert failure["failure_proof"]["kind"] == proof_kind
    assert "private host path" not in json.dumps(payload)
    if execution == "internal_error":
        assert failure["argv"] == []
    else:
        assert failure["argv"][:2] == ["docker", "exec"]
    docker_status.validate_live_verifier_evidence(payload)


@pytest.mark.parametrize(
    ("case", "execution", "exception_kind"),
    [
        ("timeout-bytes", "command_exception", "timeout"),
        ("timeout-text", "internal_error", None),
        ("oserror-bytes", "command_exception", "os_error"),
        ("oserror-text", "internal_error", None),
    ],
)
def test_fix4_workflow_partial_streams_are_raw_or_commandless(
    tmp_path: Path,
    case: str,
    execution: str,
    exception_kind: str | None,
) -> None:
    """Normal run-step exceptions never encode synthetic partial text."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    expected_argv = [
        "docker",
        "compose",
        "--project-name",
        resources.compose_project,
        "build",
        "judge",
    ]
    delegate = _LiveVerifierRunner()

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv == expected_argv:
            stdout: bytes | str = (
                b"workflow-partial-out"
                if case.endswith("bytes")
                else "synthetic-text-out"
            )
            if case.startswith("timeout"):
                raise subprocess.TimeoutExpired(
                    argv, 3, output=stdout, stderr=b"workflow-partial-err"
                )
            error = OSError("private workflow path")
            error.stdout = stdout  # type: ignore[attr-defined]
            error.stderr = b"workflow-partial-err"  # type: ignore[attr-defined]
            raise error
        return delegate(argv, root, **kwargs)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    failure = payload["headless_build"]
    assert payload["reason"] == "headless_build_failed"
    assert failure["execution"] == execution
    assert failure["exit_code"] is None
    if execution == "command_exception":
        assert failure["argv"] == expected_argv
        assert failure["failure_proof"] == {
            "kind": "command_exception",
            "exception_kind": exception_kind,
        }
        assert failure["stdout_sha256"] == hashlib.sha256(
            b"workflow-partial-out"
        ).hexdigest()
        assert failure["stderr_sha256"] == hashlib.sha256(
            b"workflow-partial-err"
        ).hexdigest()
    else:
        assert failure["argv"] == []
        assert failure["failure_proof"] == {"kind": "internal_error"}
        assert failure["stdout_sha256"] == hashlib.sha256(b"").hexdigest()
        assert failure["stderr_sha256"] == hashlib.sha256(b"").hexdigest()
    docker_status.validate_live_verifier_evidence(payload)


def _write_docker_save_tar(
    path: Path,
    *,
    tag: str,
    rootfs_layers: list[str],
    config_layers: list[str] | None = None,
    config_name: str | None = None,
) -> tuple[str, bytes]:
    config = json.dumps(
        {
            "architecture": "amd64",
            "os": "linux",
            "rootfs": {
                "type": "layers",
                "diff_ids": config_layers or rootfs_layers,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    image_id = hashlib.sha256(config).hexdigest()
    selected_config = config_name or f"{image_id}.json"
    manifest = json.dumps(
        [
            {
                "Config": selected_config,
                "RepoTags": [tag],
                "Layers": [
                    f"layer-{index}/layer.tar"
                    for index in range(len(rootfs_layers))
                ],
            }
        ],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    with tarfile.open(path, "w") as archive:
        for name, data in [
            ("manifest.json", manifest),
            (selected_config, config),
            *[
                (f"layer-{index}/layer.tar", f"layer-{index}".encode())
                for index in range(len(rootfs_layers))
            ],
        ]:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return "sha256:" + image_id, config


def test_binding1_saved_archive_binds_config_rootfs_and_tar_bytes(
    tmp_path: Path,
) -> None:
    tag = "ca-mp-task19-a1b2c3d4e5f6-headless:local"
    layers = ["sha256:" + "b" * 64, "sha256:" + "c" * 64]
    archive = tmp_path / "headless-image.tar"
    image_id, config = _write_docker_save_tar(
        archive, tag=tag, rootfs_layers=layers
    )

    proof = docker_verify._validate_saved_image_archive(
        archive,
        expected_tag=tag,
        expected_image_id=image_id,
        expected_rootfs_layers=layers,
    )

    raw_tar = archive.read_bytes()
    assert proof == {
        "config_digest": image_id,
        "byte_length": len(raw_tar),
        "sha256": hashlib.sha256(raw_tar).hexdigest(),
    }
    assert hashlib.sha256(config).hexdigest() == image_id.removeprefix(
        "sha256:"
    )


@pytest.mark.parametrize(
    "defect",
    ["config-name-alias", "rootfs-mismatch", "absolute-config"],
)
def test_binding1_saved_archive_rejects_unsafe_or_unbound_members(
    tmp_path: Path,
    defect: str,
) -> None:
    tag = "ca-mp-task19-a1b2c3d4e5f6-headless:local"
    layers = ["sha256:" + "b" * 64]
    archive = tmp_path / "headless-image.tar"
    image_id, _config = _write_docker_save_tar(
        archive,
        tag=tag,
        rootfs_layers=layers,
        config_layers=(
            ["sha256:" + "c" * 64]
            if defect == "rootfs-mismatch"
            else None
        ),
        config_name=(
            "./config.json"
            if defect == "config-name-alias"
            else "/config.json"
            if defect == "absolute-config"
            else None
        ),
    )

    with pytest.raises(docker_verify.SafetyError):
        docker_verify._validate_saved_image_archive(
            archive,
            expected_tag=tag,
            expected_image_id=image_id,
            expected_rootfs_layers=layers,
        )


@pytest.mark.parametrize(
    "run_id",
    [
        "../escape",
        "a1b2c3d4e5f",
        "a1b2c3d4e5f60",
        "A1B2C3D4E5F6",
        "headless-run-a1b2c3d4e5f6",
    ],
)
def test_binding1_api_proof_rejects_unsafe_server_run_id(
    run_id: str,
) -> None:
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    proof = _handwritten_api_smoke_proof(
        container=resources.containers[0],
        image=resources.headless_image,
        run_id=run_id,
    )
    result = _completed(
        ["docker", "exec"], stdout=json.dumps(proof)
    )

    with pytest.raises(docker_verify.SafetyError, match="run id"):
        docker_verify._parse_api_proof(result, resources)


@pytest.mark.parametrize(
    "script",
    [docker_verify._API_SMOKE_SCRIPT, docker_verify._GUI_FRAMES_SCRIPT],
    ids=["api-smoke", "gui-frames"],
)
def test_binding1_container_probe_rejects_unsafe_run_id_before_url(
    script: str,
) -> None:
    guard = 're.fullmatch(r"[0-9a-f]{12}", run_id)'
    assert "import re" in script
    assert guard in script
    assert script.index(guard) < script.index("+ run_id")


@pytest.mark.parametrize(
    "requested",
    [
        Path("赛题资料.7z"),
        Path("data/intersection_data"),
        Path("data/intersection_data/child"),
        Path("output/../data/intersection_data/child"),
    ],
    ids=["archive", "official", "descendant", "traversal"],
)
def test_verifier_evidence_root_rejects_protected_inputs_before_mutation(
    tmp_path: Path,
    requested: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    (tmp_path / "赛题资料.7z").write_bytes(b"protected")
    calls: list[str] = []

    def unexpected(*_args: object, **_kwargs: object) -> object:
        calls.append("dependency")
        raise AssertionError("protected path reached a mutation dependency")

    with pytest.raises(docker_status.DockerStatusError, match="protected"):
        docker_verify._verify_live(
            tmp_path,
            requested,
            command_runner=unexpected,
            evidence_writer=unexpected,
            invocation_id="a1b2c3d4e5f6",
            expected_root=tmp_path,
        )

    assert calls == []
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize(
    "requested",
    [Path("output/evidence/docker/live"), Path("absolute-live-root")],
    ids=["relative", "absolute"],
)
def test_verifier_evidence_root_allows_legal_relative_and_absolute_paths(
    tmp_path: Path,
    requested: Path,
    verifier_fake_runner: _VerifierFakeRunner,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    (tmp_path / "赛题资料.7z").write_bytes(b"protected")
    live_root = tmp_path / "output" / "evidence" / "docker" / "live"
    target = (
        requested
        if requested.name != "absolute-live-root"
        else live_root.resolve()
    )

    def cli_unavailable(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        verifier_fake_runner.calls.append(list(argv))
        return _completed(argv, returncode=1, stderr="CLI unavailable")

    payload = docker_verify._verify_live(
        tmp_path,
        target,
        command_runner=cli_unavailable,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert payload["reason"] == "docker_cli_unavailable"
    assert verifier_fake_runner.calls == [["docker", "--version"]]
    assert not live_root.exists()


def test_verifier_rejects_other_safe_absolute_root_before_mutation(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    calls: list[str] = []

    def unexpected(*_args: object, **_kwargs: object) -> object:
        calls.append("dependency")
        raise AssertionError("noncanonical path reached mutation")

    with pytest.raises(docker_verify.SafetyError, match="canonical live"):
        docker_verify._verify_live(
            tmp_path,
            tmp_path / "other-safe-root",
            command_runner=unexpected,
            evidence_writer=unexpected,
            invocation_id="a1b2c3d4e5f6",
            expected_root=tmp_path,
        )

    assert calls == []


def test_verifier_command_record_hashes_full_streams_and_redacts_root(
    tmp_path: Path,
) -> None:
    stdout = "x" * 600 + str(tmp_path.resolve())
    stderr = "secret diagnostic" * 40
    result = _completed(["docker", "info"], stdout=stdout, stderr=stderr)

    record = docker_verify._command_record(
        "pass",
        f"completed under {tmp_path.resolve()}",
        ["docker", "image", "save", str(tmp_path / "image.tar")],
        result,
        tmp_path,
    )

    assert (
        record["stdout_sha256"] == hashlib.sha256(stdout.encode()).hexdigest()
    )
    assert (
        record["stderr_sha256"] == hashlib.sha256(stderr.encode()).hexdigest()
    )
    assert len(record["detail"]) <= docker_status.MAX_DETAIL_LENGTH
    assert str(tmp_path.resolve()) not in json.dumps(record)


def test_verifier_headless_workflow_is_ordered_and_schema_valid(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner()
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    docker_status.validate_evidence(payload)
    assert payload["status"] == "pass"
    key_events = [
        event
        for event in runner.events
        if event
        in {
            "config_quiet",
            "config_json",
            "build",
            "start",
            "health",
            "api_health",
            "quick_smoke",
            "stop",
            "save",
            "load",
            "imported_start",
            "imported_health",
            "imported_api_health",
            "imported_smoke",
            "export",
        }
    ]
    assert key_events == [
        "config_quiet",
        "config_json",
        "build",
        "start",
        "health",
        "api_health",
        "quick_smoke",
        "stop",
        "save",
        "load",
        "imported_start",
        "imported_health",
        "imported_api_health",
        "imported_smoke",
        "export",
        "export",
        "export",
        "export",
    ]
    for command, env in zip(runner.calls, runner.envs, strict=True):
        if command[:2] == ["docker", "compose"]:
            assert env == {
                "COMPOSE_PROJECT_NAME": "ca-mp-task19-a1b2c3d4e5f6",
                "JUDGE_IMAGE": "ca-mp-task19-a1b2c3d4e5f6-headless:local",
                "JUDGE_GUI_IMAGE": "ca-mp-task19-a1b2c3d4e5f6-gui:local",
                "TASK19_INVOCATION_ID": "a1b2c3d4e5f6",
            }
    assert payload["headless_smoke"]["execution"] == "api_result"
    assert (
        payload["save_load_proof"]["imported_api_smoke"]["execution"]
        == "api_result"
    )
    assert payload["owned_resources"]["after_cleanup"] == []
    assert runner.final_inventory_seen is True


def test_verifier_gui_uses_independent_api_run_and_real_linked_pngs(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner()
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        include_gui=True,
        expected_root=tmp_path,
    )

    docker_status.validate_evidence(payload)
    assert payload["gui_smoke"]["execution"] == "api_result"
    run_ids = {
        payload["headless_smoke"]["api_proof"]["run_id"],
        payload["save_load_proof"]["imported_api_smoke"]["api_proof"]["run_id"],
        payload["gui_smoke"]["api_proof"]["run_id"],
    }
    assert len(run_ids) == 3
    frames = payload["gui_frame_proof"]["frames"]
    assert [frame["sequence"] for frame in frames] == [1, 2]
    assert [frame["simulation_time"] for frame in frames] == [1.0, 2.0]
    live = tmp_path / "output/evidence/docker/live/a1b2c3d4e5f6"
    for frame in frames:
        data = (live / frame["path"]).read_bytes()
        assert data.startswith(b"\x89PNG\r\n\x1a\n")
        assert frame["byte_length"] == len(data) > 0
        assert frame["sha256"] == hashlib.sha256(data).hexdigest()
    assert runner.events.index("config_json") < runner.events.index(
        "gui_build"
    )
    assert runner.events.index("export") < runner.events.index("cleanup_rm")


def test_verifier_executes_real_api_probe_scripts_and_server_gui_run_id(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner()

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        include_gui=True,
        expected_root=tmp_path,
    )

    exec_commands = [
        command
        for command in runner.calls
        if command[:2] == ["docker", "exec"]
    ]
    health_commands = [
        command for command in exec_commands if "api-health" in command
    ]
    smoke_commands = [
        command for command in exec_commands if "api-smoke" in command
    ]
    frame_command = next(
        command for command in exec_commands if "gui-frames" in command
    )
    assert health_commands
    assert all(
        docker_verify._API_HEALTH_SCRIPT in command
        for command in health_commands
    )
    assert len(smoke_commands) == 2
    assert all(
        docker_verify._API_SMOKE_SCRIPT in command
        for command in smoke_commands
    )
    assert docker_verify._GUI_FRAMES_SCRIPT in frame_command
    assert "--run-id" not in frame_command
    assert payload["gui_smoke"]["api_proof"]["run_id"] == "333333333333"


@pytest.mark.parametrize("unavailable", ["cli", "daemon"])
def test_verifier_capability_failure_is_not_run_before_mutation(
    tmp_path: Path,
    unavailable: str,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner(fail_at=unavailable)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    docker_status.validate_evidence(payload)
    assert payload["status"] == "fail"
    assert payload["reason"] == (
        "docker_cli_failed"
        if unavailable == "cli"
        else "docker_daemon_failed"
    )
    assert runner.mutation_started is False


@pytest.mark.parametrize(
    ("failure_event", "expected_boundary", "expected_owner"),
    [
        ("config_quiet", "compose_contract", "static_contract"),
        ("config_json", "compose_contract", "static_contract"),
        ("build", "headless_build", "headless_build"),
        ("image_identity", "image_identity", "headless_build"),
        ("start", "headless_start", "headless_health"),
        ("health", "container_health", "headless_health"),
        ("api_health", "api_health", "headless_health"),
        ("quick_smoke", "primary_api_run", "headless_smoke"),
        ("stop", "controlled_stop", "save_load"),
        ("save", "image_save", "save_load"),
        ("load", "image_load", "save_load"),
        ("retag", "image_retag", "save_load"),
        ("imported_create", "imported_container_create", "save_load"),
        ("imported_start", "imported_container_start", "save_load"),
        ("imported_health", "imported_docker_health", "save_load"),
        ("imported_api_health", "imported_api_health", "save_load"),
        ("imported_smoke", "imported_api_smoke", "save_load"),
        ("gui_build", "gui_build", "gui_build"),
        ("gui_start", "gui_start", "gui_smoke"),
        ("gui_health", "gui_health", "gui_smoke"),
        ("gui_api_health", "gui_health", "gui_smoke"),
        ("gui_frames", "gui_frame_capture", "gui_smoke"),
        ("export", "evidence_export", "exported_evidence"),
    ],
)
def test_verifier_partial_failure_always_enters_exact_cleanup(
    tmp_path: Path,
    failure_event: str,
    expected_boundary: str,
    expected_owner: str,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner(fail_at=failure_event)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        include_gui=failure_event.startswith("gui"),
        expected_root=tmp_path,
    )

    assert payload["status"] == "fail"
    assert payload["reason"] == f"{expected_boundary}_failed"
    if expected_owner == "exported_evidence":
        assert (
            payload[expected_owner]["attempt"]["boundary"] == expected_boundary
        )
        assert payload[expected_owner]["attempt"]["execution"] == "command"
    else:
        assert payload[expected_owner]["boundary"] == expected_boundary
        assert payload[expected_owner]["execution"] == "command"
    docker_status.validate_evidence(payload)
    assert all(
        command[:3]
        not in (
            ["docker", "system", "prune"],
            ["docker", "volume", "prune"],
        )
        and not ("down" in command and "-v" in command)
        for command in runner.calls
    )
    if runner.mutation_started:
        assert any(
            event in {"cleanup_inventory", "final_inventory"}
            for event in runner.events
        )
    else:
        assert payload["cleanup"]["status"] == "not_run"


def test_verifier_keyboard_interrupt_is_classified_after_finally_cleanup(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner(interrupt_at="quick_smoke")

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert payload["status"] == "fail"
    assert payload["headless_smoke"]["execution"] == "interruption"
    assert payload["cleanup"]["status"] == "pass"


def test_verifier_non_exception_base_exception_still_runs_cleanup(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner(base_exception_at="imported_start")

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    failure = payload["save_load"]
    assert payload["reason"] == "imported_container_start_failed"
    assert failure["execution"] == "interruption"
    assert failure["failure_proof"]["interruption_kind"] == "base_exception"
    assert payload["cleanup"]["status"] == "pass"
    docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("event", "boundary"),
    [("health", "container_health"), ("api_health", "api_health")],
)
def test_verifier_exit_zero_semantic_mismatch_preserves_command_truth(
    tmp_path: Path,
    event: str,
    boundary: str,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner(semantic_mismatch_at=event)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    failure = payload["headless_health"]
    assert payload["reason"] == f"{boundary}_failed"
    assert failure["boundary"] == boundary
    assert failure["execution"] == "verifier_result"
    assert failure["exit_code"] == 0
    assert failure["argv"][0] == "docker"
    assert failure["failure_proof"]["kind"] == "postcondition_mismatch"
    docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("event", "boundary", "owner", "include_gui"),
    [
        ("config_json", "compose_contract", "static_contract", False),
        ("imported_health", "imported_docker_health", "save_load", False),
        ("imported_api_health", "imported_api_health", "save_load", False),
        ("imported_smoke", "imported_api_smoke", "save_load", False),
        ("gui_health", "gui_health", "gui_smoke", True),
        ("gui_api_health", "gui_health", "gui_smoke", True),
        ("gui_frames", "gui_frame_capture", "gui_smoke", True),
    ],
)
def test_verifier_all_exit_zero_mismatches_are_verifier_results(
    tmp_path: Path,
    event: str,
    boundary: str,
    owner: str,
    include_gui: bool,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner(semantic_mismatch_at=event)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        include_gui=include_gui,
        expected_root=tmp_path,
    )

    failure = payload[owner]
    assert payload["reason"] == f"{boundary}_failed"
    assert failure["boundary"] == boundary
    assert failure["execution"] == "verifier_result"
    assert failure["exit_code"] == 0
    assert failure["failure_proof"]["kind"] == "postcondition_mismatch"
    docker_status.validate_evidence(payload)


def test_verifier_local_image_with_empty_repo_digests_remains_valid(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner(semantic_mismatch_at="image_identity")

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert payload["status"] == "pass"
    assert "headless_image_id" in payload["invocation"]
    assert "repository_digest" not in payload["invocation"]
    assert payload["invocation"]["config_digest"] == payload["invocation"][
        "headless_image_id"
    ]
    assert "content_digest" not in payload["invocation"]
    docker_status.validate_evidence(payload)


def test_verifier_local_export_write_failure_is_commandless_and_truthful(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner()
    original = Path.write_bytes

    def fail_first_frame(path: Path, data: bytes) -> int:
        if path.name == "frame-0001.png":
            raise OSError("simulated local write failure")
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_first_frame)
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        include_gui=True,
        expected_root=tmp_path,
    )

    assert payload["reason"] == "evidence_export_failed"
    attempt = payload["exported_evidence"]["attempt"]
    assert attempt["boundary"] == "evidence_export"
    assert attempt["execution"] == "local_operation"
    assert attempt["argv"] == []
    assert attempt["exit_code"] is None
    assert attempt["failure_proof"] == {
        "kind": "local_operation",
        "operation": "write_exported_artifact",
    }
    docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("kind", "name_suffix"),
    [
        ("container", "-judge-1"),
        ("network", "_default"),
        ("volume", "_judge-output"),
        ("image", "-headless:local"),
    ],
)
@pytest.mark.parametrize(
    "labels",
    [
        {},
        {"io.challengecup.task19.invocation": "001122334455"},
        {"io.challengecup.task19.invocation": "a1b2c3d4e5f6"},
    ],
    ids=["missing-label", "foreign-label", "current-label"],
)
def test_verifier_collision_never_adopts_or_cleans_any_exact_resource(
    tmp_path: Path,
    kind: str,
    name_suffix: str,
    labels: dict[str, str],
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    project = "ca-mp-task19-a1b2c3d4e5f6"
    name = f"{project}{name_suffix}"
    runner = _LiveVerifierRunner()
    runner.resources[name] = {"kind": kind, "name": name, "labels": labels}

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert payload["status"] == "fail"
    assert payload["reason"] == "collision_failed"
    assert payload["static_contract"]["boundary"] == "collision"
    assert payload["static_contract"]["execution"] == "verifier_result"
    projected_labels = (
        labels
        if labels.get("io.challengecup.task19.invocation")
        == "a1b2c3d4e5f6"
        else {}
    )
    assert payload["name_collisions"]["before"] == [
        {"kind": kind, "name": name, "labels": projected_labels}
    ]
    assert payload["owned_resources"]["before_cleanup"] == []
    assert payload["cleanup"]["status"] == "not_run"
    assert runner.mutation_started is False
    assert not any(
        "rm" in command or "build" in command for command in runner.calls
    )
    docker_status.validate_evidence(payload)


@pytest.mark.parametrize("mode", ["nonzero", "invalid-json"])
def test_verifier_collision_inventory_errors_fail_closed_as_evidence(
    tmp_path: Path,
    mode: str,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner()

    def broken_inventory(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if (
            len(argv) == 4
            and argv[1] in {"container", "network", "volume", "image"}
            and argv[2] == "inspect"
        ):
            if mode == "nonzero":
                return _completed(
                    argv, returncode=17, stderr="permission denied"
                )
            return _completed(argv, stdout="not-json")
        return delegate(argv, root, **kwargs)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=broken_inventory,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    failure = payload["static_contract"]
    assert payload["reason"] == "collision_failed"
    assert failure["boundary"] == "collision"
    assert failure.get("execution", "command") == (
        "command" if mode == "nonzero" else "verifier_result"
    )
    assert payload["name_collisions"]["before"] == []
    assert payload["cleanup"]["status"] == "not_run"
    assert not (tmp_path / "output").exists()
    assert delegate.mutation_started is False
    docker_status.validate_evidence(payload)


def test_verifier_rejects_any_existing_compose_project_resource(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner()
    project_query_seen = False

    def project_collision(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal project_query_seen
        if (
            len(argv) >= 7
            and argv[:3] == ["docker", "network", "ls"]
            and "--filter" in argv
        ):
            project_query_seen = True
            return _completed(
                argv,
                stdout=json.dumps(
                    {
                        "Name": "orphan-from-same-project",
                        "Labels": (
                            "com.docker.compose.project="
                            "ca-mp-task19-a1b2c3d4e5f6"
                        ),
                    }
                ),
            )
        return delegate(argv, root, **kwargs)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=project_collision,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert project_query_seen is True
    assert payload["status"] == "fail"
    assert payload["reason"] == "collision_failed"
    failure = payload["static_contract"]
    assert failure["boundary"] == "collision"
    assert failure["execution"] == "verifier_result"
    assert failure["failure_proof"] == {
        "kind": "postcondition_mismatch",
        "expected": "no_compose_project_resources",
        "observed": "compose_project_resources_present",
    }
    assert payload["name_collisions"]["before"] == []
    assert delegate.mutation_started is False
    assert not any("rm" in command for command in delegate.calls)
    docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("runner_kwargs", "execution"),
    [
        ({"cleanup_wrong_label": True}, "safety_refusal"),
        ({"cleanup_fail": True}, "verifier_result"),
        ({"retain_after_cleanup": True}, "verifier_result"),
    ],
)
def test_verifier_cleanup_refusal_failure_or_nonempty_inventory_forces_fail(
    tmp_path: Path,
    runner_kwargs: dict[str, bool],
    execution: str,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner(**runner_kwargs)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert payload["status"] == "fail"
    assert payload["cleanup"]["status"] == "fail"
    assert payload["cleanup"].get("execution", "command") == execution
    docker_status.validate_evidence(payload)
    assert all(
        len(command) == 4 for command in runner.calls if "rm" in command
    )


@pytest.mark.parametrize(
    "mode",
    ["initial-nonzero", "initial-malformed", "after-malformed"],
)
def test_verifier_cleanup_inventory_failure_is_terminal_evidence(
    tmp_path: Path,
    mode: str,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner()
    failed = False
    removal_seen = False

    def broken_cleanup_inventory(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal failed, removal_seen
        if len(argv) == 4 and argv[2] == "rm":
            removal_seen = True
        typed_inventory = (
            len(argv) == 4
            and argv[1] in {"container", "network", "volume", "image"}
            and argv[2] == "inspect"
        )
        should_fail = (
            delegate.mutation_started
            and "export" in delegate.events
            and typed_inventory
            and not failed
            and (mode != "after-malformed" or removal_seen)
        )
        if should_fail:
            failed = True
            if mode == "initial-nonzero":
                return _completed(
                    argv, returncode=23, stderr="inventory permission denied"
                )
            return _completed(argv, stdout="not-json")
        return delegate(argv, root, **kwargs)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=broken_cleanup_inventory,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    cleanup = payload["cleanup"]
    assert payload["status"] == "fail"
    assert payload["reason"] == "cleanup_failed"
    assert cleanup["status"] == "fail"
    assert cleanup["boundary"] == "cleanup"
    assert cleanup["execution"] == (
        "command" if mode == "initial-nonzero" else "verifier_result"
    )
    assert cleanup["argv"][0] == "docker"
    assert cleanup["argv"][2] == "inspect"
    assert (
        payload["owned_resources"]["cleanup_actions"][-1]["argv"]
        == cleanup["argv"]
    )
    docker_status.validate_evidence(payload)


@pytest.mark.parametrize("case", ["empty", "multiple", "valid-plus-foreign"])
def test_fix2_successful_exact_inventory_requires_one_exact_object(
    tmp_path: Path,
    case: str,
) -> None:
    """A zero-exit exact inspect is absence only when Docker says absent."""
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    target = resources.containers[0]
    exact = {"Name": "/" + target, "Config": {"Labels": {}}}
    foreign = {
        "Name": "/" + target + "-foreign",
        "Config": {"Labels": {}},
    }
    values = {
        "empty": [],
        "multiple": [exact, exact],
        "valid-plus-foreign": [exact, foreign],
    }[case]

    def runner(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv == ["docker", "container", "inspect", target]:
            return _completed(argv, stdout=json.dumps(values))
        return _completed(
            argv,
            returncode=1,
            stdout="[]",
            stderr=f"Error: No such {argv[1]}: {argv[3]}",
        )

    with pytest.raises(docker_verify._InventoryFailure) as caught:
        docker_verify._inventory(runner, resources, tmp_path)
    assert caught.value.semantic is True
    assert caught.value.argv == ["docker", "container", "inspect", target]


@pytest.mark.parametrize("kind", ["container", "network", "volume", "image"])
def test_fix2_exact_inventory_identity_mismatch_is_malformed_not_absent(
    tmp_path: Path,
    kind: str,
) -> None:
    """A successful exact inspect with the wrong identity must fail closed."""
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    names = {
        "container": resources.containers,
        "network": resources.networks,
        "volume": resources.volumes,
        "image": (
            resources.headless_image,
            resources.gui_image,
            resources.imported_image,
        ),
    }
    target = names[kind][0]

    def malformed(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv == ["docker", kind, "inspect", target]:
            wrong_name = target + "-foreign"
            if kind == "container":
                value: object = {
                    "Name": "/" + wrong_name,
                    "Config": {"Labels": {}},
                }
            elif kind in {"network", "volume"}:
                value = {"Name": wrong_name, "Labels": {}}
            else:
                value = {
                    "RepoTags": [wrong_name],
                    "Config": {"Labels": {}},
                }
            return _completed(argv, stdout=json.dumps([value]))
        return _completed(
            argv,
            returncode=1,
            stdout="[]",
            stderr=f"Error: No such {argv[1]}: {argv[3]}",
        )

    with pytest.raises(docker_verify._InventoryFailure) as caught:
        docker_verify._inventory(malformed, resources, tmp_path)
    assert caught.value.semantic is True
    assert caught.value.argv == ["docker", kind, "inspect", target]


@pytest.mark.parametrize("kind", ["container", "network", "volume", "image"])
def test_fix2_exact_inventory_rejects_malformed_label_shape(
    tmp_path: Path,
    kind: str,
) -> None:
    """An exact identity with non-mapping labels is malformed."""
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    names = {
        "container": resources.containers,
        "network": resources.networks,
        "volume": resources.volumes,
        "image": (
            resources.headless_image,
            resources.gui_image,
            resources.imported_image,
        ),
    }
    target = names[kind][0]
    if kind == "container":
        value: object = {
            "Name": "/" + target,
            "Config": {"Labels": ["not-a-mapping"]},
        }
    elif kind in {"network", "volume"}:
        value = {"Name": target, "Labels": ["not-a-mapping"]}
    else:
        value = {
            "RepoTags": [target],
            "Config": {"Labels": ["not-a-mapping"]},
        }

    def runner(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv == ["docker", kind, "inspect", target]:
            return _completed(argv, stdout=json.dumps([value]))
        return _completed(
            argv,
            returncode=1,
            stdout="[]",
            stderr=f"Error: No such {argv[1]}: {argv[3]}",
        )

    with pytest.raises(docker_verify._InventoryFailure) as caught:
        docker_verify._inventory(runner, resources, tmp_path)
    assert caught.value.semantic is True
    assert caught.value.argv == ["docker", kind, "inspect", target]


def test_fix2_compose_hashes_exact_bytes_and_decodes_for_projection(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner()
    config_bytes: bytes | None = None

    def raw_config(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal config_bytes
        result = delegate(argv, root, **kwargs)
        if "config" in argv and "--format" in argv:
            config_bytes = str(result.stdout).encode("utf-8")
            result.stdout = config_bytes  # type: ignore[assignment]
        return result

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=raw_config,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    assert payload["status"] == "pass"
    assert config_bytes is not None
    render = payload["static_contract"]["render_proof"]
    expected_hash = hashlib.sha256(config_bytes).hexdigest()
    assert render["stdout_sha256"] == expected_hash
    assert render["selected_facts"]["source_stdout_sha256"] == expected_hash
    docker_status.validate_live_verifier_evidence(payload)


def test_fix2_invalid_utf8_compose_retains_exact_raw_hash(
    tmp_path: Path,
) -> None:
    """Invalid Compose bytes fail semantically with their literal hash."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner()
    config_bytes: bytes | None = None

    def invalid_config(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal config_bytes
        result = delegate(argv, root, **kwargs)
        if "config" in argv and "--format" in argv:
            config_bytes = str(result.stdout).encode("utf-8") + b"\xff"
            result.stdout = config_bytes  # type: ignore[assignment]
        return result

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=invalid_config,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    assert config_bytes is not None
    assert payload["status"] == "fail"
    assert payload["reason"] == "compose_contract_failed"
    failure = payload["static_contract"]
    assert failure["execution"] == "verifier_result"
    assert failure["stdout_sha256"] == hashlib.sha256(config_bytes).hexdigest()
    docker_status.validate_live_verifier_evidence(payload)


def test_fix2_healthy_bytes_are_decoded_for_health_postcondition(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner()

    def byte_health(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        result = delegate(argv, root, **kwargs)
        if argv[:3] == ["docker", "inspect", "--format"]:
            result.stdout = b"healthy\n"  # type: ignore[assignment]
        return result

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=byte_health,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    assert payload["status"] == "pass"
    docker_status.validate_live_verifier_evidence(payload)


def test_fix2_cleanup_exception_is_internal_error_and_keeps_primary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner(fail_at="start")

    def broken_cleanup(*_args: object, **_kwargs: object) -> tuple[object, object]:
        raise RuntimeError("private cleanup construction detail")

    monkeypatch.setattr(docker_verify, "_cleanup_owned", broken_cleanup)
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    assert payload["status"] == "fail"
    assert payload["reason"] == "headless_start_failed"
    assert payload["headless_health"]["boundary"] == "headless_start"
    assert payload["headless_health"]["execution"] == "command"
    assert payload["cleanup"]["status"] == "fail"
    assert payload["cleanup"]["execution"] == "internal_error"
    assert payload["cleanup"]["argv"] == []
    assert payload["cleanup"]["exit_code"] is None
    assert payload["cleanup"]["failure_proof"] == {"kind": "internal_error"}
    docker_status.validate_live_verifier_evidence(payload)


def test_fix2_workflow_exception_is_commandless_internal_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An ordinary exception outside the runner is not an interruption."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)

    def broken_identity(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("private workflow construction detail")

    monkeypatch.setattr(docker_verify, "_parse_image_identity", broken_identity)
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    assert payload["status"] == "fail"
    assert payload["reason"] == "image_identity_failed"
    failure = payload["headless_build"]
    assert failure["execution"] == "internal_error"
    assert failure["argv"] == []
    assert failure["exit_code"] is None
    assert failure["stdout_sha256"] == hashlib.sha256(b"").hexdigest()
    assert failure["stderr_sha256"] == hashlib.sha256(b"").hexdigest()
    assert failure["failure_proof"] == {"kind": "internal_error"}
    assert "private workflow" not in json.dumps(payload)
    docker_status.validate_live_verifier_evidence(payload)


@pytest.mark.parametrize(
    "kind", ["container", "network", "volume", "image"]
)
def test_fix3_inventory_rejects_substring_lookalike_absence(
    tmp_path: Path,
    kind: str,
) -> None:
    """Only exact kind/name absence errors may produce an empty inventory."""
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    targets = {
        "container": resources.containers,
        "network": resources.networks,
        "volume": resources.volumes,
        "image": (
            resources.headless_image,
            resources.gui_image,
            resources.imported_image,
        ),
    }
    target = targets[kind][0]

    def runner(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv == ["docker", kind, "inspect", target]:
            return _completed(
                argv,
                returncode=17,
                stderr="permission helper not found",
            )
        if (
            len(argv) == 4
            and argv[0] == "docker"
            and argv[1] in {"container", "network", "volume", "image"}
            and argv[2] == "inspect"
        ):
            return _completed(
                argv,
                returncode=1,
                stdout="[]",
                stderr=f"Error: No such {argv[1]}: {argv[3]}",
            )
        return _completed(argv, returncode=1, stderr="permission denied")

    with pytest.raises(docker_verify._InventoryFailure) as caught:
        docker_verify._inventory(runner, resources, tmp_path)
    assert caught.value.semantic is False
    assert caught.value.error is None
    assert caught.value.result.returncode == 17


def test_fix3_inventory_accepts_exact_kind_name_absence(
    tmp_path: Path,
) -> None:
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    target = resources.containers[0]

    def runner(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv == ["docker", "container", "inspect", target]:
            return _completed(
                argv,
                returncode=1,
                stdout="[]",
                stderr=f"Error: No such container: {target}",
            )
        if (
            len(argv) == 4
            and argv[0] == "docker"
            and argv[1] in {"container", "network", "volume", "image"}
            and argv[2] == "inspect"
        ):
            return _completed(
                argv,
                returncode=1,
                stdout="[]",
                stderr=f"Error: No such {argv[1]}: {argv[3]}",
            )
        return _completed(argv, returncode=1, stderr="permission denied")

    all_entries, owned = docker_verify._inventory(runner, resources, tmp_path)
    assert all_entries == []
    assert owned == []


def test_fix3_collision_record_hashes_real_inspect_streams(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    target = resources.containers[0]
    runner = _LiveVerifierRunner()
    runner.resources[target] = {
        "kind": "container",
        "name": target,
        "labels": {"private": "must-not-project"},
    }
    captured: dict[str, bytes] = {}

    def raw_collision(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        result = runner(argv, root, **kwargs)
        if argv == ["docker", "container", "inspect", target]:
            raw_stdout = (
                b" \n"
                + str(result.stdout).encode("utf-8")
                + b"\n"
            )
            raw_stderr = b"collision-stderr\n"
            captured["stdout"] = raw_stdout
            captured["stderr"] = raw_stderr
            result.stdout = raw_stdout  # type: ignore[assignment]
            result.stderr = raw_stderr  # type: ignore[assignment]
        return result

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=raw_collision,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    assert payload["reason"] == "collision_failed"
    failure = payload["static_contract"]
    assert failure["argv"] == ["docker", "container", "inspect", target]
    assert failure["exit_code"] == 0
    assert failure["stdout_sha256"] == hashlib.sha256(
        captured["stdout"]
    ).hexdigest()
    assert failure["stderr_sha256"] == hashlib.sha256(
        captured["stderr"]
    ).hexdigest()
    assert payload["name_collisions"]["before"][0]["labels"] == {}
    docker_status.validate_live_verifier_evidence(payload)


@pytest.mark.parametrize(
    "kind", ["container", "network", "volume", "image"]
)
def test_fix4_collision_record_rejects_noncanonical_inspect_argv(
    tmp_path: Path,
    kind: str,
) -> None:
    """Collision proof is bound to the typed inspect that observed it."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    target = {
        "container": resources.containers[0],
        "network": resources.networks[0],
        "volume": resources.volumes[0],
        "image": resources.headless_image,
    }[kind]
    runner = _LiveVerifierRunner()
    runner.resources[target] = {
        "kind": kind,
        "name": target,
        "labels": {docker_status.OWNERSHIP_LABEL_KEY: "foreign-owner"},
    }

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    docker_status.validate_live_verifier_evidence(payload)
    assert payload["static_contract"]["argv"] == [
        "docker",
        kind,
        "inspect",
        target,
    ]

    payload["static_contract"]["argv"] = ["docker", "info"]
    with pytest.raises(ValueError, match="collision.*command"):
        docker_status.validate_live_verifier_evidence(payload)


def test_fix3_collision_inventory_oserror_is_closed(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner()
    injected = False

    def broken_collision(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal injected
        typed_inspect = (
            len(argv) == 4
            and argv[0] == "docker"
            and argv[1] in {"container", "network", "volume", "image"}
            and argv[2] == "inspect"
        )
        if typed_inspect and not injected:
            injected = True
            raise OSError("private collision helper path")
        return delegate(argv, root, **kwargs)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=broken_collision,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    failure = payload["static_contract"]
    assert payload["reason"] == "collision_failed"
    assert failure["execution"] == "command_exception"
    assert failure["argv"][:3] == ["docker", "container", "inspect"]
    assert failure["exit_code"] is None
    assert failure["failure_proof"] == {
        "kind": "command_exception",
        "exception_kind": "os_error",
    }
    docker_status.validate_live_verifier_evidence(payload)


def test_fix3_collision_inventory_timeout_is_closed(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner()
    injected = False

    def broken_collision(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal injected
        typed_inspect = (
            len(argv) == 4
            and argv[0] == "docker"
            and argv[1] in {"container", "network", "volume", "image"}
            and argv[2] == "inspect"
        )
        if typed_inspect and not injected:
            injected = True
            raise subprocess.TimeoutExpired(
                argv, 3, output=b"timeout-out", stderr=b"timeout-err"
            )
        return delegate(argv, root, **kwargs)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=broken_collision,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    failure = payload["static_contract"]
    assert payload["reason"] == "collision_failed"
    assert failure["execution"] == "command_exception"
    assert failure["argv"][:3] == ["docker", "container", "inspect"]
    assert failure["exit_code"] is None
    assert failure["failure_proof"] == {
        "kind": "command_exception",
        "exception_kind": "timeout",
    }
    assert failure["stdout_sha256"] == hashlib.sha256(b"timeout-out").hexdigest()
    assert failure["stderr_sha256"] == hashlib.sha256(b"timeout-err").hexdigest()
    docker_status.validate_live_verifier_evidence(payload)


@pytest.mark.parametrize(
    ("case", "execution", "proof"),
    [
        (
            "timeout-bytes",
            "command_exception",
            {"kind": "command_exception", "exception_kind": "timeout"},
        ),
        (
            "oserror-bytes",
            "command_exception",
            {"kind": "command_exception", "exception_kind": "os_error"},
        ),
        ("timeout-text", "internal_error", {"kind": "internal_error"}),
        ("oserror-text", "internal_error", {"kind": "internal_error"}),
        ("exception", "internal_error", {"kind": "internal_error"}),
        (
            "keyboard",
            "interruption",
            {
                "kind": "interruption",
                "interruption_kind": "keyboard_interrupt",
                "phase": "collision",
            },
        ),
        (
            "base-exception",
            "interruption",
            {
                "kind": "interruption",
                "interruption_kind": "base_exception",
                "phase": "collision",
            },
        ),
    ],
)
def test_fix4_compose_collision_inventory_exception_union_is_closed(
    tmp_path: Path,
    case: str,
    execution: str,
    proof: dict[str, object],
) -> None:
    """Compose list failures enter the same closed collision union."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    expected_argv = [
        "docker",
        "container",
        "ls",
        "--all",
        "--filter",
        "label=com.docker.compose.project=" + resources.compose_project,
        "--format",
        "json",
    ]
    delegate = _LiveVerifierRunner()

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv == expected_argv:
            if case.startswith("timeout"):
                partial: bytes | str = (
                    b"compose-list-out"
                    if case == "timeout-bytes"
                    else "synthetic-text-out"
                )
                raise subprocess.TimeoutExpired(
                    argv, 3, output=partial, stderr=b"compose-list-err"
                )
            if case.startswith("oserror"):
                error = OSError("private Compose list path")
                error.stdout = (  # type: ignore[attr-defined]
                    b"compose-list-out"
                    if case == "oserror-bytes"
                    else "synthetic-text-out"
                )
                error.stderr = b"compose-list-err"  # type: ignore[attr-defined]
                raise error
            if case == "exception":
                raise RuntimeError("private Compose list failure")
            if case == "keyboard":
                raise KeyboardInterrupt("stop")
            raise BaseException("stop")
        return delegate(argv, root, **kwargs)

    payload: dict[str, object] | None = None
    escaped: BaseException | None = None
    try:
        payload = docker_verify._verify_live(
            tmp_path,
            Path("output/evidence/docker/live"),
            command_runner=runner,
            invocation_id="a1b2c3d4e5f6",
            expected_root=tmp_path,
        )
    except BaseException as exc:
        escaped = exc
    assert escaped is None, f"Compose collision exception escaped: {case}"
    assert payload is not None
    assert payload["reason"] == "collision_failed"
    assert payload["name_collisions"]["before"] == []
    failure = payload["static_contract"]
    assert failure["execution"] == execution
    assert failure["failure_proof"] == proof
    assert failure["exit_code"] is None
    if execution == "command_exception":
        assert failure["argv"] == expected_argv
        assert failure["stdout_sha256"] == hashlib.sha256(
            b"compose-list-out"
        ).hexdigest()
        assert failure["stderr_sha256"] == hashlib.sha256(
            b"compose-list-err"
        ).hexdigest()
    else:
        assert failure["argv"] == []
        assert failure["stdout_sha256"] == hashlib.sha256(b"").hexdigest()
        assert failure["stderr_sha256"] == hashlib.sha256(b"").hexdigest()
    docker_status.validate_live_verifier_evidence(payload)


@pytest.mark.parametrize(
    ("raised", "interruption_kind"),
    [
        (KeyboardInterrupt("stop"), "keyboard_interrupt"),
        (BaseException("stop"), "base_exception"),
    ],
    ids=["keyboard-interrupt", "base-exception"],
)
def test_fix5_collision_interruption_phase_is_bound_to_terminal_boundary(
    tmp_path: Path,
    raised: BaseException,
    interruption_kind: str,
) -> None:
    """Changing only an interruption proof phase cannot forge its owner."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    resources = docker_verify.InvocationResources.from_id("a1b2c3d4e5f6")
    expected_argv = [
        "docker",
        "container",
        "ls",
        "--all",
        "--filter",
        "label=com.docker.compose.project=" + resources.compose_project,
        "--format",
        "json",
    ]
    delegate = _LiveVerifierRunner()

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if argv == expected_argv:
            raise raised
        return delegate(argv, root, **kwargs)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    assert payload["reason"] == "collision_failed"
    failure = payload["static_contract"]
    assert failure["boundary"] == "collision"
    assert failure["failure_proof"] == {
        "kind": "interruption",
        "interruption_kind": interruption_kind,
        "phase": "collision",
    }
    docker_status.validate_live_verifier_evidence(payload)

    forged = copy.deepcopy(payload)
    forged["static_contract"]["failure_proof"]["phase"] = "headless_build"
    with pytest.raises(ValueError, match="interruption.*phase|phase.*boundary"):
        docker_status.validate_live_verifier_evidence(forged)


def test_fix5_cleanup_rejects_terminal_remove_reusing_successful_identity(
    tmp_path: Path,
) -> None:
    """A failed remove cannot reuse an earlier successful remove identity."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner()

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if (
            len(argv) == 4
            and argv[0] == "docker"
            and argv[2] == "rm"
            and len(delegate.resources) == 1
        ):
            delegate.resources.pop(argv[-1], None)
            return _completed(
                argv,
                returncode=17,
                stderr="injected cleanup remove failure",
            )
        return delegate(argv, root, **kwargs)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    actions = payload["owned_resources"]["cleanup_actions"]
    successful = next(
        action
        for action in actions
        if action["action_kind"] == "remove" and action["status"] == "pass"
    )
    terminal = actions[-1]
    assert successful["status"] == "pass"
    assert successful["action_kind"] == "remove"
    assert terminal["status"] == "fail"
    assert terminal["action_kind"] == "remove"
    assert (
        successful["resource_kind"],
        successful["resource_name"],
    ) != (terminal["resource_kind"], terminal["resource_name"])
    docker_status.validate_live_verifier_evidence(payload)

    forged = copy.deepcopy(payload)
    successful_identity = (
        successful["resource_kind"],
        successful["resource_name"],
    )
    forged_argv = [
        "docker",
        successful_identity[0],
        "rm",
        successful_identity[1],
    ]
    for carrier in (
        forged["owned_resources"]["cleanup_actions"][-1],
        forged["cleanup"],
    ):
        carrier["resource_kind"] = successful_identity[0]
        carrier["resource_name"] = successful_identity[1]
        carrier["argv"] = list(forged_argv)

    with pytest.raises(ValueError, match="chronology|already.*removed|duplicate"):
        docker_status.validate_live_verifier_evidence(forged)


@pytest.mark.parametrize("stage", ["requery", "post_remove", "final"])
def test_fix5_cleanup_helper_failure_retains_best_known_inventory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stage: str,
) -> None:
    """Throwing phase construction cannot erase cleanup observations."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner(fail_at="start")
    cleanup_inspects = 0
    removal_seen = False
    empty_inspects = 0
    injected = False

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal cleanup_inspects, removal_seen, empty_inspects, injected
        typed_inspect = (
            len(argv) == 4
            and argv[0] == "docker"
            and argv[1] in {"container", "network", "volume", "image"}
            and argv[2] == "inspect"
        )
        cleanup_started = "start" in delegate.events
        if cleanup_started and typed_inspect:
            cleanup_inspects += 1
            if not delegate.resources:
                empty_inspects += 1
        should_raise = (
            not injected
            and cleanup_started
            and typed_inspect
            and (
                (stage == "requery" and cleanup_inspects == 10)
                or (stage == "post_remove" and removal_seen)
                or (stage == "final" and empty_inspects == 10)
            )
        )
        if should_raise:
            injected = True
            raise RuntimeError("private cleanup inventory failure")
        result = delegate(argv, root, **kwargs)
        if cleanup_started and len(argv) == 4 and argv[2] == "rm":
            removal_seen = True
        return result

    def fail_phase_helper(
        _action: Mapping[str, object], _detail: str
    ) -> dict[str, object]:
        raise RuntimeError("cleanup phase helper failed")

    monkeypatch.setattr(
        docker_verify, "_cleanup_phase_from_action", fail_phase_helper
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert injected is True
    assert payload["status"] == "fail"
    assert payload["reason"] == "headless_start_failed"
    assert payload["headless_health"]["boundary"] == "headless_start"
    owned = payload["owned_resources"]
    assert owned["before_cleanup_complete"] is True
    assert owned["before_cleanup"]
    assert owned["after_cleanup_complete"] is False
    if stage == "final":
        assert owned["after_cleanup"] == []
    elif stage == "post_remove":
        removed = {
            (action["resource_kind"], action["resource_name"])
            for action in owned["cleanup_actions"]
            if action.get("action_kind") == "remove"
            and action.get("status") == "pass"
        }
        assert not removed.intersection(
            (item["kind"], item["name"])
            for item in owned["after_cleanup"]
        )
    else:
        assert owned["after_cleanup"] == owned["before_cleanup"]
    actions = owned["cleanup_actions"]
    assert any(action.get("inventory_stage") == stage for action in actions)
    successful_removes = [
        action
        for action in actions
        if action.get("action_kind") == "remove"
        and action.get("status") == "pass"
    ]
    assert len(successful_removes) == {
        "requery": 0,
        "post_remove": 1,
        "final": len(owned["before_cleanup"]),
    }[stage]
    assert payload["cleanup"]["status"] == "fail"
    assert payload["cleanup"]["execution"] == "internal_error"
    docker_status.validate_live_verifier_evidence(payload)


@pytest.mark.parametrize(
    "stage", ["initial", "requery", "post_remove", "final", "remove"]
)
@pytest.mark.parametrize("exception_kind", ["timeout", "os_error"])
def test_fix4_cleanup_command_exception_rejects_noncanonical_argv(
    tmp_path: Path,
    stage: str,
    exception_kind: str,
) -> None:
    """Cleanup command exceptions retain their exact inspect or remove identity."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner()
    cleanup_inspects = 0
    removal_seen = False
    empty_inspects = 0
    injected = False

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal cleanup_inspects, removal_seen, empty_inspects, injected
        typed_inspect = (
            len(argv) == 4
            and argv[0] == "docker"
            and argv[1] in {"container", "network", "volume", "image"}
            and argv[2] == "inspect"
        )
        cleanup_started = "export" in delegate.events
        if cleanup_started and typed_inspect:
            cleanup_inspects += 1
            if not delegate.resources:
                empty_inspects += 1
        should_raise = (
            not injected
            and cleanup_started
            and (
                (stage == "initial" and typed_inspect and cleanup_inspects == 1)
                or (stage == "requery" and typed_inspect and cleanup_inspects == 10)
                or (stage == "post_remove" and typed_inspect and removal_seen)
                or (stage == "final" and typed_inspect and empty_inspects == 10)
                or (
                    stage == "remove"
                    and len(argv) == 4
                    and argv[2] == "rm"
                    and len(delegate.resources) == 1
                )
            )
        )
        if should_raise:
            injected = True
            if stage == "remove":
                delegate.resources.pop(argv[-1], None)
            if exception_kind == "timeout":
                raise subprocess.TimeoutExpired(
                    argv,
                    3,
                    output=b"cleanup-partial-out",
                    stderr=b"cleanup-partial-err",
                )
            error = OSError("private cleanup path")
            error.stdout = b"cleanup-partial-out"  # type: ignore[attr-defined]
            error.stderr = b"cleanup-partial-err"  # type: ignore[attr-defined]
            raise error
        result = delegate(argv, root, **kwargs)
        if cleanup_started and len(argv) == 4 and argv[2] == "rm":
            removal_seen = True
        return result

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    assert injected is True
    docker_status.validate_live_verifier_evidence(payload)
    terminal = payload["owned_resources"]["cleanup_actions"][-1]
    assert terminal["execution"] == "command_exception"
    assert terminal["failure_proof"] == {
        "kind": "command_exception",
        "exception_kind": exception_kind,
    }
    expected_argv = [
        "docker",
        terminal["resource_kind"],
        "rm" if terminal["action_kind"] == "remove" else "inspect",
        terminal["resource_name"],
    ]
    assert terminal["argv"] == expected_argv
    assert payload["cleanup"]["argv"] == expected_argv

    terminal["argv"] = ["docker", "info"]
    payload["cleanup"]["argv"] = ["docker", "info"]
    with pytest.raises(ValueError, match="command exception"):
        docker_status.validate_live_verifier_evidence(payload)


def test_fix3_cleanup_evidence_construction_failure_is_terminal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner(fail_at="start")

    def fail_cleanup_phase(
        _action: Mapping[str, object], _detail: str
    ) -> dict[str, object]:
        raise RuntimeError("failure-evidence-construction")

    original_not_run = docker_verify._not_run_record

    def fail_terminal_fallback(detail: str) -> dict[str, object]:
        if runner.final_inventory_seen:
            raise RuntimeError("ultimate-fallback-construction")
        return original_not_run(detail)

    monkeypatch.setattr(
        docker_verify, "_cleanup_phase_from_action", fail_cleanup_phase
    )
    monkeypatch.setattr(docker_verify, "_not_run_record", fail_terminal_fallback)
    payload: dict[str, object] | None = None
    escaped: BaseException | None = None
    try:
        payload = docker_verify._verify_live(
            tmp_path,
            Path("output/evidence/docker/live"),
            command_runner=runner,
            invocation_id="a1b2c3d4e5f6",
            expected_root=tmp_path,
        )
    except BaseException as exc:
        escaped = exc
    assert escaped is None, "ultimate cleanup fallback escaped"
    assert payload is not None
    assert runner.final_inventory_seen is True
    assert "cleanup_rm" in runner.events
    assert payload["status"] == "fail"
    assert payload["reason"] == "headless_start_failed"
    assert payload["headless_health"]["boundary"] == "headless_start"
    cleanup = payload["cleanup"]
    assert cleanup["status"] == "fail"
    assert cleanup["boundary"] == "cleanup"
    assert cleanup["execution"] == "internal_error"
    assert cleanup["failure_proof"] == {"kind": "internal_error"}
    owned = payload["owned_resources"]
    assert owned["before_cleanup_complete"] is True
    assert owned["after_cleanup_complete"] is True
    assert owned["after_cleanup"] == []
    actions = owned["cleanup_actions"]
    removed = [action for action in actions if action["action_kind"] == "remove"]
    assert [
        (action["resource_kind"], action["resource_name"])
        for action in removed
    ] == sorted(
        (entry["kind"], entry["name"]) for entry in owned["before_cleanup"]
    )
    assert all(action["status"] == "pass" for action in removed)
    terminal = actions[-1]
    assert terminal["action_kind"] == "inventory"
    assert terminal["inventory_stage"] == "final"
    assert terminal["execution"] == "internal_error"
    assert terminal["failure_proof"] == {"kind": "internal_error"}
    docker_status.validate_live_verifier_evidence(payload)


@pytest.mark.parametrize(
    ("primary_event", "primary_reason"),
    [
        ("start", "headless_start_failed"),
        ("load", "image_load_failed"),
        ("export", "evidence_export_failed"),
    ],
)
def test_verifier_cleanup_failure_never_overwrites_earliest_primary(
    tmp_path: Path,
    primary_event: str,
    primary_reason: str,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner(
        fail_at=primary_event,
        cleanup_fail=True,
    )

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )

    assert payload["reason"] == primary_reason
    assert payload["cleanup"]["status"] == "fail"
    assert payload["cleanup"]["boundary"] == "cleanup"
    docker_status.validate_evidence(payload)


def test_verifier_validates_before_writer_and_writer_failure_is_not_export(
    tmp_path: Path,
) -> None:
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    runner = _LiveVerifierRunner()
    observations: list[str] = []

    def failing_writer(_path: Path, payload: object) -> None:
        docker_status.validate_evidence(payload)
        observations.append(payload["reason"])
        raise OSError("simulated atomic writer failure")

    with pytest.raises(OSError, match="writer failure"):
        docker_verify._verify_live(
            tmp_path,
            Path("output/evidence/docker/live"),
            command_runner=runner,
            evidence_writer=failing_writer,
            invocation_id="a1b2c3d4e5f6",
            expected_root=tmp_path,
        )

    assert observations == ["live_verification_complete"]
    assert runner.final_inventory_seen is True


_AMENDED_BOUNDARY_OWNERS = {
    "collision": "static_contract",
    "compose_contract": "static_contract",
    "headless_build": "headless_build",
    "image_identity": "headless_build",
    "headless_start": "headless_health",
    "container_health": "headless_health",
    "api_health": "headless_health",
    "primary_api_run": "headless_smoke",
    "controlled_stop": "save_load",
    "image_save": "save_load",
    "image_load": "save_load",
    "image_retag": "save_load",
    "imported_container_create": "save_load",
    "imported_container_start": "save_load",
    "imported_docker_health": "save_load",
    "imported_api_smoke": "save_load",
    "gui_build": "gui_build",
    "gui_start": "gui_smoke",
    "gui_health": "gui_smoke",
    "gui_api_run": "gui_smoke",
    "gui_frame_capture": "gui_smoke",
    "cleanup": "cleanup",
}


_AMENDED_BOUNDARY_EVENTS = {
    "compose_contract": "config_quiet",
    "headless_build": "build",
    "image_identity": "image_identity",
    "headless_start": "start",
    "container_health": "health",
    "api_health": "api_health",
    "primary_api_run": "quick_smoke",
    "controlled_stop": "stop",
    "image_save": "save",
    "image_load": "load",
    "image_retag": "retag",
    "imported_container_create": "imported_create",
    "imported_container_start": "imported_start",
    "imported_docker_health": "imported_health",
    "imported_api_smoke": "imported_smoke",
    "gui_build": "gui_build",
    "gui_start": "gui_start",
    "gui_health": "gui_health",
    "gui_api_run": "gui_frames",
    "gui_frame_capture": "gui_frames",
}


AmendedEvidenceFactory = Callable[..., dict[str, object]]


@pytest.fixture
def amended_evidence(tmp_path: Path) -> AmendedEvidenceFactory:
    """Build strict amended-test inputs through the injected live producer."""
    sequence = 0

    def produce(
        boundary: str,
        *,
        cleanup_fails: bool = False,
        include_gui: bool = False,
        retain_after_cleanup: bool = False,
    ) -> dict[str, object]:
        nonlocal sequence
        sequence += 1
        root = tmp_path / f"producer-{sequence}-{boundary}"
        (root / "data" / "intersection_data").mkdir(parents=True)

        delegate = _LiveVerifierRunner(
            fail_at=(
                "export"
                if boundary == "evidence_export"
                else _AMENDED_BOUNDARY_EVENTS.get(boundary)
            ),
            retain_after_cleanup=retain_after_cleanup,
        )
        runner: Callable[..., subprocess.CompletedProcess[str]] = delegate
        if boundary == "collision":
            resources = docker_verify.InvocationResources.from_id(
                "a1b2c3d4e5f6"
            )
            target = resources.containers[0]
            delegate.resources[target] = {
                "kind": "container",
                "name": target,
                "labels": {"foreign": "owner"},
            }
        elif (
            boundary == "cleanup" or cleanup_fails
        ) and not retain_after_cleanup:

            def fail_terminal_remove(
                argv: list[str],
                cwd: Path,
                **kwargs: object,
            ) -> subprocess.CompletedProcess[str]:
                terminal_remove = (
                    len(argv) == 4
                    and argv[0] == "docker"
                    and argv[2] == "rm"
                    and len(delegate.resources) == 1
                )
                result = delegate(argv, cwd, **kwargs)
                if terminal_remove:
                    result.returncode = 19
                    result.stderr = "cleanup_rm failed"
                return result

            runner = fail_terminal_remove

        payload = docker_verify._verify_live(
            root,
            Path("output/evidence/docker/live"),
            command_runner=runner,
            invocation_id="a1b2c3d4e5f6",
            include_gui=include_gui or boundary.startswith("gui_"),
            expected_root=root,
        )
        if boundary == "gui_api_run":
            payload["reason"] = "gui_api_run_failed"
            payload["gui_smoke"]["boundary"] = "gui_api_run"
        return payload

    return produce


def _without_observed_image_identity(payload: dict[str, object]) -> None:
    for field in (
        "headless_image_id",
        "repository_digest",
        "config_digest",
        "content_digest",
    ):
        payload["invocation"].pop(field, None)


def _legacy_identity_failure(phase: str) -> dict[str, object]:
    """Return a boundary-free legacy command failure for identity mutations."""
    payload = _truthful_command_phase_failure(phase)
    if phase == "headless_build":
        _without_observed_image_identity(payload)
    docker_status.validate_evidence(payload)
    return payload


def _legacy_identity_pass() -> dict[str, object]:
    """Return a genuine discriminator-free legacy pass identity fixture."""
    payload = _complete_live_pass_evidence()
    docker_status.validate_evidence(payload)
    return payload


def test_amended_early_failure_accepts_planned_identity_without_digests(
    amended_evidence: AmendedEvidenceFactory,
) -> None:
    payload = amended_evidence("headless_build")

    docker_status.validate_evidence(payload)
    assert not {
        "headless_image_id",
        "repository_digest",
        "config_digest",
        "content_digest",
    }.intersection(payload["invocation"])


@pytest.mark.parametrize(
    ("boundary", "owner"), list(_AMENDED_BOUNDARY_OWNERS.items())
)
def test_amended_boundary_binds_exact_owner_and_reason(
    boundary: str,
    owner: str,
    amended_evidence: AmendedEvidenceFactory,
) -> None:
    payload = amended_evidence(boundary)

    docker_status.validate_evidence(payload)
    assert payload["reason"] == f"{boundary}_failed"
    assert payload[owner]["boundary"] == boundary


def test_amended_boundary_rejects_wrong_owner_or_reason(
    amended_evidence: AmendedEvidenceFactory,
) -> None:
    wrong_owner = amended_evidence("headless_start")
    wrong_owner["headless_health"].pop("boundary")
    wrong_owner["headless_build"]["boundary"] = "headless_start"
    with pytest.raises(ValueError, match="boundary"):
        docker_status.validate_evidence(wrong_owner)

    wrong_reason = amended_evidence("headless_start")
    wrong_reason["reason"] = "container_health_failed"
    with pytest.raises(ValueError, match="boundary carrier"):
        docker_status.validate_evidence(wrong_reason)


@pytest.mark.parametrize(
    "cleanup_fails", [False, True], ids=["cleanup-pass", "cleanup-fail"]
)
def test_amended_export_is_terminal_primary_with_independent_cleanup(
    cleanup_fails: bool,
    amended_evidence: AmendedEvidenceFactory,
) -> None:
    docker_status.validate_evidence(
        amended_evidence("evidence_export", cleanup_fails=cleanup_fails)
    )


def test_amended_gui_capture_may_survive_failed_export_without_false_link(
    amended_evidence: AmendedEvidenceFactory,
) -> None:
    payload = amended_evidence("evidence_export", include_gui=True)

    docker_status.validate_evidence(payload)


def test_amended_observed_image_identity_is_atomic_and_required_late(
    amended_evidence: AmendedEvidenceFactory,
) -> None:
    partial = _legacy_identity_failure("headless_build")
    partial["invocation"]["headless_image_id"] = "sha256:" + "a" * 64
    with pytest.raises(ValueError, match="observed image identity"):
        docker_status.validate_evidence(partial)

    late = _legacy_identity_pass()
    _without_observed_image_identity(late)
    with pytest.raises(ValueError, match="observed image identity"):
        docker_status.validate_evidence(late)

    strict_early = amended_evidence("headless_build")
    strict_early["invocation"]["headless_image_id"] = "sha256:" + "a" * 64
    docker_status.validate_live_verifier_evidence(strict_early)

    strict_late = amended_evidence("headless_start")
    _without_observed_image_identity(strict_late)
    with pytest.raises(ValueError, match="observed image identity"):
        docker_status.validate_live_verifier_evidence(strict_late)


@pytest.mark.parametrize("mask", range(1, 15))
def test_amended_rejects_every_proper_observed_digest_subset(
    mask: int,
) -> None:
    payload = _legacy_identity_failure("headless_build")
    fields = (
        "headless_image_id",
        "repository_digest",
        "config_digest",
        "content_digest",
    )
    for index, field in enumerate(fields):
        if mask & (1 << index):
            payload["invocation"][field] = "sha256:" + chr(97 + index) * 64

    with pytest.raises(ValueError, match="all-or-none"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "boundary",
    [
        boundary
        for boundary, owner in _AMENDED_BOUNDARY_OWNERS.items()
        if owner not in {"static_contract", "headless_build", "cleanup"}
    ],
)
def test_amended_every_post_identity_boundary_requires_observed_digests(
    boundary: str,
    amended_evidence: AmendedEvidenceFactory,
) -> None:
    legacy = _legacy_identity_pass()
    _without_observed_image_identity(legacy)

    with pytest.raises(ValueError, match="observed image identity"):
        docker_status.validate_evidence(legacy)

    strict = amended_evidence(boundary)
    _without_observed_image_identity(strict)
    with pytest.raises(ValueError, match="observed image identity"):
        docker_status.validate_live_verifier_evidence(strict)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "001122334455"),
        ("compose_project", "foreign-project"),
        ("headless_image", "foreign-headless:local"),
        ("gui_image", "foreign-gui:local"),
        ("imported_image", "foreign-imported:local"),
    ],
)
def test_amended_early_identity_still_derives_every_planned_field(
    field: str,
    value: str,
    amended_evidence: AmendedEvidenceFactory,
) -> None:
    payload = amended_evidence("headless_build")
    payload["invocation"][field] = value

    with pytest.raises(ValueError, match="invocation"):
        docker_status.validate_evidence(payload)


def test_amended_verifier_result_proof_kinds_cannot_cross_boundaries(
    amended_evidence: AmendedEvidenceFactory,
) -> None:
    health = amended_evidence("container_health")
    record = health["headless_health"]
    record.update(
        {
            "execution": "verifier_result",
            "argv": [
                "docker",
                "inspect",
                "--format",
                "{{.State.Health.Status}}",
                "ca-mp-task19-a1b2c3d4e5f6-judge-1",
            ],
            "exit_code": 0,
            "failure_proof": {"kind": "collision_detected", "collisions": []},
        }
    )
    with pytest.raises(ValueError, match="collision-boundary"):
        docker_status.validate_evidence(health)

    unrelated = amended_evidence("container_health")
    unrelated["headless_health"].update(
        {
            "execution": "verifier_result",
            "argv": ["docker", "info"],
            "exit_code": 0,
            "failure_proof": {
                "kind": "postcondition_mismatch",
                "expected": "healthy",
                "observed": "starting",
            },
        }
    )
    with pytest.raises(ValueError, match="canonical"):
        docker_status.validate_evidence(unrelated)

    collision = amended_evidence("collision")
    collision["static_contract"]["failure_proof"] = {
        "kind": "postcondition_mismatch",
        "expected": "valid_inventory_json",
        "observed": "malformed_inventory_json",
    }
    collision["static_contract"]["argv"] = [
        "docker",
        "container",
        "inspect",
        "ca-mp-task19-a1b2c3d4e5f6-judge-1",
    ]
    with pytest.raises(ValueError, match="collision inventory"):
        docker_status.validate_evidence(collision)


def test_amended_verifier_result_preserves_honest_execution_shape(
    amended_evidence: AmendedEvidenceFactory,
) -> None:
    collision = amended_evidence("collision")
    docker_status.validate_evidence(collision)

    dishonest_nonzero = copy.deepcopy(collision)
    dishonest_nonzero["static_contract"]["exit_code"] = 9
    with pytest.raises(ValueError, match="preserve success"):
        docker_status.validate_evidence(dishonest_nonzero)

    local = amended_evidence("image_identity")
    local["headless_build"].update(
        {
            "execution": "internal_error",
            "argv": [],
            "exit_code": None,
            "stdout_sha256": hashlib.sha256(b"").hexdigest(),
            "stderr_sha256": hashlib.sha256(b"").hexdigest(),
            "failure_proof": {"kind": "internal_error"},
        }
    )
    docker_status.validate_evidence(local)

    dishonest_local = copy.deepcopy(local)
    dishonest_local["headless_build"]["argv"] = ["docker", "image", "inspect"]
    with pytest.raises(ValueError, match="internal error"):
        docker_status.validate_evidence(dishonest_local)


def test_amended_cleanup_retention_preserves_successful_rm_as_mismatch(
    amended_evidence: AmendedEvidenceFactory,
) -> None:
    payload = amended_evidence("cleanup", retain_after_cleanup=True)

    docker_status.validate_evidence(payload)


def test_amended_collision_and_export_proofs_are_closed_and_canonical(
    amended_evidence: AmendedEvidenceFactory,
) -> None:
    foreign = amended_evidence("collision")
    foreign["static_contract"]["failure_proof"]["collisions"][0][
        "name"
    ] = "foreign-container"
    with pytest.raises(ValueError, match="collision"):
        docker_status.validate_evidence(foreign)

    traversal = amended_evidence("evidence_export")
    traversal["exported_evidence"]["contents"][0]["path"] = "../escape.json"
    with pytest.raises(ValueError, match="relative"):
        docker_status.validate_evidence(traversal)

    unknown = amended_evidence("collision")
    unknown["static_contract"]["failure_proof"]["private"] = "no"
    with pytest.raises(ValueError, match="unexpected"):
        docker_status.validate_evidence(unknown)


def _completed(
    argv: list[str],
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout, stderr)


def _canonical_json_hash(value: object) -> str:
    """Match the strict producer's canonical structured-body hash."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _legacy_command_smoke_live_pass_evidence() -> dict[str, object]:
    """Return the obsolete command-smoke document for negative test setup.

    Deliberately do not call production builders or derive keys from
    ``docker_status.PHASES``: this fixture is the schema oracle used to catch
    accidental weakening of the release-evidence contract.
    """
    invocation_id = "a1b2c3d4e5f6"
    compose_project = f"ca-mp-task19-{invocation_id}"
    headless_image = f"{compose_project}-headless:local"
    gui_image = f"{compose_project}-gui:local"
    imported_image = f"{compose_project}-imported:local"
    ownership_key = "io.challengecup.task19.invocation"
    digest_a = "a" * 64
    digest_b = "b" * 64
    digest_c = "c" * 64
    digest_d = "d" * 64
    empty_stream_digest = hashlib.sha256(b"").hexdigest()

    def record(
        status: str,
        argv: list[str],
        exit_code: int | None,
        detail: str,
        *,
        version: str | None = None,
        empty_streams: bool = False,
    ) -> dict[str, object]:
        value: dict[str, object] = {
            "status": status,
            "started_at": "2026-08-24T00:00:00Z",
            "finished_at": "2026-08-24T00:00:01Z",
            "argv": argv,
            "exit_code": exit_code,
            "stdout_sha256": (
                empty_stream_digest if empty_streams else digest_a
            ),
            "stderr_sha256": (
                empty_stream_digest if empty_streams else digest_b
            ),
            "detail": detail,
        }
        if version is not None:
            value["version"] = version
        return value

    resources = {
        "compose_project": compose_project,
        "containers": [
            f"{compose_project}-judge-1",
            f"{compose_project}-judge-gui-1",
            f"{compose_project}-imported-judge-1",
        ],
        "networks": [f"{compose_project}_default"],
        "volumes": [
            f"{compose_project}_judge-output",
            f"{compose_project}_judge-gui-output",
        ],
        "images": [headless_image, gui_image, imported_image],
    }
    owner = {ownership_key: invocation_id}
    return {
        "schema": "judge-docker-evidence.v1",
        "checked_at": "2026-08-24T00:00:00Z",
        "status": "pass",
        "reason": "live_verification_complete",
        "platform": {"os": "Linux", "architecture": "x86_64"},
        "cli": record(
            "pass",
            ["docker", "--version"],
            0,
            "Docker CLI detected",
            version="27.0.0",
        ),
        "daemon": record(
            "pass",
            ["docker", "info", "--format", "{{json .ServerVersion}}"],
            0,
            "Docker daemon responded",
            version="27.0.0",
        ),
        "static_contract": record(
            "pass",
            [
                "docker",
                "compose",
                "--project-name",
                compose_project,
                "config",
                "--quiet",
            ],
            0,
            "static Docker contract verified",
        ),
        "headless_build": record(
            "pass",
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",
                "-t",
                headless_image,
                ".",
            ],
            0,
            "headless image built",
        ),
        "headless_health": record(
            "pass",
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Health.Status}}",
                f"{compose_project}-judge-1",
            ],
            0,
            "headless health check passed",
        ),
        "headless_smoke": record(
            "pass",
            [
                "docker",
                "exec",
                f"{compose_project}-judge-1",
                "python",
                "-m",
                "scripts.quick_smoke",
                "--run-id",
                f"quick-smoke-{invocation_id}",
                "--output",
                f"app/output/runs/quick-smoke-{invocation_id}",
                "--steps",
                "100",
            ],
            0,
            "100-step API quick smoke passed",
        ),
        "save_load": record(
            "pass",
            [
                "docker",
                "image",
                "save",
                "--output",
                f"output/evidence/docker/live/{invocation_id}/"
                "headless-image.tar",
                headless_image,
            ],
            0,
            "headless image saved for independent reload",
        ),
        "gui_build": record(
            "not_run",
            [],
            None,
            "GUI profile was not requested",
            empty_streams=True,
        ),
        "gui_smoke": record(
            "not_run",
            [],
            None,
            "GUI profile was not requested",
            empty_streams=True,
        ),
        "cleanup": record(
            "pass",
            [
                "docker",
                "container",
                "rm",
                f"{compose_project}-judge-1",
            ],
            0,
            "owned resources removed after label recheck",
        ),
        "invocation_id": invocation_id,
        "invocation": {
            "id": invocation_id,
            "compose_project": compose_project,
            "headless_image": headless_image,
            "gui_image": gui_image,
            "imported_image": imported_image,
            "headless_image_id": f"sha256:{digest_a}",
            "repository_digest": f"sha256:{digest_b}",
            "config_digest": f"sha256:{digest_c}",
            "content_digest": f"sha256:{digest_d}",
            "ownership_label": {"key": ownership_key, "value": invocation_id},
        },
        "quick_smoke": {
            "evidence_class": "quick_smoke",
            "requested_steps": 100,
            "completed_steps": [
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
                20,
                21,
                22,
                23,
                24,
                25,
                26,
                27,
                28,
                29,
                30,
                31,
                32,
                33,
                34,
                35,
                36,
                37,
                38,
                39,
                40,
                41,
                42,
                43,
                44,
                45,
                46,
                47,
                48,
                49,
                50,
                51,
                52,
                53,
                54,
                55,
                56,
                57,
                58,
                59,
                60,
                61,
                62,
                63,
                64,
                65,
                66,
                67,
                68,
                69,
                70,
                71,
                72,
                73,
                74,
                75,
                76,
                77,
                78,
                79,
                80,
                81,
                82,
                83,
                84,
                85,
                86,
                87,
                88,
                89,
                90,
                91,
                92,
                93,
                94,
                95,
                96,
                97,
                98,
                99,
                100,
            ],
            "run_id": f"quick-smoke-{invocation_id}",
            "terminal_status": "completed",
            "output": {
                "root": "app/output",
                "path": f"runs/quick-smoke-{invocation_id}",
            },
        },
        "save_load_proof": {
            "tar_path": (
                f"output/evidence/docker/live/{invocation_id}/"
                "headless-image.tar"
            ),
            "imported_image": imported_image,
            "imported_container": f"{compose_project}-imported-judge-1",
            "image_load": record(
                "pass",
                [
                    "docker",
                    "image",
                    "load",
                    "--input",
                    (
                        f"output/evidence/docker/live/{invocation_id}/"
                        "headless-image.tar"
                    ),
                ],
                0,
                "image loaded under independent tag",
            ),
            "image_retag": record(
                "pass",
                ["docker", "image", "tag", headless_image, imported_image],
                0,
                "loaded image retagged under the independent image name",
            ),
            "imported_container_create": record(
                "pass",
                [
                    "docker",
                    "container",
                    "create",
                    "--name",
                    f"{compose_project}-imported-judge-1",
                    "--label",
                    f"{ownership_key}={invocation_id}",
                    imported_image,
                ],
                0,
                "independent imported-image container created",
            ),
            "imported_container_start": record(
                "pass",
                [
                    "docker",
                    "container",
                    "start",
                    f"{compose_project}-imported-judge-1",
                ],
                0,
                "independent imported-image container started",
            ),
            "repeated_health": record(
                "pass",
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Health.Status}}",
                    f"{compose_project}-imported-judge-1",
                ],
                0,
                "loaded image health check passed",
            ),
            "repeated_smoke": record(
                "pass",
                [
                    "docker",
                    "exec",
                    f"{compose_project}-imported-judge-1",
                    "python",
                    "-m",
                    "scripts.quick_smoke",
                ],
                0,
                "loaded image quick smoke passed",
            ),
        },
        "name_collisions": {"expected_resources": resources, "before": []},
        "owned_resources": {
            "before_cleanup": [
                {
                    "kind": "container",
                    "name": resources["containers"][0],
                    "labels": owner,
                },
                {
                    "kind": "container",
                    "name": resources["containers"][2],
                    "labels": owner,
                },
                {
                    "kind": "network",
                    "name": resources["networks"][0],
                    "labels": owner,
                },
                {
                    "kind": "volume",
                    "name": resources["volumes"][0],
                    "labels": owner,
                },
                {"kind": "image", "name": headless_image, "labels": owner},
                {"kind": "image", "name": imported_image, "labels": owner},
            ],
            "after_cleanup": [],
            "cleanup_actions": [
                {
                    "resource_kind": "container",
                    "resource_name": f"{compose_project}-judge-1",
                    "required_label": {
                        "key": ownership_key,
                        "value": invocation_id,
                    },
                    "execution": "command",
                    "argv": [
                        "docker",
                        "container",
                        "rm",
                        f"{compose_project}-judge-1",
                    ],
                    "exit_code": 0,
                    "stdout_sha256": digest_a,
                    "stderr_sha256": digest_b,
                },
                {
                    "resource_kind": "container",
                    "resource_name": f"{compose_project}-imported-judge-1",
                    "required_label": {
                        "key": ownership_key,
                        "value": invocation_id,
                    },
                    "execution": "command",
                    "argv": [
                        "docker",
                        "container",
                        "rm",
                        f"{compose_project}-imported-judge-1",
                    ],
                    "exit_code": 0,
                    "stdout_sha256": digest_a,
                    "stderr_sha256": digest_b,
                },
                {
                    "resource_kind": "network",
                    "resource_name": f"{compose_project}_default",
                    "required_label": {
                        "key": ownership_key,
                        "value": invocation_id,
                    },
                    "execution": "command",
                    "argv": [
                        "docker",
                        "network",
                        "rm",
                        f"{compose_project}_default",
                    ],
                    "exit_code": 0,
                    "stdout_sha256": digest_a,
                    "stderr_sha256": digest_b,
                },
                {
                    "resource_kind": "volume",
                    "resource_name": f"{compose_project}_judge-output",
                    "required_label": {
                        "key": ownership_key,
                        "value": invocation_id,
                    },
                    "execution": "command",
                    "argv": [
                        "docker",
                        "volume",
                        "rm",
                        f"{compose_project}_judge-output",
                    ],
                    "exit_code": 0,
                    "stdout_sha256": digest_a,
                    "stderr_sha256": digest_b,
                },
                {
                    "resource_kind": "image",
                    "resource_name": headless_image,
                    "required_label": {
                        "key": ownership_key,
                        "value": invocation_id,
                    },
                    "execution": "command",
                    "argv": ["docker", "image", "rm", headless_image],
                    "exit_code": 0,
                    "stdout_sha256": digest_a,
                    "stderr_sha256": digest_b,
                },
                {
                    "resource_kind": "image",
                    "resource_name": imported_image,
                    "required_label": {
                        "key": ownership_key,
                        "value": invocation_id,
                    },
                    "execution": "command",
                    "argv": ["docker", "image", "rm", imported_image],
                    "exit_code": 0,
                    "stdout_sha256": digest_a,
                    "stderr_sha256": digest_b,
                },
            ],
        },
        "exported_evidence": {
            "status": "pass",
            "path": f"output/evidence/docker/live/{invocation_id}",
            "contents": [
                {"path": "docker-status.json", "sha256": digest_c},
                {"path": "quick-smoke.json", "sha256": digest_d},
            ],
        },
    }


def _real_live_fail_evidence() -> dict[str, object]:
    """Return a real health failure with a legal phase prefix."""
    return _truthful_command_phase_failure("headless_health")


def _contradictory_complete_pass_then_flip_failure() -> dict[str, object]:
    """Return the obsolete impossible failure timeline for rejection tests."""
    payload = _complete_live_api_pass_evidence()
    payload["status"] = "fail"
    payload["reason"] = "headless_health_failed"
    payload["headless_health"].update(
        {
            "status": "fail",
            "exit_code": 17,
            "detail": "headless health check exited 17",
        }
    )
    return payload


def _save_load_stage_failure_evidence(argv: list[str]) -> dict[str, object]:
    """Return the truthful prefix selected by one hand-written stage argv."""
    project = "ca-mp-task19-a1b2c3d4e5f6"
    tar_path = "output/evidence/docker/live/a1b2c3d4e5f6/headless-image.tar"
    canonical = {
        tuple(["docker", "image", "load", "--input", tar_path]): "image_load",
        tuple(
            [
                "docker",
                "image",
                "tag",
                f"{project}-headless:local",
                f"{project}-imported:local",
            ]
        ): "image_retag",
        tuple(
            [
                "docker",
                "container",
                "create",
                "--name",
                f"{project}-imported-judge-1",
                "--label",
                "io.challengecup.task19.invocation=a1b2c3d4e5f6",
                f"{project}-imported:local",
            ]
        ): "imported_container_create",
        tuple(
            [
                "docker",
                "container",
                "start",
                f"{project}-imported-judge-1",
            ]
        ): "imported_container_start",
        tuple(
            ["docker", "inspect", f"{project}-imported-judge-1"]
        ): "repeated_health",
        tuple(
            [
                "docker",
                "exec",
                f"{project}-imported-judge-1",
                "python",
                "-m",
                "scripts.quick_smoke",
            ]
        ): "repeated_smoke",
    }
    stage = canonical.get(tuple(argv))
    if stage is not None:
        payload = _truthful_save_load_stage_failure(stage)
        if stage == "repeated_health":
            exact_argv = [
                "docker",
                "inspect",
                "--format",
                "{{.State.Health.Status}}",
                f"{project}-imported-judge-1",
            ]
            payload["save_load"]["argv"] = copy.deepcopy(exact_argv)
            payload["save_load_proof"][stage]["argv"] = exact_argv
        return payload
    payload = _truthful_save_load_stage_failure("image_save")
    payload["save_load"]["argv"] = argv
    return payload


def _complete_live_pass_evidence_with_gui() -> dict[str, object]:
    """Return a hand-written live pass document with the optional GUI chain."""
    payload = _complete_live_pass_evidence()
    invocation_id = "a1b2c3d4e5f6"
    compose_project = f"ca-mp-task19-{invocation_id}"
    gui_image = f"{compose_project}-gui:local"
    gui_container = f"{compose_project}-judge-gui-1"
    gui_volume = f"{compose_project}_judge-gui-output"
    owner = {"io.challengecup.task19.invocation": invocation_id}
    digest_a = "a" * 64
    digest_b = "b" * 64
    empty_digest = hashlib.sha256(b"").hexdigest()
    gui_run_id = "gui-run-4b8e2d6f"
    frame_one = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00\x05"
        b"\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    frame_two = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc`\xf8\xcf\xf0\x1f\x00\x04\x01"
        b"\x01\xffq\xebG\xe5\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    payload["gui_build"] = {
        "status": "pass",
        "started_at": "2026-08-24T00:00:00Z",
        "finished_at": "2026-08-24T00:00:01Z",
        "argv": [
            "docker",
            "compose",
            "--project-name",
            "ca-mp-task19-a1b2c3d4e5f6",
            "--profile",
            "gui",
            "build",
            "judge-gui",
        ],
        "exit_code": 0,
        "stdout_sha256": digest_a,
        "stderr_sha256": digest_b,
        "detail": "GUI image built with the invocation ownership label",
    }
    payload["static_contract"]["argv"] = [
        "docker",
        "compose",
        "--project-name",
        "ca-mp-task19-a1b2c3d4e5f6",
        "--profile",
        "gui",
        "config",
        "--quiet",
    ]
    payload["static_contract"]["render_proof"] = {
        "status": "pass",
        "argv": [
            "docker",
            "compose",
            "--project-name",
            "ca-mp-task19-a1b2c3d4e5f6",
            "--profile",
            "gui",
            "config",
            "--format",
            "json",
        ],
        "exit_code": 0,
        "stdout_sha256": "f" * 64,
        "selected_facts": {
            "source_stdout_sha256": "f" * 64,
            "project": "ca-mp-task19-a1b2c3d4e5f6",
            "profiles": ["gui"],
            "services": [
                {
                    "name": "judge",
                    "image": ("ca-mp-task19-a1b2c3d4e5f6-headless:local"),
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": ("a1b2c3d4e5f6")
                    },
                    "additional_contexts": {},
                },
                {
                    "name": "judge-gui",
                    "image": "ca-mp-task19-a1b2c3d4e5f6-gui:local",
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": ("a1b2c3d4e5f6")
                    },
                    "additional_contexts": {"judge_base": "service:judge"},
                },
            ],
        },
    }
    payload["gui_smoke"] = {
        "status": "pass",
        "started_at": "2026-08-24T00:00:00Z",
        "finished_at": "2026-08-24T00:00:01Z",
        "argv": [],
        "exit_code": None,
        "stdout_sha256": empty_digest,
        "stderr_sha256": empty_digest,
        "detail": "GUI API run and frame capture passed",
        "execution": "api_result",
        "api_proof": _handwritten_api_smoke_proof(
            container=gui_container,
            image=gui_image,
            run_id=gui_run_id,
        ),
    }
    payload["gui_frame_proof"] = {
        "run_id": gui_run_id,
        "container": gui_container,
        "image": gui_image,
        "frames": [
            {
                "path": "gui/frames/frame-000001.png",
                "byte_length": len(frame_one),
                "sha256": hashlib.sha256(frame_one).hexdigest(),
                "sequence": 1,
                "simulation_time": 1.0,
            },
            {
                "path": "gui/frames/frame-000002.png",
                "byte_length": len(frame_two),
                "sha256": hashlib.sha256(frame_two).hexdigest(),
                "sequence": 2,
                "simulation_time": 2.0,
            },
        ],
    }
    payload["exported_evidence"]["contents"].extend(
        [
            {
                "path": "gui/frames/frame-000001.png",
                "byte_length": len(frame_one),
                "sha256": hashlib.sha256(frame_one).hexdigest(),
            },
            {
                "path": "gui/frames/frame-000002.png",
                "byte_length": len(frame_two),
                "sha256": hashlib.sha256(frame_two).hexdigest(),
            },
        ]
    )
    payload["owned_resources"]["before_cleanup"].extend(
        [
            {"kind": "container", "name": gui_container, "labels": owner},
            {"kind": "volume", "name": gui_volume, "labels": owner},
            {"kind": "image", "name": gui_image, "labels": owner},
        ]
    )
    payload["owned_resources"]["cleanup_actions"].extend(
        [
            {
                "resource_kind": "container",
                "resource_name": gui_container,
                "required_label": {
                    "key": "io.challengecup.task19.invocation",
                    "value": invocation_id,
                },
                "execution": "command",
                "argv": ["docker", "container", "rm", gui_container],
                "exit_code": 0,
                "stdout_sha256": digest_a,
                "stderr_sha256": digest_b,
            },
            {
                "resource_kind": "volume",
                "resource_name": gui_volume,
                "required_label": {
                    "key": "io.challengecup.task19.invocation",
                    "value": invocation_id,
                },
                "execution": "command",
                "argv": ["docker", "volume", "rm", gui_volume],
                "exit_code": 0,
                "stdout_sha256": digest_a,
                "stderr_sha256": digest_b,
            },
            {
                "resource_kind": "image",
                "resource_name": gui_image,
                "required_label": {
                    "key": "io.challengecup.task19.invocation",
                    "value": invocation_id,
                },
                "execution": "command",
                "argv": ["docker", "image", "rm", gui_image],
                "exit_code": 0,
                "stdout_sha256": digest_a,
                "stderr_sha256": digest_b,
            },
        ]
    )
    return payload


def _handwritten_api_smoke_proof(
    *, container: str, image: str, run_id: str
) -> dict[str, object]:
    """Return a literal API smoke proof without calling production builders."""
    return {
        "container": container,
        "image": image,
        "request": {
            "method": "POST",
            "path": "/api/runs",
            "body": {
                "intersection_id": "1",
                "algorithm": "fixed_time",
                "steps": 100,
            },
            "body_sha256": hashlib.sha256(
                f"post:{run_id}".encode("utf-8")
            ).hexdigest(),
        },
        "response": {
            "status": 202,
            "run_id": run_id,
            "body_sha256": hashlib.sha256(
                f"created:{run_id}".encode("utf-8")
            ).hexdigest(),
        },
        "terminal": {
            "method": "GET",
            "path": f"/api/runs/{run_id}",
            "status": 200,
            "run_id": run_id,
            "state": "completed",
            "completed_steps": 100,
            "body_sha256": hashlib.sha256(
                f"terminal:{run_id}".encode("utf-8")
            ).hexdigest(),
        },
        "run_id": run_id,
        "terminal_status": "completed",
        "requested_steps": 100,
        "completed_steps": list(range(1, 101)),
        "output": {
            "root": "app/output",
            "path": f"runs/{run_id}",
            "run_id": run_id,
        },
    }


def _complete_live_api_pass_evidence() -> dict[str, object]:
    """Return a hand-written pass with separate API-created smoke proofs."""
    payload = copy.deepcopy(_legacy_command_smoke_live_pass_evidence())
    project = "ca-mp-task19-a1b2c3d4e5f6"
    payload["static_contract"]["stdout_sha256"] = hashlib.sha256(
        b""
    ).hexdigest()
    payload["headless_build"]["argv"] = [
        "docker",
        "compose",
        "--project-name",
        "ca-mp-task19-a1b2c3d4e5f6",
        "build",
        "judge",
    ]
    payload["static_contract"]["render_proof"] = {
        "status": "pass",
        "argv": [
            "docker",
            "compose",
            "--project-name",
            "ca-mp-task19-a1b2c3d4e5f6",
            "config",
            "--format",
            "json",
        ],
        "exit_code": 0,
        "stdout_sha256": "e" * 64,
        "selected_facts": {
            "source_stdout_sha256": "e" * 64,
            "project": "ca-mp-task19-a1b2c3d4e5f6",
            "profiles": [],
            "services": [
                {
                    "name": "judge",
                    "image": ("ca-mp-task19-a1b2c3d4e5f6-headless:local"),
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": ("a1b2c3d4e5f6")
                    },
                    "additional_contexts": {},
                }
            ],
        },
    }
    headless = _handwritten_api_smoke_proof(
        container=f"{project}-judge-1",
        image=f"{project}-headless:local",
        run_id="headless-run-7e4a1b2c",
    )
    imported = _handwritten_api_smoke_proof(
        container=f"{project}-imported-judge-1",
        image=f"{project}-imported:local",
        run_id="imported-run-9d3f5a7c",
    )
    payload["quick_smoke"] = copy.deepcopy(headless)
    payload["quick_smoke"]["evidence_class"] = "quick_smoke"
    payload["headless_smoke"].update(
        {
            "execution": "api_result",
            "argv": [],
            "exit_code": None,
            "stdout_sha256": hashlib.sha256(b"").hexdigest(),
            "stderr_sha256": hashlib.sha256(b"").hexdigest(),
            "api_proof": headless,
        }
    )
    payload["save_load_proof"]["repeated_smoke"].update(
        {
            "execution": "api_result",
            "argv": [],
            "exit_code": None,
            "stdout_sha256": hashlib.sha256(b"").hexdigest(),
            "stderr_sha256": hashlib.sha256(b"").hexdigest(),
            "api_proof": imported,
        }
    )
    return payload


def _cleanup_only_failure_evidence() -> dict[str, object]:
    """Return valid API results followed by a canonical cleanup failure."""
    return _truthful_cleanup_command_failure_evidence()


def _truthful_cleanup_safety_refusal_evidence() -> dict[str, object]:
    """Return an ownership refusal without a fabricated cleanup command."""
    payload = _truthful_phase_prefix_failure("headless_build")
    empty_sha256 = hashlib.sha256(b"").hexdigest()
    payload["cleanup"].update(
        {
            "status": "fail",
            "execution": "safety_refusal",
            "argv": [],
            "exit_code": None,
            "stdout_sha256": empty_sha256,
            "stderr_sha256": empty_sha256,
            "detail": "cleanup refused after exact ownership check",
            "failure_proof": {
                "kind": "cleanup_ownership_refusal",
                "resource_kind": "volume",
                "resource_name": ("ca-mp-task19-a1b2c3d4e5f6_judge-output"),
                "required_label": {
                    "key": "io.challengecup.task19.invocation",
                    "value": "a1b2c3d4e5f6",
                },
                "observed_ownership": "missing_label",
            },
        }
    )
    payload["owned_resources"]["cleanup_actions"] = [
        {
            "resource_kind": "volume",
            "resource_name": "ca-mp-task19-a1b2c3d4e5f6_judge-output",
            "required_label": {
                "key": "io.challengecup.task19.invocation",
                "value": "a1b2c3d4e5f6",
            },
            "execution": "safety_refusal",
            "argv": [],
            "exit_code": None,
            "stdout_sha256": empty_sha256,
            "stderr_sha256": empty_sha256,
            "failure_proof": copy.deepcopy(
                payload["cleanup"]["failure_proof"]
            ),
        }
    ]
    return payload


def _truthful_static_interruption_evidence(
    interruption_kind: str,
) -> dict[str, object]:
    """Return a first-phase interruption with every later phase untouched."""
    payload = _complete_live_api_pass_evidence()
    empty_sha256 = hashlib.sha256(b"").hexdigest()
    payload["status"] = "fail"
    payload["reason"] = "static_contract_failed"
    for phase in (
        "static_contract",
        "headless_build",
        "headless_health",
        "headless_smoke",
        "save_load",
        "gui_build",
        "gui_smoke",
        "cleanup",
    ):
        payload[phase].update(
            {
                "status": "not_run",
                "argv": [],
                "exit_code": None,
                "stdout_sha256": empty_sha256,
                "stderr_sha256": empty_sha256,
                "detail": "phase was not reached",
            }
        )
        payload[phase].pop("execution", None)
        payload[phase].pop("api_proof", None)
        payload[phase].pop("render_proof", None)
    payload["static_contract"].update(
        {
            "status": "fail",
            "execution": "interruption",
            "detail": "verification interrupted before a command completed",
            "failure_proof": {
                "kind": "interruption",
                "interruption_kind": interruption_kind,
                "phase": "static_contract",
            },
        }
    )
    for key in ("quick_smoke", "save_load_proof", "exported_evidence"):
        payload.pop(key, None)
    payload["owned_resources"]["before_cleanup"] = []
    payload["owned_resources"]["after_cleanup"] = []
    payload["owned_resources"]["cleanup_actions"] = []
    return payload


def _complete_live_pass_evidence() -> dict[str, object]:
    """Return the independent hand-written API-created pass oracle."""
    return _complete_live_api_pass_evidence()


def _truthful_phase_prefix_failure(phase: str) -> dict[str, object]:
    """Return one literal seven-phase failure prefix with honest cleanup."""
    order = (
        "static_contract",
        "headless_build",
        "headless_health",
        "headless_smoke",
        "save_load",
        "gui_build",
        "gui_smoke",
    )
    index = order.index(phase)
    payload = (
        _complete_live_pass_evidence_with_gui()
        if phase in {"gui_build", "gui_smoke"}
        else _complete_live_pass_evidence()
    )
    empty_sha256 = hashlib.sha256(b"").hexdigest()
    payload["status"] = "fail"
    payload["reason"] = f"{phase}_failed"
    for later in order[index + 1 :]:
        payload[later].update(
            {
                "status": "not_run",
                "argv": [],
                "exit_code": None,
                "stdout_sha256": empty_sha256,
                "stderr_sha256": empty_sha256,
                "detail": "phase was not reached",
            }
        )
        payload[later].pop("execution", None)
        payload[later].pop("api_proof", None)
        payload[later].pop("failure_proof", None)
        payload[later].pop("render_proof", None)
    payload[phase].update(
        {
            "status": "fail",
            "execution": "interruption",
            "argv": [],
            "exit_code": None,
            "stdout_sha256": empty_sha256,
            "stderr_sha256": empty_sha256,
            "detail": "phase interrupted between commands",
            "failure_proof": {
                "kind": "interruption",
                "interruption_kind": "keyboard_interrupt",
                "phase": phase,
            },
        }
    )
    payload[phase].pop("api_proof", None)
    if phase == "static_contract":
        payload[phase].pop("render_proof", None)
    if index <= order.index("headless_smoke"):
        payload.pop("quick_smoke", None)
    if index <= order.index("save_load"):
        payload.pop("save_load_proof", None)
    payload.pop("exported_evidence", None)
    payload.pop("gui_frame_proof", None)

    if index <= order.index("headless_build"):
        payload["cleanup"].update(
            {
                "status": "not_run",
                "argv": [],
                "exit_code": None,
                "stdout_sha256": empty_sha256,
                "stderr_sha256": empty_sha256,
                "detail": "no owned resource required cleanup",
            }
        )
        payload["cleanup"].pop("execution", None)
        payload["cleanup"].pop("failure_proof", None)
        before_cleanup: list[dict[str, object]] = []
        cleanup_actions: list[dict[str, object]] = []
    else:
        payload["cleanup"].update(
            {
                "status": "fail",
                "execution": "interruption",
                "argv": [],
                "exit_code": None,
                "stdout_sha256": empty_sha256,
                "stderr_sha256": empty_sha256,
                "detail": "cleanup interrupted between commands",
                "failure_proof": {
                    "kind": "interruption",
                    "interruption_kind": "base_exception",
                    "phase": "cleanup",
                },
            }
        )
        before_cleanup = copy.deepcopy(
            payload["owned_resources"]["before_cleanup"]
        )
        if index <= order.index("save_load"):
            before_cleanup = [
                record
                for record in before_cleanup
                if "imported" not in record["name"]
                and "judge-gui" not in record["name"]
                and "gui:local" not in record["name"]
            ]
        elif phase == "gui_build":
            before_cleanup = [
                record
                for record in before_cleanup
                if "judge-gui" not in record["name"]
                and "gui:local" not in record["name"]
            ]
        target = before_cleanup[0]
        cleanup_actions = [
            {
                "resource_kind": target["kind"],
                "resource_name": target["name"],
                "required_label": {
                    "key": "io.challengecup.task19.invocation",
                    "value": "a1b2c3d4e5f6",
                },
                "execution": "interruption",
                "argv": [],
                "exit_code": None,
                "stdout_sha256": empty_sha256,
                "stderr_sha256": empty_sha256,
                "failure_proof": copy.deepcopy(
                    payload["cleanup"]["failure_proof"]
                ),
            }
        ]
    payload["owned_resources"]["before_cleanup"] = before_cleanup
    payload["owned_resources"]["after_cleanup"] = copy.deepcopy(before_cleanup)
    payload["owned_resources"]["cleanup_actions"] = cleanup_actions
    return payload


def _truthful_command_phase_failure(phase: str) -> dict[str, object]:
    """Return a legal prefix whose primary is one exact failed command."""
    project = "ca-mp-task19-a1b2c3d4e5f6"
    commands = {
        "static_contract": [
            "docker",
            "compose",
            "--project-name",
            project,
            "config",
            "--quiet",
        ],
        "headless_build": [
            "docker",
            "compose",
            "--project-name",
            project,
            "build",
            "judge",
        ],
        "headless_health": [
            "docker",
            "inspect",
            "--format",
            "{{.State.Health.Status}}",
            f"{project}-judge-1",
        ],
        "headless_smoke": [
            "docker",
            "exec",
            f"{project}-judge-1",
            "python",
        ],
        "gui_build": [
            "docker",
            "compose",
            "--project-name",
            project,
            "--profile",
            "gui",
            "build",
            "judge-gui",
        ],
        "gui_smoke": [
            "docker",
            "exec",
            f"{project}-judge-gui-1",
            "python",
        ],
    }
    payload = _truthful_phase_prefix_failure(phase)
    payload[phase].update(
        {
            "execution": "command",
            "argv": commands[phase],
            "exit_code": 29,
            "stdout_sha256": "a" * 64,
            "stderr_sha256": "b" * 64,
            "detail": f"{phase} command exited 29",
        }
    )
    payload[phase].pop("failure_proof")
    return payload


def _truthful_cleanup_command_failure_evidence() -> dict[str, object]:
    """Return one successful removal followed by one real failed removal."""
    payload = _complete_live_pass_evidence()
    payload["status"] = "fail"
    payload["reason"] = "cleanup_failed"
    actions = payload["owned_resources"]["cleanup_actions"]
    successful = copy.deepcopy(actions[0])
    failed = copy.deepcopy(actions[3])
    failed["exit_code"] = 31
    payload["owned_resources"]["cleanup_actions"] = [successful, failed]
    payload["cleanup"].update(
        {
            "status": "fail",
            "execution": "command",
            "argv": copy.deepcopy(failed["argv"]),
            "exit_code": 31,
            "stdout_sha256": failed["stdout_sha256"],
            "stderr_sha256": failed["stderr_sha256"],
            "detail": "owned volume removal exited 31",
        }
    )
    removed_identity = (
        successful["resource_kind"],
        successful["resource_name"],
    )
    payload["owned_resources"]["after_cleanup"] = [
        copy.deepcopy(record)
        for record in payload["owned_resources"]["before_cleanup"]
        if (record["kind"], record["name"]) != removed_identity
    ]
    return payload


def _truthful_gui_cleanup_command_failure_evidence() -> dict[str, object]:
    """Return a completed GUI workflow followed by one cleanup failure."""
    payload = _complete_gui_compose_pass_evidence()
    payload["status"] = "fail"
    payload["reason"] = "cleanup_failed"
    actions = payload["owned_resources"]["cleanup_actions"]
    successful = copy.deepcopy(actions[0])
    failed = copy.deepcopy(actions[3])
    failed["exit_code"] = 17
    payload["owned_resources"]["cleanup_actions"] = [successful, failed]
    payload["cleanup"].update(
        {
            "status": "fail",
            "argv": copy.deepcopy(failed["argv"]),
            "exit_code": 17,
            "stdout_sha256": failed["stdout_sha256"],
            "stderr_sha256": failed["stderr_sha256"],
            "detail": "owned cleanup exited 17",
        }
    )
    removed = (successful["resource_kind"], successful["resource_name"])
    payload["owned_resources"]["after_cleanup"] = [
        copy.deepcopy(record)
        for record in payload["owned_resources"]["before_cleanup"]
        if (record["kind"], record["name"]) != removed
    ]
    return payload


def _truthful_save_load_stage_failure(stage: str) -> dict[str, object]:
    """Return a literal nested save/load prefix ending at one failed stage."""
    project = "ca-mp-task19-a1b2c3d4e5f6"
    tar_path = "output/evidence/docker/live/a1b2c3d4e5f6/headless-image.tar"
    headless_image = f"{project}-headless:local"
    imported_image = f"{project}-imported:local"
    imported_container = f"{project}-imported-judge-1"
    commands = {
        "image_save": [
            "docker",
            "image",
            "save",
            "--output",
            tar_path,
            headless_image,
        ],
        "image_load": ["docker", "image", "load", "--input", tar_path],
        "image_retag": [
            "docker",
            "image",
            "tag",
            headless_image,
            imported_image,
        ],
        "imported_container_create": [
            "docker",
            "container",
            "create",
            "--name",
            imported_container,
            "--label",
            "io.challengecup.task19.invocation=a1b2c3d4e5f6",
            imported_image,
        ],
        "imported_container_start": [
            "docker",
            "container",
            "start",
            imported_container,
        ],
        "repeated_health": [
            "docker",
            "inspect",
            "--format",
            "{{.State.Health.Status}}",
            imported_container,
        ],
        "repeated_smoke": [
            "docker",
            "exec",
            imported_container,
            "python",
        ],
    }
    nested_order = (
        "image_load",
        "image_retag",
        "imported_container_create",
        "imported_container_start",
        "repeated_health",
        "repeated_smoke",
    )
    payload = _complete_live_pass_evidence()
    empty_sha256 = hashlib.sha256(b"").hexdigest()
    payload["status"] = "fail"
    payload["reason"] = "save_load_failed"
    payload["save_load"].update(
        {
            "status": "fail",
            "argv": commands[stage],
            "exit_code": 23,
            "stdout_sha256": "a" * 64,
            "stderr_sha256": "b" * 64,
            "detail": f"{stage} exited 23",
        }
    )
    failure_index = -1 if stage == "image_save" else nested_order.index(stage)
    for index, nested_stage in enumerate(nested_order):
        record = payload["save_load_proof"][nested_stage]
        if index < failure_index:
            continue
        record.update(
            {
                "status": "not_run",
                "argv": [],
                "exit_code": None,
                "stdout_sha256": empty_sha256,
                "stderr_sha256": empty_sha256,
                "detail": "nested stage was not reached",
            }
        )
        record.pop("execution", None)
        record.pop("api_proof", None)
        record.pop("failure_proof", None)
    if failure_index >= 0:
        failed = payload["save_load_proof"][stage]
        failed.update(
            {
                "status": "fail",
                "execution": "command",
                "argv": commands[stage],
                "exit_code": 23,
                "stdout_sha256": "a" * 64,
                "stderr_sha256": "b" * 64,
                "detail": f"{stage} exited 23",
            }
        )
    payload["cleanup"] = copy.deepcopy(
        _truthful_phase_prefix_failure("save_load")["cleanup"]
    )
    payload["owned_resources"] = copy.deepcopy(
        _truthful_phase_prefix_failure("save_load")["owned_resources"]
    )
    payload.pop("exported_evidence", None)
    return payload


def test_validator_accepts_round4_3_truthful_cleanup_safety_refusal() -> None:
    """A missing cleanup label is evidence of refusal, not a fake ``rm``."""
    docker_status.validate_evidence(
        _truthful_cleanup_safety_refusal_evidence()
    )


@pytest.mark.parametrize(
    "interruption_kind", ["keyboard_interrupt", "base_exception"]
)
def test_validator_accepts_round4_3_truthful_interruption(
    interruption_kind: str,
) -> None:
    """An interruption between commands has proof but no command metadata."""
    docker_status.validate_evidence(
        _truthful_static_interruption_evidence(interruption_kind)
    )


@pytest.mark.parametrize(
    ("execution", "field", "value"),
    [
        ("safety_refusal", "argv", ["docker", "volume", "rm", "fabricated"]),
        ("safety_refusal", "exit_code", 71),
        ("safety_refusal", "stdout_sha256", "c" * 64),
        ("interruption", "argv", ["docker", "compose", "config"]),
        ("interruption", "exit_code", 130),
        ("interruption", "stderr_sha256", "d" * 64),
    ],
    ids=[
        "refusal-argv",
        "refusal-exit",
        "refusal-stream",
        "interruption-argv",
        "interruption-exit",
        "interruption-stream",
    ],
)
def test_validator_rejects_round4_3_fabricated_failure_execution_metadata(
    execution: str, field: str, value: object
) -> None:
    """Non-command failures cannot claim an unexecuted command or streams."""
    payload = (
        _truthful_cleanup_safety_refusal_evidence()
        if execution == "safety_refusal"
        else _truthful_static_interruption_evidence("keyboard_interrupt")
    )
    phase = "cleanup" if execution == "safety_refusal" else "static_contract"
    payload[phase][field] = value

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("case", "field", "value"),
    [
        ("unknown-field", "unexpected", "safe"),
        ("traceback-field", "traceback", "private traceback text"),
        ("foreign-kind", "resource_kind", "project"),
        ("vague-name", "resource_name", "judge-output"),
        ("foreign-name", "resource_name", "foreign-volume"),
        ("unknown-observation", "observed_ownership", "probably-owned"),
    ],
)
def test_validator_rejects_round4_3_invalid_safety_refusal_proof(
    case: str, field: str, value: object
) -> None:
    """Cleanup refusal proof is closed and bound to one canonical resource."""
    del case
    payload = _truthful_cleanup_safety_refusal_evidence()
    payload["cleanup"]["failure_proof"][field] = value

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("case", "key", "value"),
    [
        ("foreign-key", "key", "other.label"),
        ("foreign-value", "value", "001122334455"),
        ("missing-value", "value", None),
    ],
)
def test_validator_rejects_round4_3_invalid_refusal_required_label(
    case: str, key: str, value: object
) -> None:
    """A refusal names the exact invocation ownership label it required."""
    del case
    payload = _truthful_cleanup_safety_refusal_evidence()
    label = payload["cleanup"]["failure_proof"]["required_label"]
    if value is None:
        label.pop(key)
    else:
        label[key] = value

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "exception"),
        ("interruption_kind", "system_exit"),
        ("phase", "headless_build"),
        ("message", "private exception message"),
    ],
)
def test_validator_rejects_round4_3_invalid_interruption_proof(
    field: str, value: object
) -> None:
    """Interruption proof uses a bounded kind and exact failed phase."""
    payload = _truthful_static_interruption_evidence("keyboard_interrupt")
    payload["static_contract"]["failure_proof"][field] = value

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_safety_refusal_outside_cleanup() -> None:
    """Ownership refusal is a cleanup-only execution variant."""
    payload = _truthful_static_interruption_evidence("keyboard_interrupt")
    payload["static_contract"]["execution"] = "safety_refusal"
    payload["static_contract"]["failure_proof"] = copy.deepcopy(
        _truthful_cleanup_safety_refusal_evidence()["cleanup"]["failure_proof"]
    )

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_failure_execution_under_not_run() -> None:
    """A not-run phase cannot claim that an interruption occurred."""
    payload = docker_status.new_evidence()
    payload["headless_build"].update(
        {
            "execution": "interruption",
            "failure_proof": {
                "kind": "interruption",
                "interruption_kind": "keyboard_interrupt",
                "phase": "headless_build",
            },
        }
    )

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize("execution", ["command", "api_result"])
def test_validator_rejects_round4_3_failure_proof_on_other_execution(
    execution: str,
) -> None:
    """Only a non-command failure execution may carry ``failure_proof``."""
    payload = _complete_live_pass_evidence()
    phase = "headless_build" if execution == "command" else "headless_smoke"
    payload[phase]["failure_proof"] = {
        "kind": "interruption",
        "interruption_kind": "keyboard_interrupt",
        "phase": phase,
    }

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "phase",
    [
        "static_contract",
        "headless_build",
        "headless_health",
        "headless_smoke",
        "save_load",
        "gui_build",
        "gui_smoke",
    ],
)
def test_validator_accepts_round4_3_each_legal_phase_failure_prefix(
    phase: str,
) -> None:
    """Each failure has passed predecessors and untouched successors."""
    docker_status.validate_evidence(_truthful_phase_prefix_failure(phase))


def test_validator_accepts_round4_3_primary_and_cleanup_failure() -> None:
    """Cleanup failure does not erase the earlier primary failure reason."""
    payload = _truthful_phase_prefix_failure("headless_health")

    assert payload["reason"] == "headless_health_failed"
    assert payload["headless_health"]["status"] == "fail"
    assert payload["cleanup"]["status"] == "fail"
    docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_complete_pass_suffix_after_failure() -> (
    None
):
    """A failed health phase cannot retain later successful phases."""
    payload = _contradictory_complete_pass_then_flip_failure()

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_unselected_noncleanup_failure() -> None:
    """Only the reason-selected non-cleanup phase may fail."""
    payload = _truthful_phase_prefix_failure("headless_health")
    payload["gui_build"].update(
        {
            "status": "fail",
            "execution": "interruption",
            "failure_proof": {
                "kind": "interruption",
                "interruption_kind": "keyboard_interrupt",
                "phase": "gui_build",
            },
        }
    )

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_gui_smoke_failure_without_build() -> None:
    """A reached GUI smoke failure requires a successful GUI build."""
    payload = _truthful_phase_prefix_failure("gui_smoke")
    headless = _complete_live_pass_evidence()
    payload["static_contract"] = copy.deepcopy(headless["static_contract"])
    payload["gui_build"] = copy.deepcopy(headless["gui_build"])

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "primary",
    ["static_contract", "headless_build", "headless_smoke", "save_load"],
)
def test_validator_rejects_round4_3_impossible_pass_after_primary(
    primary: str,
) -> None:
    """A non-cleanup pass suffix cannot appear after the primary failure."""
    payload = _truthful_phase_prefix_failure(primary)
    complete = _complete_live_pass_evidence()
    if primary == "static_contract":
        payload["headless_build"] = copy.deepcopy(
            _legacy_command_smoke_live_pass_evidence()["headless_build"]
        )
    elif primary == "headless_build":
        payload["headless_health"] = copy.deepcopy(complete["headless_health"])
    elif primary == "headless_smoke":
        payload["save_load"] = copy.deepcopy(complete["save_load"])
    else:
        gui = _complete_live_pass_evidence_with_gui()
        payload["static_contract"] = copy.deepcopy(gui["static_contract"])
        payload["gui_build"] = copy.deepcopy(gui["gui_build"])

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "phase",
    [
        "static_contract",
        "headless_build",
        "headless_health",
        "headless_smoke",
        "gui_build",
        "gui_smoke",
    ],
)
def test_validator_accepts_round4_3_canonical_command_failure(
    phase: str,
) -> None:
    """A command failure stays bound to its canonical outer Docker argv."""
    docker_status.validate_evidence(_truthful_command_phase_failure(phase))


@pytest.mark.parametrize(
    ("phase", "argv"),
    [
        (
            "static_contract",
            ["docker", "compose", "--project-name", "foreign", "config"],
        ),
        (
            "headless_build",
            [
                "docker",
                "compose",
                "--project-name",
                "foreign",
                "build",
                "judge",
            ],
        ),
        (
            "headless_health",
            ["docker", "inspect", "foreign-container"],
        ),
        (
            "headless_health",
            [
                "docker",
                "inspect",
                "ca-mp-task19-a1b2c3d4e5f6-judge-1",
                "docker",
            ],
        ),
        (
            "headless_smoke",
            ["docker", "exec", "foreign-container", "python"],
        ),
        (
            "headless_smoke",
            ["docker", "exec", "ca-mp-task19-a1b2c3d4e5f6-judge-1"],
        ),
        (
            "gui_build",
            [
                "docker",
                "compose",
                "--project-name",
                "foreign",
                "--profile",
                "gui",
                "build",
                "judge-gui",
            ],
        ),
        (
            "gui_smoke",
            ["docker", "exec", "foreign-gui-container", "python"],
        ),
    ],
    ids=[
        "static-foreign-project",
        "build-foreign-project",
        "health-foreign-target",
        "health-late-docker",
        "smoke-foreign-target",
        "smoke-empty-suffix",
        "gui-build-foreign-project",
        "gui-smoke-foreign-target",
    ],
)
def test_validator_rejects_round4_3_noncanonical_failure_command(
    phase: str, argv: list[str]
) -> None:
    """A failed command cannot borrow loose tokens from a canonical command."""
    payload = _truthful_command_phase_failure(phase)
    payload[phase]["argv"] = argv

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_accepts_round4_3_imported_container_start_pass() -> None:
    """The successful save/load chain records the imported container start."""
    docker_status.validate_evidence(_complete_live_pass_evidence())


def test_validator_accepts_round4_3_cleanup_action_ledger_pass() -> None:
    """A cleanup pass has one successful action for each owned resource."""
    docker_status.validate_evidence(_complete_live_pass_evidence())


def test_validator_accepts_round4_3_cleanup_command_failure_ledger() -> None:
    """A real failed removal remains a command with its nonzero exit."""
    docker_status.validate_evidence(
        _truthful_cleanup_command_failure_evidence()
    )


# Production mutation caught: accepting a successful cleanup action after the
# failed removal that terminates cleanup.
def test_validator_rejects_round4_3_nonterminal_cleanup_failure_action() -> (
    None
):
    """A failed cleanup action is the final chronological ledger entry."""
    payload = _truthful_cleanup_command_failure_evidence()
    payload["owned_resources"]["cleanup_actions"].reverse()

    with pytest.raises(ValueError, match="final"):
        docker_status.validate_evidence(payload)


def test_validator_accepts_round4_3_cleanup_interruption_ledger() -> None:
    """An interruption action retains every current-label owned resource."""
    docker_status.validate_evidence(
        _truthful_phase_prefix_failure("headless_health")
    )


@pytest.mark.parametrize(
    "case",
    [
        "unknown-field",
        "foreign-name",
        "foreign-label",
        "multiple-targets",
        "boolean-exit",
        "float-exit",
        "wrong-kind-command",
    ],
)
def test_validator_rejects_round4_3_invalid_cleanup_action(case: str) -> None:
    """Each cleanup action is closed, exact, labeled, and single-target."""
    payload = _complete_live_pass_evidence()
    action = payload["owned_resources"]["cleanup_actions"][0]
    if case == "unknown-field":
        action["unexpected"] = "safe"
    elif case == "foreign-name":
        action["resource_name"] = "foreign-container"
    elif case == "foreign-label":
        action["required_label"]["value"] = "001122334455"
    elif case == "multiple-targets":
        action["argv"].append("ca-mp-task19-a1b2c3d4e5f6-imported-judge-1")
    elif case == "boolean-exit":
        action["exit_code"] = False
    elif case == "float-exit":
        action["exit_code"] = 0.0
    else:
        action["argv"] = [
            "docker",
            "volume",
            "rm",
            "ca-mp-task19-a1b2c3d4e5f6-judge-1",
        ]

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "case", ["missing", "duplicate", "nonzero", "not-list"]
)
def test_validator_rejects_round4_3_invalid_cleanup_pass_ledger(
    case: str,
) -> None:
    """Cleanup pass actions exactly cover before-cleanup and all succeed."""
    payload = _complete_live_pass_evidence()
    actions = payload["owned_resources"]["cleanup_actions"]
    if case == "missing":
        actions.pop()
    elif case == "duplicate":
        actions.append(copy.deepcopy(actions[0]))
    elif case == "nonzero":
        actions[0]["exit_code"] = 9
    else:
        payload["owned_resources"]["cleanup_actions"] = {}

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "case",
    [
        "retained-success",
        "unjustified-removal",
        "failed-target-absent",
        "foreign-after",
        "duplicate-after",
    ],
)
def test_validator_rejects_round4_3_invalid_cleanup_failure_inventory(
    case: str,
) -> None:
    """Final inventory is exactly before minus successful command actions."""
    payload = _truthful_cleanup_command_failure_evidence()
    before = payload["owned_resources"]["before_cleanup"]
    after = payload["owned_resources"]["after_cleanup"]
    if case == "retained-success":
        after.append(copy.deepcopy(before[0]))
    elif case == "unjustified-removal":
        after.pop(0)
    elif case == "failed-target-absent":
        after[:] = [
            record
            for record in after
            if record["name"] != "ca-mp-task19-a1b2c3d4e5f6_judge-output"
        ]
    elif case == "foreign-after":
        after[0]["name"] = "foreign-container"
    else:
        after.append(copy.deepcopy(after[0]))

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_nonempty_inventory_with_cleanup_not_run(
) -> None:
    """Owned resources require an attempted cleanup outcome."""
    payload = _truthful_phase_prefix_failure("headless_build")
    owned = copy.deepcopy(
        _complete_live_pass_evidence()["owned_resources"]["before_cleanup"][4]
    )
    payload["owned_resources"]["before_cleanup"] = [owned]
    payload["owned_resources"]["after_cleanup"] = [copy.deepcopy(owned)]

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_refusal_target_as_current_owned() -> None:
    """A refusal target with no current label is absent from inventories."""
    payload = _truthful_cleanup_safety_refusal_evidence()
    target = {
        "kind": "volume",
        "name": "ca-mp-task19-a1b2c3d4e5f6_judge-output",
        "labels": {"io.challengecup.task19.invocation": "a1b2c3d4e5f6"},
    }
    payload["owned_resources"]["before_cleanup"] = [copy.deepcopy(target)]
    payload["owned_resources"]["after_cleanup"] = [copy.deepcopy(target)]

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_hidden_nonzero_cleanup_command() -> None:
    """A real failed removal cannot be relabeled as a safety refusal."""
    payload = _truthful_cleanup_safety_refusal_evidence()
    hidden = copy.deepcopy(
        _complete_live_pass_evidence()["owned_resources"]["cleanup_actions"][4]
    )
    hidden["exit_code"] = 9
    payload["owned_resources"]["cleanup_actions"].append(hidden)

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_cleanup_phase_ledger_mismatch() -> None:
    """The cleanup phase command identifies the same failed ledger action."""
    payload = _truthful_cleanup_command_failure_evidence()
    payload["cleanup"]["argv"] = [
        "docker",
        "image",
        "rm",
        "ca-mp-task19-a1b2c3d4e5f6-imported:local",
    ]

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_open_cleanup_action_failure_proof() -> (
    None
):
    """A refusal action carries the same closed proof as its cleanup phase."""
    payload = _truthful_cleanup_safety_refusal_evidence()
    payload["owned_resources"]["cleanup_actions"][0]["failure_proof"][
        "traceback"
    ] = "private traceback"

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "stage",
    [
        "image_save",
        "image_load",
        "image_retag",
        "imported_container_create",
        "imported_container_start",
        "repeated_health",
        "repeated_smoke",
    ],
)
def test_validator_accepts_round4_3_truthful_save_load_failure_prefix(
    stage: str,
) -> None:
    """Each nested failure has only reached predecessors marked pass."""
    docker_status.validate_evidence(_truthful_save_load_stage_failure(stage))


def test_validator_rejects_round4_3_save_load_outer_nested_mismatch() -> None:
    """The top-level command identifies the same failed nested stage."""
    payload = _truthful_save_load_stage_failure("image_retag")
    payload["save_load"]["argv"] = [
        "docker",
        "image",
        "load",
        "--input",
        "output/evidence/docker/live/a1b2c3d4e5f6/headless-image.tar",
    ]

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_save_load_unpassed_predecessor() -> None:
    """A failed retag requires the image-load predecessor to have passed."""
    payload = _truthful_save_load_stage_failure("image_retag")
    empty_sha256 = hashlib.sha256(b"").hexdigest()
    payload["save_load_proof"]["image_load"].update(
        {
            "status": "not_run",
            "argv": [],
            "exit_code": None,
            "stdout_sha256": empty_sha256,
            "stderr_sha256": empty_sha256,
        }
    )

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_save_load_touched_successor() -> None:
    """A failed image load leaves the retag and every later stage untouched."""
    payload = _truthful_save_load_stage_failure("image_load")
    payload["save_load_proof"]["image_retag"] = copy.deepcopy(
        _complete_live_pass_evidence()["save_load_proof"]["image_retag"]
    )

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_save_load_second_nested_failure() -> None:
    """One save/load reason cannot hide a second failed nested stage."""
    payload = _truthful_save_load_stage_failure("image_retag")
    payload["save_load_proof"]["repeated_health"].update(
        {
            "status": "fail",
            "argv": [
                "docker",
                "inspect",
                "--format",
                "{{.State.Health.Status}}",
                "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1",
            ],
            "exit_code": 44,
        }
    )

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("argv", ["docker", "image", "load"]),
        ("exit_code", 19),
        ("stdout_sha256", "c" * 64),
        (
            "failure_proof",
            {
                "kind": "interruption",
                "interruption_kind": "keyboard_interrupt",
                "phase": "save_load",
            },
        ),
    ],
)
def test_validator_rejects_round4_3_touched_nested_not_run_record(
    field: str, value: object
) -> None:
    """Every unreached nested save/load record is completely untouched."""
    payload = _truthful_save_load_stage_failure("image_save")
    payload["save_load_proof"]["image_load"][field] = value

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize("exit_code", [False, 0.0])
def test_validator_rejects_round4_3_noninteger_nested_save_load_exit(
    exit_code: object,
) -> None:
    """A reached nested command uses an exact non-Boolean integer exit."""
    payload = _truthful_save_load_stage_failure("image_retag")
    payload["save_load_proof"]["image_load"]["exit_code"] = exit_code

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_3_unknown_nested_save_load_field() -> None:
    """Nested save/load records remain closed on a failure document."""
    payload = _truthful_save_load_stage_failure("image_load")
    payload["save_load_proof"]["image_load"]["unexpected"] = "safe"

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("unexpected", "safe"),
        (
            "tar_path",
            "output/evidence/docker/live/foreign/headless-image.tar",
        ),
    ],
)
def test_validator_rejects_round4_3_invalid_save_load_failure_proof_outer(
    field: str, value: object
) -> None:
    """Early save/load failure validates the closed outer proof identity."""
    payload = _truthful_save_load_stage_failure("image_save")
    payload["save_load_proof"][field] = value

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("stage", "argv"),
    [
        (
            "repeated_health",
            [
                "docker",
                "inspect",
                "foreign",
                "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1",
            ],
        ),
        (
            "repeated_smoke",
            [
                "docker",
                "exec",
                "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1",
                "python",
                "docker",
            ],
        ),
    ],
)
def test_validator_rejects_round4_3_noncanonical_nested_failure_command(
    stage: str, argv: list[str]
) -> None:
    """Inspect/exec failures reject foreign or late outer Docker tokens."""
    payload = _truthful_save_load_stage_failure(stage)
    payload["save_load"]["argv"] = copy.deepcopy(argv)
    payload["save_load_proof"][stage]["argv"] = copy.deepcopy(argv)

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def _complete_headless_compose_pass_evidence() -> dict[str, object]:
    """Return a handwritten headless pass using canonical Compose build."""
    payload = _complete_live_api_pass_evidence()
    payload["headless_build"]["argv"] = [
        "docker",
        "compose",
        "--project-name",
        "ca-mp-task19-a1b2c3d4e5f6",
        "build",
        "judge",
    ]
    payload["static_contract"]["render_proof"] = {
        "status": "pass",
        "argv": [
            "docker",
            "compose",
            "--project-name",
            "ca-mp-task19-a1b2c3d4e5f6",
            "config",
            "--format",
            "json",
        ],
        "exit_code": 0,
        "stdout_sha256": "e" * 64,
        "selected_facts": {
            "source_stdout_sha256": "e" * 64,
            "project": "ca-mp-task19-a1b2c3d4e5f6",
            "profiles": [],
            "services": [
                {
                    "name": "judge",
                    "image": ("ca-mp-task19-a1b2c3d4e5f6-headless:local"),
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": ("a1b2c3d4e5f6")
                    },
                    "additional_contexts": {},
                }
            ],
        },
    }
    return payload


def _complete_gui_compose_pass_evidence() -> dict[str, object]:
    """Return a handwritten GUI pass using canonical Compose builds."""
    payload = _complete_live_pass_evidence_with_gui()
    payload["headless_build"]["argv"] = [
        "docker",
        "compose",
        "--project-name",
        "ca-mp-task19-a1b2c3d4e5f6",
        "build",
        "judge",
    ]
    payload["gui_build"]["argv"] = [
        "docker",
        "compose",
        "--project-name",
        "ca-mp-task19-a1b2c3d4e5f6",
        "--profile",
        "gui",
        "build",
        "judge-gui",
    ]
    payload["static_contract"]["argv"] = [
        "docker",
        "compose",
        "--project-name",
        "ca-mp-task19-a1b2c3d4e5f6",
        "--profile",
        "gui",
        "config",
        "--quiet",
    ]
    payload["static_contract"]["render_proof"] = {
        "status": "pass",
        "argv": [
            "docker",
            "compose",
            "--project-name",
            "ca-mp-task19-a1b2c3d4e5f6",
            "--profile",
            "gui",
            "config",
            "--format",
            "json",
        ],
        "exit_code": 0,
        "stdout_sha256": "f" * 64,
        "selected_facts": {
            "source_stdout_sha256": "f" * 64,
            "project": "ca-mp-task19-a1b2c3d4e5f6",
            "profiles": ["gui"],
            "services": [
                {
                    "name": "judge",
                    "image": ("ca-mp-task19-a1b2c3d4e5f6-headless:local"),
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": ("a1b2c3d4e5f6")
                    },
                    "additional_contexts": {},
                },
                {
                    "name": "judge-gui",
                    "image": "ca-mp-task19-a1b2c3d4e5f6-gui:local",
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": ("a1b2c3d4e5f6")
                    },
                    "additional_contexts": {"judge_base": "service:judge"},
                },
            ],
        },
    }
    return payload


def test_validator_accepts_canonical_headless_compose_build() -> None:
    """Compose headless build is proved by its linked rendered config."""
    docker_status.validate_evidence(_complete_headless_compose_pass_evidence())


def test_validator_accepts_canonical_gui_compose_build() -> None:
    """GUI Compose build shares one linked GUI-scope render proof."""
    docker_status.validate_evidence(_complete_gui_compose_pass_evidence())


@pytest.mark.parametrize("axis", ["headless", "gui"])
@pytest.mark.parametrize(
    ("case", "replacement"),
    [
        ("missing", ["docker", "compose", "build"]),
        (
            "foreign",
            ["docker", "compose", "--project-name", "foreign", "build"],
        ),
        (
            "inline",
            [
                "docker",
                "compose",
                "--project-name=ca-mp-task19-a1b2c3d4e5f6",
                "build",
            ],
        ),
        (
            "short",
            [
                "docker",
                "compose",
                "-p",
                "ca-mp-task19-a1b2c3d4e5f6",
                "build",
            ],
        ),
        (
            "duplicate",
            [
                "docker",
                "compose",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "build",
            ],
        ),
        (
            "conflicting",
            [
                "docker",
                "compose",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "--project-name=foreign",
                "build",
            ],
        ),
        (
            "post-subcommand",
            [
                "docker",
                "compose",
                "build",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
            ],
        ),
    ],
)
def test_validator_rejects_noncanonical_compose_build_project(
    axis: str, case: str, replacement: list[str]
) -> None:
    """Compose builds use one split global project before the subcommand."""
    payload = (
        _complete_gui_compose_pass_evidence()
        if axis == "gui"
        else _complete_headless_compose_pass_evidence()
    )
    record_name = "gui_build" if axis == "gui" else "headless_build"
    service = "judge-gui" if axis == "gui" else "judge"
    argv = list(replacement)
    if axis == "gui" and "build" in argv:
        build_index = argv.index("build")
        argv[build_index:build_index] = ["--profile", "gui"]
    argv.append(service)
    payload[record_name]["argv"] = argv

    with pytest.raises(ValueError, match="project"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("axis", "argv"),
    [
        (
            "headless",
            [
                "docker",
                "compose",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "--profile",
                "gui",
                "build",
                "judge",
            ],
        ),
        (
            "gui-missing",
            [
                "docker",
                "compose",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "build",
                "judge-gui",
            ],
        ),
        (
            "gui-foreign",
            [
                "docker",
                "compose",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "--profile",
                "other",
                "build",
                "judge-gui",
            ],
        ),
        (
            "gui-inline",
            [
                "docker",
                "compose",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "--profile=gui",
                "build",
                "judge-gui",
            ],
        ),
        (
            "gui-duplicate",
            [
                "docker",
                "compose",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "--profile",
                "gui",
                "--profile",
                "gui",
                "build",
                "judge-gui",
            ],
        ),
    ],
)
def test_validator_rejects_noncanonical_compose_build_profile(
    axis: str, argv: list[str]
) -> None:
    """Only the GUI build carries one split global GUI profile."""
    if axis == "headless":
        payload = _complete_headless_compose_pass_evidence()
        record_name = "headless_build"
    else:
        payload = _complete_gui_compose_pass_evidence()
        record_name = "gui_build"
    payload[record_name]["argv"] = argv

    with pytest.raises(ValueError, match="profile"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize("axis", ["headless", "gui"])
@pytest.mark.parametrize(
    "direct_tokens",
    [
        ["--platform", "linux/amd64"],
        ["-t", "ca-mp-task19-a1b2c3d4e5f6-headless:local"],
        [
            "--label",
            "io.challengecup.task19.invocation=a1b2c3d4e5f6",
        ],
    ],
    ids=["platform", "tag", "label"],
)
def test_validator_rejects_direct_only_options_on_compose_build(
    axis: str, direct_tokens: list[str]
) -> None:
    """Compose render facts replace direct platform, tag, and label flags."""
    payload = (
        _complete_gui_compose_pass_evidence()
        if axis == "gui"
        else _complete_headless_compose_pass_evidence()
    )
    record_name = "gui_build" if axis == "gui" else "headless_build"
    argv = payload[record_name]["argv"]
    build_index = argv.index("build")
    argv[build_index:build_index] = direct_tokens

    with pytest.raises(ValueError, match="direct-only"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize("axis", ["headless", "gui"])
@pytest.mark.parametrize(
    ("case", "services"),
    [
        ("wrong", ["foreign-service"]),
        ("multiple", ["judge", "judge"]),
        ("extra", ["judge", "foreign-service"]),
    ],
)
def test_validator_rejects_noncanonical_compose_build_service(
    axis: str, case: str, services: list[str]
) -> None:
    """Each Compose build ends with exactly its one canonical service."""
    payload = (
        _complete_gui_compose_pass_evidence()
        if axis == "gui"
        else _complete_headless_compose_pass_evidence()
    )
    record_name = "gui_build" if axis == "gui" else "headless_build"
    argv = payload[record_name]["argv"]
    build_index = argv.index("build")
    if axis == "gui" and case != "wrong":
        services = ["judge-gui", *services[1:]]
    argv[build_index + 1 :] = services

    with pytest.raises(ValueError, match="service"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("case", "argv"),
    [
        (
            "duplicate-platform",
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",
                "--platform",
                "linux/amd64",
                "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local",
                ".",
            ],
        ),
        (
            "conflicting-platform",
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",
                "--platform=linux/arm64",
                "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local",
                ".",
            ],
        ),
        (
            "missing-tag",
            ["docker", "build", "--platform", "linux/amd64", "."],
        ),
        (
            "inline-tag",
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",
                "-t=ca-mp-task19-a1b2c3d4e5f6-headless:local",
                ".",
            ],
        ),
        (
            "duplicate-tag",
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",
                "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local",
                "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local",
                ".",
            ],
        ),
        (
            "conflicting-tag",
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",
                "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local",
                "--tag=foreign:local",
                ".",
            ],
        ),
        (
            "foreign-tag",
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",
                "-t",
                "foreign:local",
                ".",
            ],
        ),
        (
            "compose-mixed",
            [
                "docker",
                "build",
                "compose",
                "--platform",
                "linux/amd64",
                "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local",
                ".",
            ],
        ),
        (
            "foreign-context",
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",
                "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local",
                "other",
            ],
        ),
        (
            "non-final-context",
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",
                "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local",
                ".",
                "--pull",
            ],
        ),
    ],
)
def test_validator_rejects_ambiguous_direct_headless_build(
    case: str, argv: list[str]
) -> None:
    """Direct headless proof has one platform, tag, and final context."""
    payload = _complete_live_api_pass_evidence()
    payload["headless_build"]["argv"] = argv

    with pytest.raises(ValueError, match="direct headless build"):
        docker_status.validate_evidence(payload)


def test_validator_accepts_canonical_direct_headless_build() -> None:
    """Preserve the exact direct headless build as a supported proof form."""
    payload = _complete_live_api_pass_evidence()
    payload["headless_build"]["argv"] = [
        "docker",
        "build",
        "--platform",
        "linux/amd64",
        "-t",
        "ca-mp-task19-a1b2c3d4e5f6-headless:local",
        ".",
    ]
    docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "argv",
    [
        [
            "docker",
            "build",
            "-t",
            "ca-mp-task19-a1b2c3d4e5f6-headless:local",
            ".",
        ],
        [
            "docker",
            "build",
            "--platform=linux/amd64",
            "-t",
            "ca-mp-task19-a1b2c3d4e5f6-headless:local",
            ".",
        ],
        [
            "docker",
            "build",
            "--platform",
            "linux/arm64",
            "-t",
            "ca-mp-task19-a1b2c3d4e5f6-headless:local",
            ".",
        ],
    ],
    ids=["missing", "inline", "foreign"],
)
def test_validator_rejects_noncanonical_direct_headless_platform(
    argv: list[str],
) -> None:
    """Direct headless platform is one split exact linux/amd64 option."""
    payload = _complete_live_api_pass_evidence()
    payload["headless_build"]["argv"] = argv

    with pytest.raises(ValueError, match="direct headless build"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("scope", "argv"),
    [
        (
            "headless-foreign-project",
            [
                "docker",
                "compose",
                "--project-name",
                "foreign",
                "config",
                "--quiet",
            ],
        ),
        (
            "headless-profile",
            [
                "docker",
                "compose",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "--profile",
                "gui",
                "config",
                "--quiet",
            ],
        ),
        (
            "headless-inline-project",
            [
                "docker",
                "compose",
                "--project-name=ca-mp-task19-a1b2c3d4e5f6",
                "config",
                "--quiet",
            ],
        ),
        (
            "headless-extra",
            [
                "docker",
                "compose",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "config",
                "--quiet",
                "extra",
            ],
        ),
        (
            "gui-missing-profile",
            [
                "docker",
                "compose",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "config",
                "--quiet",
            ],
        ),
        (
            "gui-foreign-profile",
            [
                "docker",
                "compose",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "--profile",
                "other",
                "config",
                "--quiet",
            ],
        ),
        (
            "gui-inline-profile",
            [
                "docker",
                "compose",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "--profile=gui",
                "config",
                "--quiet",
            ],
        ),
        (
            "gui-duplicate-profile",
            [
                "docker",
                "compose",
                "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6",
                "--profile",
                "gui",
                "--profile",
                "gui",
                "config",
                "--quiet",
            ],
        ),
    ],
)
def test_validator_rejects_mismatched_static_contract_scope(
    scope: str, argv: list[str]
) -> None:
    """Static config quiet exactly matches the document's rendered scope."""
    payload = (
        _complete_gui_compose_pass_evidence()
        if scope.startswith("gui-")
        else _complete_headless_compose_pass_evidence()
    )
    payload["static_contract"]["argv"] = argv

    with pytest.raises(ValueError, match="static_contract"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize("scope", ["headless", "gui"])
@pytest.mark.parametrize(
    "case",
    ["missing", "nonzero", "wrong-status", "wrong-argv", "hash-mismatch"],
)
def test_validator_rejects_invalid_compose_render_proof(
    scope: str, case: str
) -> None:
    """Render proof is a real, successful, hash-linked scoped command."""
    payload = (
        _complete_gui_compose_pass_evidence()
        if scope == "gui"
        else _complete_headless_compose_pass_evidence()
    )
    static = payload["static_contract"]
    if case == "missing":
        static.pop("render_proof")
    elif case == "nonzero":
        static["render_proof"]["exit_code"] = 7
    elif case == "wrong-status":
        static["render_proof"]["status"] = "fail"
    elif case == "wrong-argv":
        static["render_proof"]["argv"][-2:] = ["config", "--quiet"]
    else:
        facts = static["render_proof"]["selected_facts"]
        facts["source_stdout_sha256"] = "d" * 64

    with pytest.raises(ValueError, match="render"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize("scope", ["headless", "gui"])
def test_validator_rejects_nonempty_quiet_config_stdout(scope: str) -> None:
    """Quiet config stdout stays empty and never stands in for render facts."""
    payload = (
        _complete_gui_compose_pass_evidence()
        if scope == "gui"
        else _complete_headless_compose_pass_evidence()
    )
    payload["static_contract"]["stdout_sha256"] = "a" * 64

    with pytest.raises(ValueError, match="quiet stdout"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "case",
    [
        "foreign-project",
        "headless-profile",
        "gui-foreign-profile",
        "foreign-service",
        "duplicate-service",
        "missing-headless-service",
        "foreign-headless-image",
        "mutable-gui-image",
        "foreign-platform",
        "missing-ownership-label",
        "foreign-ownership-label",
    ],
)
def test_validator_rejects_foreign_compose_render_facts(case: str) -> None:
    """Selected render facts exactly bind the invocation and build records."""
    gui_case = case.startswith("gui-") or case in {
        "missing-headless-service",
        "mutable-gui-image",
    }
    payload = (
        _complete_gui_compose_pass_evidence()
        if gui_case
        else _complete_headless_compose_pass_evidence()
    )
    facts = payload["static_contract"]["render_proof"]["selected_facts"]
    services = facts["services"]
    if case == "foreign-project":
        facts["project"] = "foreign"
    elif case == "headless-profile":
        facts["profiles"] = ["gui"]
    elif case == "gui-foreign-profile":
        facts["profiles"] = ["other"]
    elif case == "foreign-service":
        services[0]["name"] = "foreign-service"
    elif case == "duplicate-service":
        services.append(copy.deepcopy(services[0]))
    elif case == "missing-headless-service":
        services.pop(0)
    elif case == "foreign-headless-image":
        services[0]["image"] = "foreign:local"
    elif case == "mutable-gui-image":
        services[1]["image"] = "ca-mp-task19-a1b2c3d4e5f6-gui:latest"
    elif case == "foreign-platform":
        services[0]["platform"] = "linux/arm64"
    elif case == "missing-ownership-label":
        services[0]["labels"] = {}
    else:
        services[0]["labels"]["io.challengecup.task19.invocation"] = "foreign"

    with pytest.raises(ValueError, match="render selected"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "case", ["headless-present", "gui-missing", "gui-foreign", "gui-extra"]
)
def test_validator_rejects_invalid_rendered_additional_contexts(
    case: str,
) -> None:
    """Only GUI has the exact immutable judge-base service link."""
    payload = _complete_gui_compose_pass_evidence()
    services = payload["static_contract"]["render_proof"]["selected_facts"][
        "services"
    ]
    if case == "headless-present":
        services[0]["additional_contexts"] = {"foreign": "service:judge-gui"}
    elif case == "gui-missing":
        services[1]["additional_contexts"] = {}
    elif case == "gui-foreign":
        services[1]["additional_contexts"]["judge_base"] = "service:foreign"
    else:
        services[1]["additional_contexts"]["other"] = "service:judge"

    with pytest.raises(ValueError, match="additional contexts"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize("level", ["proof", "facts", "service"])
def test_validator_rejects_unknown_compose_render_field(level: str) -> None:
    """Every new render-proof mapping remains closed to unknown fields."""
    payload = _complete_headless_compose_pass_evidence()
    proof = payload["static_contract"]["render_proof"]
    if level == "proof":
        target = proof
    elif level == "facts":
        target = proof["selected_facts"]
    else:
        target = proof["selected_facts"]["services"][0]
    target["unexpected"] = "value"

    with pytest.raises(ValueError, match="unexpected fields"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize("scope", ["headless", "gui"])
def test_validator_accepts_nonempty_render_with_exact_integer_zero(
    scope: str,
) -> None:
    """A real nonempty render with integer exit zero remains canonical."""
    payload = (
        _complete_gui_compose_pass_evidence()
        if scope == "gui"
        else _complete_headless_compose_pass_evidence()
    )
    render = payload["static_contract"]["render_proof"]

    assert render["stdout_sha256"] in {"e" * 64, "f" * 64}
    assert type(render["exit_code"]) is int
    assert render["exit_code"] == 0
    docker_status.validate_evidence(payload)


@pytest.mark.parametrize("scope", ["headless", "gui"])
@pytest.mark.parametrize(
    ("case", "value"),
    [
        (
            "empty-stdout",
            "e3b0c44298fc1c149afbf4c8996fb924"
            "27ae41e4649b934ca495991b7852b855",
        ),
        ("boolean-exit", False),
        ("float-exit", 0.0),
    ],
)
def test_validator_rejects_false_render_transport(
    scope: str, case: str, value: object
) -> None:
    """A render is nonempty output from an exact integer-zero command."""
    payload = (
        _complete_gui_compose_pass_evidence()
        if scope == "gui"
        else _complete_headless_compose_pass_evidence()
    )
    render = payload["static_contract"]["render_proof"]
    if case == "empty-stdout":
        render["stdout_sha256"] = value
        render["selected_facts"]["source_stdout_sha256"] = value
    else:
        render["exit_code"] = value

    with pytest.raises(ValueError, match="render proof"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "case",
    [
        "headless-build-project",
        "static-project",
        "render-project",
        "selected-project",
        "gui-rendered-service",
    ],
)
def test_validator_rejects_cleanup_failure_with_corrupt_compose_success(
    case: str,
) -> None:
    """A later cleanup failure cannot launder prior Compose success claims."""
    payload = (
        _complete_gui_compose_pass_evidence()
        if case == "gui-rendered-service"
        else _complete_headless_compose_pass_evidence()
    )
    payload["status"] = "fail"
    payload["reason"] = "cleanup_failed"
    payload["cleanup"].update(
        {
            "status": "fail",
            "exit_code": 17,
            "detail": "owned cleanup exited 17",
        }
    )
    if case == "headless-build-project":
        payload["headless_build"]["argv"][3] = "foreign"
    elif case == "static-project":
        payload["static_contract"]["argv"][3] = "foreign"
    elif case == "render-project":
        payload["static_contract"]["render_proof"]["argv"][3] = "foreign"
    elif case == "selected-project":
        payload["static_contract"]["render_proof"]["selected_facts"][
            "project"
        ] = "foreign"
    else:
        services = payload["static_contract"]["render_proof"][
            "selected_facts"
        ]["services"]
        services[1]["image"] = "foreign-gui-image:local"

    with pytest.raises(ValueError, match="Compose|static|render"):
        docker_status.validate_evidence(payload)


def test_validator_accepts_cleanup_failure_with_canonical_compose_success(
) -> None:
    """A cleanup failure preserves fully canonical prior Compose proof."""
    payload = _cleanup_only_failure_evidence()

    docker_status.validate_evidence(payload)


def test_validator_accepts_cleanup_failure_with_canonical_gui_compose_success(
) -> None:
    """A cleanup failure preserves canonical GUI build and render proof."""
    docker_status.validate_evidence(
        _truthful_gui_cleanup_command_failure_evidence()
    )


def test_validator_rejects_cleanup_failure_with_unpaired_compose_build() -> (
    None
):
    """A successful Compose build requires successful static render proof."""
    payload = _cleanup_only_failure_evidence()
    empty_sha256 = (
        "e3b0c44298fc1c149afbf4c8996fb924" "27ae41e4649b934ca495991b7852b855"
    )
    payload["static_contract"].update(
        {
            "status": "not_run",
            "argv": [],
            "exit_code": None,
            "stdout_sha256": empty_sha256,
            "stderr_sha256": empty_sha256,
        }
    )
    payload["static_contract"].pop("render_proof")

    with pytest.raises(ValueError, match="Compose success requires"):
        docker_status.validate_evidence(payload)


def test_validator_rejects_not_run_static_with_nested_render_proof() -> None:
    """A non-pass static record cannot hide a structured render claim."""
    payload = docker_status.new_evidence()
    payload["static_contract"]["render_proof"] = {
        "status": "pass",
        "argv": [
            "docker",
            "compose",
            "--project-name",
            "ca-mp-task19-a1b2c3d4e5f6",
            "config",
            "--format",
            "json",
        ],
        "exit_code": 0,
        "stdout_sha256": "e" * 64,
        "selected_facts": {
            "source_stdout_sha256": "e" * 64,
            "project": "ca-mp-task19-a1b2c3d4e5f6",
            "profiles": [],
            "services": [
                {
                    "name": "judge",
                    "image": ("ca-mp-task19-a1b2c3d4e5f6-headless:local"),
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": ("a1b2c3d4e5f6")
                    },
                    "additional_contexts": {},
                }
            ],
        },
    }

    with pytest.raises(ValueError, match="non-pass static_contract"):
        docker_status.validate_evidence(payload)


def test_validator_rejects_gui_smoke_pass_without_gui_build_pass() -> None:
    """A GUI smoke success depends on a successful canonical GUI build."""
    payload = _complete_gui_compose_pass_evidence()
    untouched = _complete_headless_compose_pass_evidence()["gui_build"]
    payload["gui_build"] = copy.deepcopy(untouched)

    with pytest.raises(ValueError, match="GUI smoke.*GUI build"):
        docker_status.validate_evidence(payload)


def test_validator_accepts_gui_build_pass_with_gui_smoke_not_run() -> None:
    """A built GUI image need not claim that its smoke was executed."""
    payload = _complete_gui_compose_pass_evidence()
    untouched = _complete_headless_compose_pass_evidence()["gui_smoke"]
    payload["gui_smoke"] = copy.deepcopy(untouched)
    payload["owned_resources"]["before_cleanup"] = [
        record
        for record in payload["owned_resources"]["before_cleanup"]
        if record["name"]
        not in {
            "ca-mp-task19-a1b2c3d4e5f6-judge-gui-1",
            "ca-mp-task19-a1b2c3d4e5f6_judge-gui-output",
        }
    ]
    payload["owned_resources"]["cleanup_actions"] = [
        action
        for action in payload["owned_resources"]["cleanup_actions"]
        if action["resource_name"]
        not in {
            "ca-mp-task19-a1b2c3d4e5f6-judge-gui-1",
            "ca-mp-task19-a1b2c3d4e5f6_judge-gui-output",
        }
    ]
    payload.pop("gui_frame_proof")
    payload["exported_evidence"]["contents"] = [
        item
        for item in payload["exported_evidence"]["contents"]
        if not item["path"].endswith(".png")
    ]

    docker_status.validate_evidence(payload)


# Production mutation caught: retaining a fabricated Docker exec of the
# nonexistent scripts.quick_smoke module instead of validating real API smoke.
def test_validator_accepts_handwritten_api_smoke_for_each_container() -> None:
    """Headless and imported images each prove a distinct API-created run."""
    docker_status.validate_evidence(_complete_live_api_pass_evidence())


# Production mutation caught: accepting an omitted, foreign, or non-string
# primary request target merely because the body otherwise asks for 100 steps.
@pytest.mark.parametrize(
    ("field", "value", "remove"),
    [
        ("intersection_id", None, True),
        ("intersection_id", "2", False),
        ("intersection_id", 1, False),
        ("algorithm", None, True),
        ("algorithm", "adaptive", False),
        ("algorithm", 17, False),
    ],
    ids=[
        "missing-intersection-id",
        "foreign-intersection-id",
        "non-string-intersection-id",
        "missing-algorithm",
        "foreign-algorithm",
        "non-string-algorithm",
    ],
)
def test_validator_rejects_noncanonical_api_request_target(
    field: str, value: object, remove: bool
) -> None:
    """API smoke always creates the canonical fixed-time intersection run."""
    payload = _complete_live_api_pass_evidence()
    proof_body = payload["headless_smoke"]["api_proof"]["request"]["body"]
    summary_body = payload["quick_smoke"]["request"]["body"]
    for body in (proof_body, summary_body):
        if remove:
            body.pop(field)
        else:
            body[field] = value

    with pytest.raises(ValueError, match=field):
        docker_status.validate_evidence(payload)


# Existing contract control: the exact-100 check already rejects an omitted
# step count once the complete canonical request body is admitted.
def test_validator_rejects_api_request_body_without_steps() -> None:
    """The API request body explicitly records its 100-step workload."""
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"]["request"]["body"].pop("steps")
    payload["quick_smoke"]["request"]["body"].pop("steps")

    with pytest.raises(ValueError, match="exactly 100 steps"):
        docker_status.validate_evidence(payload)


def test_validator_accepts_cleanup_only_failure_after_valid_api_results() -> (
    None
):
    """A later cleanup failure preserves two valid successful API results."""
    docker_status.validate_evidence(_cleanup_only_failure_evidence())


# Production mutation caught: successful primary API evidence bypassing its
# closed proof schema merely because the later cleanup phase failed.
def test_validator_rejects_cleanup_failure_with_unknown_primary_api_field(
) -> None:
    payload = _cleanup_only_failure_evidence()
    payload["headless_smoke"]["api_proof"]["unexpected"] = "safe"

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


# Production mutation caught: successful primary API evidence bypassing its
# exact creation target merely because the later cleanup phase failed.
def test_validator_rejects_cleanup_failure_with_foreign_primary_api_path() -> (
    None
):
    payload = _cleanup_only_failure_evidence()
    payload["headless_smoke"]["api_proof"]["request"][
        "path"
    ] = "/api/runs/foreign-run-8c2d1e5f"

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


# Production mutation caught: nested imported API evidence escaping the
# API-result record metadata contract on a later cleanup failure.
def test_validator_rejects_cleanup_failure_with_imported_api_command() -> None:
    payload = _cleanup_only_failure_evidence()
    payload["save_load_proof"]["repeated_smoke"]["argv"] = [
        "docker",
        "exec",
        "forbidden-imported-smoke",
    ]

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


# Production mutation caught: a nested API proof cannot evade record
# validation by omitting the explicit API-result execution discriminator.
def test_validator_rejects_cleanup_failure_with_untyped_imported_api_proof(
) -> None:
    payload = _cleanup_only_failure_evidence()
    payload["save_load_proof"]["repeated_smoke"].pop("execution")

    with pytest.raises(ValueError, match="command cannot contain API proof"):
        docker_status.validate_evidence(payload)


# Production mutation caught: a later cleanup failure cannot make the outer
# save/load proof mapping open to unverified fields.
def test_validator_rejects_cleanup_failure_with_unknown_save_load_field() -> (
    None
):
    payload = _cleanup_only_failure_evidence()
    payload["save_load_proof"]["unexpected"] = "safe"

    with pytest.raises(
        ValueError, match="save/load proof contains unexpected fields"
    ):
        docker_status.validate_evidence(payload)


# Production mutation caught: all records supporting the imported API result
# remain subject to command metadata validation after a cleanup failure.
def test_validator_rejects_cleanup_failure_with_malformed_image_load_record(
) -> None:
    payload = _cleanup_only_failure_evidence()
    payload["save_load_proof"]["image_load"]["argv"] = []

    with pytest.raises(ValueError, match="pass record must have a command"):
        docker_status.validate_evidence(payload)


# Production mutation caught: skipping the successful top-level save summary
# for every failure reason instead of only for a real save/load failure.
def test_validator_rejects_cleanup_failure_with_foreign_save_summary() -> None:
    payload = _cleanup_only_failure_evidence()
    payload["save_load"]["argv"] = [
        "docker",
        "image",
        "save",
        "--output",
        "output/evidence/docker/live/foreign/headless-image.tar",
        "foreign-headless:local",
    ]

    with pytest.raises(ValueError, match="save/load phase"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting an unrelated Docker command merely
# because it carries the canonical tar and image as otherwise-unused tokens.
def test_validator_rejects_cleanup_failure_with_unrelated_save_summary() -> (
    None
):
    payload = _cleanup_only_failure_evidence()
    payload["save_load"]["argv"] = [
        "docker",
        "exec",
        "unrelated-container",
        "--output",
        "output/evidence/docker/live/a1b2c3d4e5f6/headless-image.tar",
        "ca-mp-task19-a1b2c3d4e5f6-headless:local",
    ]

    with pytest.raises(ValueError, match="save/load phase"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting duplicate or conflicting save-summary
# identity tokens because validation reads only their first occurrence.
@pytest.mark.parametrize(
    "extra_tokens",
    [
        [
            "--output",
            "output/evidence/docker/live/a1b2c3d4e5f6/" "headless-image.tar",
        ],
        [
            "--output",
            "output/evidence/docker/live/foreign/headless-image.tar",
        ],
        ["ca-mp-task19-a1b2c3d4e5f6-headless:local"],
    ],
    ids=[
        "repeated-output",
        "conflicting-output",
        "repeated-image",
    ],
)
def test_validator_rejects_cleanup_failure_with_duplicate_save_tokens(
    extra_tokens: list[str],
) -> None:
    payload = _cleanup_only_failure_evidence()
    payload["save_load"]["argv"].extend(extra_tokens)

    with pytest.raises(ValueError, match="save/load phase"):
        docker_status.validate_evidence(payload)


# Production mutation caught: shallow discovery accepting an imported API
# result hidden below the one exact nested location the schema permits.
@pytest.mark.parametrize("wrapper_kind", ["mapping", "list"])
def test_validator_rejects_wrapped_imported_api_result(
    wrapper_kind: str,
) -> None:
    payload = _cleanup_only_failure_evidence()
    imported = payload["save_load_proof"]["repeated_smoke"]
    if wrapper_kind == "mapping":
        wrapped: object = {"wrapped": imported}
    else:
        wrapped = [imported]
    payload["save_load_proof"]["repeated_smoke"] = wrapped

    with pytest.raises(ValueError, match="API result location"):
        docker_status.validate_evidence(payload)


# Production mutation caught: successful imported API evidence bypassing its
# closed proof schema merely because the later cleanup phase failed.
def test_validator_rejects_cleanup_failure_with_unknown_imported_api_field(
) -> None:
    payload = _cleanup_only_failure_evidence()
    payload["save_load_proof"]["repeated_smoke"]["api_proof"].update(
        {"unexpected": "safe"}
    )

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


# Production mutation caught: cleanup-failure dispatch skipping the required
# independence comparison after both API proofs validate individually.
def test_validator_rejects_cleanup_failure_with_reused_api_response_hash() -> (
    None
):
    payload = _cleanup_only_failure_evidence()
    primary = payload["headless_smoke"]["api_proof"]
    imported = payload["save_load_proof"]["repeated_smoke"]["api_proof"]
    imported["response"]["body_sha256"] = primary["response"]["body_sha256"]

    with pytest.raises(ValueError, match="imported API response hash"):
        docker_status.validate_evidence(payload)


# Production mutation caught: treating any top-level phase as a legal holder
# for an otherwise well-formed primary API result.
def test_validator_rejects_api_result_outside_headless_smoke() -> None:
    payload = _cleanup_only_failure_evidence()
    payload["headless_health"] = copy.deepcopy(payload["headless_smoke"])

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


# Production mutation caught: treating any nested save/load record as a legal
# holder for an otherwise well-formed imported API result.
def test_validator_rejects_api_result_outside_repeated_smoke() -> None:
    payload = _cleanup_only_failure_evidence()
    payload["save_load_proof"]["repeated_health"] = copy.deepcopy(
        payload["save_load_proof"]["repeated_smoke"]
    )

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


# Production mutation caught: retaining the obsolete command-shaped primary
# smoke as a valid pass instead of requiring the API-created run result.
def test_validator_rejects_primary_smoke_without_api_result_proof() -> None:
    """A passing primary smoke is the returned API result, not Docker exec."""
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"].pop("execution")
    payload["headless_smoke"].pop("api_proof")
    payload["headless_smoke"]["argv"] = [
        "docker",
        "exec",
        "ca-mp-task19-a1b2c3d4e5f6-judge-1",
        "python",
        "-m",
        "scripts.quick_smoke",
    ]
    payload["headless_smoke"]["exit_code"] = 0

    with pytest.raises(ValueError, match="primary API smoke"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting an API create response without the
# server-issued run identifier that must bind the terminal request and output.
def test_validator_rejects_api_smoke_missing_created_run_id() -> None:
    payload = _complete_live_api_pass_evidence()
    del payload["headless_smoke"]["api_proof"]["response"]["run_id"]

    with pytest.raises(ValueError, match="created API run ID"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a terminal GET for a foreign API run.
def test_validator_rejects_api_smoke_foreign_terminal_run_id() -> None:
    payload = _complete_live_api_pass_evidence()
    proof = payload["headless_smoke"]["api_proof"]
    proof["terminal"]["path"] = "/api/runs/foreign-run-8c2d1e5f"
    proof["terminal"]["run_id"] = "foreign-run-8c2d1e5f"

    with pytest.raises(ValueError, match="terminal API run ID"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a smoke request to an endpoint other
# than the exact API run-creation route.
def test_validator_rejects_api_smoke_wrong_create_endpoint() -> None:
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"]["request"][
        "path"
    ] = "/api/runs/foreign-run-8c2d1e5f"

    with pytest.raises(ValueError, match="create endpoint"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a terminal lookup outside the exact
# run-specific GET endpoint.
def test_validator_rejects_api_smoke_wrong_terminal_endpoint() -> None:
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"]["terminal"]["path"] = "/api/runs"

    with pytest.raises(ValueError, match="terminal endpoint"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a POST body that did not actually ask
# the API for exactly one hundred simulation steps.
def test_validator_rejects_api_smoke_non_100_requested_steps() -> None:
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"]["request"]["body"]["steps"] = 99

    with pytest.raises(
        ValueError, match="API request must ask for exactly 100"
    ):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a terminal API body that completed
# fewer than the requested one hundred steps.
def test_validator_rejects_api_smoke_non_100_completed_steps() -> None:
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"]["terminal"]["completed_steps"] = 99

    with pytest.raises(
        ValueError, match="API terminal must complete exactly 100"
    ):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a create response other than the API's
# asynchronous accepted status.
def test_validator_rejects_api_smoke_wrong_create_response_status() -> None:
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"]["response"]["status"] = 201

    with pytest.raises(ValueError, match="create response status"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a terminal lookup without its exact
# successful API response status.
def test_validator_rejects_api_smoke_wrong_terminal_response_status() -> None:
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"]["terminal"]["status"] = 202

    with pytest.raises(ValueError, match="terminal response status"):
        docker_status.validate_evidence(payload)


# Production mutation caught: treating Boolean true as a valid integer step
# count in the API request body.
def test_validator_rejects_api_smoke_boolean_requested_steps() -> None:
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"]["request"]["body"]["steps"] = True

    with pytest.raises(
        ValueError, match="API request must ask for exactly 100"
    ):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a non-terminal API run state even when
# the legacy quick-smoke summary claims completion.
def test_validator_rejects_api_smoke_nonterminal_api_state() -> None:
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"]["terminal"]["state"] = "running"

    with pytest.raises(ValueError, match="terminal state"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a terminal response without a closed
# content hash for the independently observed terminal body.
def test_validator_rejects_api_smoke_missing_terminal_body_hash() -> None:
    payload = _complete_live_api_pass_evidence()
    del payload["headless_smoke"]["api_proof"]["terminal"]["body_sha256"]

    with pytest.raises(ValueError, match="terminal body SHA-256"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting output whose recorded run ID is not
# the server-created ID proved by the API response and terminal lookup.
def test_validator_rejects_api_smoke_unlinked_output_run_id() -> None:
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"]["output"][
        "run_id"
    ] = "foreign-run-8c2d1e5f"

    with pytest.raises(ValueError, match="API output run ID"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting the primary run proof copied as the
# imported-container smoke instead of an independent imported-image run.
def test_validator_rejects_reused_primary_api_smoke_for_imported_container(
) -> None:
    payload = _complete_live_api_pass_evidence()
    payload["save_load_proof"]["repeated_smoke"]["api_proof"] = copy.deepcopy(
        payload["headless_smoke"]["api_proof"]
    )

    with pytest.raises(ValueError, match="imported API smoke"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting the historical Docker-exec repeated
# smoke rather than a separate API-created run for the imported image.
def test_validator_rejects_imported_smoke_without_independent_api_proof() -> (
    None
):
    payload = _complete_live_api_pass_evidence()
    payload["save_load_proof"]["repeated_smoke"] = copy.deepcopy(
        _legacy_command_smoke_live_pass_evidence()["save_load_proof"][
            "repeated_smoke"
        ]
    )

    with pytest.raises(ValueError, match="independent imported API smoke"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting API response hashes copied from the
# primary smoke into a purportedly independent imported-image run.
def test_validator_rejects_imported_api_smoke_with_reused_response_hash() -> (
    None
):
    payload = _complete_live_api_pass_evidence()
    primary = payload["headless_smoke"]["api_proof"]
    imported = payload["save_load_proof"]["repeated_smoke"]["api_proof"]
    imported["response"]["body_sha256"] = primary["response"]["body_sha256"]

    with pytest.raises(ValueError, match="imported API response hash"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting an imported-container proof that names
# the primary image rather than the imported image that was actually loaded.
def test_validator_rejects_imported_api_smoke_with_primary_image() -> None:
    payload = _complete_live_api_pass_evidence()
    payload["save_load_proof"]["repeated_smoke"]["api_proof"][
        "image"
    ] = "ca-mp-task19-a1b2c3d4e5f6-headless:local"

    with pytest.raises(ValueError, match="imported API smoke image"):
        docker_status.validate_evidence(payload)


# Production mutation caught: allowing the top-level smoke summary to diverge
# from the closed API proof that the phase itself records.
def test_validator_rejects_api_smoke_summary_not_linked_to_api_proof() -> None:
    payload = _complete_live_api_pass_evidence()
    payload["quick_smoke"]["run_id"] = "summary-run-1a2b3c4d"
    payload["quick_smoke"]["output"]["path"] = "runs/summary-run-1a2b3c4d"
    payload["quick_smoke"]["output"]["run_id"] = "summary-run-1a2b3c4d"

    with pytest.raises(ValueError, match="summary must match API proof"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a run-creation request or terminal
# lookup whose HTTP method does not match the API contract.
@pytest.mark.parametrize(
    ("section", "method", "expected_fragment"),
    [
        ("request", "GET", "create method"),
        ("terminal", "POST", "terminal method"),
    ],
    ids=["create", "terminal"],
)
def test_validator_rejects_api_smoke_wrong_http_method(
    section: str, method: str, expected_fragment: str
) -> None:
    """The API proof records exact POST creation and GET terminal lookup."""
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"][section]["method"] = method

    with pytest.raises(ValueError, match=expected_fragment):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a request or create response without
# a closed hash of the body that was sent or received.
@pytest.mark.parametrize(
    ("section", "expected_fragment"),
    [
        ("request", "request body SHA-256"),
        ("response", "create response body SHA-256"),
    ],
    ids=["request", "response"],
)
def test_validator_rejects_api_smoke_missing_create_exchange_hash(
    section: str, expected_fragment: str
) -> None:
    """Both sides of the API creation exchange have valid body hashes."""
    payload = _complete_live_api_pass_evidence()
    del payload["headless_smoke"]["api_proof"][section]["body_sha256"]

    with pytest.raises(ValueError, match=expected_fragment):
        docker_status.validate_evidence(payload)


# Production mutation caught: treating an empty string as a server-allocated
# run ID merely because the response field exists.
def test_validator_rejects_api_smoke_empty_created_run_id() -> None:
    """The accepted create response contains a nonempty returned run ID."""
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"]["response"]["run_id"] = ""

    with pytest.raises(ValueError, match="created API run ID"):
        docker_status.validate_evidence(payload)


# Production mutation caught: treating Boolean true as the integer terminal
# count one hundred because bool is an int subclass.
def test_validator_rejects_api_smoke_boolean_completed_steps() -> None:
    """The terminal completed-step count is the non-Boolean integer 100."""
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"]["terminal"][
        "completed_steps"
    ] = True

    with pytest.raises(
        ValueError, match="API terminal must complete exactly 100"
    ):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting integral floats for API counts or
# response statuses because Python considers them equal to integer literals.
@pytest.mark.parametrize(
    ("target", "expected_fragment"),
    [
        ("request-steps", "API request must ask for exactly 100"),
        ("response-status", "create response status"),
        ("terminal-status", "terminal response status"),
        ("terminal-steps", "API terminal must complete exactly 100"),
        ("proof-requested-steps", "record exactly 100 requested steps"),
    ],
)
def test_validator_rejects_noninteger_api_numeric_fields(
    target: str, expected_fragment: str
) -> None:
    """API counts and status codes are non-Boolean integers, not floats."""
    payload = _complete_live_api_pass_evidence()
    proof = payload["headless_smoke"]["api_proof"]
    if target == "request-steps":
        proof["request"]["body"]["steps"] = 100.0
    elif target == "response-status":
        proof["response"]["status"] = 202.0
    elif target == "terminal-status":
        proof["terminal"]["status"] = 200.0
    elif target == "terminal-steps":
        proof["terminal"]["completed_steps"] = 100.0
    else:
        proof["requested_steps"] = 100.0

    with pytest.raises(ValueError, match=expected_fragment):
        docker_status.validate_evidence(payload)


# Production mutation caught: validating only one of the terminal path and
# terminal response-body run IDs against the server-created ID.
@pytest.mark.parametrize(
    ("target", "expected_fragment"),
    [
        ("path", "terminal endpoint"),
        ("run_id", "terminal API run ID"),
    ],
    ids=["path-id", "body-id"],
)
def test_validator_rejects_api_smoke_each_foreign_terminal_id(
    target: str, expected_fragment: str
) -> None:
    """Terminal path and body independently name the returned run ID."""
    payload = _complete_live_api_pass_evidence()
    terminal = payload["headless_smoke"]["api_proof"]["terminal"]
    if target == "path":
        terminal["path"] = "/api/runs/foreign-run-8c2d1e5f"
    else:
        terminal["run_id"] = "foreign-run-8c2d1e5f"

    with pytest.raises(ValueError, match=expected_fragment):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a proof summary or output directory
# whose run identity diverges from the create response.
@pytest.mark.parametrize(
    ("target", "expected_fragment"),
    [
        ("run_id", "API proof run ID"),
        ("output-path", "API output path"),
    ],
    ids=["proof-run-id", "output-path"],
)
def test_validator_rejects_api_smoke_each_unlinked_proof_id(
    target: str, expected_fragment: str
) -> None:
    """Proof summary and output path independently use the returned run ID."""
    payload = _complete_live_api_pass_evidence()
    proof = payload["headless_smoke"]["api_proof"]
    if target == "run_id":
        proof["run_id"] = "foreign-run-8c2d1e5f"
    else:
        proof["output"]["path"] = "runs/foreign-run-8c2d1e5f"

    with pytest.raises(ValueError, match=expected_fragment):
        docker_status.validate_evidence(payload)


# Production mutation caught: permitting extension or raw fields in any
# nested API proof mapping because only the outer command record is closed.
@pytest.mark.parametrize(
    "location",
    ["proof", "request", "request-body", "response", "terminal", "output"],
)
def test_validator_rejects_unknown_fields_in_each_api_proof_mapping(
    location: str,
) -> None:
    """Every independently hand-written API proof mapping is closed."""
    payload = _complete_live_api_pass_evidence()
    proof = payload["headless_smoke"]["api_proof"]
    mappings = {
        "proof": proof,
        "request": proof["request"],
        "request-body": proof["request"]["body"],
        "response": proof["response"],
        "terminal": proof["terminal"],
        "output": proof["output"],
    }
    mappings[location]["unexpected"] = "safe"

    with pytest.raises(ValueError, match="unexpected"):
        docker_status.validate_evidence(payload)


# Production mutation caught: trusting a primary API proof aimed at a foreign
# container or image despite otherwise-correct run evidence.
@pytest.mark.parametrize(
    ("field", "expected_fragment"),
    [
        ("container", "primary API smoke container"),
        ("image", "primary API smoke image"),
    ],
)
def test_validator_rejects_primary_api_smoke_with_foreign_target(
    field: str, expected_fragment: str
) -> None:
    """The primary API proof is bound to its exact container and image."""
    payload = _complete_live_api_pass_evidence()
    payload["headless_smoke"]["api_proof"][field] = f"foreign-{field}"

    with pytest.raises(ValueError, match=expected_fragment):
        docker_status.validate_evidence(payload)


# Production mutation caught: trusting an imported-image API smoke against a
# foreign container while its image and run evidence appear independent.
def test_validator_rejects_imported_api_smoke_with_foreign_container() -> None:
    """The repeated API proof targets the exact imported container."""
    payload = _complete_live_api_pass_evidence()
    payload["save_load_proof"]["repeated_smoke"]["api_proof"][
        "container"
    ] = "foreign-imported-container"

    with pytest.raises(ValueError, match="imported API smoke container"):
        docker_status.validate_evidence(payload)


# Production mutation caught: claiming two independent API smokes after
# changing every imported run-ID location to the primary server-issued ID.
def test_validator_rejects_imported_api_smoke_with_reused_run_id() -> None:
    """Primary and imported API smokes have distinct returned run IDs."""
    payload = _complete_live_api_pass_evidence()
    primary_id = payload["headless_smoke"]["api_proof"]["response"]["run_id"]
    imported = payload["save_load_proof"]["repeated_smoke"]["api_proof"]
    imported["response"]["run_id"] = primary_id
    imported["terminal"]["path"] = f"/api/runs/{primary_id}"
    imported["terminal"]["run_id"] = primary_id
    imported["run_id"] = primary_id
    imported["output"]["path"] = f"runs/{primary_id}"
    imported["output"]["run_id"] = primary_id

    with pytest.raises(ValueError, match="distinct run IDs"):
        docker_status.validate_evidence(payload)


# Production mutation caught: laundering a copied primary terminal response
# as an imported-image result while only the other proof fields differ.
def test_validator_rejects_imported_api_smoke_with_reused_terminal_hash() -> (
    None
):
    """Independent API smokes have distinct terminal response hashes."""
    payload = _complete_live_api_pass_evidence()
    primary = payload["headless_smoke"]["api_proof"]
    imported = payload["save_load_proof"]["repeated_smoke"]["api_proof"]
    imported["terminal"]["body_sha256"] = primary["terminal"]["body_sha256"]

    with pytest.raises(ValueError, match="imported API terminal hash"):
        docker_status.validate_evidence(payload)


# Production mutation caught: laundering the entire primary response proof by
# changing only its target container and image to imported identities.
def test_validator_rejects_primary_api_proof_with_only_imported_target_changed(
) -> None:
    """A target-only change cannot turn the primary proof into a repeat."""
    payload = _complete_live_api_pass_evidence()
    imported = copy.deepcopy(payload["headless_smoke"]["api_proof"])
    imported["container"] = "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1"
    imported["image"] = "ca-mp-task19-a1b2c3d4e5f6-imported:local"
    payload["save_load_proof"]["repeated_smoke"]["api_proof"] = imported

    with pytest.raises(ValueError, match="distinct run IDs"):
        docker_status.validate_evidence(payload)


def test_new_evidence_declares_schema_and_all_phases_not_run() -> None:
    """Catch omitted phases or a live claim in a new evidence document."""
    payload = docker_status.new_evidence()

    assert payload["schema"] == "judge-docker-evidence.v1"
    assert payload["status"] == "not_run"
    for phase in docker_status.PHASES:
        assert payload[phase]["status"] == "not_run"


def test_phase_names_are_the_frozen_eight_phase_schema() -> None:
    """Catch a renamed, added, or omitted phase in the published schema."""
    assert docker_status.PHASES == (
        "static_contract",
        "headless_build",
        "headless_health",
        "headless_smoke",
        "save_load",
        "gui_build",
        "gui_smoke",
        "cleanup",
    )


def test_independent_handwritten_live_pass_fixture_validates() -> None:
    """Keep the exhaustive verifier-facing pass schema independently valid."""
    docker_status.validate_evidence(_complete_live_pass_evidence())


# Production mutation caught: accepting a pass whose quick-smoke terminal
# state is not completed.
def test_validator_rejects_pass_with_uncompleted_quick_smoke_terminal() -> (
    None
):
    """Require a completed terminal status for the 100-step quick smoke."""
    payload = _complete_live_pass_evidence()
    payload["quick_smoke"]["terminal_status"] = "failed"

    with pytest.raises(ValueError, match="terminal"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a pass after fewer than all 100
# requested quick-smoke steps finished.
def test_validator_rejects_pass_with_incomplete_quick_smoke_steps() -> None:
    """Require each literal quick-smoke step from one through one hundred."""
    payload = _complete_live_pass_evidence()
    payload["quick_smoke"]["completed_steps"].pop()

    with pytest.raises(ValueError, match="completed steps"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a quick-smoke output that does not
# prove the declared run ID produced it.
def test_validator_rejects_pass_with_unlinked_quick_smoke_output() -> None:
    """Bind the quick-smoke run ID, command, and app-output evidence path."""
    payload = _complete_live_pass_evidence()
    payload["quick_smoke"]["output"]["path"] = "runs/another-run"

    with pytest.raises(ValueError, match="output"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a loaded image that uses a different
# tar artifact than the preceding save phase.
def test_validator_rejects_pass_with_unlinked_save_load_tar() -> None:
    """Bind the save command, load command, and proof tar path together."""
    payload = _complete_live_pass_evidence()
    payload["save_load_proof"]["image_load"]["argv"][-1] = "other.tar"

    with pytest.raises(ValueError, match="tar"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a retag that does not create the
# independent imported image declared in the invocation.
def test_validator_rejects_pass_with_nonindependent_retagged_image() -> None:
    """Require a saved image to become the imported image."""
    payload = _complete_live_pass_evidence()
    payload["save_load_proof"]["image_retag"]["argv"][-1] = payload[
        "invocation"
    ]["headless_image"]

    with pytest.raises(ValueError, match="retag"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting repeated proof commands against the
# original headless container instead of the declared imported-image container.
def test_validator_rejects_pass_with_repeated_proof_on_original_container(
) -> None:
    """Require repeated health and smoke checks on the imported container."""
    payload = _complete_live_pass_evidence()
    payload["save_load_proof"]["repeated_health"]["argv"][
        -1
    ] = "ca-mp-task19-a1b2c3d4e5f6-judge-1"

    with pytest.raises(ValueError, match="imported container"):
        docker_status.validate_evidence(payload)


# Production mutation caught: ignoring a failed GUI axis while publishing an
# otherwise-headless pass document.
def test_validator_rejects_pass_with_failed_gui_phase() -> None:
    """Allow GUI not-run, but never allow an explicitly failed GUI phase."""
    payload = _complete_live_pass_evidence()
    payload["gui_smoke"].update({"status": "fail", "exit_code": 9})

    with pytest.raises(ValueError, match="gui"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a GUI phase relabeled ``not_run``
# despite Docker argv and a nonzero execution result proving it ran.
def test_validator_rejects_pass_with_touched_not_run_gui_phase() -> None:
    """A not-run GUI phase cannot hide an attempted Docker command."""
    payload = _complete_live_pass_evidence()
    payload["gui_smoke"].update(
        {
            "argv": [
                "docker",
                "exec",
                "ca-mp-task19-a1b2c3d4e5f6-judge-gui-1",
                "python",
                "-m",
                "scripts.quick_smoke",
            ],
            "exit_code": 9,
        }
    )

    with pytest.raises(ValueError, match="not_run"):
        docker_status.validate_evidence(payload)


def test_independent_handwritten_live_pass_with_gui_fixture_validates() -> (
    None
):
    """Keep a valid optional-GUI proof independent of production builders."""
    docker_status.validate_evidence(_complete_live_pass_evidence_with_gui())


def test_validator_accepts_round4_4_gui_api_two_frame_proof() -> None:
    """A GUI pass proves one bound API run and two advancing PNG frames."""
    docker_status.validate_evidence(_complete_live_pass_evidence_with_gui())


def test_validator_rejects_round4_4_gui_pass_without_frame_proof() -> None:
    """A successful GUI API run alone does not prove visible frames."""
    payload = _complete_live_pass_evidence_with_gui()
    del payload["gui_frame_proof"]

    with pytest.raises(ValueError, match="GUI frame proof"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("mutation", "value"),
    [
        ("frames", []),
        ("frames", [{}]),
        ("proof-field", "private"),
        ("frame-field", "private"),
    ],
    ids=["empty-frames", "one-open-frame", "proof-field", "frame-field"],
)
def test_validator_rejects_round4_4_open_or_short_frame_proof(
    mutation: str, value: object
) -> None:
    """The GUI proof is closed and contains at least two full frames."""
    payload = _complete_live_pass_evidence_with_gui()
    proof = payload["gui_frame_proof"]
    if mutation == "frames":
        proof["frames"] = value
    elif mutation == "proof-field":
        proof["private"] = value
    else:
        proof["frames"][0]["private"] = value

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("byte_length", True),
        ("byte_length", 18.0),
        ("byte_length", 0),
        ("byte_length", -1),
        ("sequence", True),
        ("sequence", 1.0),
        ("sequence", -1),
        ("simulation_time", True),
        ("simulation_time", -1.0),
        ("simulation_time", math.nan),
        ("simulation_time", math.inf),
    ],
    ids=[
        "bool-bytes",
        "float-bytes",
        "zero-bytes",
        "negative-bytes",
        "bool-sequence",
        "float-sequence",
        "negative-sequence",
        "bool-time",
        "negative-time",
        "nan-time",
        "infinite-time",
    ],
)
def test_validator_rejects_round4_4_invalid_frame_scalar(
    field: str, value: object
) -> None:
    """Frame size, sequence, and simulation time use bounded real types."""
    payload = _complete_live_pass_evidence_with_gui()
    payload["gui_frame_proof"]["frames"][0][field] = value

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sequence", 1),
        ("sequence", 0),
        ("simulation_time", 1.0),
        ("simulation_time", 0.5),
    ],
    ids=[
        "equal-sequence",
        "decreasing-sequence",
        "equal-time",
        "decreasing-time",
    ],
)
def test_validator_rejects_round4_4_nonincreasing_frames(
    field: str, value: object
) -> None:
    """Listed frames advance in both sequence and simulation time."""
    payload = _complete_live_pass_evidence_with_gui()
    payload["gui_frame_proof"]["frames"][1][field] = value

    with pytest.raises(ValueError, match="increase"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "path",
    [
        "",
        ".",
        "frame",
        "frame.jpg",
        "../frame.png",
        "/frame.png",
        "C:\\frame.png",
        "C:frame.png",
        "\\\\host\\share\\frame.png",
    ],
    ids=[
        "empty",
        "dot",
        "no-extension",
        "non-png",
        "traversal",
        "posix-absolute",
        "drive-absolute",
        "drive-relative",
        "unc",
    ],
)
def test_validator_rejects_round4_4_unsafe_frame_path(path: str) -> None:
    """A frame stays below the exported root and uses a PNG path."""
    payload = _complete_live_pass_evidence_with_gui()
    old_path = payload["gui_frame_proof"]["frames"][0]["path"]
    payload["gui_frame_proof"]["frames"][0]["path"] = path
    exported = payload["exported_evidence"]["contents"]
    next(item for item in exported if item["path"] == old_path)["path"] = path

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-export",
        "missing-export-size",
        "hash-mismatch",
        "size-mismatch",
        "extra-png",
        "reordered-png",
        "duplicate-path",
    ],
)
def test_validator_rejects_round4_4_frame_export_mismatch(
    mutation: str,
) -> None:
    """Every proof frame matches exactly one ordered exported PNG entry."""
    payload = _complete_live_pass_evidence_with_gui()
    frames = payload["gui_frame_proof"]["frames"]
    contents = payload["exported_evidence"]["contents"]
    png_entries = [item for item in contents if item["path"].endswith(".png")]
    if mutation == "missing-export":
        contents.remove(png_entries[0])
    elif mutation == "missing-export-size":
        del png_entries[0]["byte_length"]
    elif mutation == "hash-mismatch":
        png_entries[0]["sha256"] = "0" * 64
    elif mutation == "size-mismatch":
        png_entries[0]["byte_length"] += 1
    elif mutation == "extra-png":
        contents.append(
            {
                "path": "gui/frames/foreign.png",
                "byte_length": 9,
                "sha256": "9" * 64,
            }
        )
    elif mutation == "reordered-png":
        first = contents.index(png_entries[0])
        second = contents.index(png_entries[1])
        contents[first], contents[second] = contents[second], contents[first]
    else:
        frames[1]["path"] = frames[0]["path"]
        png_entries[1]["path"] = png_entries[0]["path"]

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_round4_4_rejects_canonical_aliases_for_one_gui_frame() -> None:
    """One exported GUI artifact cannot appear under two path spellings."""
    payload = _complete_live_pass_evidence_with_gui()
    frames = payload["gui_frame_proof"]["frames"]
    contents = payload["exported_evidence"]["contents"]
    first_path = frames[0]["path"]
    alias = first_path.replace("frames/", "frames/./")
    frames[1]["path"] = alias
    png_entries = [item for item in contents if item["path"].endswith(".png")]
    png_entries[1]["path"] = alias

    with pytest.raises(ValueError, match="canonical"):
        docker_status.validate_evidence(payload)


def test_round4_4_rejects_case_aliases_for_gui_frame_identity() -> None:
    """Windows-portable GUI artifact identity is case-insensitive."""
    payload = _complete_live_pass_evidence_with_gui()
    frames = payload["gui_frame_proof"]["frames"]
    contents = payload["exported_evidence"]["contents"]
    case_alias = frames[0]["path"].replace(
        "frame-000001.png", "FRAME-000001.png"
    )
    frames[1]["path"] = case_alias
    png_entries = [item for item in contents if item["path"].endswith(".png")]
    png_entries[1]["path"] = case_alias

    with pytest.raises(ValueError, match="unique"):
        docker_status.validate_evidence(payload)


def test_round4_4_rejects_duplicate_gui_proof_path() -> None:
    """Frame-proof uniqueness is checked independently of export entries."""
    payload = _complete_live_pass_evidence_with_gui()
    frames = payload["gui_frame_proof"]["frames"]
    frames[1]["path"] = frames[0]["path"]

    with pytest.raises(ValueError, match="paths must be unique"):
        docker_status.validate_evidence(payload)


def test_round4_4_rejects_duplicate_gui_export_path() -> None:
    """Exported PNG uniqueness is separate from frame-proof paths."""
    payload = _complete_live_pass_evidence_with_gui()
    contents = payload["exported_evidence"]["contents"]
    png_entries = [item for item in contents if item["path"].endswith(".png")]
    png_entries[1]["path"] = png_entries[0]["path"]

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_round4_4_accepts_headless_duplicate_exported_content_path() -> None:
    """Legacy headless exports need no uniqueness rule without GUI frames."""
    payload = _complete_live_pass_evidence()
    contents = payload["exported_evidence"]["contents"]
    contents.append(copy.deepcopy(contents[0]))

    docker_status.validate_evidence(payload)


def test_validator_rejects_round4_4_command_only_gui_smoke() -> None:
    """A Docker exec or Xvfb liveness command cannot prove GUI frames."""
    payload = _complete_live_pass_evidence_with_gui()
    payload["gui_smoke"] = {
        "status": "pass",
        "started_at": "2026-08-24T00:00:00Z",
        "finished_at": "2026-08-24T00:00:01Z",
        "argv": [
            "docker",
            "exec",
            "ca-mp-task19-a1b2c3d4e5f6-judge-gui-1",
            "python",
            "-c",
            "print('xvfb alive')",
        ],
        "exit_code": 0,
        "stdout_sha256": "a" * 64,
        "stderr_sha256": "b" * 64,
        "detail": "GUI container command passed",
    }

    with pytest.raises(ValueError, match="GUI.*API"):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_4_frame_proof_without_gui() -> None:
    """A headless-only pass cannot fabricate an unreachable GUI proof."""
    gui = _complete_live_pass_evidence_with_gui()
    payload = _complete_live_pass_evidence()
    payload["gui_frame_proof"] = copy.deepcopy(gui["gui_frame_proof"])
    payload["exported_evidence"]["contents"].extend(
        copy.deepcopy(gui["exported_evidence"]["contents"][-2:])
    )

    with pytest.raises(ValueError, match="GUI frame proof"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_id", "foreign-gui-run"),
        ("container", "foreign-gui-container"),
        ("image", "foreign-gui-image:local"),
    ],
)
def test_validator_rejects_round4_4_frame_proof_identity_mismatch(
    field: str, value: str
) -> None:
    """Frame proof identity matches the GUI API run and invocation."""
    payload = _complete_live_pass_evidence_with_gui()
    payload["gui_frame_proof"][field] = value

    with pytest.raises(ValueError, match="GUI frame proof"):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_4_foreign_gui_api_image() -> None:
    """The GUI API result comes from the invocation's GUI image."""
    payload = _complete_live_pass_evidence_with_gui()
    payload["gui_smoke"]["api_proof"]["image"] = "foreign:local"

    with pytest.raises(ValueError, match="GUI API smoke image"):
        docker_status.validate_evidence(payload)


def test_round4_4_rejects_foreign_gui_api_container_after_cleanup() -> None:
    """Cleanup failure cannot skip deep validation of the GUI API smoke.

    The failed cleanup must not hide an invalid earlier result.
    """
    payload = _truthful_gui_cleanup_command_failure_evidence()
    gui_smoke = payload["gui_smoke"]
    api_proof = gui_smoke["api_proof"]
    api_proof["container"] = "foreign-gui-container"

    with pytest.raises(ValueError, match="GUI API smoke container"):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_4_frame_proof_after_gui_smoke_not_run() -> (
    None
):
    """A completed GUI build without a smoke cannot retain future frames."""
    payload = _complete_gui_compose_pass_evidence()
    payload["gui_smoke"] = copy.deepcopy(
        _complete_headless_compose_pass_evidence()["gui_smoke"]
    )

    with pytest.raises(ValueError, match="GUI frame proof"):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_4_reused_headless_gui_run() -> None:
    """GUI capture uses an API run independent from the headless smoke."""
    payload = _complete_live_pass_evidence_with_gui()
    primary = copy.deepcopy(payload["headless_smoke"]["api_proof"])
    primary["container"] = "ca-mp-task19-a1b2c3d4e5f6-judge-gui-1"
    primary["image"] = "ca-mp-task19-a1b2c3d4e5f6-gui:local"
    payload["gui_smoke"]["api_proof"] = primary
    payload["gui_frame_proof"]["run_id"] = primary["run_id"]

    with pytest.raises(ValueError, match="distinct run IDs"):
        docker_status.validate_evidence(payload)


def test_round4_4_rejects_reused_imported_gui_run() -> None:
    """GUI capture must not reuse the save/load independent API run ID."""
    payload = _complete_live_pass_evidence_with_gui()
    gui_run_id = payload["gui_smoke"]["api_proof"]["run_id"]
    imported = payload["save_load_proof"]["repeated_smoke"]["api_proof"]
    imported["response"]["run_id"] = gui_run_id
    imported["terminal"]["run_id"] = gui_run_id
    imported["terminal"]["path"] = f"/api/runs/{gui_run_id}"
    imported["run_id"] = gui_run_id
    imported["output"]["path"] = f"runs/{gui_run_id}"
    imported["output"]["run_id"] = gui_run_id

    with pytest.raises(ValueError, match="distinct run IDs"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize("value", [True, 18.0, 0, -1])
def test_validator_rejects_round4_4_invalid_exported_frame_size(
    value: object,
) -> None:
    """The exported PNG inventory records an exact positive byte length."""
    payload = _complete_live_pass_evidence_with_gui()
    payload["exported_evidence"]["contents"][-2]["byte_length"] = value

    with pytest.raises(ValueError, match="byte length"):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_4_frame_proof_after_gui_failure() -> None:
    """A GUI failure cannot retain future frame evidence."""
    payload = _truthful_phase_prefix_failure("gui_smoke")
    gui = _complete_live_pass_evidence_with_gui()
    payload["gui_frame_proof"] = copy.deepcopy(gui["gui_frame_proof"])

    with pytest.raises(ValueError, match="GUI frame proof"):
        docker_status.validate_evidence(payload)


def test_round4_4_rejects_frames_after_gui_build_failure() -> None:
    """A failed GUI build cannot retain evidence from a future GUI run."""
    payload = _truthful_phase_prefix_failure("gui_build")
    gui = _complete_live_pass_evidence_with_gui()
    payload["gui_frame_proof"] = copy.deepcopy(gui["gui_frame_proof"])

    with pytest.raises(ValueError, match="GUI frame proof"):
        docker_status.validate_evidence(payload)


def test_round4_4_rejects_gui_request_after_cleanup_failure() -> None:
    """A later cleanup failure cannot bypass the GUI API request contract."""
    payload = _truthful_gui_cleanup_command_failure_evidence()
    gui_smoke = payload["gui_smoke"]
    api_proof = gui_smoke["api_proof"]
    api_proof["request"]["body"]["steps"] = 99

    with pytest.raises(ValueError, match="GUI API smoke API request"):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_4_malformed_gui_api_terminal() -> None:
    """A GUI API proof must retain the exact terminal completion result."""
    payload = _complete_live_pass_evidence_with_gui()
    gui_smoke = payload["gui_smoke"]
    api_proof = gui_smoke["api_proof"]
    api_proof["terminal"]["completed_steps"] = 99

    with pytest.raises(ValueError, match="GUI API smoke API terminal"):
        docker_status.validate_evidence(payload)


def test_validator_rejects_round4_4_frame_proof_in_not_run_document() -> None:
    """Detector-created not-run evidence cannot claim GUI frames."""
    payload = docker_status.new_evidence()
    gui = _complete_live_pass_evidence_with_gui()
    payload["gui_frame_proof"] = copy.deepcopy(gui["gui_frame_proof"])

    with pytest.raises(ValueError, match="GUI frame proof"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting an executed headless workflow after
# ownership evidence drops its canonical network or output volume.
@pytest.mark.parametrize(
    ("kind", "name"),
    [
        ("network", "ca-mp-task19-a1b2c3d4e5f6_default"),
        ("volume", "ca-mp-task19-a1b2c3d4e5f6_judge-output"),
    ],
    ids=["network", "headless-output-volume"],
)
def test_validator_rejects_pass_without_each_headless_owned_resource(
    kind: str, name: str
) -> None:
    """The headless chain owns its network and output volume, not a subset."""
    payload = _complete_live_pass_evidence()
    records = payload["owned_resources"]["before_cleanup"]
    records[:] = [
        record
        for record in records
        if not (record["kind"] == kind and record["name"] == name)
    ]

    with pytest.raises(ValueError, match="owned"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting rendered GUI facts whose image is
# foreign to the invocation-derived GUI image.
def test_validator_rejects_gui_pass_with_foreign_build_image() -> None:
    """A GUI render must select the canonical GUI image."""
    payload = _complete_live_pass_evidence_with_gui()
    services = payload["static_contract"]["render_proof"]["selected_facts"][
        "services"
    ]
    services[1]["image"] = "foreign-gui-image:local"

    with pytest.raises(ValueError, match="render selected service image"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a GUI API result that targets a
# foreign container instead of the invocation-derived GUI container.
def test_validator_rejects_gui_pass_with_foreign_smoke_container() -> None:
    """A GUI API smoke must target the canonical GUI container."""
    payload = _complete_live_pass_evidence_with_gui()
    payload["gui_smoke"]["api_proof"]["container"] = "foreign-gui-container"

    with pytest.raises(ValueError, match="GUI API smoke container"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting an executed GUI chain after the GUI
# image, container, or output volume disappears from ownership evidence.
@pytest.mark.parametrize(
    ("kind", "name"),
    [
        ("container", "ca-mp-task19-a1b2c3d4e5f6-judge-gui-1"),
        ("volume", "ca-mp-task19-a1b2c3d4e5f6_judge-gui-output"),
        ("image", "ca-mp-task19-a1b2c3d4e5f6-gui:local"),
    ],
    ids=["container", "volume", "image"],
)
def test_validator_rejects_gui_pass_without_each_gui_owned_resource(
    kind: str, name: str
) -> None:
    """An executed GUI chain has complete labeled GUI ownership evidence."""
    payload = _complete_live_pass_evidence_with_gui()
    records = payload["owned_resources"]["before_cleanup"]
    records[:] = [
        record
        for record in records
        if not (record["kind"] == kind and record["name"] == name)
    ]

    with pytest.raises(ValueError, match="owned"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting rendered GUI facts with a foreign
# ownership label instead of the current invocation label.
def test_validator_rejects_gui_pass_with_mismatched_build_label() -> None:
    """A GUI render must carry the current invocation ownership label."""
    payload = _complete_live_pass_evidence_with_gui()
    services = payload["static_contract"]["render_proof"]["selected_facts"][
        "services"
    ]
    services[1]["labels"][
        "io.challengecup.task19.invocation"
    ] = "foreign-invocation"

    with pytest.raises(ValueError, match="render selected ownership label"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("org.example.release-axis", "gui"),
        ("io.challengecup.task19.other", "a1b2c3d4e5f6"),
    ],
    ids=["foreign-label", "foreign-ownership-key"],
)
def test_validator_rejects_conflicting_gui_ownership_label_by_key(
    key: str, value: str
) -> None:
    """Rendered GUI labels contain only the invocation ownership label."""
    payload = _complete_live_pass_evidence_with_gui()
    services = payload["static_contract"]["render_proof"]["selected_facts"][
        "services"
    ]
    services[1]["labels"][key] = value

    with pytest.raises(ValueError, match="render selected ownership label"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting collision preflight that omits the
# imported container used by independent save/load verification.
def test_validator_rejects_pass_without_expected_imported_container() -> None:
    """Require the canonical imported container in collision preflight."""
    payload = _complete_live_pass_evidence()
    replacement = "ca-mp-task19-a1b2c3d4e5f6-replacement-1"
    payload["name_collisions"]["expected_resources"]["containers"][
        2
    ] = replacement
    payload["owned_resources"]["before_cleanup"][1]["name"] = replacement

    with pytest.raises(ValueError, match="containers"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting cleanup ownership proof that omits the
# imported container used by the repeated health and smoke commands.
def test_validator_rejects_pass_without_owned_imported_container() -> None:
    """Require ownership evidence for each proof-used imported container."""
    payload = _complete_live_pass_evidence()
    records = payload["owned_resources"]["before_cleanup"]
    records[:] = [
        record
        for record in records
        if record["name"] != "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1"
    ]

    with pytest.raises(ValueError, match="owned"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a nonempty resource name merely because
# it happens to contain the invocation ID.
def test_validator_rejects_pass_with_extra_noncanonical_resource_name() -> (
    None
):
    """Require exact canonical collision resource sets, not ID substrings."""
    payload = _complete_live_pass_evidence()
    payload["name_collisions"]["expected_resources"]["containers"].append(
        "ca-mp-task19-a1b2c3d4e5f6-other-1"
    )

    with pytest.raises(ValueError, match="containers"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting an imported-container create command
# whose ownership label does not name the current invocation.
def test_validator_rejects_pass_with_mismatched_imported_container_label() -> (
    None
):
    """Bind independent container creation to the current ownership label."""
    payload = _complete_live_pass_evidence()
    payload["save_load_proof"]["imported_container_create"]["argv"][
        6
    ] = "io.challengecup.task19.invocation=another"

    with pytest.raises(ValueError, match="label"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a real live failure after erasing the
# successful Docker CLI capability command that establishes its provenance.
def test_validator_rejects_fail_without_successful_cli_query() -> None:
    """A real failure must retain the successful Docker version query."""
    payload = _real_live_fail_evidence()
    payload["cli"]["argv"] = []

    with pytest.raises(ValueError, match="cli"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a real live failure after erasing the
# successful Docker daemon-info command that establishes live capability.
def test_validator_rejects_fail_without_successful_daemon_query() -> None:
    """A real failure must retain the successful Docker daemon-info query."""
    payload = _real_live_fail_evidence()
    payload["daemon"]["argv"] = []

    with pytest.raises(ValueError, match="daemon"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a failed phase that has no Docker argv
# to tie its nonzero exit to the claimed phase behavior.
def test_validator_rejects_fail_without_failed_phase_docker_command() -> None:
    """A real failed phase requires its phase-appropriate Docker command."""
    payload = _real_live_fail_evidence()
    payload["headless_health"]["argv"] = []

    with pytest.raises(ValueError, match="headless_health"):
        docker_status.validate_evidence(payload)


# Production mutation caught: classifying a host as daemon-unavailable without
# recording both the successful CLI query and attempted daemon-info command.
def test_validator_rejects_daemon_unavailable_without_capability_queries() -> (
    None
):
    """Require a version pass and an attempted daemon-info query."""
    payload = docker_status.new_evidence()
    payload["reason"] = "docker_daemon_unavailable"
    payload["cli"].update({"status": "pass", "exit_code": 0})

    with pytest.raises(ValueError, match="cli"):
        docker_status.validate_evidence(payload)


# Production mutation caught: allowing a missing-CLI classification to retain
# a successful `docker --version` execution record.
def test_validator_rejects_cli_unavailable_with_successful_version_command(
) -> None:
    """Executable-not-found evidence cannot contain a successful CLI query."""
    payload = docker_status.new_evidence()
    payload["cli"].update({"argv": ["docker", "--version"], "exit_code": 0})

    with pytest.raises(ValueError, match="cli"):
        docker_status.validate_evidence(payload)


# Production mutation caught: permitting a not-run phase to carry a zero-exit
# Docker command, which asserts an execution the status denies.
def test_validator_rejects_not_run_phase_with_successful_command_metadata(
) -> None:
    """A `not_run` record cannot claim a successful Docker execution."""
    payload = docker_status.new_evidence()
    payload["headless_smoke"].update(
        {
            "argv": ["docker", "exec", "unverified", "quick-smoke"],
            "exit_code": 0,
        }
    )

    with pytest.raises(ValueError, match="not_run"):
        docker_status.validate_evidence(payload)


# Production mutation caught: treating live verification as not-run even when
# its phase records retain an attempted Docker command.
def test_validator_rejects_live_not_run_with_a_touched_phase() -> None:
    """Live-not-run evidence leaves every live phase untouched."""
    payload = _complete_live_pass_evidence()
    empty_stream_digest = hashlib.sha256(b"").hexdigest()
    payload["status"] = "not_run"
    payload["reason"] = "live_verification_not_run"
    for phase in (
        "static_contract",
        "headless_build",
        "headless_health",
        "headless_smoke",
        "save_load",
        "gui_build",
        "gui_smoke",
        "cleanup",
    ):
        payload[phase].update(
            {
                "status": "not_run",
                "argv": [],
                "exit_code": None,
                "stdout_sha256": empty_stream_digest,
                "stderr_sha256": empty_stream_digest,
            }
        )
        payload[phase].pop("execution", None)
        payload[phase].pop("api_proof", None)
    payload["headless_smoke"]["argv"] = [
        "docker",
        "exec",
        "unverified",
        "quick-smoke",
    ]

    with pytest.raises(ValueError, match="not_run"):
        docker_status.validate_evidence(payload)


# Production mutation caught: declaring live verification not-run while
# suppressing the successful CLI and daemon-info commands that justify it.
def test_validator_rejects_live_not_run_without_successful_capability_queries(
) -> None:
    """Live-not-run evidence requires recorded successful capability probes."""
    payload = docker_status.new_evidence()
    payload["reason"] = "live_verification_not_run"
    payload["cli"].update({"status": "pass", "exit_code": 0})
    payload["daemon"].update({"status": "pass", "exit_code": 0})

    with pytest.raises(ValueError, match="cli"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a legitimate overall live failure
# while a nonfailed headless or optional GUI phase is relabeled ``not_run``
# despite recording an attempted Docker command and nonzero exit.
@pytest.mark.parametrize(
    ("phase", "argv"),
    [
        (
            "cleanup",
            [
                "docker",
                "container",
                "rm",
                "ca-mp-task19-a1b2c3d4e5f6-judge-1",
            ],
        ),
        (
            "gui_smoke",
            [
                "docker",
                "exec",
                "ca-mp-task19-a1b2c3d4e5f6-judge-gui-1",
                "python",
                "-m",
                "scripts.quick_smoke",
            ],
        ),
    ],
    ids=["headless-cleanup", "optional-gui-smoke"],
)
def test_validator_rejects_fail_with_touched_not_run_phase(
    phase: str, argv: list[str]
) -> None:
    """Every not-run live phase stays untouched even in an overall failure."""
    payload = _real_live_fail_evidence()
    payload[phase].update(
        {
            "status": "not_run",
            "execution": "command",
            "argv": argv,
            "exit_code": 9,
        }
    )
    payload[phase].pop("failure_proof", None)

    with pytest.raises(ValueError, match="not_run"):
        docker_status.validate_evidence(payload)


# Production mutation caught: serializing raw command streams instead of only
# their hashes and bounded sanitized detail.
@pytest.mark.parametrize("raw_field", ["stdout", "stderr", "raw_stdout"])
def test_validator_rejects_raw_output_fields_in_command_records(
    raw_field: str,
) -> None:
    """Command records expose hashes, never raw output fields."""
    payload = _complete_live_pass_evidence()
    payload["headless_smoke"][raw_field] = "private raw command output"

    with pytest.raises(ValueError, match="unexpected"):
        docker_status.validate_evidence(payload)


# Production mutation caught: publishing a secret-bearing URL query in an
# otherwise allowed bounded diagnostic string.
@pytest.mark.parametrize("query_key", ["token", "secret", "password", "auth"])
def test_validator_rejects_secret_url_query_values(query_key: str) -> None:
    """URL diagnostics may be public, but their query secrets are forbidden."""
    payload = _complete_live_pass_evidence()
    payload["headless_smoke"][
        "detail"
    ] = f"https://judge.example.invalid/health?{query_key}=private-value"

    with pytest.raises(ValueError, match="secret"):
        docker_status.validate_evidence(payload)


# Production mutation caught: allowing underscore, hyphen, or case aliases for
# sensitive user and authorization keys to evade recursive privacy rejection.
@pytest.mark.parametrize("sensitive_alias", ["user_name", "AUTHORIZATION"])
def test_validator_rejects_normalized_sensitive_key_aliases(
    sensitive_alias: str,
) -> None:
    """Sensitive label keys are rejected after separator/case normalization."""
    payload = _complete_live_pass_evidence()
    payload["owned_resources"]["before_cleanup"][0]["labels"][
        sensitive_alias
    ] = "private-value"

    with pytest.raises(ValueError, match="private"):
        docker_status.validate_evidence(payload)


# Production mutation caught: silently accepting a field outside an individual
# proof object's published schema.
@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update({"unexpected": "safe"}),
        lambda payload: payload["platform"].update({"unexpected": "safe"}),
        lambda payload: payload["quick_smoke"].update({"unexpected": "safe"}),
        lambda payload: payload["quick_smoke"]["output"].update(
            {"unexpected": "safe"}
        ),
        lambda payload: payload["save_load_proof"].update(
            {"unexpected": "safe"}
        ),
        lambda payload: payload["invocation"].update({"unexpected": "safe"}),
        lambda payload: payload["invocation"]["ownership_label"].update(
            {"unexpected": "safe"}
        ),
        lambda payload: payload["name_collisions"].update(
            {"unexpected": "safe"}
        ),
        lambda payload: (
            payload["name_collisions"]["expected_resources"].update(
                {"unexpected": "safe"}
            )
        ),
        lambda payload: payload["owned_resources"].update(
            {"unexpected": "safe"}
        ),
        lambda payload: payload["owned_resources"]["before_cleanup"][0].update(
            {"unexpected": "safe"}
        ),
        lambda payload: payload["exported_evidence"].update(
            {"unexpected": "safe"}
        ),
        lambda payload: payload["exported_evidence"]["contents"][0].update(
            {"unexpected": "safe"}
        ),
    ],
    ids=[
        "top-level",
        "platform",
        "quick-smoke",
        "quick-smoke-output",
        "save-load-proof",
        "invocation",
        "ownership-label",
        "collision",
        "collision-expected-resources",
        "owned-resources",
        "owned-resource-entry",
        "exported-evidence",
        "exported-content-entry",
    ],
)
def test_validator_rejects_unknown_fields_in_each_proof_object(
    mutation: object,
) -> None:
    """Every structured proof object accepts only its documented fields."""
    payload = _complete_live_pass_evidence()
    mutation(payload)

    with pytest.raises(ValueError, match="unexpected"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(
            {"reason": "live_verification_not_run"}
        ),
        lambda payload: payload["platform"].update(
            {"os": "windows", "architecture": "arm64"}
        ),
        lambda payload: payload.pop("invocation"),
        lambda payload: payload["invocation"].update(
            {"imported_image": payload["invocation"]["headless_image"]}
        ),
        lambda payload: payload["quick_smoke"].update({"requested_steps": 99}),
        lambda payload: payload["quick_smoke"]["output"].update(
            {"root": "output", "path": "docker-status.json"}
        ),
        lambda payload: payload["save_load_proof"]["repeated_smoke"].update(
            {"status": "not_run"}
        ),
        lambda payload: payload["name_collisions"].update(
            {"expected_resources": {"containers": []}}
        ),
        lambda payload: payload["owned_resources"]["before_cleanup"][0][
            "labels"
        ].update({"io.challengecup.task19.invocation": "different"}),
        lambda payload: payload["exported_evidence"].update({"contents": []}),
        lambda payload: payload["headless_build"].update(
            {"argv": ["docker", "info"]}
        ),
        lambda payload: payload["headless_health"].update({"argv": []}),
    ],
    ids=[
        "pass-reason-mismatch",
        "wrong-platform",
        "missing-invocation-object",
        "non-independent-imported-tag",
        "wrong-quick-smoke-step-count",
        "non-app-output-quick-smoke",
        "missing-repeated-load-smoke",
        "incomplete-collision-expected-names",
        "wrong-ownership-label",
        "missing-export-content-proof",
        "build-record-is-not-build-command",
        "health-record-missing-command",
    ],
)
def test_validator_rejects_each_missing_or_corrupt_live_pass_proof(
    mutation: object,
) -> None:
    """Catch a false pass with a mandatory verifier-facing proof lost."""
    payload = _complete_live_pass_evidence()
    mutation(payload)

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_accepts_real_failure_and_rejects_contradictions() -> None:
    """Distinguish an executed project failure from capability ``not_run``."""
    failure = _real_live_fail_evidence()
    docker_status.validate_evidence(failure)

    wrong_reason = copy.deepcopy(failure)
    wrong_reason["reason"] = "headless_build_failed"
    with pytest.raises(ValueError, match="reason"):
        docker_status.validate_evidence(wrong_reason)

    missing_failure = copy.deepcopy(failure)
    missing_failure["headless_health"].update(
        {"status": "pass", "exit_code": 0}
    )
    with pytest.raises(ValueError, match="fail"):
        docker_status.validate_evidence(missing_failure)


# Production mutation caught: rejecting a real save/load workflow failure just
# because it occurred after the initial successful-summary image-save command.
@pytest.mark.parametrize(
    "argv",
    [
        [
            "docker",
            "image",
            "load",
            "--input",
            "output/evidence/docker/live/a1b2c3d4e5f6/headless-image.tar",
        ],
        [
            "docker",
            "image",
            "tag",
            "ca-mp-task19-a1b2c3d4e5f6-headless:local",
            "ca-mp-task19-a1b2c3d4e5f6-imported:local",
        ],
        [
            "docker",
            "container",
            "create",
            "--name",
            "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1",
            "--label",
            "io.challengecup.task19.invocation=a1b2c3d4e5f6",
            "ca-mp-task19-a1b2c3d4e5f6-imported:local",
        ],
        [
            "docker",
            "container",
            "start",
            "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1",
        ],
        [
            "docker",
            "inspect",
            "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1",
        ],
        [
            "docker",
            "exec",
            "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1",
            "python",
            "-m",
            "scripts.quick_smoke",
        ],
    ],
    ids=[
        "image-load",
        "image-retag",
        "imported-container-create",
        "imported-container-start",
        "repeated-health",
        "repeated-smoke",
    ],
)
def test_validator_accepts_each_canonical_save_load_stage_failure(
    argv: list[str],
) -> None:
    """A real failed save/load stage keeps its own canonical Docker argv."""
    docker_status.validate_evidence(_save_load_stage_failure_evidence(argv))


# Production mutation caught: treating an unrelated Docker action as though it
# were a failed stage in the declared save/load workflow.
def test_validator_rejects_unrelated_save_load_failure_command() -> None:
    """The save/load failure allowlist excludes unrelated Docker actions."""
    payload = _save_load_stage_failure_evidence(["docker", "system", "prune"])

    with pytest.raises(ValueError, match="save_load"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a save/load image-load failure whose
# tar identity belongs to a foreign invocation rather than the current one.
def test_validator_rejects_save_load_failure_with_foreign_identity() -> None:
    """A save/load failure remains bound to the current invocation tar path."""
    payload = _save_load_stage_failure_evidence(
        [
            "docker",
            "image",
            "load",
            "--input",
            "output/evidence/docker/live/foreign/headless-image.tar",
        ]
    )

    with pytest.raises(ValueError, match="save_load"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "reason", ["docker_daemon_unavailable", "live_verification_not_run"]
)
def test_validator_rejects_not_run_reason_and_capability_contradictions(
    reason: str,
) -> None:
    """Keep the three unavailable classifications mutually exclusive."""
    payload = docker_status.new_evidence()
    payload["reason"] = reason

    with pytest.raises(ValueError, match="classification"):
        docker_status.validate_evidence(payload)


def test_detector_marks_missing_cli_not_run_without_subprocess(
    tmp_path: Path,
) -> None:
    """Catch capability probing that invokes a missing Docker executable."""
    commands: list[list[str]] = []

    def runner(
        argv: list[str], _cwd: Path
    ) -> subprocess.CompletedProcess[str]:
        commands.append(argv)
        raise AssertionError("missing Docker CLI must not run a subprocess")

    payload = docker_status.detect(
        tmp_path,
        which=lambda _name: None,
        command_runner=runner,
        expected_root=tmp_path,
    )

    assert commands == []
    assert payload["status"] == "not_run"
    assert payload["reason"] == "docker_cli_unavailable"
    assert payload["cli"]["status"] == "not_run"
    docker_status.validate_evidence(payload)


def test_detector_marks_unreachable_daemon_not_run(tmp_path: Path) -> None:
    """Catch a daemon failure being reported as a project failure."""

    def runner(
        argv: list[str], _cwd: Path
    ) -> subprocess.CompletedProcess[str]:
        if argv == ["docker", "--version"]:
            return _completed(
                argv, stdout="Docker version 27.0.0, build deadbeef\n"
            )
        assert argv == [
            "docker",
            "info",
            "--format",
            "{{json .ServerVersion}}",
        ]
        return _completed(argv, returncode=1, stderr="daemon unavailable")

    payload = docker_status.detect(
        tmp_path,
        which=lambda _name: "docker.exe",
        command_runner=runner,
        expected_root=tmp_path,
    )

    assert payload["status"] == "not_run"
    assert payload["reason"] == "docker_daemon_unavailable"
    assert payload["cli"]["status"] == "pass"
    assert payload["daemon"]["status"] == "not_run"
    docker_status.validate_evidence(payload)


def test_detector_does_not_promote_capability_to_live_pass(
    tmp_path: Path,
) -> None:
    """Catch capability alone being represented as live proof."""

    def runner(
        argv: list[str], _cwd: Path
    ) -> subprocess.CompletedProcess[str]:
        if argv == ["docker", "--version"]:
            return _completed(
                argv, stdout="Docker version 27.0.0, build deadbeef\n"
            )
        assert argv == [
            "docker",
            "info",
            "--format",
            "{{json .ServerVersion}}",
        ]
        return _completed(argv, stdout='"27.0.0"\n')

    payload = docker_status.detect(
        tmp_path,
        which=lambda _name: "docker.exe",
        command_runner=runner,
        expected_root=tmp_path,
    )

    assert payload["status"] == "not_run"
    assert payload["reason"] == "live_verification_not_run"
    assert payload["cli"]["status"] == "pass"
    assert payload["daemon"]["status"] == "pass"
    assert all(
        payload[phase]["status"] == "not_run" for phase in docker_status.PHASES
    )
    docker_status.validate_evidence(payload)


def test_detector_records_bounded_sanitized_read_only_command_metadata(
    tmp_path: Path,
) -> None:
    """Catch unsafe metadata or a mutable Docker operation in detection."""
    commands: list[list[str]] = []

    def runner(
        argv: list[str], _cwd: Path
    ) -> subprocess.CompletedProcess[str]:
        commands.append(argv)
        if argv == ["docker", "--version"]:
            return _completed(
                argv, stdout="Docker version 27.0.0, build deadbeef\n"
            )
        return _completed(argv, stdout='"27.0.0"\n')

    payload = docker_status.detect(
        tmp_path,
        which=lambda _name: "docker.exe",
        command_runner=runner,
        expected_root=tmp_path,
    )

    assert commands == [
        ["docker", "--version"],
        ["docker", "info", "--format", "{{json .ServerVersion}}"],
    ]
    for name in ("cli", "daemon", *docker_status.PHASES):
        record = payload[name]
        assert record["started_at"]
        assert record["finished_at"]
        assert isinstance(record["argv"], list)
        assert (
            record["stdout_sha256"]
            == hashlib.sha256(
                (
                    "Docker version 27.0.0, build deadbeef\n"
                    if name == "cli"
                    else '"27.0.0"\n' if name == "daemon" else ""
                ).encode("utf-8")
            ).hexdigest()
        )
        assert record["stderr_sha256"] == hashlib.sha256(b"").hexdigest()
        assert len(record["detail"]) <= docker_status.MAX_DETAIL_LENGTH
        assert "D:\\" not in " ".join(record["argv"])
    docker_status.validate_evidence(payload)


@pytest.mark.parametrize("invalid_status", [True, "pending"])
def test_validator_rejects_boolean_and_unknown_phase_statuses(
    invalid_status: object,
) -> None:
    """Catch status fields accepting booleans or unknown vocabulary values."""
    payload = _complete_live_pass_evidence()
    payload["headless_build"]["status"] = invalid_status

    with pytest.raises(ValueError, match="status"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("mutation", "expected_fragment"),
    [
        (
            lambda payload: payload["headless_health"].update(
                {"status": "not_run"}
            ),
            "headless",
        ),
        (lambda payload: payload.pop("invocation_id"), "invocation"),
        (
            lambda payload: payload["name_collisions"].update(
                {"before": ["taken"]}
            ),
            "collision",
        ),
        (lambda payload: payload.pop("exported_evidence"), "export"),
        (
            lambda payload: payload["owned_resources"].update(
                {"after_cleanup": ["owned"]}
            ),
            "inventory",
        ),
    ],
    ids=[
        "missing-headless-phase",
        "missing-invocation",
        "collision-before",
        "missing-export",
        "nonempty-final-inventory",
    ],
)
def test_validator_rejects_a_pass_without_required_live_evidence(
    mutation: object,
    expected_fragment: str,
) -> None:
    """Catch a claimed pass that lacks a mandatory live-verification proof."""
    payload = _complete_live_pass_evidence()
    mutation(payload)

    with pytest.raises(ValueError, match=expected_fragment):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("mutation", "expected_fragment"),
    [
        (
            lambda payload: payload["exported_evidence"].update(
                {"status": "not_run"}
            ),
            "export",
        ),
        (
            lambda payload: payload["exported_evidence"].update(
                {"path": "../outside"}
            ),
            "relative",
        ),
        (
            lambda payload: payload["headless_smoke"].update(
                {
                    "started_at": "2026-08-24T00:00:02Z",
                    "finished_at": "2026-08-24T00:00:01Z",
                }
            ),
            "before",
        ),
    ],
    ids=["unconfirmed-export", "traversal-export", "reversed-phase-time"],
)
def test_validator_rejects_unconfirmed_export_or_invalid_time_order(
    mutation: object,
    expected_fragment: str,
) -> None:
    """Catch an unconfirmed export, traversal path, or reversed phase time."""
    payload = _complete_live_pass_evidence()
    mutation(payload)

    with pytest.raises(ValueError, match=expected_fragment):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update({"duration": math.nan}),
        lambda payload: payload["headless_smoke"].update(
            {"detail": r"failed under D:\\Users\\judge\\private"}
        ),
        lambda payload: payload.update({"environment": {"USER": "judge"}}),
    ],
    ids=["nan", "absolute-personal-path", "environment-dump"],
)
def test_validator_rejects_nonfinite_or_private_evidence_values(
    mutation: object,
) -> None:
    """Catch NaN, personal paths, or environment contents in evidence."""
    payload = _complete_live_pass_evidence()
    mutation(payload)

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["headless_smoke"].update(
            {"detail": "/workspace/challenge-cup/private"}
        ),
        lambda payload: payload["headless_health"].update(
            {
                "argv": payload["headless_health"]["argv"]
                + [r"\\server\judge-share\private"]
            }
        ),
        lambda payload: payload["daemon"].update(
            {"version": r"\\?\Volume{evidence}\private"}
        ),
        lambda payload: payload.update(
            {"verifier_metadata": {"host_location": "/root/.docker"}}
        ),
        lambda payload: payload.update(
            {
                "verifier_metadata": {
                    "snapshot": '{"HOME":"/root","USER":"judge"}'
                }
            }
        ),
    ],
    ids=[
        "posix-workspace-detail",
        "unc-argv",
        "extended-windows-version",
        "nested-posix-root",
        "nested-json-environment-dump",
    ],
)
def test_validator_rejects_private_host_values_everywhere(
    mutation: object,
) -> None:
    """Apply privacy rules recursively to all evidence fields."""
    payload = _complete_live_pass_evidence()
    mutation(payload)

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


def test_validator_allows_urls_and_relative_json_templates() -> None:
    """Do not mistake public URLs or relative JSON for host data."""
    payload = _complete_live_pass_evidence()
    payload["headless_smoke"][
        "detail"
    ] = "https://judge.example.invalid/api/health"
    payload["save_load"]["detail"] = '{"output":"app/output/runs/quick-smoke"}'

    docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["headless_smoke"].pop("finished_at"),
        lambda payload: payload["headless_smoke"].update({"exit_code": True}),
        lambda payload: payload["headless_smoke"].update(
            {"stdout_sha256": "not-a-hash"}
        ),
        lambda payload: payload["headless_smoke"].update(
            {"argv": ["docker", r"D:\\Users\\judge\\private"]}
        ),
        lambda payload: payload["headless_smoke"].update(
            {"detail": "x" * (docker_status.MAX_DETAIL_LENGTH + 1)}
        ),
    ],
    ids=[
        "missing-timestamp",
        "boolean-exit",
        "invalid-hash",
        "unsafe-argv",
        "long-detail",
    ],
)
def test_validator_rejects_incomplete_or_unsafe_phase_metadata(
    mutation: object,
) -> None:
    """Catch phase records missing metadata or exposing unsafe text."""
    payload = _complete_live_pass_evidence()
    mutation(payload)

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    "target_kind", ["archive", "official", "descendant", "traversal"]
)
def test_output_resolution_rejects_all_protected_input_targets(
    target_kind: str,
    tmp_path: Path,
) -> None:
    """Catch output resolving onto the archive or official scene data."""
    repo_root = tmp_path / "repo"
    archive = repo_root / "赛题资料.7z"
    official_root = repo_root / "data" / "intersection_data"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"protected archive")
    official_root.mkdir(parents=True)
    (official_root / "official.net.xml").write_text(
        "protected", encoding="utf-8"
    )
    targets = {
        "archive": archive,
        "official": official_root,
        "descendant": official_root / "status.json",
        "traversal": Path("output")
        / ".."
        / "data"
        / "intersection_data"
        / "status.json",
    }

    with pytest.raises(ValueError, match="protected"):
        docker_status.resolve_protected_output_path(
            repo_root, targets[target_kind], expected_root=repo_root
        )


@pytest.mark.parametrize("root_kind", ["nested", "sibling", "missing"])
def test_output_resolution_rejects_noncanonical_project_roots(
    root_kind: str,
    tmp_path: Path,
) -> None:
    """Reject a nested, sibling, or nonexistent root before path use."""
    expected_root = Path(docker_status.__file__).resolve().parents[2]
    if root_kind == "nested":
        supplied_root = expected_root / "scripts"
    elif root_kind == "sibling":
        supplied_root = tmp_path / "sibling"
        supplied_root.mkdir()
    else:
        supplied_root = tmp_path / "does-not-exist"

    with pytest.raises(ValueError, match="root"):
        docker_status.resolve_protected_output_path(
            supplied_root, Path("output/evidence/docker/status.json")
        )


def test_output_resolution_allows_an_explicit_test_root_injection(
    tmp_path: Path,
) -> None:
    """Keep isolated unit tests possible without trusting production roots."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    target = docker_status.resolve_protected_output_path(
        repo_root,
        Path("output/evidence/docker/status.json"),
        expected_root=repo_root,
    )

    assert (
        target == (repo_root / "output/evidence/docker/status.json").resolve()
    )


def test_default_root_is_the_real_script_checkout_without_writing(
    tmp_path: Path,
) -> None:
    """The production default binds to this script's checkout, not CWD."""
    expected_root = Path(docker_status.__file__).resolve().parents[2]
    requested = tmp_path / "external" / "docker-status.json"

    target = docker_status.resolve_protected_output_path(
        expected_root, requested
    )

    assert docker_status.expected_project_root() == expected_root
    assert target == requested.resolve()
    assert not requested.parent.exists()


@pytest.mark.parametrize(
    "target_kind", ["archive", "official", "descendant", "traversal"]
)
def test_wrong_root_rejects_protected_target_before_its_own_path_rules(
    target_kind: str,
    tmp_path: Path,
) -> None:
    """A supplied non-checkout root cannot redirect archive/data protection."""
    repo_root = tmp_path / "repo"
    archive = repo_root / "赛题资料.7z"
    official_root = repo_root / "data" / "intersection_data"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"protected archive")
    official_root.mkdir(parents=True)
    wrong_root = tmp_path / "wrong-root"
    wrong_root.mkdir()
    targets = {
        "archive": archive,
        "official": official_root,
        "descendant": official_root / "status.json",
        "traversal": (
            repo_root / "output/../data/intersection_data/status.json"
        ),
    }

    with pytest.raises(ValueError, match="root"):
        docker_status.resolve_protected_output_path(
            wrong_root, targets[target_kind], expected_root=repo_root
        )


def test_output_resolution_rejects_a_symlink_or_junction_project_root(
    tmp_path: Path,
) -> None:
    """Fail closed when the supplied root itself is a reparse point."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    linked_root = tmp_path / "linked-repo"
    if os.name == "nt":
        linked = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(linked_root),
                str(repo_root),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if linked.returncode != 0:
            pytest.skip(
                f"directory junction unavailable: {linked.stderr.strip()}"
            )
    else:
        linked_root.symlink_to(repo_root, target_is_directory=True)

    with pytest.raises(ValueError, match="root"):
        docker_status.resolve_protected_output_path(
            linked_root,
            Path("output/evidence/docker/status.json"),
            expected_root=repo_root,
        )


def test_cli_rejects_wrong_root_before_detector_or_writer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Do not probe Docker or create output under an untrusted project root."""
    wrong_root = tmp_path / "wrong-root"
    wrong_root.mkdir()
    output = wrong_root / "new" / "status.json"
    invoked: list[str] = []

    def unexpected_detect(
        *_args: object, **_kwargs: object
    ) -> dict[str, object]:
        invoked.append("detect")
        raise AssertionError("wrong root must reject before Docker detection")

    def unexpected_writer(*_args: object, **_kwargs: object) -> None:
        invoked.append("writer")
        raise AssertionError("wrong root must reject before evidence writing")

    monkeypatch.setattr(docker_status, "detect", unexpected_detect)
    monkeypatch.setattr(docker_status, "write_evidence", unexpected_writer)

    code = docker_status.main(
        ["--repo-root", str(wrong_root), "--output", str(output)]
    )

    assert code == 2
    assert invoked == []
    assert not output.parent.exists()
    assert "rejected" in capsys.readouterr().err.lower()


def test_output_resolution_rejects_a_reparse_into_official_data(
    tmp_path: Path,
) -> None:
    """Catch a reparse point hiding an official-data output target."""
    repo_root = tmp_path / "repo"
    official_root = repo_root / "data" / "intersection_data"
    official_root.mkdir(parents=True)
    (official_root / "official.net.xml").write_text(
        "protected", encoding="utf-8"
    )
    linked_root = repo_root / "linked-official-data"
    if os.name == "nt":
        linked = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(linked_root),
                str(official_root),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if linked.returncode != 0:
            pytest.skip(
                f"directory junction unavailable: {linked.stderr.strip()}"
            )
    else:
        linked_root.symlink_to(official_root, target_is_directory=True)

    with pytest.raises(ValueError, match="protected"):
        docker_status.resolve_protected_output_path(
            repo_root,
            linked_root / "docker-status.json",
            expected_root=repo_root,
        )


@pytest.mark.parametrize("absolute", [False, True])
def test_legal_output_paths_resolve_without_creating_directories(
    absolute: bool,
    tmp_path: Path,
) -> None:
    """Catch protection rejecting safe output or creating it early."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    requested = (
        tmp_path / "external-evidence" / "docker-status.json"
        if absolute
        else Path("output") / "evidence" / "docker" / "docker-status.json"
    )

    target = docker_status.resolve_protected_output_path(
        repo_root, requested, expected_root=repo_root
    )

    expected = (
        requested.resolve() if absolute else (repo_root / requested).resolve()
    )
    assert target == expected
    assert not target.parent.exists()


def test_output_resolution_fails_closed_when_canonicalization_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catch resolution exceptions being treated as safe output paths."""

    def fail_resolution(*_args: object, **_kwargs: object) -> Path:
        raise OSError("resolution unavailable")

    monkeypatch.setattr(docker_status.Path, "resolve", fail_resolution)

    with pytest.raises(ValueError, match="resolved safely"):
        docker_status.resolve_protected_output_path(
            tmp_path, Path("status.json"), expected_root=tmp_path
        )


def test_writer_uses_a_sibling_temporary_file_and_atomic_replacement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catch a writer publishing partial JSON or a non-sibling temp file."""
    target = tmp_path / "nested" / "docker-status.json"
    calls: list[tuple[Path, Path]] = []
    original_replace = os.replace

    def recording_replace(source: Path, destination: Path) -> None:
        calls.append((Path(source), Path(destination)))
        original_replace(source, destination)

    monkeypatch.setattr(docker_status.os, "replace", recording_replace)
    docker_status.write_evidence(target, docker_status.new_evidence())

    assert calls and calls == [(calls[0][0], target)]
    assert calls[0][0].parent == target.parent
    assert calls[0][0].name.startswith(".docker-status.json.")
    assert calls[0][0].name.endswith(".tmp")
    evidence = json.loads(target.read_text(encoding="utf-8"))
    assert evidence["schema"] == docker_status.SCHEMA
    assert not list(target.parent.glob(".docker-status.json.*.tmp"))


def test_writer_preserves_previous_document_when_replace_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catch failed replacement overwriting the last complete document."""
    target = tmp_path / "docker-status.json"
    target.write_text('{"previous": true}\n', encoding="utf-8")
    before = target.read_bytes()

    def fail_replace(*_args: object, **_kwargs: object) -> None:
        raise OSError("busy")

    monkeypatch.setattr(docker_status.os, "replace", fail_replace)

    with pytest.raises(OSError, match="busy"):
        docker_status.write_evidence(target, docker_status.new_evidence())

    assert target.read_bytes() == before
    assert not list(tmp_path.glob(".docker-status.json.*.tmp"))


@pytest.mark.parametrize(
    "argv",
    [
        ["docker", "build", "."],
        ["docker", "compose", "up"],
        ["docker", "system", "prune"],
        ["docker", "volume", "rm", "other"],
    ],
)
def test_command_runner_refuses_every_non_version_or_info_command(
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catch detector helpers gaining any Docker-mutating command path."""
    called = False

    def fail_subprocess(*_args: object, **_kwargs: object) -> object:
        nonlocal called
        called = True
        raise AssertionError("non-read-only Docker command reached subprocess")

    monkeypatch.setattr(docker_status.subprocess, "run", fail_subprocess)

    with pytest.raises(ValueError, match="read-only"):
        docker_status.run_command(argv, tmp_path)

    assert called is False


def test_detector_uses_runtime_shutil_lookup_for_default_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catch an import-bound lookup that ignores the current host state."""
    commands: list[list[str]] = []

    def runner(
        argv: list[str], _cwd: Path
    ) -> subprocess.CompletedProcess[str]:
        commands.append(argv)
        return _completed(argv, stdout="Docker version 27.0.0\n")

    monkeypatch.setattr(
        docker_status.shutil, "which", lambda _name: "docker.exe"
    )
    payload = docker_status.detect(
        tmp_path, command_runner=runner, expected_root=tmp_path
    )

    assert commands == [
        ["docker", "--version"],
        ["docker", "info", "--format", "{{json .ServerVersion}}"],
    ]
    assert payload["cli"]["status"] == "pass"


def test_detector_records_sanitized_version_fields_without_raw_output(
    tmp_path: Path,
) -> None:
    """Catch version evidence storing raw output with a private host path."""

    def runner(
        argv: list[str], _cwd: Path
    ) -> subprocess.CompletedProcess[str]:
        if argv == ["docker", "--version"]:
            return _completed(
                argv,
                stdout=(
                    "Docker version 27.0.0, build deadbeef\\n"
                    "D:\\\\Users\\\\judge\\\\private"
                ),
            )
        return _completed(
            argv, stdout='"27.0.0"\\nD:\\\\Users\\\\judge\\\\private'
        )

    payload = docker_status.detect(
        tmp_path,
        which=lambda _name: "docker.exe",
        command_runner=runner,
        expected_root=tmp_path,
    )

    assert payload["cli"]["version"] == "27.0.0"
    assert payload["daemon"]["version"] == "27.0.0"
    encoded = json.dumps(payload, ensure_ascii=False)
    assert r"D:\\Users" not in encoded


def test_detector_records_command_start_and_finish_timestamps_separately(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catch capability records using post-command time for both boundaries."""
    timestamps = iter(
        [
            "2026-08-24T00:00:00.000Z",
            "2026-08-24T00:00:01.000Z",
            "2026-08-24T00:00:02.000Z",
            "2026-08-24T00:00:03.000Z",
            "2026-08-24T00:00:04.000Z",
        ]
    )
    monkeypatch.setattr(docker_status, "_timestamp", lambda: next(timestamps))

    payload = docker_status.detect(
        tmp_path,
        which=lambda _name: "docker.exe",
        command_runner=lambda argv, _cwd: _completed(
            argv, stdout="Docker version 27.0.0"
        ),
        expected_root=tmp_path,
    )

    assert payload["cli"]["started_at"] == "2026-08-24T00:00:01.000Z"
    assert payload["cli"]["finished_at"] == "2026-08-24T00:00:02.000Z"
    assert payload["daemon"]["started_at"] == "2026-08-24T00:00:03.000Z"
    assert payload["daemon"]["finished_at"] == "2026-08-24T00:00:04.000Z"


def test_command_runner_calls_subprocess_without_a_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catch a future runner allowing shell interpretation of an argv list."""
    received: dict[str, object] = {}

    def fake_run(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        received["args"] = args
        received.update(kwargs)
        return _completed(["docker", "info"])

    monkeypatch.setattr(docker_status.subprocess, "run", fake_run)

    docker_status.run_command(["docker", "info"], tmp_path)

    assert received["args"] == (["docker", "info"],)
    assert received["shell"] is False
    assert received["check"] is False
    assert received["capture_output"] is True


def test_command_runner_passes_a_positive_explicit_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Prevent a read-only Docker probe from waiting indefinitely."""
    received: dict[str, object] = {}

    def fake_run(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        received.update(kwargs)
        return _completed(["docker", "--version"])

    monkeypatch.setattr(docker_status.subprocess, "run", fake_run)

    docker_status.run_command(["docker", "--version"], tmp_path)

    assert isinstance(received["timeout"], (int, float))
    assert received["timeout"] > 0


@pytest.mark.parametrize(
    "timed_out_command",
    ["cli", "daemon"],
    ids=["cli-timeout", "daemon-timeout"],
)
def test_detector_classifies_timeout_without_hanging(
    timed_out_command: str,
    tmp_path: Path,
) -> None:
    """Timeouts are unavailable-host evidence with safe command metadata."""
    calls: list[list[str]] = []

    def runner(
        argv: list[str], _cwd: Path
    ) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        is_cli = argv == ["docker", "--version"]
        if (timed_out_command == "cli" and is_cli) or (
            timed_out_command == "daemon" and not is_cli
        ):
            raise subprocess.TimeoutExpired(
                argv,
                3,
                output=b"partial stdout",
                stderr=b"partial stderr",
            )
        return _completed(
            argv, stdout="Docker version 27.0.0, build deadbeef\n"
        )

    payload = docker_status.detect(
        tmp_path,
        which=lambda _name: "docker.exe",
        command_runner=runner,
        expected_root=tmp_path,
    )

    record_name = "cli" if timed_out_command == "cli" else "daemon"
    expected_reason = (
        "docker_cli_unavailable"
        if timed_out_command == "cli"
        else "docker_daemon_unavailable"
    )
    assert payload["status"] == "not_run"
    assert payload["reason"] == expected_reason
    assert payload[record_name]["status"] == "not_run"
    assert payload[record_name]["exit_code"] is None
    assert payload[record_name]["argv"] == calls[-1]
    assert (
        payload[record_name]["stdout_sha256"]
        == hashlib.sha256(b"partial stdout").hexdigest()
    )
    assert (
        payload[record_name]["stderr_sha256"]
        == hashlib.sha256(b"partial stderr").hexdigest()
    )
    docker_status.validate_evidence(payload)


def test_cli_rejects_protected_path_before_detector_or_writer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Catch the CLI acting before it validates the protected output path."""
    archive = tmp_path / "赛题资料.7z"
    archive.write_bytes(b"protected archive")
    invoked: list[str] = []

    def unexpected_detect(_root: Path, **_kwargs: object) -> dict[str, object]:
        invoked.append("detect")
        raise AssertionError(
            "detector must not run after protected output rejection"
        )

    monkeypatch.setattr(docker_status, "detect", unexpected_detect)

    code = docker_status.main(
        ["--repo-root", str(tmp_path), "--output", str(archive)],
        expected_root=tmp_path,
    )

    assert code != 0
    assert invoked == []
    assert "rejected" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("record_name", ["cli", "daemon", "static_contract"])
def test_validator_rejects_pass_without_capability_or_static_contract(
    record_name: str,
) -> None:
    """Catch a pass that skips capability or static prerequisite evidence."""
    payload = _complete_live_pass_evidence()
    payload[record_name]["status"] = "not_run"

    with pytest.raises(ValueError, match=record_name.split("_")[0]):
        docker_status.validate_evidence(payload)


def test_cli_writes_valid_not_run_evidence_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Catch unavailable-host evidence treated as an execution failure."""
    output = tmp_path / "evidence" / "docker-status.json"
    monkeypatch.setattr(docker_status.shutil, "which", lambda _name: None)

    code = docker_status.main(
        ["--repo-root", str(tmp_path), "--output", str(output)],
        expected_root=tmp_path,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    summary = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "not_run"
    assert payload["reason"] == "docker_cli_unavailable"
    assert summary == {
        "reason": "docker_cli_unavailable",
        "status": "not_run",
    }


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        (_real_live_fail_evidence(), 1),
        ({"schema": "invalid"}, 2),
    ],
    ids=["real-fail", "invalid-schema"],
)
def test_cli_returns_nonzero_for_failure_or_invalid_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    payload: dict[str, object],
    expected_code: int,
) -> None:
    """Catch CLI success exits for failed or unvalidated evidence documents."""
    output = tmp_path / "evidence" / "docker-status.json"
    monkeypatch.setattr(
        docker_status, "detect", lambda _root, **_kwargs: payload
    )

    code = docker_status.main(
        ["--repo-root", str(tmp_path), "--output", str(output)],
        expected_root=tmp_path,
    )

    assert code == expected_code
    if payload["schema"] == docker_status.SCHEMA:
        evidence = json.loads(output.read_text(encoding="utf-8"))
        assert evidence["status"] == "fail"
    else:
        assert not output.exists()


def test_task19c_f03_config_digest_requires_archive_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A pre-archive strict failure cannot claim a config digest."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at="start"),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator(payload)
    assert payload["reason"] == "headless_start_failed"
    assert "config_digest" not in payload["invocation"]

    forged = copy.deepcopy(payload)
    forged["invocation"]["config_digest"] = forged["invocation"][
        "headless_image_id"
    ]
    with pytest.raises(ValueError, match="config digest|archive|premature"):
        validator(forged)


@pytest.mark.parametrize(
    "exception_kind", ["ordinary", "command_exception"],
    ids=["ordinary-command", "command-exception"],
)
def test_task19c_f05_failure_carrier_uses_canonical_argv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    exception_kind: str,
) -> None:
    """Every strict command-bound failure retains its attempted command."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    delegate = _LiveVerifierRunner()
    expected_start = [
        "docker",
        "compose",
        "--project-name",
        "ca-mp-task19-a1b2c3d4e5f6",
        "up",
        "--detach",
        "--no-build",
        "judge",
    ]

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if exception_kind == "command_exception" and argv == expected_start:
            raise subprocess.TimeoutExpired(
                argv, 1, output=b"start-out", stderr=b"start-err"
            )
        if exception_kind == "ordinary" and argv == expected_start:
            return _completed(argv, returncode=19, stderr="start failed")
        return delegate(argv, root, **kwargs)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator(payload)
    failure = payload["headless_health"]
    assert payload["reason"] == "headless_start_failed"
    assert failure["execution"] == (
        "command_exception" if exception_kind == "command_exception" else "command"
    )
    forged = copy.deepcopy(payload)
    forged["headless_health"]["argv"] = ["docker", "info"]
    with pytest.raises(ValueError, match="canonical|command|argv"):
        validator(forged)


@pytest.mark.parametrize(
    "terminal_before_first_frame", [True, False],
    ids=["terminal-before-frame", "active-before-frame"],
)
def test_task19c_f08_gui_probe_observes_active_run_before_first_frame(
    monkeypatch: pytest.MonkeyPatch,
    terminal_before_first_frame: bool,
) -> None:
    """The embedded GUI probe orders an active observation before frame one."""
    run_id = "a1b2c3d4e5f6"
    run_path = f"runs/i1/fixed_time/x1/s42/{run_id}"
    run_dir = f"/app/output/{run_path}"
    calls: list[str] = []
    status_reads = 0

    class Headers(dict[str, str]):
        def get_content_type(self) -> str:
            return "image/png"

    class Response:
        def __init__(self, status: int, body: bytes, headers: Headers) -> None:
            self.status = status
            self._body = body
            self.headers = headers

        def read(self) -> bytes:
            return self._body

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def response(status: str) -> Response:
        return Response(
            200 if status != "created" else 202,
            json.dumps(
                {"run_id": run_id, "run_dir": run_dir, "status": status}
            ).encode(),
            Headers(),
        )

    def urlopen(request: object, **_kwargs: object) -> Response:
        nonlocal status_reads
        url = request.full_url if isinstance(request, urllib.request.Request) else str(request)
        if isinstance(request, urllib.request.Request):
            calls.append("POST")
            return response("created")
        if "/frame?sequence=" in url:
            calls.append("FRAME2")
            return Response(
                200,
                _LiveVerifierRunner._PNG_TWO,
                Headers(
                    {
                        "X-Run-Id": run_id,
                        "X-Frame-Sequence": "2",
                        "X-Simulation-Time": "2.0",
                    }
                ),
            )
        if url.endswith("/frame"):
            calls.append("FRAME1")
            return Response(
                200,
                _LiveVerifierRunner._PNG_ONE,
                Headers(
                    {
                        "X-Run-Id": run_id,
                        "X-Frame-Sequence": "1",
                        "X-Simulation-Time": "1.0",
                    }
                ),
            )
        status_reads += 1
        calls.append("STATUS")
        if terminal_before_first_frame or status_reads > 1:
            return response("completed")
        return response("running")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        docker_verify,
        "_read_observed_completion",
        lambda *_args, **_kwargs: {
            "source": "sealed_simulation_log.v1",
            "run_id": run_id,
            "run_path": run_path,
            "requested_steps": 100,
            "observed_step_count": 100,
            "observed_step_indices": list(range(100)),
            "step_log_path": "simulation_log.csv",
            "step_log_sha256": "a" * 64,
            "hashes_path": "hashes.json",
            "hashes_sha256": "b" * 64,
        },
    )
    output = io.StringIO()
    with pytest.MonkeyPatch.context() as local:
        local.setattr("sys.stdout", output)
        if terminal_before_first_frame:
            with pytest.raises(RuntimeError, match="active|nonterminal"):
                exec(docker_verify._GUI_FRAMES_SCRIPT, {"__name__": "__main__"})
        else:
            exec(docker_verify._GUI_FRAMES_SCRIPT, {"__name__": "__main__"})
            assert calls == ["POST", "STATUS", "FRAME1", "FRAME2", "STATUS"]


def test_task19c_f09_failed_export_closes_contents_to_current_unit_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Failed-export contents cannot contain an unbound foreign path."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at="export"),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator(payload)
    assert payload["reason"] == "evidence_export_failed"
    foreign = {
        "path": "foreign/unbound.bin",
        "byte_length": 7,
        "sha256": hashlib.sha256(b"foreign").hexdigest(),
    }
    forged = copy.deepcopy(payload)
    forged["exported_evidence"]["contents"].append(foreign)
    forged["exported_evidence"]["contents"].sort(key=lambda item: item["path"])
    with pytest.raises(ValueError, match="export|content|unit|prefix"):
        validator(forged)


@pytest.mark.parametrize("stage", ["requery", "post_remove", "final"])
def test_task19c_f11a_cleanup_helper_failure_keeps_one_terminal_action(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stage: str,
) -> None:
    """A phase-construction error cannot append a false cleanup terminal."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner(fail_at="start")
    cleanup_inspects = 0
    removal_seen = False
    empty_inspects = 0
    injected = False

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal cleanup_inspects, removal_seen, empty_inspects, injected
        typed_inspect = (
            len(argv) == 4
            and argv[0] == "docker"
            and argv[1] in {"container", "network", "volume", "image"}
            and argv[2] == "inspect"
        )
        cleanup_started = "start" in delegate.events
        if cleanup_started and typed_inspect:
            cleanup_inspects += 1
            if not delegate.resources:
                empty_inspects += 1
        should_raise = (
            not injected
            and cleanup_started
            and typed_inspect
            and (
                (stage == "requery" and cleanup_inspects == 10)
                or (stage == "post_remove" and removal_seen)
                or (stage == "final" and empty_inspects == 10)
            )
        )
        if should_raise:
            injected = True
            raise RuntimeError("injected cleanup inventory failure")
        result = delegate(argv, root, **kwargs)
        if cleanup_started and len(argv) == 4 and argv[2] == "rm":
            removal_seen = True
        return result

    def fail_phase_helper(
        _action: Mapping[str, object], _detail: str
    ) -> dict[str, object]:
        raise RuntimeError("cleanup phase helper failed")

    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(docker_verify, "_cleanup_phase_from_action", fail_phase_helper)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    assert injected is True
    assert payload["reason"] == "headless_start_failed"
    owned = payload["owned_resources"]
    assert owned["before_cleanup_complete"] is True
    assert owned["before_cleanup"]
    assert owned["after_cleanup_complete"] is False
    if stage == "final":
        assert owned["after_cleanup"] == []
    elif stage == "post_remove":
        removed = {
            (action["resource_kind"], action["resource_name"])
            for action in owned["cleanup_actions"]
            if action["action_kind"] == "remove" and action["status"] == "pass"
        }
        assert not removed.intersection(
            (item["kind"], item["name"]) for item in owned["after_cleanup"]
        )
    failures = [
        action for action in owned["cleanup_actions"] if action["status"] == "fail"
    ]
    assert len(failures) == 1
    terminal = failures[0]
    assert terminal is owned["cleanup_actions"][-1]
    assert terminal["inventory_stage"] == stage
    cleanup = payload["cleanup"]
    assert all(
        cleanup.get(field) == terminal.get(field)
        for field in docker_status._STRICT_CLEANUP_PROJECTION
    )
    validator(payload)


def test_task19c_f11b_retained_terminal_identity_is_in_complete_after_inventory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A retained cleanup claim must name an item in a complete after list."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(retain_after_cleanup=True),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator(payload)
    terminal = payload["owned_resources"]["cleanup_actions"][-1]
    assert terminal["action_kind"] == "retained_postcondition"
    assert payload["owned_resources"]["after_cleanup_complete"] is True
    assert payload["owned_resources"]["after_cleanup"]

    forged = copy.deepcopy(payload)
    forged["owned_resources"]["after_cleanup"] = []
    with pytest.raises(ValueError, match="retained|after|inventory"):
        validator(forged)


def test_task19c_f12c_failed_remove_targets_established_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A complete initial inventory forbids removing an unobserved resource."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    delegate = _LiveVerifierRunner()
    injected = False

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal injected
        if (
            not injected
            and len(argv) == 4
            and argv[0] == "docker"
            and argv[2] == "rm"
            and len(delegate.resources) == 1
        ):
            injected = True
            delegate.resources.pop(argv[-1], None)
            return _completed(argv, returncode=19, stderr="cleanup remove failed")
        return delegate(argv, root, **kwargs)

    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator(payload)
    owned = payload["owned_resources"]
    assert owned["before_cleanup_complete"] is True
    assert not any(
        item["name"] == "ca-mp-task19-a1b2c3d4e5f6-gui:local"
        for item in owned["before_cleanup"]
    )
    terminal = owned["cleanup_actions"][-1]
    assert terminal["status"] == "fail"
    forged = copy.deepcopy(payload)
    gui_image = "ca-mp-task19-a1b2c3d4e5f6-gui:local"
    forged_terminal = forged["owned_resources"]["cleanup_actions"][-1]
    for carrier in (forged_terminal, forged["cleanup"]):
        carrier["resource_kind"] = "image"
        carrier["resource_name"] = gui_image
        carrier["argv"] = ["docker", "image", "rm", gui_image]
    with pytest.raises(ValueError, match="before|established|owned|cleanup"):
        validator(forged)


@pytest.mark.parametrize(
    "mutation", ["predecessor", "save-load-prefix", "cleanup"],
    ids=["predecessor-not-run", "save-load-earlier-omitted", "cleanup-not-run"],
)
def test_task19c_a1_strict_failure_phase_prefix_and_cleanup_obligation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    """Strict failures retain the reached phase prefix and cleanup obligation."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    failure_at = "load" if mutation == "save-load-prefix" else "start"
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at=failure_at),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator(payload)

    forged = copy.deepcopy(payload)
    if mutation == "predecessor":
        forged["headless_build"] = docker_verify._not_run_record(
            "phase was not reached"
        )
    elif mutation == "save-load-prefix":
        forged["headless_health"] = docker_verify._not_run_record(
            "phase was not reached"
        )
    else:
        forged["cleanup"] = docker_verify._not_run_record(
            "cleanup was not reached"
        )
        forged["owned_resources"] = {
            "before_cleanup": [],
            "before_cleanup_complete": True,
            "after_cleanup": [],
            "after_cleanup_complete": True,
            "cleanup_actions": [],
        }
    with pytest.raises(ValueError, match="prefix|predecessor|cleanup|reached"):
        validator(forged)


def test_task19c_a2_save_load_failure_requires_nested_proof_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A save/load failure cannot stand without its nested stage ledger."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at="save"),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator(payload)
    assert payload["reason"] == "image_save_failed"
    assert payload["save_load"]["status"] == "fail"
    assert payload["save_load_proof"]["image_save"]["status"] == "fail"

    forged = copy.deepcopy(payload)
    forged.pop("save_load_proof")
    with pytest.raises(ValueError, match="save/load proof|nested|incomplete"):
        validator(forged)


def test_task19c_a3_strict_pass_requires_empty_collision_preflight(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A strict successful run cannot carry a canonical collision entry."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator(payload)
    invocation = payload["invocation"]
    project = invocation["compose_project"]
    forged = copy.deepcopy(payload)
    forged["name_collisions"]["before"] = [
        {"kind": "container", "name": f"{project}-judge-1", "labels": {}}
    ]
    with pytest.raises(ValueError, match="collision|preflight"):
        validator(forged)


def test_task19c_a4_strict_pass_requires_complete_resource_closure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A strict pass cannot omit an owned resource and its removal action."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator(payload)
    forged = copy.deepcopy(payload)
    removed = forged["owned_resources"]["before_cleanup"][-1]
    identity = (removed["kind"], removed["name"])
    forged["owned_resources"]["before_cleanup"] = [
        item
        for item in forged["owned_resources"]["before_cleanup"]
        if (item["kind"], item["name"]) != identity
    ]
    forged["owned_resources"]["cleanup_actions"] = [
        action
        for action in forged["owned_resources"]["cleanup_actions"]
        if (action["resource_kind"], action["resource_name"]) != identity
    ]
    with pytest.raises(ValueError, match="resource closure|complete exact removals"):
        validator(forged)


def test_task19c_a5_strict_pass_requires_linux_amd64_platform(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A strict pass must identify the release target, not the host target."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator(payload)
    forged = copy.deepcopy(payload)
    forged["platform"] = {"os": "windows", "architecture": "arm64"}
    with pytest.raises(ValueError, match="platform|linux/amd64"):
        validator(forged)


@pytest.mark.parametrize("capability", ["cli", "daemon"])
def test_task19c_a6_strict_pass_requires_exact_capabilities(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capability: str,
) -> None:
    """A strict pass must retain both successful canonical capability probes."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator(payload)
    forged = copy.deepcopy(payload)
    if capability == "cli":
        forged["cli"]["argv"] = ["docker", "info"]
    else:
        forged["daemon"] = docker_verify._not_run_record("daemon was not run")
    with pytest.raises(ValueError, match="capabilit|cli|daemon|canonical"):
        validator(forged)


def test_task19c_a7_strict_privacy_rejection_is_recursive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Strict sanitization must cover nested capability facts and argv data."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator(payload)
    forged = copy.deepcopy(payload)
    forged["daemon"]["version"] = r"C:\Users\judge\private"
    with pytest.raises(ValueError, match="private|absolute path|privacy"):
        validator(forged)


def test_task19c_ext_c1_stops_all_running_owned_containers_before_remove(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cleanup must stop every owned running container before any rm."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    delegate = _LiveVerifierRunner()
    running = {
        "ca-mp-task19-a1b2c3d4e5f6-judge-1",
        "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1",
        "ca-mp-task19-a1b2c3d4e5f6-judge-gui-1",
    }
    stopped: set[str] = set()

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        result = delegate(argv, root, **kwargs)
        if (
            len(argv) == 4
            and argv[:2] == ["docker", "container"]
            and argv[2] == "inspect"
            and result.returncode == 0
        ):
            values = json.loads(result.stdout)
            if values and values[0].get("Name", "").lstrip("/") in running:
                values[0]["State"] = {
                    "Running": values[0]["Name"].lstrip("/") not in stopped
                }
                result.stdout = json.dumps(values)
        if argv[:3] == ["docker", "container", "stop"]:
            stopped.add(argv[-1])
        if len(argv) == 4 and argv[:3] == ["docker", "container", "rm"]:
            if argv[-1] in running and argv[-1] not in stopped:
                return _completed(argv, returncode=19, stderr="still running")
        return result

    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        include_gui=True,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(
        docker_status,
        "validate_live_verifier_evidence",
        docker_status.validate_evidence,
    )
    stop_actions = [
        action
        for action in payload["owned_resources"]["cleanup_actions"]
        if action.get("action_kind") == "stop"
    ]
    headless_name = "ca-mp-task19-a1b2c3d4e5f6-judge-1"
    stopped_identities = {
        *(action["resource_name"] for action in stop_actions),
        headless_name,
    }
    assert payload["save_load_proof"]["controlled_stop"]["status"] == "pass"
    assert stopped_identities == running
    rm_positions = [
        index
        for index, action in enumerate(
            payload["owned_resources"]["cleanup_actions"]
        )
        if action.get("action_kind") == "remove"
        and action.get("resource_kind") == "container"
    ]
    assert rm_positions
    assert all(
        any(
            index < rm_index
            and (
                (
                    action.get("action_kind") == "stop"
                    and action.get("resource_name") == action_name
                )
                or (action_name == headless_name and action_name in stopped_identities)
            )
            for index, action in enumerate(
                payload["owned_resources"]["cleanup_actions"]
            )
        )
        for rm_index, action_name in (
            (rm_index, payload["owned_resources"]["cleanup_actions"][rm_index]["resource_name"])
            for rm_index in rm_positions
        )
    )
    assert payload["status"] == "pass"


@pytest.mark.parametrize("mutation", ["phase", "nested", "matrix"])
def test_task19c_ext_c2_not_run_is_exact_capability_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    """Strict capability-unavailable results cannot claim live evidence."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)

    def unavailable(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> object:
        if argv == ["docker", "--version"]:
            raise OSError("docker unavailable")
        return _completed(argv)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=unavailable,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    docker_status.validate_live_verifier_evidence(payload)
    forged = copy.deepcopy(payload)
    if mutation == "phase":
        forged["headless_build"]["status"] = "pass"
        forged["headless_build"]["argv"] = ["docker", "info"]
        forged["headless_build"]["exit_code"] = 0
    elif mutation == "nested":
        forged["quick_smoke"] = {"forged": True}
    else:
        forged["reason"] = "live_verification_not_run"
        forged["cli"]["status"] = "pass"
        forged["cli"]["exit_code"] = 0
    with pytest.raises(ValueError, match="not.?run|capabilit|phase|nested|producer"):
        docker_status.validate_live_verifier_evidence(forged)


def test_task19c_ext_c2_export_failure_keeps_complete_non_export_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An export failure cannot erase a previously reached success prefix."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at="export"),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(
        docker_status,
        "validate_live_verifier_evidence",
        docker_status.validate_evidence,
    )
    docker_status.validate_live_verifier_evidence(payload)
    forged = copy.deepcopy(payload)
    forged["headless_health"] = docker_verify._not_run_record(
        "phase was not reached"
    )
    with pytest.raises(ValueError, match="prefix|predecessor|export"):
        docker_status.validate_live_verifier_evidence(forged)


@pytest.mark.parametrize(
    ("fail_at", "owner"),
    [
        ("build", "headless_build"),
        ("start", "headless_health"),
        ("gui_build", "gui_build"),
        ("gui_start", "gui_smoke"),
        ("gui_health", "gui_smoke"),
        ("gui_frames", "gui_smoke"),
    ],
)
def test_task19c_ext_f05b_all_command_boundaries_use_canonical_argv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fail_at: str,
    owner: str,
) -> None:
    """Every strict command failure is bound to its attempted Docker argv."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    include_gui = fail_at.startswith("gui")
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at=fail_at),
        include_gui=include_gui,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(
        docker_status,
        "validate_live_verifier_evidence",
        docker_status.validate_evidence,
    )
    docker_status.validate_live_verifier_evidence(payload)
    forged = copy.deepcopy(payload)
    forged[owner]["argv"] = ["docker", "info"]
    with pytest.raises(ValueError, match="canonical|command|argv"):
        docker_status.validate_live_verifier_evidence(forged)


def test_task19c_ext_f09b_failed_export_closes_exact_observed_partial_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A forged path within the failed unit prefix is still rejected."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at="export"),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(
        docker_status,
        "validate_live_verifier_evidence",
        docker_status.validate_evidence,
    )
    docker_status.validate_live_verifier_evidence(payload)
    attempt = payload["exported_evidence"]["attempt"]
    destination = attempt["argv"][-1].split("/", 5)[-1]
    forged = copy.deepcopy(payload)
    forged["exported_evidence"]["contents"].append(
        {
            "path": f"{destination}/foreign.bin",
            "byte_length": 7,
            "sha256": hashlib.sha256(b"foreign").hexdigest(),
        }
    )
    forged["exported_evidence"]["contents"].sort(
        key=lambda item: item["path"]
    )
    with pytest.raises(ValueError, match="partial|observed|contents|export"):
        docker_status.validate_live_verifier_evidence(forged)


@pytest.mark.parametrize("state", ["bogus", "stopped", "ended_early", "running"])
def test_task19c_ext_f08b_gui_active_state_has_explicit_nonterminal_grammar(
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    """The first GUI observation accepts only explicit nonterminal states."""
    run_id = "333333333333"
    run_dir = f"/app/output/runs/i1/fixed_time/x1/s42/{run_id}"
    calls: list[str] = []

    class Headers(dict[str, str]):
        def get_content_type(self) -> str:
            return "image/png"

    class Response:
        def __init__(self, status: int, body: bytes, headers: Headers) -> None:
            self.status = status
            self._body = body
            self.headers = headers

        def read(self) -> bytes:
            return self._body

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def urlopen(request: object, **_kwargs: object) -> Response:
        url = (
            request.full_url
            if isinstance(request, urllib.request.Request)
            else str(request)
        )
        if isinstance(request, urllib.request.Request):
            calls.append("POST")
            body = {"run_id": run_id, "run_dir": run_dir, "status": "running"}
            return Response(202, json.dumps(body).encode(), Headers())
        if url.endswith("/frame"):
            calls.append("FRAME1")
            return Response(
                200,
                _LiveVerifierRunner._PNG_ONE,
                Headers(
                    {
                        "X-Run-Id": run_id,
                        "X-Frame-Sequence": "1",
                        "X-Simulation-Time": "1.0",
                    }
                ),
            )
        if "/frame?sequence=" in url:
            calls.append("FRAME2")
            return Response(
                200,
                _LiveVerifierRunner._PNG_TWO,
                Headers(
                    {
                        "X-Run-Id": run_id,
                        "X-Frame-Sequence": "2",
                        "X-Simulation-Time": "2.0",
                    }
                ),
            )
        calls.append("STATUS")
        status = state if len(calls) == 2 else "completed"
        body = {"run_id": run_id, "run_dir": run_dir, "status": status}
        return Response(200, json.dumps(body).encode(), Headers())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        docker_verify,
        "_read_observed_completion",
        lambda *_args, **_kwargs: {
            "source": "sealed_simulation_log.v1",
            "run_id": run_id,
            "run_path": f"runs/i1/fixed_time/x1/s42/{run_id}",
            "requested_steps": 100,
            "observed_step_count": 100,
            "observed_step_indices": list(range(100)),
            "step_log_path": "simulation_log.csv",
            "step_log_sha256": "a" * 64,
            "hashes_path": "hashes.json",
            "hashes_sha256": "b" * 64,
        },
    )
    namespace = {"__name__": "__main__"}
    if state == "running":
        exec(docker_verify._GUI_FRAMES_SCRIPT, namespace, namespace)
    else:
        with pytest.raises(RuntimeError, match="active|nonterminal"):
            exec(docker_verify._GUI_FRAMES_SCRIPT, namespace, namespace)


def test_task19c_ext_f11c_cleanup_failure_has_one_terminal_and_subset_after(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cleanup failure cannot append terminals or invent after identities."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(retain_after_cleanup=True),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    forged = copy.deepcopy(payload)
    owner = {"io.challengecup.task19.invocation": "a1b2c3d4e5f6"}
    forged["owned_resources"]["after_cleanup"].append(
        {
            "kind": "image",
            "name": "ca-mp-task19-a1b2c3d4e5f6-gui:local",
            "labels": owner,
        }
    )
    with pytest.raises(ValueError, match="subset|before|terminal|cleanup"):
        validator(forged)


def test_task19c_ext_i3_export_verifier_result_binds_copy_argv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A verifier-result export failure retains its exact docker cp target."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    delegate = _LiveVerifierRunner()

    def runner(
        argv: list[str], root: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        result = delegate(argv, root, **kwargs)
        if argv[:2] == ["docker", "cp"]:
            return result
        return result

    original_walk = docker_verify._walk_exported_regular_files
    walk_calls = 0

    def fail_after_first_copy(root: Path) -> list[dict[str, object]]:
        nonlocal walk_calls
        walk_calls += 1
        if walk_calls == 3:
            raise docker_verify.SafetyError("injected export postcondition")
        return original_walk(root)

    monkeypatch.setattr(
        docker_verify, "_walk_exported_regular_files", fail_after_first_copy
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(
        docker_status,
        "validate_live_verifier_evidence",
        docker_status.validate_evidence,
    )
    attempt = payload["exported_evidence"]["attempt"]
    assert attempt["execution"] == "verifier_result"
    docker_status.validate_live_verifier_evidence(payload)
    forged = copy.deepcopy(payload)
    forged["exported_evidence"]["attempt"]["argv"] = ["docker", "info"]
    with pytest.raises(ValueError, match="export|copy|canonical|argv"):
        docker_status.validate_live_verifier_evidence(forged)


def test_task19c_ext_i4_api_and_gui_hashes_bind_canonical_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Strict proof hashes cannot be replaced by another valid hex digest."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    forged = copy.deepcopy(payload)
    forged["headless_smoke"]["api_proof"]["response"]["body_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="hash|body|canonical"):
        validator(forged)


@pytest.mark.parametrize("value", ["bogus", "username", "99.77", "???"])
def test_task19c_ext_i5_capability_versions_use_sanitized_producer_grammar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    value: str,
) -> None:
    """Strict capability versions reject arbitrary or username-like values."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    forged = copy.deepcopy(payload)
    forged["cli"]["version"] = value
    with pytest.raises(ValueError, match="version|capabilit|sanit"):
        validator(forged)


def test_task19c_ext_i6_capability_runtime_error_is_closed_without_traceback(
    tmp_path: Path,
) -> None:
    """Unexpected capability exceptions return a stable fail-closed result."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)

    def runner(
        _argv: list[str], _root: Path, **_kwargs: object
    ) -> object:
        raise RuntimeError("unexpected capability probe failure")

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    assert payload["status"] == "fail"
    assert payload["reason"] == "docker_cli_failed"
    assert payload["cli"]["execution"] == "internal_error"
    docker_status.validate_live_verifier_evidence(payload)


@pytest.mark.parametrize("location", ["version", "detail"])
def test_task19c_ext_a7b_privacy_rejects_nested_traversal_and_username_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    location: str,
) -> None:
    """Recursive strict sanitization rejects traversal and private names."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    forged = copy.deepcopy(payload)
    forged["daemon"][location] = (
        "username" if location == "version" else "/app/output/../../Users/judge"
    )
    with pytest.raises(
        ValueError, match="private|absolute|traversal|privacy|username"
    ):
        validator(forged)


def test_task19c_ext_m1_repository_digest_is_bound_or_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A strict repository digest cannot be an unrelated valid-looking hash."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    forged = copy.deepcopy(payload)
    forged["invocation"]["repository_digest"] = "sha256:" + "f" * 64
    with pytest.raises(ValueError, match="repository|digest|snapshot"):
        validator(forged)


def test_task19c_r3_c2_not_run_exact_capability_reason_envelope(
    tmp_path: Path,
) -> None:
    """A capability-unavailable envelope cannot carry version/detail claims."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)

    def unavailable(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> object:
        if argv == ["docker", "--version"]:
            raise OSError("docker unavailable")
        return _completed(argv)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=unavailable,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    docker_status.validate_live_verifier_evidence(payload)
    forged = copy.deepcopy(payload)
    forged["cli"]["version"] = "27.0.0"
    with pytest.raises(ValueError, match="not.?run|version|detail|capabilit"):
        docker_status.validate_live_verifier_evidence(forged)


def test_task19c_r3_f09b_failed_export_binds_observed_partial_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed export cannot add an unobserved artifact to both manifests."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at="export"),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    attempt = payload["exported_evidence"]["attempt"]
    destination = attempt["argv"][-1].split("/", 5)[-1]
    foreign = {
        "path": f"{destination}/foreign.bin",
        "byte_length": 7,
        "sha256": hashlib.sha256(b"foreign").hexdigest(),
    }
    forged = copy.deepcopy(payload)
    forged["exported_evidence"]["contents"].append(dict(foreign))
    forged["exported_evidence"]["contents"].sort(
        key=lambda item: item["path"]
    )
    forged["exported_evidence"]["attempt"]["partial_contents"].append(
        dict(foreign)
    )
    forged["exported_evidence"]["attempt"]["partial_contents"].sort(
        key=lambda item: item["path"]
    )
    with pytest.raises(ValueError, match="partial|observed|contents|export"):
        validator(forged)


@pytest.mark.parametrize("mutation", ["digest", "extra"])
def test_task19c_r3_i3_launcher_diagnostics_binds_observed_singleton(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    """Launcher export evidence is bound to its observed singleton bytes."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    forged = copy.deepcopy(payload)
    exported = forged["exported_evidence"]
    launcher_unit = next(
        unit
        for unit in exported["export_units"]
        if unit["kind"] == "launcher_diagnostics" and unit["scope"] == "headless"
    )
    launcher_path = "headless/diagnostics/launcher.json"
    launcher_entry = next(
        entry for entry in exported["contents"] if entry["path"] == launcher_path
    )
    if mutation == "digest":
        launcher_entry["sha256"] = "f" * 64
    else:
        extra = {
            "path": "headless/diagnostics/launcher.json/extra",
            "byte_length": 5,
            "sha256": hashlib.sha256(b"extra").hexdigest(),
        }
        exported["contents"].append(extra)
        launcher_unit["content_paths"].append(extra["path"])
        exported["contents"].sort(key=lambda item: item["path"])
    with pytest.raises(ValueError, match="launcher|digest|singleton|content|export"):
        validator(forged)


@pytest.mark.parametrize("scope", ["headless", "gui"])
def test_task19c_r3_i4_api_request_hash_binds_canonical_body(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scope: str,
) -> None:
    """A valid-looking request hash cannot replace the canonical body hash."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(),
        include_gui=scope == "gui",
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    forged = copy.deepcopy(payload)
    phase = "headless_smoke" if scope == "headless" else "gui_smoke"
    forged[phase]["api_proof"]["request"]["body_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="request|body|canonical|hash"):
        validator(forged)


def test_task19c_r3_a1_image_identity_failure_owes_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An owned image cannot be hidden behind an empty cleanup not-run claim."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at="image_identity"),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    assert payload["headless_build"]["status"] == "fail"
    assert payload["headless_build"]["boundary"] == "image_identity"
    assert payload["owned_resources"]["before_cleanup"]
    validator(payload)
    forged = copy.deepcopy(payload)
    forged["cleanup"] = docker_verify._not_run_record("no cleanup required")
    forged["owned_resources"] = {
        "before_cleanup": [],
        "before_cleanup_complete": True,
        "after_cleanup": [],
        "after_cleanup_complete": True,
        "cleanup_actions": [],
    }
    with pytest.raises(ValueError, match="cleanup|owned|obligation|image"):
        validator(forged)


def test_task19c_r3_f11c_incomplete_inventory_cannot_forge_failed_remove(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An incomplete before inventory cannot establish a fabricated remove target."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)

    class InitialInventoryFailureRunner(_LiveVerifierRunner):
        def __init__(self) -> None:
            super().__init__(fail_at="start")
            self.failed_initial_inventory = False

        def __call__(
            self,
            argv: list[str],
            cwd: Path,
            *,
            env: dict[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
            if (
                self.mutation_started
                and self.image_identity_seen
                and not self.failed_initial_inventory
                and len(argv) == 4
                and argv[0] == "docker"
                and argv[2] == "inspect"
            ):
                self.failed_initial_inventory = True
                raise OSError("initial inventory unavailable")
            return super().__call__(argv, cwd, env=env)

    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=InitialInventoryFailureRunner(),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    owned = payload["owned_resources"]
    assert owned["before_cleanup_complete"] is False
    assert owned["before_cleanup"] == []
    forged = copy.deepcopy(payload)
    terminal = forged["owned_resources"]["cleanup_actions"][-1]
    terminal.update(
        {
            "action_kind": "remove",
            "resource_kind": "image",
            "resource_name": forged["invocation"]["gui_image"],
            "argv": ["docker", "image", "rm", forged["invocation"]["gui_image"]],
        }
    )
    terminal.pop("inventory_stage", None)
    for field in docker_status._STRICT_CLEANUP_PROJECTION:
        if field in terminal:
            forged["cleanup"][field] = terminal[field]
        else:
            forged["cleanup"].pop(field, None)
    with pytest.raises(ValueError, match="before|established|remove|inventory"):
        validator(forged)


def test_task19c_r3_a2_save_load_outer_failure_binds_nested_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An outer save/load failure cannot erase its reached nested stage prefix."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at="save"),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    assert payload["save_load"]["status"] == "fail"
    assert payload["save_load"]["boundary"] == "image_save"
    forged = copy.deepcopy(payload)
    forged["save_load_proof"].update(
        {
            stage: docker_verify._not_run_record("nested stage was not reached")
            for stage in docker_status._STRICT_SAVE_STAGE_NAMES
        }
    )
    with pytest.raises(ValueError, match="save/load|nested|prefix|stage"):
        validator(forged)


@pytest.mark.parametrize(
    ("semantic_mismatch", "owner"),
    [("config_json", "static_contract"), ("api_health", "headless_health")],
)
def test_task19c_r3_f05b_verifier_result_binds_exact_argv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    semantic_mismatch: str,
    owner: str,
) -> None:
    """Semantic verifier-result carriers cannot claim an unrelated command."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(
            semantic_mismatch_at=semantic_mismatch
        ),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    assert payload[owner]["execution"] == "verifier_result"
    forged = copy.deepcopy(payload)
    forged[owner]["argv"] = ["docker", "info"]
    with pytest.raises(ValueError, match="canonical|command|argv|verifier"):
        validator(forged)


def test_task19c_r3_f11c_failed_cleanup_successful_remove_needs_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed cleanup cannot record a successful remove for an unobserved owner."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(cleanup_fail=True),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    assert payload["status"] == "fail"
    assert payload["reason"] == "cleanup_failed"
    owned = payload["owned_resources"]
    assert owned["before_cleanup_complete"] is True
    assert owned["cleanup_actions"][-1]["status"] == "fail"
    invocation_id = payload["invocation_id"]
    gui_image = payload["invocation"]["gui_image"]
    forged_action = {
        "status": "pass",
        "execution": "command",
        "action_kind": "remove",
        "resource_kind": "image",
        "resource_name": gui_image,
        "required_label": {
            "key": "io.challengecup.task19.invocation",
            "value": invocation_id,
        },
        "argv": ["docker", "image", "rm", gui_image],
        "exit_code": 0,
        "stdout_sha256": hashlib.sha256(b"").hexdigest(),
        "stderr_sha256": hashlib.sha256(b"").hexdigest(),
    }
    forged = copy.deepcopy(payload)
    forged["owned_resources"]["cleanup_actions"].insert(0, forged_action)
    with pytest.raises(ValueError, match="before|established|remove|owner|cleanup"):
        validator(forged)


@pytest.mark.parametrize(
    ("reached_stage", "forged_stage"),
    [("requery", "final"), ("post_remove", "initial"), ("final", "requery")],
)
def test_task19c_r3_f11a_cleanup_terminal_stage_binds_chronology(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    reached_stage: str,
    forged_stage: str,
) -> None:
    """A cleanup inventory terminal cannot claim an impossible chronology stage."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)

    class InventoryStageFailureRunner(_LiveVerifierRunner):
        def __init__(self, stage: str) -> None:
            super().__init__()
            self.stage = stage
            self.cleanup_inspects = 0
            self.just_removed = False
            self.empty_inventory_groups = 0

        def __call__(
            self,
            argv: list[str],
            cwd: Path,
            *,
            env: dict[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
            typed_inspect = (
                len(argv) == 4
                and argv[0] == "docker"
                and argv[2] == "inspect"
            )
            if len(argv) == 4 and argv[:3] == ["docker", "image", "rm"]:
                self.just_removed = True
            if typed_inspect and self.image_identity_seen:
                self.cleanup_inspects += 1
                within_inventory = ((self.cleanup_inspects - 1) % 9) + 1
                if self.stage == "requery" and self.cleanup_inspects == 10:
                    raise OSError("requery inventory unavailable")
                if self.stage == "post_remove" and self.just_removed:
                    raise OSError("post-remove inventory unavailable")
                if not self.resources and within_inventory == 1:
                    self.empty_inventory_groups += 1
                if (
                    self.stage == "final"
                    and self.empty_inventory_groups == 2
                    and within_inventory == 1
                ):
                    raise OSError("final inventory unavailable")
            result = super().__call__(argv, cwd, env=env)
            if typed_inspect and self.image_identity_seen:
                within_inventory = ((self.cleanup_inspects - 1) % 9) + 1
                if self.just_removed and within_inventory == 9:
                    self.just_removed = False
            return result

    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=InventoryStageFailureRunner(reached_stage),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    terminal = payload["owned_resources"]["cleanup_actions"][-1]
    assert terminal["inventory_stage"] == reached_stage
    assert payload["cleanup"]["inventory_stage"] == reached_stage
    forged = copy.deepcopy(payload)
    forged["owned_resources"]["cleanup_actions"][-1]["inventory_stage"] = forged_stage
    forged["cleanup"]["inventory_stage"] = forged_stage
    with pytest.raises(ValueError, match="stage|chronolog|inventory|cleanup"):
        validator(forged)


@pytest.mark.parametrize("mutation", ["before_owner", "after_complete"])
def test_task19c_r3_f12c_cleanup_completeness_is_producer_bound(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    """Cleanup completeness flags cannot bypass ownership or finality checks."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(cleanup_fail=True),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    assert payload["owned_resources"]["before_cleanup_complete"] is True
    forged = copy.deepcopy(payload)
    terminal = forged["owned_resources"]["cleanup_actions"][-1]
    if mutation == "before_owner":
        gui_image = forged["invocation"]["gui_image"]
        forged["owned_resources"]["before_cleanup_complete"] = False
        terminal.update(
            {
                "resource_kind": "image",
                "resource_name": gui_image,
                "argv": ["docker", "image", "rm", gui_image],
            }
        )
        for field in docker_status._STRICT_CLEANUP_PROJECTION:
            if field in terminal:
                forged["cleanup"][field] = terminal[field]
            else:
                forged["cleanup"].pop(field, None)
    else:
        forged["owned_resources"]["after_cleanup_complete"] = True
        forged["owned_resources"]["after_cleanup"] = []
    with pytest.raises(ValueError, match="complete|before|after|owner|cleanup|remove"):
        validator(forged)


def test_task19c_r3_f05b_headless_api_health_binds_primary_container(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Headless API-health failure evidence cannot target an alternate container."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(fail_at="api_health"),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    assert payload["headless_health"]["boundary"] == "api_health"
    assert payload["headless_health"]["execution"] == "command"
    forged = copy.deepcopy(payload)
    imported = forged["invocation"]["compose_project"] + "-imported-judge-1"
    forged["headless_health"]["argv"] = docker_status._strict_api_command(
        imported, "api-health"
    )
    with pytest.raises(ValueError, match="primary|headless|container|canonical|argv"):
        validator(forged)


@pytest.mark.parametrize("phase", ["static_contract", "headless_build", "headless_health"])
def test_task19c_r3_a1_cleanup_failed_retains_predecessor_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    phase: str,
) -> None:
    """A cleanup terminal cannot erase a pass-shaped predecessor phase."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(cleanup_fail=True),
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    assert payload["reason"] == "cleanup_failed"
    assert payload["cleanup"]["status"] == "fail"
    forged = copy.deepcopy(payload)
    forged[phase] = docker_verify._not_run_record("phase was not reached")
    with pytest.raises(ValueError, match="prefix|predecessor|phase|cleanup"):
        validator(forged)


@pytest.mark.parametrize("running_phase", ["initial", "requery"])
def test_task19c_r3_c1_owned_running_containers_stop_before_remove(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    running_phase: str,
) -> None:
    """Owned imported/GUI containers are stopped before any cleanup removal."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)

    class RunningContainerRunner(_LiveVerifierRunner):
        def __init__(self, phase: str) -> None:
            super().__init__()
            self.phase = phase
            self.cleanup_inspects = 0
            self.stopped: set[str] = set()
            self.cleanup_stops: list[str] = []

        def __call__(
            self,
            argv: list[str],
            cwd: Path,
            *,
            env: dict[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
            if argv[:3] == ["docker", "container", "stop"]:
                name = argv[-1]
                if "export" in self.events:
                    self.cleanup_stops.append(name)
                self.stopped.add(name)
            result = super().__call__(argv, cwd, env=env)
            typed_container_inspect = (
                len(argv) == 4
                and argv[0] == "docker"
                and argv[2] == "inspect"
            )
            if typed_container_inspect and self.image_identity_seen:
                self.cleanup_inspects += 1
                inventory_number = (self.cleanup_inspects - 1) // 9
                name = argv[-1]
                target = argv[1] == "container" and name.endswith(
                    ("-imported-judge-1", "-judge-gui-1")
                )
                running = (
                    target
                    and name not in self.stopped
                    and (
                        (self.phase == "initial" and inventory_number == 0)
                        or (self.phase == "requery" and inventory_number >= 1)
                    )
                )
                values = json.loads(result.stdout)
                if values:
                    values[0]["State"] = {"Running": running}
                    result.stdout = json.dumps(values)
            return result

    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    runner = RunningContainerRunner(running_phase)
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=runner,
        include_gui=True,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    validator(payload)
    expected = {
        "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1",
        "ca-mp-task19-a1b2c3d4e5f6-judge-gui-1",
    }
    assert expected.issubset(set(runner.stopped))
    cleanup_actions = payload["owned_resources"]["cleanup_actions"]
    rm_positions = {
        action["resource_name"]: index
        for index, action in enumerate(cleanup_actions)
        if action.get("action_kind") == "remove"
        and action.get("resource_kind") == "container"
    }
    assert expected.issubset(rm_positions)
    for name in expected:
        stop_positions = [
            index
            for index, action in enumerate(cleanup_actions)
            if action.get("action_kind") == "stop"
            and action.get("status") == "pass"
            and action.get("resource_name") == name
        ]
        assert stop_positions and max(stop_positions) < rm_positions[name]


def test_task19c_r3_c2_not_run_requires_exact_attempted_cli_argv(
    tmp_path: Path,
) -> None:
    """A CLI-unavailable envelope must retain the attempted probe argv."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)

    def unavailable(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> object:
        if argv == ["docker", "--version"]:
            raise OSError("docker unavailable")
        return _completed(argv)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=unavailable,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    docker_status.validate_live_verifier_evidence(payload)
    forged = copy.deepcopy(payload)
    forged["cli"]["argv"] = []
    with pytest.raises(ValueError, match="argv|query|capabilit|not.?run"):
        docker_status.validate_live_verifier_evidence(forged)


@pytest.mark.parametrize(
    ("capability", "failure_mode"),
    [
        ("cli", "command"),
        ("cli", "internal_error"),
        ("daemon", "command"),
        ("daemon", "internal_error"),
    ],
    ids=[
        "cli-command",
        "cli-internal-error",
        "daemon-command",
        "daemon-internal-error",
    ],
)
def test_task19c_r3_i5_i6_failed_capability_has_no_version(
    tmp_path: Path,
    capability: str,
    failure_mode: str,
) -> None:
    """Failed capability carriers cannot claim an observed version."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)

    def capability_failure(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> object:
        is_target = (
            capability == "cli"
            and argv == ["docker", "--version"]
        ) or (
            capability == "daemon"
            and argv == ["docker", "info", "--format", "{{json .ServerVersion}}"]
        )
        if is_target:
            if failure_mode == "internal_error":
                raise RuntimeError("capability probe failed")
            return _completed(argv, returncode=2, stderr="probe failed")
        result = _completed(argv)
        if argv == ["docker", "--version"]:
            result.stdout = "Docker version 27.0.0, build capability-test"
        elif argv[:2] == ["docker", "info"]:
            result.stdout = '"27.0.0"'
        return result

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=capability_failure,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    assert payload["status"] == "fail"
    expected_reason = (
        "docker_cli_failed" if capability == "cli" else "docker_daemon_failed"
    )
    assert payload["reason"] == expected_reason
    docker_status.validate_live_verifier_evidence(payload)
    forged = copy.deepcopy(payload)
    forged[capability]["version"] = "27.0.0"
    with pytest.raises(ValueError, match="version|capabilit|failure"):
        docker_status.validate_live_verifier_evidence(forged)


def test_task19c_r3_include_gui_static_failure_keeps_profile_argv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An early GUI-scoped Compose failure retains its honest profile argv."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=_LiveVerifierRunner(semantic_mismatch_at="config_json"),
        include_gui=True,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    assert payload["reason"] == "compose_contract_failed"
    assert payload["static_contract"]["argv"] == [
        "docker",
        "compose",
        "--project-name",
        "ca-mp-task19-a1b2c3d4e5f6",
        "--profile",
        "gui",
        "config",
        "--format",
        "json",
    ]
    validator(payload)


def _task19c_r4_producer_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    command_runner: object,
    *,
    include_gui: bool = False,
) -> dict[str, object]:
    """Produce strict live evidence without exercising a real Docker daemon."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    validator = docker_status.validate_live_verifier_evidence
    monkeypatch.setattr(
        docker_status, "validate_live_verifier_evidence", lambda _payload: None
    )
    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=command_runner,
        include_gui=include_gui,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    monkeypatch.setattr(docker_status, "validate_live_verifier_evidence", validator)
    return payload


@pytest.mark.parametrize(
    ("running_phase", "mutation"),
    [("initial", "late-stop"), ("requery", "missing-stop")],
    ids=["initial-stop-moved-after-remove", "requery-stop-deleted"],
)
def test_task19c_r4_c1_cleanup_observation_binds_stop_before_remove(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    running_phase: str,
    mutation: str,
) -> None:
    """A running container's observed stop must precede its own removal."""
    target = "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1"

    class RunningContainerRunner(_LiveVerifierRunner):
        def __init__(self, phase: str) -> None:
            super().__init__()
            self.phase = phase
            self.cleanup_inspects = 0
            self.stopped: set[str] = set()

        def __call__(
            self,
            argv: list[str],
            cwd: Path,
            *,
            env: dict[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
            in_cleanup_inventory = (
                self.image_identity_seen
                and len(argv) == 4
                and argv[0] == "docker"
                and argv[1] in {"container", "network", "volume", "image"}
                and argv[2] == "inspect"
            )
            if argv[:3] == ["docker", "container", "stop"]:
                self.stopped.add(argv[-1])
            result = super().__call__(argv, cwd, env=env)
            if in_cleanup_inventory:
                self.cleanup_inspects += 1
                inventory_round = (self.cleanup_inspects - 1) // 9
                if argv[1] == "container" and argv[-1] == target:
                    values = json.loads(result.stdout)
                    if values:
                        running = (
                            inventory_round == 0
                            if self.phase == "initial"
                            else inventory_round >= 1 and target not in self.stopped
                        )
                        values[0]["State"] = {"Running": running}
                        result.stdout = json.dumps(values)
            return result

    payload = _task19c_r4_producer_payload(
        monkeypatch,
        tmp_path,
        RunningContainerRunner(running_phase),
        include_gui=True,
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    actions = forged["owned_resources"]["cleanup_actions"]
    stop_index = next(
        index
        for index, action in enumerate(actions)
        if action["action_kind"] == "stop"
        and action["status"] == "pass"
        and action["resource_name"] == target
    )
    if mutation == "late-stop":
        stop = actions.pop(stop_index)
        remove_index = next(
            index
            for index, action in enumerate(actions)
            if action["action_kind"] == "remove"
            and action["resource_kind"] == "container"
            and action["resource_name"] == target
        )
        actions.insert(remove_index + 1, stop)
    else:
        actions.pop(stop_index)
    with pytest.raises(ValueError, match="stop|running|observ|chronolog|cleanup"):
        validator(forged)


def test_task19c_r4_f11c_complete_after_inventory_excludes_successful_removes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A complete after inventory cannot retain an already removed resource."""

    class LaterRemoveFailureRunner(_LiveVerifierRunner):
        def __init__(self) -> None:
            super().__init__()
            self.remove_count = 0

        def __call__(
            self,
            argv: list[str],
            cwd: Path,
            *,
            env: dict[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
            if len(argv) == 4 and argv[:3] == ["docker", "container", "rm"]:
                self.remove_count += 1
                if self.remove_count == 2:
                    return _completed(argv, returncode=19, stderr="later remove failed")
            return super().__call__(argv, cwd, env=env)

    payload = _task19c_r4_producer_payload(
        monkeypatch, tmp_path, LaterRemoveFailureRunner()
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    assert payload["owned_resources"]["after_cleanup_complete"] is True
    successful = next(
        action
        for action in payload["owned_resources"]["cleanup_actions"]
        if action["action_kind"] == "remove" and action["status"] == "pass"
    )
    identity = (successful["resource_kind"], successful["resource_name"])
    removed_entry = next(
        entry
        for entry in payload["owned_resources"]["before_cleanup"]
        if (entry["kind"], entry["name"]) == identity
    )
    assert identity not in {
        (entry["kind"], entry["name"])
        for entry in payload["owned_resources"]["after_cleanup"]
    }
    forged = copy.deepcopy(payload)
    forged["owned_resources"]["after_cleanup"].append(
        copy.deepcopy(removed_entry)
    )
    forged["owned_resources"]["after_cleanup"].sort(
        key=lambda entry: (entry["kind"], entry["name"])
    )
    with pytest.raises(ValueError, match="after|complete|remove|cleanup"):
        validator(forged)


@pytest.mark.parametrize(
    "mutation",
    ["retained-incomplete", "final-incomplete", "retained-without-remove"],
)
def test_task19c_r4_f12c_retained_and_final_terminals_bind_completeness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    """Retained and final cleanup terminals cannot weaken their closure proof."""

    class FinalInventoryFailureRunner(_LiveVerifierRunner):
        def __init__(self) -> None:
            super().__init__()
            self.cleanup_inspects = 0
            self.empty_inventory_groups = 0

        def __call__(
            self,
            argv: list[str],
            cwd: Path,
            *,
            env: dict[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
            in_cleanup_inventory = (
                self.image_identity_seen
                and len(argv) == 4
                and argv[0] == "docker"
                and argv[1] in {"container", "network", "volume", "image"}
                and argv[2] == "inspect"
            )
            if in_cleanup_inventory:
                self.cleanup_inspects += 1
                within_inventory = ((self.cleanup_inspects - 1) % 9) + 1
                if not self.resources and within_inventory == 1:
                    self.empty_inventory_groups += 1
                if self.empty_inventory_groups == 2 and within_inventory == 1:
                    raise OSError("final inventory unavailable")
            return super().__call__(argv, cwd, env=env)

    if mutation == "final-incomplete":
        payload = _task19c_r4_producer_payload(
            monkeypatch, tmp_path, FinalInventoryFailureRunner()
        )
    else:
        payload = _task19c_r4_producer_payload(
            monkeypatch,
            tmp_path,
            _LiveVerifierRunner(retain_after_cleanup=True),
        )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    if mutation == "retained-incomplete":
        assert forged["owned_resources"]["cleanup_actions"][-1]["action_kind"] == (
            "retained_postcondition"
        )
        forged["owned_resources"]["after_cleanup_complete"] = False
        forged["owned_resources"]["after_cleanup"] = []
    elif mutation == "final-incomplete":
        terminal = forged["owned_resources"]["cleanup_actions"][-1]
        assert terminal["action_kind"] == "inventory"
        assert terminal["inventory_stage"] == "final"
        forged["owned_resources"]["after_cleanup_complete"] = True
    else:
        terminal = forged["owned_resources"]["cleanup_actions"][-1]
        assert terminal["action_kind"] == "retained_postcondition"
        identity = (terminal["resource_kind"], terminal["resource_name"])
        remove_index = next(
            index
            for index, action in enumerate(
                forged["owned_resources"]["cleanup_actions"]
            )
            if action["action_kind"] == "remove"
            and action["status"] == "pass"
            and (action["resource_kind"], action["resource_name"]) == identity
        )
        forged["owned_resources"]["cleanup_actions"].pop(remove_index)
    with pytest.raises(ValueError, match="retained|final|complete|after|remove|cleanup"):
        validator(forged)


def test_task19c_r4_f11a_requery_after_prior_remove_is_truthful(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A next-resource requery failure retains its earlier removal evidence."""

    class RequeryAfterRemovalRunner(_LiveVerifierRunner):
        def __init__(self) -> None:
            super().__init__()
            self.cleanup_inspects = 0

        def __call__(
            self,
            argv: list[str],
            cwd: Path,
            *,
            env: dict[str, str] | None = None,
        ) -> subprocess.CompletedProcess[str]:
            in_cleanup_inventory = (
                self.image_identity_seen
                and len(argv) == 4
                and argv[0] == "docker"
                and argv[1] in {"container", "network", "volume", "image"}
                and argv[2] == "inspect"
            )
            if in_cleanup_inventory:
                self.cleanup_inspects += 1
                if self.cleanup_inspects == 28:
                    raise OSError("next-resource requery unavailable")
            return super().__call__(argv, cwd, env=env)

    payload = _task19c_r4_producer_payload(
        monkeypatch, tmp_path, RequeryAfterRemovalRunner()
    )
    terminal = payload["owned_resources"]["cleanup_actions"][-1]
    assert terminal["action_kind"] == "inventory"
    assert terminal["inventory_stage"] == "requery"
    assert any(
        action["action_kind"] == "remove" and action["status"] == "pass"
        for action in payload["owned_resources"]["cleanup_actions"][:-1]
    )
    assert payload["owned_resources"]["before_cleanup_complete"] is True
    assert payload["owned_resources"]["after_cleanup_complete"] is False
    docker_status.validate_live_verifier_evidence(payload)


def test_task19c_r4_a1_image_identity_failure_cannot_be_empty_refusal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An established image cannot be replaced by an empty ownership refusal."""
    payload = _task19c_r4_producer_payload(
        monkeypatch,
        tmp_path,
        _LiveVerifierRunner(fail_at="image_identity"),
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    invocation_id = forged["invocation_id"]
    headless_image = forged["invocation"]["headless_image"]
    terminal = {
        "status": "fail",
        "execution": "safety_refusal",
        "action_kind": "inventory",
        "resource_kind": "image",
        "resource_name": headless_image,
        "required_label": {
            "key": "io.challengecup.task19.invocation",
            "value": invocation_id,
        },
        "argv": [],
        "exit_code": None,
        "stdout_sha256": hashlib.sha256(b"").hexdigest(),
        "stderr_sha256": hashlib.sha256(b"").hexdigest(),
        "inventory_stage": "initial",
        "failure_proof": {
            "kind": "cleanup_ownership_refusal",
            "resource_kind": "image",
            "resource_name": headless_image,
            "required_label": {
                "key": "io.challengecup.task19.invocation",
                "value": invocation_id,
            },
            "observed_ownership": "missing_label",
        },
        "boundary": "cleanup",
    }
    forged["owned_resources"] = {
        "before_cleanup": [],
        "before_cleanup_complete": True,
        "after_cleanup": [],
        "after_cleanup_complete": True,
        "cleanup_actions": [terminal],
    }
    for field in docker_status._STRICT_CLEANUP_PROJECTION:
        if field in terminal:
            forged["cleanup"][field] = terminal[field]
        else:
            forged["cleanup"].pop(field, None)
    with pytest.raises(ValueError, match="image|cleanup|owned|headless|inventory"):
        validator(forged)


@pytest.mark.parametrize(
    ("capability", "mutation"),
    [
        ("cli", "exit-code"),
        ("cli", "stream"),
        ("daemon", "exit-code"),
        ("daemon", "stream"),
    ],
)
def test_task19c_r4_c2_unavailable_capability_binds_no_result_shape(
    tmp_path: Path,
    capability: str,
    mutation: str,
) -> None:
    """An unavailable capability exception has no exit result or stream bytes."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)
    target = (
        ["docker", "--version"]
        if capability == "cli"
        else ["docker", "info", "--format", "{{json .ServerVersion}}"]
    )

    def unavailable(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> object:
        if argv == target:
            raise OSError("capability unavailable")
        result = _completed(argv)
        if argv == ["docker", "--version"]:
            result.stdout = "Docker version 27.0.0, build unit-test"
        return result

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=unavailable,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    if mutation == "exit-code":
        forged[capability]["exit_code"] = 19
    else:
        forged[capability]["stdout_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="capabilit|not.?run|exit|stream|untouched"):
        validator(forged)


def test_task19c_r4_c2_cli_failure_keeps_daemon_exactly_untouched(
    tmp_path: Path,
) -> None:
    """A CLI command failure cannot imply that a daemon probe was attempted."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)

    def cli_failure(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> object:
        if argv == ["docker", "--version"]:
            return _completed(argv, returncode=2, stderr="CLI probe failed")
        return _completed(argv)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=cli_failure,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    forged["daemon"]["argv"] = [
        "docker",
        "info",
        "--format",
        "{{json .ServerVersion}}",
    ]
    with pytest.raises(ValueError, match="daemon|untouched|capabilit|argv"):
        validator(forged)


def test_task19c_r4_c2_capability_reason_matches_failed_carrier(
    tmp_path: Path,
) -> None:
    """A daemon failure cannot be relabeled as a CLI failure."""
    (tmp_path / "data" / "intersection_data").mkdir(parents=True)

    def daemon_failure(
        argv: list[str], _root: Path, **_kwargs: object
    ) -> object:
        if argv == ["docker", "--version"]:
            result = _completed(argv)
            result.stdout = "Docker version 27.0.0, build unit-test"
            return result
        if argv == ["docker", "info", "--format", "{{json .ServerVersion}}"]:
            return _completed(argv, returncode=2, stderr="daemon probe failed")
        return _completed(argv)

    payload = docker_verify._verify_live(
        tmp_path,
        Path("output/evidence/docker/live"),
        command_runner=daemon_failure,
        invocation_id="a1b2c3d4e5f6",
        expected_root=tmp_path,
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    assert payload["reason"] == "docker_daemon_failed"
    forged = copy.deepcopy(payload)
    forged["reason"] = "docker_cli_failed"
    with pytest.raises(ValueError, match="CLI|daemon|carrier|capabilit|reason"):
        validator(forged)


@pytest.mark.parametrize("rooted_path", [r"\Users\judge", "//server/share"])
def test_task19c_r4_a7b_rejects_rooted_windows_and_network_host_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    rooted_path: str,
) -> None:
    """Strict public fields reject drive-less Windows and slash-slash roots."""
    payload = _task19c_r4_producer_payload(
        monkeypatch, tmp_path, _LiveVerifierRunner()
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    forged["headless_build"]["detail"] = rooted_path
    with pytest.raises(ValueError, match="private|absolute path|privacy"):
        validator(forged)


def test_task19c_r4_i3_run_tree_copy_binds_exact_canonical_argv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A successful run-tree copy cannot cite a foreign Docker source."""
    payload = _task19c_r4_producer_payload(
        monkeypatch, tmp_path, _LiveVerifierRunner()
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    unit = next(
        unit
        for unit in forged["exported_evidence"]["export_units"]
        if unit["kind"] == "run_tree" and unit["scope"] == "headless"
    )
    unit["record"]["argv"] = [
        "docker",
        "cp",
        "foreign-container:/app/output/runs/i1/fixed_time/x1/s42/111111111111/.",
        unit["record"]["argv"][-1],
    ]
    with pytest.raises(ValueError, match="copy|run.tree|argv|canonical|export"):
        validator(forged)


def test_task19c_r4_m2_cleanup_verifier_proof_observed_is_exact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Retained cleanup evidence cannot replace its observed postcondition."""
    payload = _task19c_r4_producer_payload(
        monkeypatch,
        tmp_path,
        _LiveVerifierRunner(retain_after_cleanup=True),
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    terminal = forged["owned_resources"]["cleanup_actions"][-1]
    assert terminal["action_kind"] == "retained_postcondition"
    terminal["failure_proof"]["observed"] = "unrelated_observation"
    forged["cleanup"]["failure_proof"]["observed"] = "unrelated_observation"
    with pytest.raises(ValueError, match="proof|observed|retained|cleanup"):
        validator(forged)


def test_task19c_r5_strict_collision_preflight_cannot_precede_workflow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A detected pre-mutation collision cannot coexist with later workflow proof."""
    payload = _task19c_r4_producer_payload(
        monkeypatch,
        tmp_path,
        _LiveVerifierRunner(fail_at="start"),
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    assert payload["reason"] == "headless_start_failed"
    assert payload["headless_build"]["status"] == "pass"
    forged = copy.deepcopy(payload)
    project = forged["invocation"]["compose_project"]
    forged["name_collisions"]["before"] = [
        {"kind": "container", "name": f"{project}-judge-1", "labels": {}}
    ]

    with pytest.raises(ValueError, match="collision|preflight|lifecycle"):
        validator(forged)


@pytest.mark.parametrize(
    "phase",
    ["headless_health", "headless_smoke", "cleanup"],
)
def test_task19c_r5_strict_pass_rejects_phase_before_lifecycle_predecessor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    phase: str,
) -> None:
    """An executed phase cannot be claimed before its lifecycle predecessor."""
    payload = _task19c_r4_producer_payload(
        monkeypatch, tmp_path, _LiveVerifierRunner()
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    forged[phase]["started_at"] = "2000-01-01T00:00:00+00:00"
    forged[phase]["finished_at"] = "2000-01-01T00:00:01+00:00"

    with pytest.raises(ValueError, match="chronology|lifecycle|predecessor"):
        validator(forged)


def test_task19c_r5_strict_pass_requires_export_before_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A cleanup phase cannot precede the evidence-export commands it depends on."""
    payload = _task19c_r4_producer_payload(
        monkeypatch, tmp_path, _LiveVerifierRunner()
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    export_record = next(
        unit["record"]
        for unit in forged["exported_evidence"]["export_units"]
        if "record" in unit
    )
    export_record["started_at"] = "2999-01-01T00:00:00+00:00"
    export_record["finished_at"] = "2999-01-01T00:00:01+00:00"

    with pytest.raises(ValueError, match="export.*cleanup|chronology|lifecycle"):
        validator(forged)


def test_task19c_r5_strict_pass_retains_canonical_primary_api_health(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Primary health proof includes the successful exact /api/health transcript."""
    payload = _task19c_r4_producer_payload(
        monkeypatch, tmp_path, _LiveVerifierRunner()
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    primary = payload["invocation"]["compose_project"] + "-judge-1"
    assert "api_health" in payload["headless_health"]
    api_health = payload["headless_health"]["api_health"]
    assert api_health["argv"] == docker_status._strict_api_command(
        primary, "api-health"
    )
    assert api_health["stdout_sha256"] == hashlib.sha256(
        b'{"run_workers":1,"status":"ok"}\n'
    ).hexdigest()
    forged = copy.deepcopy(payload)
    forged["headless_health"]["api_health"]["stdout_sha256"] = hashlib.sha256(
        b'{"status":"wrong"}\n'
    ).hexdigest()

    with pytest.raises(ValueError, match="health|canonical|stdout"):
        validator(forged)


@pytest.mark.parametrize(
    ("record_path", "forged_stdout"),
    [
        (("headless_health",), b"unhealthy\n"),
        (("save_load_proof", "imported_docker_health"), b"unhealthy\n"),
        (("save_load_proof", "imported_api_health"), b'{"status":"wrong"}\n'),
    ],
    ids=["primary-docker-health", "imported-docker-health", "imported-api-health"],
)
def test_task19c_r5_strict_pass_rejects_nonhealthy_success_transcript(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    record_path: tuple[str, ...],
    forged_stdout: bytes,
) -> None:
    """A successful health record cannot claim the digest of a known bad result."""
    payload = _task19c_r4_producer_payload(
        monkeypatch, tmp_path, _LiveVerifierRunner()
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    record: object = forged
    for key in record_path:
        record = record[key]
    record["stdout_sha256"] = hashlib.sha256(forged_stdout).hexdigest()

    with pytest.raises(ValueError, match="health|canonical|stdout"):
        validator(forged)


def _task19c_r6_shift_timestamp(value: str, seconds: int) -> str:
    stamp = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    return (stamp + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_task19c_r6_i1_strict_pass_rejects_failed_nested_export_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A completed export unit cannot embed a failed docker cp command."""
    payload = _task19c_r4_producer_payload(
        monkeypatch, tmp_path, _LiveVerifierRunner()
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    unit = next(
        unit
        for unit in forged["exported_evidence"]["export_units"]
        if unit["kind"] == "run_tree" and unit["scope"] == "headless"
    )
    unit["record"]["status"] = "fail"
    unit["record"]["exit_code"] = 1
    unit["record"]["boundary"] = "evidence_export"

    with pytest.raises(ValueError, match="successful copy|record|command"):
        validator(forged)


def test_task19c_r6_i2_strict_privacy_masks_only_container_path_tokens(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A public container path must not exempt a trailing host path."""
    payload = _task19c_r4_producer_payload(
        monkeypatch, tmp_path, _LiveVerifierRunner()
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    forged["headless_build"]["detail"] = (
        "judge:/app/output/evidence /Users/alice"
    )

    with pytest.raises(ValueError, match="private|absolute path|privacy"):
        validator(forged)


class _Task19cR6PinnedCleanupClock:
    """Fake monotonic timeline used only while cleanup runs."""

    def __init__(self, wall_clock: Callable[[], str]) -> None:
        self._wall_clock = wall_clock
        self._anchor = (
            datetime.now(timezone.utc) + timedelta(minutes=10)
        ).replace(microsecond=0)
        self.ticks = 0

    def wall(self) -> str:
        return self._wall_clock()

    def next_tick(self) -> str:
        self.ticks += 1
        stamp = self._anchor + timedelta(seconds=self.ticks)
        return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _task19c_r6_pinned_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_Task19cR6PinnedCleanupClock, dict[str, object]]:
    """Route only cleanup-scoped timestamps onto the fake timeline."""
    clock = _Task19cR6PinnedCleanupClock(docker_verify._timestamp)
    state: dict[str, object] = {"inside_cleanup": False}
    original_cleanup_owned = docker_verify._cleanup_owned
    # _unexpected_cleanup_failure also runs after the cleanup wrapper has
    # reset the flag, so it is wrapped too: its fallback stamps must stay on
    # the fake axis, or a reverted fix would be compared against wall time.
    original_unexpected = docker_verify._unexpected_cleanup_failure

    def pinned_timestamp() -> str:
        if not state["inside_cleanup"]:
            return clock.wall()
        return clock.next_tick()

    def cleanup_owned_with_pinned_clock(*args: object, **kwargs: object):
        state["inside_cleanup"] = True
        try:
            return original_cleanup_owned(*args, **kwargs)
        finally:
            state["inside_cleanup"] = False

    def unexpected_with_pinned_clock(*args: object, **kwargs: object):
        state["inside_cleanup"] = True
        try:
            return original_unexpected(*args, **kwargs)
        finally:
            state["inside_cleanup"] = False

    monkeypatch.setattr(docker_verify, "_timestamp", pinned_timestamp)
    monkeypatch.setattr(
        docker_verify, "_cleanup_owned", cleanup_owned_with_pinned_clock
    )
    monkeypatch.setattr(
        docker_verify,
        "_unexpected_cleanup_failure",
        unexpected_with_pinned_clock,
    )
    return clock, state


class _Task19cR6TickingCleanupRunner(_LiveVerifierRunner):
    """Advance the fake timeline during every cleanup-scoped command."""

    def __init__(
        self,
        clock: _Task19cR6PinnedCleanupClock,
        state: dict[str, object],
    ) -> None:
        super().__init__()
        self._clock = clock
        self._state = state

    def __call__(
        self,
        argv: list[str],
        cwd: Path,
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if self._state["inside_cleanup"]:
            self._clock.ticks += 50
        return super().__call__(argv, cwd, env=env)


def test_task19c_r6_i3_strict_export_cannot_outlive_real_cleanup_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Exports finishing after real teardown begins violate cleanup ordering."""
    clock, state = _task19c_r6_pinned_cleanup(monkeypatch)
    payload = _task19c_r4_producer_payload(
        monkeypatch,
        tmp_path,
        _Task19cR6TickingCleanupRunner(clock, state),
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    # Anchor-relative moment right after real teardown begins: inside the
    # reopened blind spot if a future regression drops the entry sampling,
    # yet strictly past the honest cleanup start the fixed producer reports.
    teardown_zone = (
        clock._anchor + timedelta(seconds=90)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    forged_unit = next(
        unit
        for unit in forged["exported_evidence"]["export_units"]
        if "record" in unit
    )
    forged_unit["record"]["finished_at"] = teardown_zone

    with pytest.raises(ValueError, match="cleanup|export"):
        validator(forged)


def test_task19c_r6_i3b_interrupted_cleanup_export_respects_real_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Interrupted-run cleanup projections inherit the real entry stamp."""
    clock, state = _task19c_r6_pinned_cleanup(monkeypatch)
    # _cleanup_owned guards every runner call, so the only way to reach the
    # _unexpected_cleanup_failure catch-all is an interrupt raised between
    # statements — here during ledger action construction, which has no guard.
    original_inventory_action = docker_verify._cleanup_inventory_action

    def interrupting_inventory_action(*args: object, **kwargs: object):
        if state["inside_cleanup"]:
            raise KeyboardInterrupt("ctrl-c between cleanup statements")
        return original_inventory_action(*args, **kwargs)

    monkeypatch.setattr(
        docker_verify,
        "_cleanup_inventory_action",
        interrupting_inventory_action,
    )
    payload = _task19c_r4_producer_payload(
        monkeypatch,
        tmp_path,
        _Task19cR6TickingCleanupRunner(clock, state),
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    assert payload["status"] == "fail"
    assert payload["cleanup"]["status"] == "fail"
    # Pins the catch-all projection path, not any guarded stop/rm failure.
    assert (
        payload["cleanup"]["detail"]
        == "cleanup failed before terminal evidence was returned"
    )
    forged = copy.deepcopy(payload)
    teardown_zone = (
        clock._anchor + timedelta(seconds=90)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    forged_unit = next(
        unit
        for unit in forged["exported_evidence"]["export_units"]
        if "record" in unit
    )
    forged_unit["record"]["finished_at"] = teardown_zone

    with pytest.raises(ValueError, match="cleanup|export"):
        validator(forged)


@pytest.mark.parametrize("anchor", ["headless_smoke", "cleanup"])
def test_task19c_r6_i4_strict_api_health_follows_lifecycle_chronology(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    anchor: str,
) -> None:
    """Nested primary API health cannot drift past later lifecycle phases."""
    payload = _task19c_r4_producer_payload(
        monkeypatch, tmp_path, _LiveVerifierRunner()
    )
    validator = docker_status.validate_live_verifier_evidence
    validator(payload)
    forged = copy.deepcopy(payload)
    moved = _task19c_r6_shift_timestamp(forged[anchor]["finished_at"], 10)
    api_health = forged["headless_health"]["api_health"]
    api_health["started_at"] = moved
    api_health["finished_at"] = _task19c_r6_shift_timestamp(moved, 1)

    with pytest.raises(ValueError, match="chronology|lifecycle|health"):
        validator(forged)
