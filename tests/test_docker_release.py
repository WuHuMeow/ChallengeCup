"""Behavioral tests for non-mutating Docker release evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

import pytest

from scripts.release import docker_status


def _completed(
    argv: list[str],
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout, stderr)


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
    tar_path = (
        "output/evidence/docker/live/a1b2c3d4e5f6/headless-image.tar"
    )
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
                    "image": (
                        "ca-mp-task19-a1b2c3d4e5f6-headless:local"
                    ),
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": (
                            "a1b2c3d4e5f6"
                        )
                    },
                    "additional_contexts": {},
                },
                {
                    "name": "judge-gui",
                    "image": "ca-mp-task19-a1b2c3d4e5f6-gui:local",
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": (
                            "a1b2c3d4e5f6"
                        )
                    },
                    "additional_contexts": {
                        "judge_base": "service:judge"
                    },
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
                    "image": (
                        "ca-mp-task19-a1b2c3d4e5f6-headless:local"
                    ),
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": (
                            "a1b2c3d4e5f6"
                        )
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
                "resource_name": (
                    "ca-mp-task19-a1b2c3d4e5f6_judge-output"
                ),
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
    for later in order[index + 1:]:
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
    tar_path = (
        "output/evidence/docker/live/a1b2c3d4e5f6/headless-image.tar"
    )
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


def test_validator_rejects_round4_3_complete_pass_suffix_after_failure(
) -> None:
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
        payload["headless_health"] = copy.deepcopy(
            complete["headless_health"]
        )
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
def test_validator_rejects_round4_3_nonterminal_cleanup_failure_action(
) -> None:
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
        action["argv"].append(
            "ca-mp-task19-a1b2c3d4e5f6-imported-judge-1"
        )
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
            if record["name"]
            != "ca-mp-task19-a1b2c3d4e5f6_judge-output"
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
        "labels": {
            "io.challengecup.task19.invocation": "a1b2c3d4e5f6"
        },
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


def test_validator_rejects_round4_3_open_cleanup_action_failure_proof(
) -> None:
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
                    "image": (
                        "ca-mp-task19-a1b2c3d4e5f6-headless:local"
                    ),
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": (
                            "a1b2c3d4e5f6"
                        )
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
                    "image": (
                        "ca-mp-task19-a1b2c3d4e5f6-headless:local"
                    ),
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": (
                            "a1b2c3d4e5f6"
                        )
                    },
                    "additional_contexts": {},
                },
                {
                    "name": "judge-gui",
                    "image": "ca-mp-task19-a1b2c3d4e5f6-gui:local",
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": (
                            "a1b2c3d4e5f6"
                        )
                    },
                    "additional_contexts": {
                        "judge_base": "service:judge"
                    },
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
    argv[build_index + 1:] = services

    with pytest.raises(ValueError, match="service"):
        docker_status.validate_evidence(payload)


@pytest.mark.parametrize(
    ("case", "argv"),
    [
        (
            "duplicate-platform",
            [
                "docker", "build", "--platform", "linux/amd64",
                "--platform", "linux/amd64", "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local", ".",
            ],
        ),
        (
            "conflicting-platform",
            [
                "docker", "build", "--platform", "linux/amd64",
                "--platform=linux/arm64", "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local", ".",
            ],
        ),
        (
            "missing-tag",
            ["docker", "build", "--platform", "linux/amd64", "."],
        ),
        (
            "inline-tag",
            [
                "docker", "build", "--platform", "linux/amd64",
                "-t=ca-mp-task19-a1b2c3d4e5f6-headless:local", ".",
            ],
        ),
        (
            "duplicate-tag",
            [
                "docker", "build", "--platform", "linux/amd64", "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local", "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local", ".",
            ],
        ),
        (
            "conflicting-tag",
            [
                "docker", "build", "--platform", "linux/amd64", "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local",
                "--tag=foreign:local", ".",
            ],
        ),
        (
            "foreign-tag",
            [
                "docker", "build", "--platform", "linux/amd64", "-t",
                "foreign:local", ".",
            ],
        ),
        (
            "compose-mixed",
            [
                "docker", "build", "compose", "--platform", "linux/amd64",
                "-t", "ca-mp-task19-a1b2c3d4e5f6-headless:local", ".",
            ],
        ),
        (
            "foreign-context",
            [
                "docker", "build", "--platform", "linux/amd64", "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local", "other",
            ],
        ),
        (
            "non-final-context",
            [
                "docker", "build", "--platform", "linux/amd64", "-t",
                "ca-mp-task19-a1b2c3d4e5f6-headless:local", ".", "--pull",
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
            "docker", "build", "-t",
            "ca-mp-task19-a1b2c3d4e5f6-headless:local", ".",
        ],
        [
            "docker", "build", "--platform=linux/amd64", "-t",
            "ca-mp-task19-a1b2c3d4e5f6-headless:local", ".",
        ],
        [
            "docker", "build", "--platform", "linux/arm64", "-t",
            "ca-mp-task19-a1b2c3d4e5f6-headless:local", ".",
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
                "docker", "compose", "--project-name", "foreign",
                "config", "--quiet",
            ],
        ),
        (
            "headless-profile",
            [
                "docker", "compose", "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6", "--profile", "gui",
                "config", "--quiet",
            ],
        ),
        (
            "headless-inline-project",
            [
                "docker", "compose",
                "--project-name=ca-mp-task19-a1b2c3d4e5f6",
                "config", "--quiet",
            ],
        ),
        (
            "headless-extra",
            [
                "docker", "compose", "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6", "config", "--quiet", "extra",
            ],
        ),
        (
            "gui-missing-profile",
            [
                "docker", "compose", "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6", "config", "--quiet",
            ],
        ),
        (
            "gui-foreign-profile",
            [
                "docker", "compose", "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6", "--profile", "other",
                "config", "--quiet",
            ],
        ),
        (
            "gui-inline-profile",
            [
                "docker", "compose", "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6", "--profile=gui",
                "config", "--quiet",
            ],
        ),
        (
            "gui-duplicate-profile",
            [
                "docker", "compose", "--project-name",
                "ca-mp-task19-a1b2c3d4e5f6", "--profile", "gui",
                "--profile", "gui", "config", "--quiet",
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
        services[1]["image"] = (
            "ca-mp-task19-a1b2c3d4e5f6-gui:latest"
        )
    elif case == "foreign-platform":
        services[0]["platform"] = "linux/arm64"
    elif case == "missing-ownership-label":
        services[0]["labels"] = {}
    else:
        services[0]["labels"][
            "io.challengecup.task19.invocation"
        ] = "foreign"

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
    services = payload["static_contract"]["render_proof"][
        "selected_facts"
    ]["services"]
    if case == "headless-present":
        services[0]["additional_contexts"] = {
            "foreign": "service:judge-gui"
        }
    elif case == "gui-missing":
        services[1]["additional_contexts"] = {}
    elif case == "gui-foreign":
        services[1]["additional_contexts"]["judge_base"] = (
            "service:foreign"
        )
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
        payload["static_contract"]["render_proof"]["argv"][3] = (
            "foreign"
        )
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


def test_validator_rejects_cleanup_failure_with_unpaired_compose_build(
) -> None:
    """A successful Compose build requires successful static render proof."""
    payload = _cleanup_only_failure_evidence()
    empty_sha256 = (
        "e3b0c44298fc1c149afbf4c8996fb924"
        "27ae41e4649b934ca495991b7852b855"
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
                    "image": (
                        "ca-mp-task19-a1b2c3d4e5f6-headless:local"
                    ),
                    "platform": "linux/amd64",
                    "labels": {
                        "io.challengecup.task19.invocation": (
                            "a1b2c3d4e5f6"
                        )
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
    payload["headless_smoke"]["api_proof"]["request"]["body"].pop(
        "steps"
    )
    payload["quick_smoke"]["request"]["body"].pop("steps")

    with pytest.raises(ValueError, match="exactly 100 steps"):
        docker_status.validate_evidence(payload)


def test_validator_accepts_cleanup_only_failure_after_valid_api_results(
) -> None:
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
def test_validator_rejects_cleanup_failure_with_foreign_primary_api_path(
) -> None:
    payload = _cleanup_only_failure_evidence()
    payload["headless_smoke"]["api_proof"]["request"]["path"] = (
        "/api/runs/foreign-run-8c2d1e5f"
    )

    with pytest.raises(ValueError):
        docker_status.validate_evidence(payload)


# Production mutation caught: nested imported API evidence escaping the
# API-result record metadata contract on a later cleanup failure.
def test_validator_rejects_cleanup_failure_with_imported_api_command(
) -> None:
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
def test_validator_rejects_cleanup_failure_with_unknown_save_load_field(
) -> None:
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
def test_validator_rejects_cleanup_failure_with_foreign_save_summary(
) -> None:
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
def test_validator_rejects_cleanup_failure_with_unrelated_save_summary(
) -> None:
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
            "output/evidence/docker/live/a1b2c3d4e5f6/"
            "headless-image.tar",
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
def test_validator_rejects_cleanup_failure_with_reused_api_response_hash(
) -> None:
    payload = _cleanup_only_failure_evidence()
    primary = payload["headless_smoke"]["api_proof"]
    imported = payload["save_load_proof"]["repeated_smoke"]["api_proof"]
    imported["response"]["body_sha256"] = primary["response"][
        "body_sha256"
    ]

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
    payload["headless_smoke"]["api_proof"]["request"]["path"] = (
        "/api/runs/foreign-run-8c2d1e5f"
    )

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
    payload["headless_smoke"]["api_proof"]["output"]["run_id"] = (
        "foreign-run-8c2d1e5f"
    )

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
def test_validator_rejects_imported_smoke_without_independent_api_proof(
) -> None:
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
def test_validator_rejects_imported_api_smoke_with_reused_response_hash(
) -> None:
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
    payload["save_load_proof"]["repeated_smoke"]["api_proof"]["image"] = (
        "ca-mp-task19-a1b2c3d4e5f6-headless:local"
    )

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
def test_validator_rejects_imported_api_smoke_with_reused_terminal_hash(
) -> None:
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
def test_validator_rejects_pass_with_uncompleted_quick_smoke_terminal(
) -> None:
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
    payload["save_load_proof"]["repeated_health"]["argv"][-1] = (
        "ca-mp-task19-a1b2c3d4e5f6-judge-1"
    )

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


def test_independent_handwritten_live_pass_with_gui_fixture_validates(
) -> None:
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


def test_validator_rejects_round4_4_frame_proof_after_gui_smoke_not_run(
) -> None:
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
    services = payload["static_contract"]["render_proof"][
        "selected_facts"
    ]["services"]
    services[1]["image"] = "foreign-gui-image:local"

    with pytest.raises(ValueError, match="render selected service image"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting a GUI API result that targets a
# foreign container instead of the invocation-derived GUI container.
def test_validator_rejects_gui_pass_with_foreign_smoke_container() -> None:
    """A GUI API smoke must target the canonical GUI container."""
    payload = _complete_live_pass_evidence_with_gui()
    payload["gui_smoke"]["api_proof"][
        "container"
    ] = "foreign-gui-container"

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
    services = payload["static_contract"]["render_proof"][
        "selected_facts"
    ]["services"]
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
    services = payload["static_contract"]["render_proof"][
        "selected_facts"
    ]["services"]
    services[1]["labels"][key] = value

    with pytest.raises(ValueError, match="render selected ownership label"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting collision preflight that omits the
# imported container used by independent save/load verification.
def test_validator_rejects_pass_without_expected_imported_container() -> None:
    """Require the canonical imported container in collision preflight."""
    payload = _complete_live_pass_evidence()
    replacement = "ca-mp-task19-a1b2c3d4e5f6-replacement-1"
    payload["name_collisions"]["expected_resources"]["containers"][2] = (
        replacement
    )
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
def test_validator_rejects_pass_with_extra_noncanonical_resource_name(
) -> None:
    """Require exact canonical collision resource sets, not ID substrings."""
    payload = _complete_live_pass_evidence()
    payload["name_collisions"]["expected_resources"]["containers"].append(
        "ca-mp-task19-a1b2c3d4e5f6-other-1"
    )

    with pytest.raises(ValueError, match="containers"):
        docker_status.validate_evidence(payload)


# Production mutation caught: accepting an imported-container create command
# whose ownership label does not name the current invocation.
def test_validator_rejects_pass_with_mismatched_imported_container_label(
) -> None:
    """Bind independent container creation to the current ownership label."""
    payload = _complete_live_pass_evidence()
    payload["save_load_proof"]["imported_container_create"]["argv"][6] = (
        "io.challengecup.task19.invocation=another"
    )

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
def test_validator_rejects_daemon_unavailable_without_capability_queries(
) -> None:
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
    payload["cli"].update(
        {"argv": ["docker", "--version"], "exit_code": 0}
    )

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
    payload["headless_smoke"]["detail"] = (
        f"https://judge.example.invalid/health?{query_key}=private-value"
    )

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
    payload = _save_load_stage_failure_evidence(
        ["docker", "system", "prune"]
    )

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
        payload[phase]["status"] == "not_run"
        for phase in docker_status.PHASES
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
        assert record["stdout_sha256"] == hashlib.sha256(
            (
                "Docker version 27.0.0, build deadbeef\n"
                if name == "cli"
                else '"27.0.0"\n' if name == "daemon" else ""
            ).encode("utf-8")
        ).hexdigest()
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
    payload["headless_smoke"]["detail"] = (
        "https://judge.example.invalid/api/health"
    )
    payload["save_load"]["detail"] = (
        '{"output":"app/output/runs/quick-smoke"}'
    )

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

    assert target == (
        repo_root / "output/evidence/docker/status.json"
    ).resolve()


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
        requested.resolve()
        if absolute
        else (repo_root / requested).resolve()
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
    assert payload[record_name]["stdout_sha256"] == hashlib.sha256(
        b"partial stdout"
    ).hexdigest()
    assert payload[record_name]["stderr_sha256"] == hashlib.sha256(
        b"partial stderr"
    ).hexdigest()
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

    def unexpected_detect(
        _root: Path, **_kwargs: object
    ) -> dict[str, object]:
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
