"""Explicitly gated live Docker verifier for the judge release."""

from __future__ import annotations

import argparse
import base64
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import secrets
import stat
import struct
import subprocess
import sys
import tarfile
from typing import Callable, Mapping, Sequence
import zlib

try:
    from scripts.release import docker_status
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.release import docker_status

from experiments.evidence import EvidenceReader

CommandRunner = Callable[..., object]
_INVOCATION_PATTERN = re.compile(r"^[0-9a-f]{12}$")
_LABEL_KEY = docker_status.OWNERSHIP_LABEL_KEY
_COMMAND_TIMEOUT_SECONDS = 120
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_HOST_ENV_ALLOWLIST = frozenset(
    {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC",
        "TEMP", "TMP", "TMPDIR", "DOCKER_HOST", "DOCKER_CONTEXT",
        "DOCKER_CONFIG", "DOCKER_API_VERSION", "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    }
)
_TASK19_ENV_KEYS = frozenset(
    {
        "COMPOSE_PROJECT_NAME",
        "JUDGE_IMAGE",
        "JUDGE_GUI_IMAGE",
        "TASK19_INVOCATION_ID",
    }
)
_API_HEALTH_SCRIPT = """
import json
import urllib.request

with urllib.request.urlopen(
    "http://127.0.0.1:8000/api/health", timeout=15
) as response:
    payload = json.load(response)
print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
""".strip()
_API_SMOKE_SCRIPT = """
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import urllib.request

from scripts.release.docker_verify import _read_observed_completion

base = "http://127.0.0.1:8000"
container, image = sys.argv[1:3]
body = {
    "intersection_id": "1",
    "algorithm": "fixed_time",
    "steps": 100,
}
encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
request = urllib.request.Request(
    base + "/api/runs",
    data=encoded,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=30) as response:
    response_status = response.status
    response_raw = response.read()
created = json.loads(response_raw)
run_id = created["run_id"]
if re.fullmatch(r"[0-9a-f]{12}", run_id) is None:
    raise RuntimeError("server returned an unsafe run id")
run_path = "runs/i1/fixed_time/x1/s42/" + run_id
run_dir = "/app/output/" + run_path
if response_status != 202 or created.get("run_dir") != run_dir:
    raise RuntimeError("server returned an invalid run creation result")
terminal_raw = b""
terminal = {}
terminal_status = 0
for _attempt in range(360):
    with urllib.request.urlopen(
        base + "/api/runs/" + run_id, timeout=15
    ) as response:
        terminal_status = response.status
        terminal_raw = response.read()
    terminal = json.loads(terminal_raw)
    if terminal.get("status") in {"completed", "failed", "interrupted"}:
        break
    time.sleep(1)
if (
    terminal_status != 200
    or terminal.get("run_id") != run_id
    or terminal.get("run_dir") != run_dir
    or terminal.get("status") != "completed"
):
    raise RuntimeError("server returned an invalid terminal result")
observed_completion = _read_observed_completion(
    Path(run_dir), run_id=run_id, run_path=run_path
)
proof = {
    "container": container,
    "image": image,
    "request": {
        "method": "POST",
        "path": "/api/runs",
        "body": body,
        "body_sha256": hashlib.sha256(encoded).hexdigest(),
    },
    "response": {
        "status": response_status,
        "run_id": run_id,
        "run_dir": run_dir,
        "body_sha256": hashlib.sha256(
            json.dumps(
                {"run_id": run_id, "run_dir": run_dir, "status": response_status},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    },
    "terminal": {
        "method": "GET",
        "path": "/api/runs/" + run_id,
        "status": terminal_status,
        "run_id": run_id,
        "state": terminal.get("status"),
        "run_dir": run_dir,
        "body_sha256": hashlib.sha256(
            json.dumps(
                {
                    "run_id": run_id,
                    "run_dir": run_dir,
                    "status": terminal.get("status"),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    },
    "run_id": run_id,
    "terminal_status": terminal.get("status"),
    "requested_steps": 100,
    "output": {
        "root": "app/output",
        "path": run_path,
        "run_id": run_id,
    },
    "observed_completion": observed_completion,
}
print(json.dumps(proof, sort_keys=True, separators=(",", ":")))
""".strip()
_GUI_FRAMES_SCRIPT = """
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

from scripts.release.docker_verify import _read_observed_completion

base = "http://127.0.0.1:8000"
container, image = sys.argv[1:3]
body = {
    "intersection_id": "1",
    "algorithm": "fixed_time",
    "steps": 100,
}
encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
request = urllib.request.Request(
    base + "/api/runs",
    data=encoded,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=30) as response:
    response_status = response.status
    response_raw = response.read()
created = json.loads(response_raw)
run_id = created["run_id"]
if re.fullmatch(r"[0-9a-f]{12}", run_id) is None:
    raise RuntimeError("server returned an unsafe run id")
run_path = "runs/i1/fixed_time/x1/s42/" + run_id
run_dir = "/app/output/" + run_path
if response_status != 202 or created.get("run_dir") != run_dir:
    raise RuntimeError("server returned an invalid run creation result")

with urllib.request.urlopen(
    base + "/api/runs/" + run_id, timeout=15
) as response:
    active_status = response.status
    active_raw = response.read()
active = json.loads(active_raw)
if (
    active_status != 200
    or active.get("run_id") != run_id
    or active.get("run_dir") != run_dir
    or active.get("status") not in {"queued", "starting", "running", "stopping"}
):
    raise RuntimeError("server run was not active before the first frame")
active_observation = {
    "method": "GET",
    "path": "/api/runs/" + run_id,
    "status": active_status,
    "run_id": active.get("run_id"),
    "state": active.get("status"),
    "run_dir": active.get("run_dir"),
    "body_sha256": hashlib.sha256(
        json.dumps(
            {
                "run_id": active.get("run_id"),
                "run_dir": active.get("run_dir"),
                "status": active.get("status"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest(),
}

deadline = time.monotonic() + 60
frames = []
def frame(url):
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                if response.status != 200:
                    raise RuntimeError("frame status is invalid")
                if response.headers["X-Run-Id"] != run_id:
                    raise RuntimeError("frame run id is invalid")
                if response.headers.get_content_type() != "image/png":
                    raise RuntimeError("frame content type is invalid")
                png = response.read()
                sequence = int(response.headers["X-Frame-Sequence"])
                simulation_time = float(response.headers["X-Simulation-Time"])
            if sequence < 0 or not math.isfinite(simulation_time) or simulation_time < 0:
                raise RuntimeError("frame headers are invalid")
            return png, sequence, simulation_time
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            time.sleep(0.25)
    raise RuntimeError("frame deadline expired")

png, first_sequence, simulation_time = frame(
    base + "/api/runs/" + run_id + "/frame"
)
frames.append(
    {
        "path": "gui/frames/frame-0001.png",
        "sequence": first_sequence,
        "simulation_time": simulation_time,
        "png_base64": base64.b64encode(png).decode("ascii"),
    }
)
png, second_sequence, simulation_time = frame(
    base + "/api/runs/" + run_id
    + "/frame?sequence=" + str(first_sequence)
)
if second_sequence <= first_sequence:
    raise RuntimeError("frame sequence did not advance")
frames.append(
    {
        "path": "gui/frames/frame-0002.png",
        "sequence": second_sequence,
        "simulation_time": simulation_time,
        "png_base64": base64.b64encode(png).decode("ascii"),
    }
)

terminal_raw = b""
terminal = {}
terminal_status = 0
for _attempt in range(360):
    with urllib.request.urlopen(
        base + "/api/runs/" + run_id, timeout=15
    ) as response:
        terminal_status = response.status
        terminal_raw = response.read()
    terminal = json.loads(terminal_raw)
    if terminal.get("status") in {"completed", "failed", "interrupted"}:
        break
    time.sleep(1)
if (
    terminal_status != 200
    or terminal.get("run_id") != run_id
    or terminal.get("run_dir") != run_dir
    or terminal.get("status") != "completed"
):
    raise RuntimeError("server returned an invalid terminal result")
observed_completion = _read_observed_completion(
    Path(run_dir), run_id=run_id, run_path=run_path
)

proof = {
    "container": container,
    "image": image,
    "request": {
        "method": "POST",
        "path": "/api/runs",
        "body": body,
        "body_sha256": hashlib.sha256(encoded).hexdigest(),
    },
    "response": {
        "status": response_status,
        "run_id": run_id,
        "run_dir": run_dir,
        "body_sha256": hashlib.sha256(
            json.dumps(
                {"run_id": run_id, "run_dir": run_dir, "status": response_status},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    },
    "terminal": {
        "method": "GET",
        "path": "/api/runs/" + run_id,
        "status": terminal_status,
        "run_id": run_id,
        "state": terminal.get("status"),
        "run_dir": run_dir,
        "body_sha256": hashlib.sha256(
            json.dumps(
                {
                    "run_id": run_id,
                    "run_dir": run_dir,
                    "status": terminal.get("status"),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    },
    "run_id": run_id,
    "terminal_status": terminal.get("status"),
    "requested_steps": 100,
    "output": {
        "root": "app/output",
        "path": run_path,
        "run_id": run_id,
    },
    "observed_completion": observed_completion,
}
print(json.dumps(
    {
        "api_proof": proof,
        "active_observation": active_observation,
        "frames": frames,
    },
    sort_keys=True,
    separators=(",", ":"),
))
""".strip()


class SafetyError(RuntimeError):
    """Raised when verifier ownership or path safety cannot be proven."""


@dataclass(frozen=True)
class InvocationResources:
    """Immutable exact Docker identities for one live verification."""

    invocation_id: str
    compose_project: str
    headless_image: str
    gui_image: str
    imported_image: str
    containers: tuple[str, ...]
    networks: tuple[str, ...]
    volumes: tuple[str, ...]
    label: str

    @classmethod
    def from_id(cls, invocation_id: str) -> "InvocationResources":
        if not _INVOCATION_PATTERN.fullmatch(invocation_id):
            raise SafetyError(
                "invocation id must be exactly 12 lowercase hexadecimal "
                "characters"
            )
        project = f"ca-mp-task19-{invocation_id}"
        return cls(
            invocation_id=invocation_id,
            compose_project=project,
            headless_image=f"{project}-headless:local",
            gui_image=f"{project}-gui:local",
            imported_image=f"{project}-imported:local",
            containers=(
                f"{project}-judge-1",
                f"{project}-judge-gui-1",
                f"{project}-imported-judge-1",
            ),
            networks=(f"{project}_default",),
            volumes=(
                f"{project}_judge-output",
                f"{project}_judge-gui-output",
            ),
            label=f"{_LABEL_KEY}={invocation_id}",
        )

    def expected_resources(self) -> dict[str, object]:
        return {
            "compose_project": self.compose_project,
            "containers": list(self.containers),
            "networks": list(self.networks),
            "volumes": list(self.volumes),
            "images": [
                self.headless_image,
                self.gui_image,
                self.imported_image,
            ],
        }


def run_command(
    argv: Sequence[str],
    cwd: Path,
    *,
    env: Mapping[str, str] | None = None,
) -> object:
    command = [str(item) for item in argv]
    if not command or command[0] != "docker":
        raise SafetyError("verifier command must be an argv Docker command")
    process_env: dict[str, str] = {}
    for key, value in os.environ.items():
        logical_key = key.upper()
        if logical_key not in _HOST_ENV_ALLOWLIST or not value:
            continue
        if "\0" in value:
            raise SafetyError("controlled host environment contains NUL")
        process_env[logical_key] = value
    if env is not None:
        injected = {str(key).upper(): str(value) for key, value in env.items()}
        if set(injected) != _TASK19_ENV_KEYS:
            raise SafetyError("Task 19 environment overlay is incomplete")
        if any(not value or "\0" in value for value in injected.values()):
            raise SafetyError("Task 19 environment overlay is invalid")
        process_env.update(injected)
    return subprocess.run(
        command,
        cwd=Path(cwd),
        env=process_env,
        check=False,
        capture_output=True,
        text=False,
        shell=False,
        timeout=_COMMAND_TIMEOUT_SECONDS,
    )


def is_owned(
    candidate: Mapping[str, object], *, name: str, invocation_id: str
) -> bool:
    labels = candidate.get("labels")
    return (
        candidate.get("name") == name
        and isinstance(labels, Mapping)
        and labels.get(_LABEL_KEY) == invocation_id
    )


def _run(
    command_runner: CommandRunner,
    argv: Sequence[str],
    repo_root: Path,
    *,
    env: Mapping[str, str] | None = None,
) -> object:
    if env is None:
        return command_runner(list(argv), repo_root)
    return command_runner(list(argv), repo_root, env=dict(env))


def _result_json(result: object) -> object:
    stdout = getattr(result, "stdout", "")
    try:
        return json.loads(stdout or "[]")
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SafetyError("Docker inventory returned invalid JSON") from exc


def _stream_bytes(value: object) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return str(value).encode("utf-8")


def _stream_text(value: object) -> str:
    raw = _stream_bytes(value)
    return raw.decode("utf-8", errors="replace")[: docker_status.MAX_DETAIL_LENGTH]


def _canonical_json_sha256(value: object) -> str:
    """Hash the canonical producer bytes for one structured API body."""
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_image_identity(
    value: object,
    *,
    expected_tag: str,
    invocation_id: str,
) -> dict[str, object]:
    """Parse one locally built image without inventing unavailable digests."""
    if not isinstance(value, Mapping):
        raise SafetyError("image identity must be one object")
    image_id = value.get("Id")
    repo_tags = value.get("RepoTags")
    repo_digests = value.get("RepoDigests")
    config = value.get("Config")
    labels = config.get("Labels") if isinstance(config, Mapping) else None
    rootfs = value.get("RootFS")
    layers = rootfs.get("Layers") if isinstance(rootfs, Mapping) else None
    if (
        not isinstance(image_id, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None
        or not isinstance(repo_tags, list)
        or expected_tag not in repo_tags
        or not all(isinstance(tag, str) for tag in repo_tags)
        or value.get("Os") != "linux"
        or value.get("Architecture") != "amd64"
        or not isinstance(labels, Mapping)
        or labels.get(_LABEL_KEY) != invocation_id
        or not isinstance(rootfs, Mapping)
        or rootfs.get("Type") != "layers"
        or not isinstance(layers, list)
        or not layers
        or not all(
            isinstance(layer, str)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", layer)
            for layer in layers
        )
    ):
        raise SafetyError("image identity is incomplete or unowned")
    if repo_digests is None:
        repo_digests = []
    if not isinstance(repo_digests, list) or not all(
        isinstance(item, str) for item in repo_digests
    ):
        raise SafetyError("image repository digests are malformed")
    repository = expected_tag.rsplit(":", 1)[0]
    exact = {
        item.split("@", 1)[1]
        for item in repo_digests
        if re.fullmatch(
            re.escape(repository) + r"@sha256:[0-9a-f]{64}", item
        )
    }
    if len(exact) > 1:
        raise SafetyError("image has conflicting exact repository digests")
    identity: dict[str, object] = {
        "headless_image_id": image_id,
        "rootfs_layers": list(layers),
    }
    if exact:
        identity["repository_digest"] = next(iter(exact))
    return identity


def _validate_saved_image_archive(
    path: Path,
    *,
    expected_tag: str,
    expected_image_id: str,
    expected_rootfs_layers: Sequence[str],
) -> dict[str, object]:
    """Bind a Docker-save archive to the inspected image and exact bytes."""
    if re.fullmatch(r"sha256:[0-9a-f]{64}", expected_image_id) is None:
        raise SafetyError("expected image identity is malformed")
    if not expected_rootfs_layers or not all(
        re.fullmatch(r"sha256:[0-9a-f]{64}", layer)
        for layer in expected_rootfs_layers
    ):
        raise SafetyError("expected root filesystem identity is malformed")

    try:
        raw_tar = Path(path).read_bytes()
    except OSError as exc:
        raise SafetyError("saved image archive could not be read") from exc
    if not raw_tar:
        raise SafetyError("saved image archive is empty")

    def safe_member_name(name: object) -> str:
        if not isinstance(name, str) or not name or "\\" in name:
            raise SafetyError("saved image archive has an unsafe member")
        if name.startswith("/") or name.startswith("./"):
            raise SafetyError("saved image archive has an unsafe member")
        parts = name.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise SafetyError("saved image archive has an unsafe member")
        canonical = PurePosixPath(name).as_posix()
        if canonical != name or PurePosixPath(name).is_absolute():
            raise SafetyError("saved image archive has an unsafe member")
        return canonical

    try:
        with tarfile.open(fileobj=io.BytesIO(raw_tar), mode="r:*") as archive:
            members: dict[str, tarfile.TarInfo] = {}
            folded_names: set[str] = set()
            for member in archive.getmembers():
                name = safe_member_name(member.name)
                folded = name.casefold()
                if name in members or folded in folded_names:
                    raise SafetyError(
                        "saved image archive has duplicate or aliased members"
                    )
                members[name] = member
                folded_names.add(folded)

            def regular_bytes(name: str, *, nonempty: bool) -> bytes:
                safe_name = safe_member_name(name)
                member = members.get(safe_name)
                if member is None or not member.isreg():
                    raise SafetyError(
                        "saved image archive member is missing or non-regular"
                    )
                stream = archive.extractfile(member)
                if stream is None:
                    raise SafetyError("saved image archive member is unreadable")
                data = stream.read()
                if len(data) != member.size or (nonempty and not data):
                    raise SafetyError(
                        "saved image archive member has invalid content"
                    )
                return data

            manifest_raw = regular_bytes("manifest.json", nonempty=True)
            manifest = json.loads(manifest_raw)
            if not isinstance(manifest, list):
                raise SafetyError("saved image manifest is malformed")
            selected: list[Mapping[str, object]] = []
            for entry in manifest:
                if not isinstance(entry, Mapping):
                    raise SafetyError("saved image manifest is malformed")
                repo_tags = entry.get("RepoTags")
                if not isinstance(repo_tags, list) or not all(
                    isinstance(tag, str) for tag in repo_tags
                ):
                    raise SafetyError("saved image manifest is malformed")
                if expected_tag in repo_tags:
                    selected.append(entry)
            if len(selected) != 1:
                raise SafetyError(
                    "saved image manifest does not select exactly one image"
                )

            config_name = selected[0].get("Config")
            layer_names = selected[0].get("Layers")
            if not isinstance(config_name, str) or not isinstance(
                layer_names, list
            ) or not all(isinstance(name, str) for name in layer_names):
                raise SafetyError("saved image manifest is malformed")
            if len(layer_names) != len(expected_rootfs_layers) or len(
                set(layer_names)
            ) != len(layer_names):
                raise SafetyError("saved image layer inventory is malformed")

            config_raw = regular_bytes(config_name, nonempty=True)
            if hashlib.sha256(config_raw).hexdigest() != expected_image_id[7:]:
                raise SafetyError(
                    "saved image config does not match inspected image identity"
                )
            config = json.loads(config_raw)
            rootfs = config.get("rootfs") if isinstance(config, Mapping) else None
            if (
                not isinstance(rootfs, Mapping)
                or rootfs.get("type") != "layers"
                or rootfs.get("diff_ids") != list(expected_rootfs_layers)
            ):
                raise SafetyError(
                    "saved image root filesystem does not match inspection"
                )
            for layer_name in layer_names:
                regular_bytes(layer_name, nonempty=True)
    except SafetyError:
        raise
    except (json.JSONDecodeError, OSError, tarfile.TarError) as exc:
        raise SafetyError("saved image archive is malformed") from exc

    return {
        "config_digest": expected_image_id,
        "byte_length": len(raw_tar),
        "sha256": hashlib.sha256(raw_tar).hexdigest(),
    }


def _validate_png_bytes(data: bytes) -> None:
    """Validate one complete, non-interlaced PNG frame without decoding it."""
    if not isinstance(data, bytes) or not data.startswith(
        b"\x89PNG\r\n\x1a\n"
    ):
        raise SafetyError("PNG signature is invalid")
    offset = 8
    chunks: list[tuple[bytes, bytes]] = []
    saw_iend = False
    while offset < len(data):
        if saw_iend or len(data) - offset < 12:
            raise SafetyError("PNG chunk framing is invalid")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        end = offset + 12 + length
        if end > len(data):
            raise SafetyError("PNG chunk exceeds the frame boundary")
        kind = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        stored_crc = struct.unpack(">I", data[offset + 8 + length : end])[0]
        if re.fullmatch(rb"[A-Za-z]{4}", kind) is None or kind[2] & 0x20:
            raise SafetyError("PNG chunk type is invalid")
        if zlib.crc32(kind + chunk_data) & 0xFFFFFFFF != stored_crc:
            raise SafetyError("PNG chunk CRC is invalid")
        chunks.append((kind, chunk_data))
        offset = end
        if kind == b"IEND":
            saw_iend = True
    if offset != len(data) or not saw_iend:
        raise SafetyError("PNG does not end at IEND")
    if not chunks or chunks[0][0] != b"IHDR":
        raise SafetyError("PNG IHDR must be first")
    if sum(kind == b"IHDR" for kind, _ in chunks) != 1:
        raise SafetyError("PNG must contain one IHDR")
    if sum(kind == b"IEND" for kind, _ in chunks) != 1:
        raise SafetyError("PNG must contain one IEND")
    if chunks[-1] != (b"IEND", b""):
        raise SafetyError("PNG IEND must be empty and final")

    ihdr = chunks[0][1]
    if len(ihdr) != 13:
        raise SafetyError("PNG IHDR length is invalid")
    width, height, depth, color_type, compression, filtering, interlace = (
        struct.unpack(">IIBBBBB", ihdr)
    )
    valid_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    if (
        width <= 0
        or height <= 0
        or depth not in valid_depths.get(color_type, set())
        or compression != 0
        or filtering != 0
        or interlace != 0
    ):
        raise SafetyError("PNG IHDR fields are unsupported")

    known_critical = {b"IHDR", b"PLTE", b"IDAT", b"IEND"}
    idat_indices: list[int] = []
    idat_parts: list[bytes] = []
    plte: bytes | None = None
    for index, (kind, chunk_data) in enumerate(chunks[1:], start=1):
        if kind[0] & 0x20 == 0 and kind not in known_critical:
            raise SafetyError("PNG contains an unknown critical chunk")
        if kind == b"PLTE":
            if plte is not None or idat_indices:
                raise SafetyError("PNG palette ordering is invalid")
            if not chunk_data or len(chunk_data) % 3 or len(chunk_data) > 768:
                raise SafetyError("PNG palette is invalid")
            plte = chunk_data
        elif kind == b"IDAT":
            idat_indices.append(index)
            idat_parts.append(chunk_data)
    if not idat_indices or idat_indices != list(
        range(idat_indices[0], idat_indices[-1] + 1)
    ):
        raise SafetyError("PNG IDAT chunks are missing or non-contiguous")
    if color_type == 3 and plte is None:
        raise SafetyError("PNG indexed color requires a palette")
    if color_type in {0, 4} and plte is not None:
        raise SafetyError("PNG grayscale must not contain a palette")

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = (width * channels * depth + 7) // 8
    expected_size = height * (row_bytes + 1)
    if expected_size > 256 * 1024 * 1024:
        raise SafetyError("PNG decoded frame is too large")
    decompressor = zlib.decompressobj()
    try:
        decoded = decompressor.decompress(
            b"".join(idat_parts), expected_size + 1
        )
        decoded += decompressor.flush()
    except zlib.error as exc:
        raise SafetyError("PNG IDAT zlib stream is invalid") from exc
    if (
        not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
        or len(decoded) != expected_size
    ):
        raise SafetyError("PNG IDAT zlib stream is incomplete or oversized")
    stride = row_bytes + 1
    if any(decoded[row * stride] > 4 for row in range(height)):
        raise SafetyError("PNG scanline filter byte is invalid")


def _read_observed_completion(
    run_dir: Path,
    *,
    run_id: str,
    run_path: str,
    evidence_validator: Callable[[Path], Sequence[object]] | None = None,
) -> dict[str, object]:
    """Read one source-side sealed run and derive observed completion."""
    expected_path = f"runs/i1/fixed_time/x1/s42/{run_id}"
    if (
        _INVOCATION_PATTERN.fullmatch(run_id) is None
        or run_path != expected_path
    ):
        raise SafetyError("sealed completion run identity is unsafe")
    source = Path(run_dir)
    if evidence_validator is None:
        from experiments.evidence import EvidenceReader

        evidence_validator = EvidenceReader.validate
    try:
        if evidence_validator(source):
            raise SafetyError("source-side sealed evidence is invalid")

        def stable_bytes(name: str) -> bytes:
            path = source / name
            if path.is_symlink() or not path.is_file():
                raise SafetyError("sealed completion file is not regular")
            before = path.stat()
            data = path.read_bytes()
            after = path.stat()
            identity_before = (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
            )
            identity_after = (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            )
            if not data or identity_before != identity_after:
                raise SafetyError("sealed completion file changed while read")
            return data

        raw = {
            name: stable_bytes(name)
            for name in (
                "manifest.json",
                "status.json",
                "run_metadata.json",
                "simulation_log.csv",
                "hashes.json",
            )
        }
        manifest = json.loads(raw["manifest.json"])
        status = json.loads(raw["status.json"])
        metadata = json.loads(raw["run_metadata.json"])
        hashes = json.loads(raw["hashes.json"])
        if not all(
            isinstance(item, Mapping)
            for item in (manifest, status, metadata, hashes)
        ):
            raise SafetyError("sealed completion JSON is malformed")
        if any(
            item.get("run_id") != run_id
            for item in (manifest, status, metadata, hashes)
        ):
            raise SafetyError("sealed completion run IDs disagree")
        if (
            type(metadata.get("requested_steps")) is not int
            or metadata.get("requested_steps") != 100
        ):
            raise SafetyError("sealed completion requested steps are invalid")
        files = hashes.get("files")
        step_digest = hashlib.sha256(raw["simulation_log.csv"]).hexdigest()
        if (
            not isinstance(files, Mapping)
            or files.get("simulation_log.csv") != step_digest
        ):
            raise SafetyError("sealed completion step log hash is invalid")
        text = raw["simulation_log.csv"].decode("utf-8")
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if reader.fieldnames is None or "step" not in reader.fieldnames:
            raise SafetyError("sealed completion step log has no step column")
        rows = list(reader)
        indices: list[int] = []
        for row in rows:
            raw_step = row.get("step")
            if not isinstance(raw_step, str) or re.fullmatch(
                r"0|[1-9][0-9]*", raw_step
            ) is None:
                raise SafetyError("sealed completion step value is invalid")
            indices.append(int(raw_step))
        if len(rows) != 100 or indices != list(range(100)):
            raise SafetyError("sealed completion does not contain steps 0..99")
        if evidence_validator(source):
            raise SafetyError("source-side sealed evidence changed")
    except SafetyError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
        raise SafetyError("sealed completion could not be read") from exc

    return {
        "source": "sealed_simulation_log.v1",
        "run_id": run_id,
        "run_path": run_path,
        "requested_steps": 100,
        "observed_step_count": len(indices),
        "observed_step_indices": indices,
        "step_log_path": "simulation_log.csv",
        "step_log_sha256": step_digest,
        "hashes_path": "hashes.json",
        "hashes_sha256": hashlib.sha256(raw["hashes.json"]).hexdigest(),
    }


def _walk_exported_regular_files(root: Path) -> list[dict[str, object]]:
    """Inventory stable regular files below root without following links."""
    base = Path(root)
    try:
        base_stat = base.lstat()
    except OSError as exc:
        raise SafetyError("export root cannot be inspected") from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)

    def redirects(details: os.stat_result) -> bool:
        return stat.S_ISLNK(details.st_mode) or bool(
            getattr(details, "st_file_attributes", 0) & reparse_flag
        )

    if not stat.S_ISDIR(base_stat.st_mode) or redirects(base_stat):
        raise SafetyError("export root is not a safe directory")
    entries: list[dict[str, object]] = []
    identities: set[str] = set()

    def visit(directory: Path, parts: tuple[str, ...]) -> None:
        try:
            children = sorted(
                os.scandir(directory), key=lambda item: item.name.casefold()
            )
        except OSError as exc:
            raise SafetyError("export directory cannot be inspected") from exc
        for child in children:
            name = child.name
            if (
                not name
                or name in {".", ".."}
                or "/" in name
                or "\\" in name
            ):
                raise SafetyError("export contains an unsafe path")
            relative_parts = (*parts, name)
            relative = PurePosixPath(*relative_parts).as_posix()
            identity = relative.casefold()
            if identity in identities:
                raise SafetyError("export contains a case-aliased path")
            identities.add(identity)
            try:
                discovered = child.stat(follow_symlinks=False)
            except OSError as exc:
                raise SafetyError("export entry cannot be inspected") from exc
            if redirects(discovered):
                raise SafetyError("export contains a link or reparse point")
            path = directory / name
            try:
                before = path.stat(follow_symlinks=False)
            except OSError as exc:
                raise SafetyError("export entry cannot be inspected") from exc
            if redirects(before):
                raise SafetyError("export contains a link or reparse point")
            if stat.S_ISDIR(discovered.st_mode):
                if not stat.S_ISDIR(before.st_mode):
                    raise SafetyError("export entry changed while inspected")
                visit(path, relative_parts)
                try:
                    after = path.stat(follow_symlinks=False)
                except OSError as exc:
                    raise SafetyError("export directory changed") from exc
                if redirects(after) or (
                    before.st_dev,
                    before.st_ino,
                    before.st_mtime_ns,
                ) != (after.st_dev, after.st_ino, after.st_mtime_ns):
                    raise SafetyError("export directory changed while walked")
                continue
            if not stat.S_ISREG(discovered.st_mode):
                raise SafetyError("export contains a non-regular entry")
            if not stat.S_ISREG(before.st_mode):
                raise SafetyError("export entry changed while inspected")
            try:
                data = path.read_bytes()
                after = path.stat(follow_symlinks=False)
            except OSError as exc:
                raise SafetyError("export file cannot be read") from exc
            if redirects(after) or (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
            ) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            ):
                raise SafetyError("export file changed while hashed")
            if not data or len(data) != before.st_size:
                raise SafetyError("export contains an empty or partial file")
            entries.append(
                {
                    "path": relative,
                    "byte_length": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )

    visit(base, ())
    return sorted(entries, key=lambda entry: str(entry["path"]))


def _inventory_shape(
    kind: str,
    name: str,
    raw: Mapping[str, object],
    invocation_id: str,
) -> dict[str, object] | None:
    running: bool | None = None
    if kind == "container":
        if raw.get("Name") != "/" + name:
            return None
        config = raw.get("Config")
        if not isinstance(config, Mapping):
            raise SafetyError("container inventory Config is malformed")
        labels = config.get("Labels")
        state = raw.get("State")
        if isinstance(state, Mapping) and "Running" in state:
            if type(state.get("Running")) is not bool:
                raise SafetyError("container inventory running state is malformed")
            running = state.get("Running")
    elif kind in {"network", "volume"}:
        if raw.get("Name") != name:
            return None
        labels = raw.get("Labels")
    elif kind == "image":
        repo_tags = raw.get("RepoTags")
        if not isinstance(repo_tags, list) or name not in repo_tags:
            return None
        config = raw.get("Config")
        if not isinstance(config, Mapping):
            raise SafetyError("image inventory Config is malformed")
        labels = config.get("Labels")
    else:
        raise SafetyError("unknown Docker inventory kind")
    if labels is not None and not isinstance(labels, Mapping):
        raise SafetyError("Docker inventory labels are malformed")
    label_value = (
        labels.get(_LABEL_KEY) if isinstance(labels, Mapping) else None
    )
    result = {
        "kind": kind,
        "name": name,
        "labels": (
            {_LABEL_KEY: invocation_id}
            if label_value == invocation_id
            else {}
        ),
        "owned": label_value == invocation_id,
    }
    if running is not None:
        result["running"] = running
    return result


def _command_record(
    status: str,
    detail: str,
    argv: Sequence[str],
    result: object | None,
    repo_root: Path,
) -> dict[str, object]:
    stdout = b"" if result is None else _stream_bytes(
        getattr(result, "stdout", b"")
    )
    stderr = b"" if result is None else _stream_bytes(
        getattr(result, "stderr", b"")
    )
    exit_code = None if result is None else getattr(result, "returncode", None)
    root_spellings = {
        str(Path(repo_root)),
        str(Path(repo_root).absolute()),
        str(Path(repo_root).resolve()),
    }

    def redact(value: object) -> str:
        text = str(value)
        script_tokens = {
            _API_HEALTH_SCRIPT: "<api-health-script>",
            _API_SMOKE_SCRIPT: "<api-smoke-script>",
            _GUI_FRAMES_SCRIPT: "<gui-frames-script>",
        }
        text = script_tokens.get(text, text)
        for spelling in sorted(root_spellings, key=len, reverse=True):
            if spelling:
                text = text.replace(spelling, "<repo>")
        return text

    now = _timestamp()
    return {
        "status": status,
        "started_at": now,
        "finished_at": now,
        "argv": [redact(item) for item in argv],
        "exit_code": exit_code,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "detail": redact(detail)[: docker_status.MAX_DETAIL_LENGTH],
    }


def _timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _not_run_record(detail: str) -> dict[str, object]:
    return _command_record("not_run", detail, [], None, Path("."))


def _capability_internal_failure_record(
    argv: Sequence[str], detail: str
) -> dict[str, object]:
    """Serialize an unexpected capability exception without a traceback."""
    del argv
    record = _not_run_record(detail)
    record.update(
        {
            "status": "fail",
            "execution": "internal_error",
            "boundary": "capability",
            "failure_proof": {"kind": "internal_error"},
            "detail": detail[: docker_status.MAX_DETAIL_LENGTH],
        }
    )
    return record


def _command_exception_streams(
    error: BaseException,
) -> tuple[bytes, bytes] | None:
    """Return literal partial bytes, or reject synthetic partial text."""
    stdout = getattr(error, "stdout", None)
    if stdout is None and isinstance(error, subprocess.TimeoutExpired):
        stdout = getattr(error, "output", None)
    stderr = getattr(error, "stderr", None)
    if not all(
        value is None or isinstance(value, bytes)
        for value in (stdout, stderr)
    ):
        return None
    return stdout or b"", stderr or b""


class _StepFailure(RuntimeError):
    def __init__(
        self,
        phase: str,
        argv: Sequence[str],
        result: object,
        detail: str,
    ) -> None:
        super().__init__(detail)
        self.phase = phase
        self.argv = list(argv)
        self.result = result
        self.detail = detail


class _SemanticFailure(RuntimeError):
    def __init__(
        self,
        boundary: str,
        argv: Sequence[str],
        result: object,
        expected: str,
        observed: str,
    ) -> None:
        super().__init__(f"{boundary} postcondition mismatched")
        self.boundary = boundary
        self.argv = list(argv)
        self.result = result
        self.expected = expected
        self.observed = observed


class _LocalFailure(RuntimeError):
    def __init__(self, boundary: str, operation: str) -> None:
        super().__init__(f"{boundary} local operation failed")
        self.boundary = boundary
        self.operation = operation


class _CommandExceptionFailure(RuntimeError):
    def __init__(
        self,
        boundary: str,
        argv: Sequence[str],
        error: subprocess.TimeoutExpired | OSError,
        stdout: bytes,
        stderr: bytes,
    ) -> None:
        super().__init__("Docker command raised a closed exception")
        self.boundary = boundary
        self.argv = list(argv)
        self.error = error
        self.stdout = stdout
        self.stderr = stderr


class _InternalFailure(RuntimeError):
    def __init__(self, boundary: str) -> None:
        super().__init__("verifier internal failure")
        self.boundary = boundary


class _InventoryFailure(RuntimeError):
    def __init__(
        self,
        argv: Sequence[str],
        result: object,
        *,
        semantic: bool,
        observed_all: Sequence[Mapping[str, object]] = (),
        observed_owned: Sequence[Mapping[str, object]] = (),
        error: BaseException | None = None,
    ) -> None:
        super().__init__("collision inventory failed closed")
        self.argv = list(argv)
        self.result = result
        self.semantic = semantic
        self.observed_all = [dict(item) for item in observed_all]
        self.observed_owned = [dict(item) for item in observed_owned]
        self.error = error


def _execute(
    runner: CommandRunner,
    argv: Sequence[str],
    root: Path,
    *,
    phase: str,
    detail: str,
    env: Mapping[str, str] | None = None,
) -> tuple[object, dict[str, object]]:
    result = _run(runner, argv, root, env=env)
    if getattr(result, "returncode", 1) != 0:
        raise _StepFailure(phase, argv, result, detail)
    return result, _command_record("pass", detail, argv, result, root)


def _api_record(proof: Mapping[str, object], detail: str) -> dict[str, object]:
    record = _not_run_record(detail)
    record.update(
        {
            "status": "pass",
            "detail": detail,
            "execution": "api_result",
            "api_proof": dict(proof),
        }
    )
    return record


def _parse_api_proof(
    result: object, expected: InvocationResources
) -> dict[str, object]:
    value = _result_json(result)
    if not isinstance(value, Mapping):
        raise SafetyError("API smoke result must be a JSON object")
    proof = dict(value)
    run_id = proof.get("run_id")
    if not isinstance(run_id, str) or _INVOCATION_PATTERN.fullmatch(
        run_id
    ) is None:
        raise SafetyError("API smoke server run id is unsafe")
    if set(proof) != {
        "requested_steps",
        "run_id",
        "terminal_status",
        "output",
        "container",
        "image",
        "request",
        "response",
        "terminal",
        "observed_completion",
    }:
        raise SafetyError("API smoke proof fields are not exact")
    run_path = f"runs/i1/fixed_time/x1/s42/{run_id}"
    run_dir = "/app/output/" + run_path
    request = proof.get("request")
    response = proof.get("response")
    terminal = proof.get("terminal")
    output = proof.get("output")
    completion = proof.get("observed_completion")
    if not all(
        isinstance(item, Mapping)
        for item in (request, response, terminal, output, completion)
    ):
        raise SafetyError("API smoke request/terminal proof is incomplete")
    body = request.get("body")
    if (
        proof.get("requested_steps") != 100
        or proof.get("terminal_status") != "completed"
        or set(request) != {"method", "path", "body", "body_sha256"}
        or request.get("method") != "POST"
        or request.get("path") != "/api/runs"
        or body
        != {
            "intersection_id": "1",
            "algorithm": "fixed_time",
            "steps": 100,
        }
        or set(response)
        != {"status", "run_id", "run_dir", "body_sha256"}
        or type(response.get("status")) is not int
        or response.get("status") != 202
        or response.get("run_id") != run_id
        or response.get("run_dir") != run_dir
        or set(terminal)
        != {
            "method",
            "path",
            "status",
            "run_id",
            "state",
            "run_dir",
            "body_sha256",
        }
        or terminal.get("method") != "GET"
        or terminal.get("path") != f"/api/runs/{run_id}"
        or type(terminal.get("status")) is not int
        or terminal.get("status") != 200
        or terminal.get("run_id") != run_id
        or terminal.get("state") != "completed"
        or terminal.get("run_dir") != run_dir
        or dict(output)
        != {"root": "app/output", "path": run_path, "run_id": run_id}
    ):
        raise SafetyError("API smoke POST/GET contract is invalid")
    expected_hashes = {
        "request body": _canonical_json_sha256(body),
        "response body": _canonical_json_sha256(
            {"run_id": run_id, "run_dir": run_dir, "status": response.get("status")}
        ),
        "terminal body": _canonical_json_sha256(
            {"run_id": run_id, "run_dir": run_dir, "status": terminal.get("state")}
        ),
    }
    observed_hashes = {
        "request body": request.get("body_sha256"),
        "response body": response.get("body_sha256"),
        "terminal body": terminal.get("body_sha256"),
    }
    if observed_hashes != expected_hashes:
        raise SafetyError("API smoke body hash is not bound to producer bytes")
    pairs = {
        expected.containers[0]: expected.headless_image,
        expected.containers[1]: expected.gui_image,
        expected.containers[2]: expected.imported_image,
    }
    if pairs.get(proof.get("container")) != proof.get("image"):
        raise SafetyError("API smoke used a foreign container or image")
    if set(completion) != {
        "source",
        "run_id",
        "run_path",
        "requested_steps",
        "observed_step_count",
        "observed_step_indices",
        "step_log_path",
        "step_log_sha256",
        "hashes_path",
        "hashes_sha256",
    }:
        raise SafetyError("API observed completion fields are not exact")
    if (
        completion.get("source") != "sealed_simulation_log.v1"
        or completion.get("run_id") != run_id
        or completion.get("run_path") != run_path
        or type(completion.get("requested_steps")) is not int
        or completion.get("requested_steps") != 100
        or type(completion.get("observed_step_count")) is not int
        or completion.get("observed_step_count") != 100
        or completion.get("observed_step_indices") != list(range(100))
        or completion.get("step_log_path") != "simulation_log.csv"
        or completion.get("hashes_path") != "hashes.json"
    ):
        raise SafetyError("API observed completion is invalid")
    for name in ("step_log_sha256", "hashes_sha256"):
        digest = completion.get(name)
        if not isinstance(digest, str) or re.fullmatch(
            r"[0-9a-f]{64}", digest
        ) is None:
            raise SafetyError("API observed completion hash is invalid")
    return proof


def _selected_render_facts(
    raw: object, resources: InvocationResources, include_gui: bool
) -> dict[str, object]:
    if not isinstance(raw, Mapping) or not isinstance(
        raw.get("services"), Mapping
    ):
        raise SafetyError("Compose rendered JSON is empty or malformed")
    expected_names = ["judge", *(["judge-gui"] if include_gui else [])]
    raw_services = raw["services"]
    if raw.get("name") != resources.compose_project or set(
        raw_services
    ) != set(expected_names):
        raise SafetyError("Compose rendered topology has unexpected scope")
    services: list[dict[str, object]] = []
    selected_profiles: set[str] = set()
    for name in expected_names:
        service = raw_services.get(name)
        if not isinstance(service, Mapping):
            raise SafetyError(f"Compose rendered JSON omits {name}")
        profiles = service.get("profiles", [])
        labels = service.get("labels")
        build = service.get("build")
        contexts: object = {}
        if isinstance(build, Mapping):
            contexts = build.get("additional_contexts", {})
        expected_profiles = ["gui"] if name == "judge-gui" else []
        expected_image = (
            resources.gui_image
            if name == "judge-gui"
            else resources.headless_image
        )
        expected_contexts = (
            {"judge_base": "service:judge"}
            if name == "judge-gui"
            else {}
        )
        if (
            not isinstance(profiles, list)
            or not all(isinstance(profile, str) for profile in profiles)
            or profiles != expected_profiles
            or service.get("image") != expected_image
            or service.get("platform") != "linux/amd64"
            or not isinstance(labels, Mapping)
            or dict(labels)
            != {_LABEL_KEY: resources.invocation_id}
            or not isinstance(contexts, Mapping)
            or dict(contexts) != expected_contexts
        ):
            raise SafetyError(
                f"Compose rendered service {name} has unexpected topology"
            )
        selected_profiles.update(profiles)
        services.append(
            {
                "name": name,
                "image": service.get("image"),
                "platform": service.get("platform"),
                "profiles": list(profiles),
                "labels": dict(labels),
                "additional_contexts": dict(contexts),
            }
        )
    return {
        "source_stdout_sha256": "",
        "project": raw.get("name"),
        "profiles": sorted(selected_profiles),
        "services": services,
    }


def _inventory(
    runner: CommandRunner,
    resources: InvocationResources,
    root: Path,
    *,
    trace: list[tuple[str, str, list[str], object]] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    all_entries: list[dict[str, object]] = []
    owned: list[dict[str, object]] = []
    kind_names = {
        "container": resources.containers,
        "network": resources.networks,
        "volume": resources.volumes,
        "image": (
            resources.headless_image,
            resources.gui_image,
            resources.imported_image,
        ),
    }
    for kind, names in kind_names.items():
        for name in names:
            argv = ["docker", kind, "inspect", name]
            try:
                result = _run(runner, argv, root)
            except BaseException as exc:
                raise _InventoryFailure(
                    argv,
                    None,
                    semantic=False,
                    observed_all=all_entries,
                    observed_owned=owned,
                    error=exc,
                ) from exc
            if trace is not None:
                trace.append((kind, name, argv, result))
            if getattr(result, "returncode", 1) != 0:
                if _is_exact_inventory_absence(kind, name, result):
                    continue
                raise _InventoryFailure(
                    argv,
                    result,
                    semantic=False,
                    observed_all=all_entries,
                    observed_owned=owned,
                )
            try:
                values = _result_json(result)
            except SafetyError as exc:
                raise _InventoryFailure(
                    argv,
                    result,
                    semantic=True,
                    observed_all=all_entries,
                    observed_owned=owned,
                ) from exc
            if not isinstance(values, list) or len(values) != 1:
                raise _InventoryFailure(
                    argv,
                    result,
                    semantic=True,
                    observed_all=all_entries,
                    observed_owned=owned,
                )
            raw = values[0]
            if not isinstance(raw, Mapping):
                raise _InventoryFailure(
                    argv,
                    result,
                    semantic=True,
                    observed_all=all_entries,
                    observed_owned=owned,
                )
            try:
                parsed = _inventory_shape(
                    kind, name, raw, resources.invocation_id
                )
            except SafetyError as exc:
                raise _InventoryFailure(
                    argv,
                    result,
                    semantic=True,
                    observed_all=all_entries,
                    observed_owned=owned,
                ) from exc
            if parsed is None:
                raise _InventoryFailure(
                    argv,
                    result,
                    semantic=True,
                    observed_all=all_entries,
                    observed_owned=owned,
                )
            entry = {
                "kind": kind,
                "name": name,
                "labels": parsed["labels"],
            }
            if "running" in parsed:
                entry["running"] = parsed["running"]
            all_entries.append(entry)
            if parsed["owned"]:
                owned.append(entry)
    return all_entries, owned


def _compose_project_inventory(
    runner: CommandRunner,
    resources: InvocationResources,
    root: Path,
) -> tuple[list[str], object] | None:
    label_filter = (
        "label=com.docker.compose.project=" + resources.compose_project
    )
    for kind in ("container", "network", "volume", "image"):
        argv = ["docker", kind, "ls"]
        if kind == "container":
            argv.append("--all")
        argv.extend(["--filter", label_filter, "--format", "json"])
        try:
            result = _run(runner, argv, root)
        except BaseException as exc:
            raise _InventoryFailure(
                argv, None, semantic=False, error=exc
            ) from exc
        if getattr(result, "returncode", 1) != 0:
            raise _InventoryFailure(argv, result, semantic=False)
        text = _stream_text(getattr(result, "stdout", b"")).strip()
        if not text:
            continue
        try:
            values = [json.loads(line) for line in text.splitlines()]
        except json.JSONDecodeError as exc:
            raise _InventoryFailure(argv, result, semantic=True) from exc
        if not values or not all(
            isinstance(value, Mapping) for value in values
        ):
            raise _InventoryFailure(argv, result, semantic=True)
        return argv, result
    return None


def _is_exact_inventory_absence(
    kind: str, name: str, result: object
) -> bool:
    """Accept only a bounded Docker absence response for this exact target."""
    if getattr(result, "returncode", 1) == 0:
        return False
    stdout = _stream_bytes(getattr(result, "stdout", b""))
    stderr = _stream_bytes(getattr(result, "stderr", b""))
    try:
        stdout_text = stdout.decode("utf-8").strip()
        stderr_text = stderr.decode("utf-8").strip()
    except UnicodeDecodeError:
        return False
    if stdout_text not in {"", "[]"}:
        return False
    accepted = {
        f"Error: No such {kind}: {name}",
        f"Error response from daemon: No such {kind}: {name}",
        f"Error response from daemon: {kind} {name} not found",
        f"Error response from daemon: get {name}: no such {kind}",
    }
    return stderr_text in accepted


def _is_exact_generic_inspect_absence(name: str, result: object) -> bool:
    """Accept only Docker's bounded generic absence for this exact name."""
    if getattr(result, "returncode", 1) == 0:
        return False
    stdout = _stream_bytes(getattr(result, "stdout", b""))
    stderr = _stream_bytes(getattr(result, "stderr", b""))
    try:
        stdout_text = stdout.decode("utf-8").strip()
        stderr_text = stderr.decode("utf-8").strip()
    except UnicodeDecodeError:
        return False
    return (
        stdout_text in {"", "[]"}
        and stderr_text == f"Error: No such object: {name}"
    )


def _cleanup_action(
    entry: Mapping[str, object], resources: InvocationResources
) -> dict[str, object]:
    return {
        "resource_kind": entry["kind"],
        "resource_name": entry["name"],
        "required_label": {
            "key": _LABEL_KEY,
            "value": resources.invocation_id,
        },
    }


def _cleanup_phase_from_action(
    action: Mapping[str, object], detail: str
) -> dict[str, object]:
    phase = _not_run_record(detail)
    phase.update(action)
    return phase


def _cleanup_terminal_phase(
    action: Mapping[str, object], detail: str
) -> dict[str, object]:
    """Project one already-published terminal action even if its helper fails."""
    try:
        return _cleanup_phase_from_action(action, detail)
    except BaseException:
        now = _timestamp()
        return {
            "status": action.get("status"),
            "started_at": now,
            "finished_at": now,
            "argv": list(action.get("argv", [])),
            "exit_code": action.get("exit_code"),
            "stdout_sha256": action.get("stdout_sha256"),
            "stderr_sha256": action.get("stderr_sha256"),
            "detail": detail,
            **dict(action),
        }


def _cleanup_result_fields(
    argv: Sequence[str], result: object
) -> dict[str, object]:
    return {
        "argv": list(argv),
        "exit_code": getattr(result, "returncode", None),
        "stdout_sha256": hashlib.sha256(
            _stream_bytes(getattr(result, "stdout", b""))
        ).hexdigest(),
        "stderr_sha256": hashlib.sha256(
            _stream_bytes(getattr(result, "stderr", b""))
        ).hexdigest(),
    }


def _cleanup_inventory_action(
    *,
    kind: str,
    name: str,
    resources: InvocationResources,
    argv: Sequence[str],
    result: object,
    stage: str,
    present: bool,
    running: bool | None = None,
) -> dict[str, object]:
    """Record one successful cleanup inventory observation in the ledger."""
    action = {
        "status": "pass",
        "execution": "inventory_observation",
        "action_kind": "inventory",
        **_cleanup_action({"kind": kind, "name": name}, resources),
        **_cleanup_result_fields(argv, result),
        "inventory_stage": stage,
        "observed_present": present,
    }
    if running is not None:
        action["observed_running"] = running
    return action


def _cleanup_failure_action(
    *,
    action_kind: str,
    kind: str,
    name: str,
    resources: InvocationResources,
    execution: str,
    argv: Sequence[str] = (),
    result: object | None = None,
    inventory_stage: str | None = None,
    failure_proof: Mapping[str, object] | None = None,
) -> dict[str, object]:
    action: dict[str, object] = {
        "status": "fail",
        "execution": execution,
        "action_kind": action_kind,
        **_cleanup_action({"kind": kind, "name": name}, resources),
        "argv": [],
        "exit_code": None,
        "stdout_sha256": _EMPTY_SHA256,
        "stderr_sha256": _EMPTY_SHA256,
        "boundary": "cleanup",
    }
    if result is not None:
        action.update(_cleanup_result_fields(argv, result))
    elif execution in {"command", "command_exception"}:
        action["argv"] = list(argv)
    if inventory_stage is not None:
        action["inventory_stage"] = inventory_stage
    if failure_proof is not None:
        action["failure_proof"] = dict(failure_proof)
    return action


def _cleanup_inventory_failure_action(
    exc: _InventoryFailure,
    resources: InvocationResources,
    *,
    stage: str,
) -> dict[str, object]:
    kind = exc.argv[1]
    name = exc.argv[3]
    error = exc.error
    if error is None:
        proof = None
        execution = "command"
        if exc.semantic:
            execution = "verifier_result"
            proof = {
                "kind": "postcondition_mismatch",
                "expected": "valid_inventory_json",
                "observed": "malformed_inventory_json",
            }
        return _cleanup_failure_action(
            action_kind="inventory",
            kind=kind,
            name=name,
            resources=resources,
            execution=execution,
            argv=exc.argv,
            result=exc.result,
            inventory_stage=stage,
            failure_proof=proof,
        )
    if isinstance(error, (subprocess.TimeoutExpired, OSError)):
        streams = _command_exception_streams(error)
        if streams is None:
            return _cleanup_failure_action(
                action_kind="inventory",
                kind=kind,
                name=name,
                resources=resources,
                execution="internal_error",
                inventory_stage=stage,
                failure_proof={"kind": "internal_error"},
            )
        stdout, stderr = streams
        result = type(
            "CleanupCommandExceptionResult",
            (),
            {
                "returncode": None,
                "stdout": stdout,
                "stderr": stderr,
            },
        )()
        return _cleanup_failure_action(
            action_kind="inventory",
            kind=kind,
            name=name,
            resources=resources,
            execution="command_exception",
            argv=exc.argv,
            result=result,
            inventory_stage=stage,
            failure_proof={
                "kind": "command_exception",
                "exception_kind": (
                    "timeout"
                    if isinstance(error, subprocess.TimeoutExpired)
                    else "os_error"
                ),
            },
        )
    if isinstance(error, KeyboardInterrupt):
        interruption_kind = "keyboard_interrupt"
    elif isinstance(error, Exception):
        return _cleanup_failure_action(
            action_kind="inventory",
            kind=kind,
            name=name,
            resources=resources,
            execution="internal_error",
            inventory_stage=stage,
            failure_proof={"kind": "internal_error"},
        )
    else:
        interruption_kind = "base_exception"
    return _cleanup_failure_action(
        action_kind="inventory",
        kind=kind,
        name=name,
        resources=resources,
        execution="interruption",
        inventory_stage=stage,
        failure_proof={
            "kind": "interruption",
            "interruption_kind": interruption_kind,
            "phase": "cleanup",
        },
    )


def _unexpected_cleanup_failure(
    resources: InvocationResources,
    error: BaseException,
    *,
    state: dict[str, object] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    if isinstance(error, KeyboardInterrupt):
        execution = "interruption"
        proof = {
            "kind": "interruption",
            "interruption_kind": "keyboard_interrupt",
            "phase": "cleanup",
        }
    elif isinstance(error, Exception):
        execution = "internal_error"
        proof = {"kind": "internal_error"}
    else:
        execution = "interruption"
        proof = {
            "kind": "interruption",
            "interruption_kind": "base_exception",
            "phase": "cleanup",
        }
    before = []
    after = []
    before_complete = False
    after_complete = False
    actions: list[dict[str, object]] = []
    if state is not None:
        raw_before = state.get("before_cleanup", [])
        raw_after = state.get("after_cleanup", [])
        raw_actions = state.get("cleanup_actions", [])
        if isinstance(raw_before, list):
            before = [dict(item) for item in raw_before if isinstance(item, Mapping)]
        if isinstance(raw_after, list):
            after = [dict(item) for item in raw_after if isinstance(item, Mapping)]
        if isinstance(raw_actions, list):
            actions = [dict(item) for item in raw_actions if isinstance(item, Mapping)]
        before_complete = state.get("before_cleanup_complete") is True
        after_complete = state.get("after_cleanup_complete") is True
    raw_entry_stamp = (
        state.get("cleanup_started_at")
        if isinstance(state, Mapping)
        else None
    )
    cleanup_started_at = (
        raw_entry_stamp
        if isinstance(raw_entry_stamp, str)
        else _timestamp()
    )
    prior_failures = [
        action for action in actions if action.get("status") == "fail"
    ]
    if prior_failures:
        terminal = prior_failures[-1]
        owned = {
            "before_cleanup": before,
            "before_cleanup_complete": before_complete,
            "after_cleanup": after,
            "after_cleanup_complete": after_complete,
            "cleanup_actions": actions,
        }
        phase = _cleanup_terminal_phase(
            terminal, "cleanup terminal evidence construction failed"
        )
        phase["started_at"] = cleanup_started_at
        return phase, owned
    source = after or before
    source_item = source[0] if source else {}
    kind = str(source_item.get("kind", "container"))
    name = str(source_item.get("name", resources.containers[0]))
    stage = "final" if after_complete else "initial"
    try:
        action = _cleanup_failure_action(
            action_kind="inventory",
            kind=kind,
            name=name,
            resources=resources,
            execution=execution,
            inventory_stage=stage,
            failure_proof=proof,
        )
        phase = _cleanup_phase_from_action(
            action, "cleanup failed before terminal evidence was returned"
        )
        phase["started_at"] = cleanup_started_at
        actions.append(action)
    except BaseException:
        action = {
            "status": "fail",
            "execution": execution,
            "action_kind": "inventory",
            "resource_kind": kind,
            "resource_name": name,
            "required_label": {
                "key": _LABEL_KEY,
                "value": resources.invocation_id,
            },
            "argv": [],
            "exit_code": None,
            "stdout_sha256": _EMPTY_SHA256,
            "stderr_sha256": _EMPTY_SHA256,
            "inventory_stage": stage,
            "failure_proof": dict(proof),
            "boundary": "cleanup",
        }
        actions.append(action)
        now = _timestamp()
        phase = {
            "started_at": cleanup_started_at,
            "finished_at": now,
            "detail": "cleanup failure evidence construction failed",
            **action,
        }
    owned = {
        "before_cleanup": before,
        "before_cleanup_complete": before_complete,
        "after_cleanup": after,
        "after_cleanup_complete": after_complete,
        "cleanup_actions": actions,
    }
    return phase, owned


def _cleanup_owned(
    runner: CommandRunner,
    resources: InvocationResources,
    root: Path,
    *,
    state: dict[str, object] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    # Sampled at entry so every projected cleanup phase carries the real
    # first-teardown time, not the later summary-construction time.
    cleanup_started_at = _timestamp()
    actions: list[dict[str, object]] = []
    if state is not None:
        state["cleanup_actions"] = actions
        state["cleanup_started_at"] = cleanup_started_at

    def ordered(values: Mapping[tuple[str, str], Mapping[str, object]]) -> list[dict[str, object]]:
        return [dict(values[key]) for key in sorted(values)]

    def owned_payload(
        before: Sequence[Mapping[str, object]],
        *,
        before_complete: bool,
        after: Sequence[Mapping[str, object]],
        after_complete: bool,
    ) -> dict[str, object]:
        payload = {
            "before_cleanup": [dict(item) for item in before],
            "before_cleanup_complete": before_complete,
            "after_cleanup": [dict(item) for item in after],
            "after_cleanup_complete": after_complete,
            "cleanup_actions": actions,
        }
        if state is not None:
            state.update(payload)
        return payload

    def inventory_action_from_trace(
        trace: Sequence[tuple[str, str, list[str], object]],
        kind: str,
        name: str,
        *,
        stage: str,
        present: bool,
        running: bool | None = None,
    ) -> dict[str, object]:
        argv, result = next(
            (argv, result)
            for item_kind, item_name, argv, result in trace
            if item_kind == kind and item_name == name
        )
        return _cleanup_inventory_action(
            kind=kind,
            name=name,
            resources=resources,
            argv=argv,
            result=result,
            stage=stage,
            present=present,
            running=running,
        )

    initial_trace: list[tuple[str, str, list[str], object]] = []
    try:
        all_before, before = _inventory(
            runner, resources, root, trace=initial_trace
        )
    except _InventoryFailure as exc:
        action = _cleanup_inventory_failure_action(
            exc, resources, stage="initial"
        )
        actions.append(action)
        observed = list(exc.observed_owned)
        owned = owned_payload(
            observed,
            before_complete=False,
            after=observed,
            after_complete=False,
        )
        phase = _cleanup_terminal_phase(
            action, "initial cleanup inventory failed closed"
        )
        phase["started_at"] = cleanup_started_at
        return phase, owned

    owned_identities = {
        (str(item["kind"]), str(item["name"])) for item in before
    }
    foreign = next(
        (
            item
            for item in all_before
            if (str(item["kind"]), str(item["name"]))
            not in owned_identities
        ),
        None,
    )
    if foreign is not None:
        kind = str(foreign["kind"])
        name = str(foreign["name"])
        action = _cleanup_failure_action(
            action_kind="inventory",
            kind=kind,
            name=name,
            resources=resources,
            execution="safety_refusal",
            inventory_stage="initial",
            failure_proof={
                "kind": "cleanup_ownership_refusal",
                "resource_kind": kind,
                "resource_name": name,
                "required_label": {
                    "key": _LABEL_KEY,
                    "value": resources.invocation_id,
                },
                "observed_ownership": (
                    "missing_label"
                    if not foreign.get("labels")
                    else "mismatched_label"
                ),
            },
        )
        actions.append(action)
        owned = owned_payload(
            before,
            before_complete=True,
            after=before,
            after_complete=True,
        )
        phase = _cleanup_phase_from_action(
            action, "cleanup ownership could not be proven"
        )
        phase["started_at"] = cleanup_started_at
        return phase, owned

    remaining = {
        (str(item["kind"]), str(item["name"])): dict(item)
        for item in before
    }
    terminal: dict[str, object] | None = None

    def finish_cleanup_failure(
        action: dict[str, object], detail: str
    ) -> tuple[dict[str, object], dict[str, object]]:
        actions.append(action)
        owned = owned_payload(
            before,
            before_complete=True,
            after=ordered(remaining),
            after_complete=False,
        )
        phase = _cleanup_terminal_phase(action, detail)
        phase["started_at"] = cleanup_started_at
        return phase, owned

    for (kind, name), entry in sorted(remaining.items()):
        if kind != "container" or entry.get("running") is not True:
            continue
        initial_observation = inventory_action_from_trace(
            initial_trace,
            kind,
            name,
            stage="initial",
            present=True,
            running=True,
        )
        actions.append(initial_observation)
        stop_argv = ["docker", "container", "stop", name]
        try:
            stop_result = _run(runner, stop_argv, root)
        except (subprocess.TimeoutExpired, OSError) as exc:
            streams = _command_exception_streams(exc)
            if streams is None:
                action = _cleanup_failure_action(
                    action_kind="stop",
                    kind=kind,
                    name=name,
                    resources=resources,
                    execution="internal_error",
                    failure_proof={"kind": "internal_error"},
                )
            else:
                stdout, stderr = streams
                partial = type(
                    "CleanupCommandExceptionResult",
                    (),
                    {"returncode": None, "stdout": stdout, "stderr": stderr},
                )()
                action = _cleanup_failure_action(
                    action_kind="stop",
                    kind=kind,
                    name=name,
                    resources=resources,
                    execution="command_exception",
                    argv=stop_argv,
                    result=partial,
                    failure_proof={
                        "kind": "command_exception",
                        "exception_kind": (
                            "timeout"
                            if isinstance(exc, subprocess.TimeoutExpired)
                            else "os_error"
                        ),
                    },
                )
            return finish_cleanup_failure(action, "owned container stop failed")
        except KeyboardInterrupt:
            action = _cleanup_failure_action(
                action_kind="stop",
                kind=kind,
                name=name,
                resources=resources,
                execution="interruption",
                failure_proof={
                    "kind": "interruption",
                    "interruption_kind": "keyboard_interrupt",
                    "phase": "cleanup",
                },
            )
            return finish_cleanup_failure(action, "owned container stop interrupted")
        except Exception:
            action = _cleanup_failure_action(
                action_kind="stop",
                kind=kind,
                name=name,
                resources=resources,
                execution="internal_error",
                failure_proof={"kind": "internal_error"},
            )
            return finish_cleanup_failure(action, "owned container stop failed")
        except BaseException:
            action = _cleanup_failure_action(
                action_kind="stop",
                kind=kind,
                name=name,
                resources=resources,
                execution="interruption",
                failure_proof={
                    "kind": "interruption",
                    "interruption_kind": "base_exception",
                    "phase": "cleanup",
                },
            )
            return finish_cleanup_failure(action, "owned container stop interrupted")

        stop_action = {
            "status": "pass" if getattr(stop_result, "returncode", 1) == 0 else "fail",
            "execution": "command",
            "action_kind": "stop",
            **_cleanup_action({"kind": kind, "name": name}, resources),
            **_cleanup_result_fields(stop_argv, stop_result),
        }
        if stop_action["status"] != "pass":
            stop_action["boundary"] = "cleanup"
            return finish_cleanup_failure(stop_action, "owned container stop failed")
        actions.append(stop_action)
        try:
            _stop_all, stop_owned = _inventory(runner, resources, root)
        except _InventoryFailure as exc:
            terminal = _cleanup_inventory_failure_action(
                exc, resources, stage="requery"
            )
            return finish_cleanup_failure(
                terminal, "container stop inventory failed closed"
            )
        stopped_entry = next(
            (
                item
                for item in stop_owned
                if item.get("kind") == kind and item.get("name") == name
            ),
            None,
        )
        if stopped_entry is not None and stopped_entry.get("running") is True:
            terminal = _cleanup_failure_action(
                action_kind="stop",
                kind=kind,
                name=name,
                resources=resources,
                execution="verifier_result",
                argv=stop_argv,
                result=stop_result,
                failure_proof={
                    "kind": "postcondition_mismatch",
                    "expected": "container_stopped",
                    "observed": "container_still_running",
                },
            )
            return finish_cleanup_failure(terminal, "container stop postcondition failed")
        entry["running"] = False

    for kind, name in sorted(remaining):
        trace: list[tuple[str, str, list[str], object]] = []
        try:
            all_now, owned_now = _inventory(
                runner, resources, root, trace=trace
            )
        except _InventoryFailure as exc:
            terminal = _cleanup_inventory_failure_action(
                exc, resources, stage="requery"
            )
            actions.append(terminal)
            best_known = {
                **remaining,
                **{
                    (str(item["kind"]), str(item["name"])): dict(item)
                    for item in exc.observed_owned
                },
            }
            owned = owned_payload(
                before,
                before_complete=True,
                after=ordered(best_known),
                after_complete=False,
            )
            phase = _cleanup_terminal_phase(
                terminal, "cleanup requery inventory failed closed"
            )
            phase["started_at"] = cleanup_started_at
            return phase, owned
        exact_all = [
            item for item in all_now
            if item["kind"] == kind and item["name"] == name
        ]
        exact_owned = [
            item for item in owned_now
            if item["kind"] == kind and item["name"] == name
        ]
        if not exact_owned:
            result = next(
                result for item_kind, item_name, _argv, result in trace
                if item_kind == kind and item_name == name
            )
            observed = (
                "missing_resource"
                if not exact_all
                else "missing_or_mismatched_ownership_label"
            )
            terminal = _cleanup_failure_action(
                action_kind="inventory",
                kind=kind,
                name=name,
                resources=resources,
                execution="verifier_result",
                argv=["docker", kind, "inspect", name],
                result=result,
                inventory_stage="requery",
                failure_proof={
                    "kind": "postcondition_mismatch",
                    "expected": "exact_current_invocation_owner",
                    "observed": observed,
                },
            )
            actions.append(terminal)
            break
        inventory_observation = (
            inventory_action_from_trace(
                trace,
                kind,
                name,
                stage="requery",
                present=True,
                running=exact_owned[0].get("running") is True,
            )
            if kind == "container"
            else None
        )
        if inventory_observation is not None:
            actions.append(inventory_observation)
        if exact_owned[0].get("running") is True:
            stop_argv = ["docker", "container", "stop", name]
            try:
                stop_result = _run(runner, stop_argv, root)
            except (subprocess.TimeoutExpired, OSError) as exc:
                streams = _command_exception_streams(exc)
                if streams is None:
                    terminal = _cleanup_failure_action(
                        action_kind="stop",
                        kind=kind,
                        name=name,
                        resources=resources,
                        execution="internal_error",
                        failure_proof={"kind": "internal_error"},
                    )
                else:
                    stdout, stderr = streams
                    partial = type(
                        "CleanupCommandExceptionResult",
                        (),
                        {
                            "returncode": None,
                            "stdout": stdout,
                            "stderr": stderr,
                        },
                    )()
                    terminal = _cleanup_failure_action(
                        action_kind="stop",
                        kind=kind,
                        name=name,
                        resources=resources,
                        execution="command_exception",
                        argv=stop_argv,
                        result=partial,
                        failure_proof={
                            "kind": "command_exception",
                            "exception_kind": (
                                "timeout"
                                if isinstance(exc, subprocess.TimeoutExpired)
                                else "os_error"
                            ),
                        },
                    )
                actions.append(terminal)
                break
            except KeyboardInterrupt:
                terminal = _cleanup_failure_action(
                    action_kind="stop",
                    kind=kind,
                    name=name,
                    resources=resources,
                    execution="interruption",
                    failure_proof={
                        "kind": "interruption",
                        "interruption_kind": "keyboard_interrupt",
                        "phase": "cleanup",
                    },
                )
                actions.append(terminal)
                break
            except Exception:
                terminal = _cleanup_failure_action(
                    action_kind="stop",
                    kind=kind,
                    name=name,
                    resources=resources,
                    execution="internal_error",
                    failure_proof={"kind": "internal_error"},
                )
                actions.append(terminal)
                break
            except BaseException:
                terminal = _cleanup_failure_action(
                    action_kind="stop",
                    kind=kind,
                    name=name,
                    resources=resources,
                    execution="interruption",
                    failure_proof={
                        "kind": "interruption",
                        "interruption_kind": "base_exception",
                        "phase": "cleanup",
                    },
                )
                actions.append(terminal)
                break

            stop_action = {
                "status": "pass" if getattr(stop_result, "returncode", 1) == 0 else "fail",
                "execution": "command",
                "action_kind": "stop",
                **_cleanup_action({"kind": kind, "name": name}, resources),
                **_cleanup_result_fields(stop_argv, stop_result),
            }
            if stop_action["status"] != "pass":
                stop_action["boundary"] = "cleanup"
                actions.append(stop_action)
                terminal = stop_action
                break
            actions.append(stop_action)
            stop_trace: list[tuple[str, str, list[str], object]] = []
            try:
                _stop_all, stop_owned = _inventory(
                    runner, resources, root, trace=stop_trace
                )
            except _InventoryFailure as exc:
                terminal = _cleanup_inventory_failure_action(
                    exc, resources, stage="requery"
                )
                actions.append(terminal)
                best_known = {
                    **remaining,
                    **{
                        (str(item["kind"]), str(item["name"])): dict(item)
                        for item in exc.observed_owned
                    },
                }
                owned = owned_payload(
                    before,
                    before_complete=True,
                    after=ordered(best_known),
                    after_complete=False,
                )
                phase = _cleanup_terminal_phase(
                    terminal, "container stop inventory failed closed"
                )
                phase["started_at"] = cleanup_started_at
                return phase, owned
            stopped_entry = next(
                (
                    item
                    for item in stop_owned
                    if item.get("kind") == kind and item.get("name") == name
                ),
                None,
            )
            if stopped_entry is not None and stopped_entry.get("running") is True:
                terminal = _cleanup_failure_action(
                    action_kind="stop",
                    kind=kind,
                    name=name,
                    resources=resources,
                    execution="verifier_result",
                    argv=stop_argv,
                    result=stop_result,
                    failure_proof={
                        "kind": "postcondition_mismatch",
                        "expected": "container_stopped",
                        "observed": "container_still_running",
                    },
                )
                actions.append(terminal)
                break
            inventory_observation = inventory_action_from_trace(
                stop_trace,
                kind,
                name,
                stage="requery",
                present=True,
                running=False,
            )
            actions.append(inventory_observation)
            entry["running"] = False

        argv = ["docker", kind, "rm", name]
        try:
            result = _run(runner, argv, root)
        except (subprocess.TimeoutExpired, OSError) as exc:
            streams = _command_exception_streams(exc)
            if streams is not None:
                stdout, stderr = streams
                partial = type(
                    "CleanupCommandExceptionResult",
                    (),
                    {
                        "returncode": None,
                        "stdout": stdout,
                        "stderr": stderr,
                    },
                )()
                terminal = _cleanup_failure_action(
                    action_kind="remove",
                    kind=kind,
                    name=name,
                    resources=resources,
                    execution="command_exception",
                    argv=argv,
                    result=partial,
                    failure_proof={
                        "kind": "command_exception",
                        "exception_kind": (
                            "timeout"
                            if isinstance(exc, subprocess.TimeoutExpired)
                            else "os_error"
                        ),
                    },
                )
            else:
                terminal = _cleanup_failure_action(
                    action_kind="remove",
                    kind=kind,
                    name=name,
                    resources=resources,
                    execution="internal_error",
                    failure_proof={"kind": "internal_error"},
                )
            actions.append(terminal)
            break
        except KeyboardInterrupt:
            terminal = _cleanup_failure_action(
                action_kind="remove",
                kind=kind,
                name=name,
                resources=resources,
                execution="interruption",
                failure_proof={
                    "kind": "interruption",
                    "interruption_kind": "keyboard_interrupt",
                    "phase": "cleanup",
                },
            )
            actions.append(terminal)
            break
        except Exception:
            terminal = _cleanup_failure_action(
                action_kind="remove",
                kind=kind,
                name=name,
                resources=resources,
                execution="internal_error",
                failure_proof={"kind": "internal_error"},
            )
            actions.append(terminal)
            break
        except BaseException:
            terminal = _cleanup_failure_action(
                action_kind="remove",
                kind=kind,
                name=name,
                resources=resources,
                execution="interruption",
                failure_proof={
                    "kind": "interruption",
                    "interruption_kind": "base_exception",
                    "phase": "cleanup",
                },
            )
            actions.append(terminal)
            break

        action = {
            "status": "pass" if getattr(result, "returncode", 1) == 0 else "fail",
            "execution": "command",
            "action_kind": "remove",
            **_cleanup_action({"kind": kind, "name": name}, resources),
            **_cleanup_result_fields(argv, result),
        }
        if action["status"] == "fail":
            action["boundary"] = "cleanup"
            action["execution"] = "verifier_result"
            action["failure_proof"] = {
                "kind": "postcondition_mismatch",
                "expected": "owned_resource_removed",
                "observed": "remove_command_failed",
            }
            actions.append(action)
            terminal = action
            break
        actions.append(action)

        post_trace: list[tuple[str, str, list[str], object]] = []
        try:
            post_all, post_owned = _inventory(
                runner, resources, root, trace=post_trace
            )
        except _InventoryFailure as exc:
            terminal = _cleanup_inventory_failure_action(
                exc, resources, stage="post_remove"
            )
            actions.append(terminal)
            removed_identity = (kind, name)
            best_known = {
                key: value
                for key, value in remaining.items()
                if key != removed_identity
            }
            best_known.update(
                {
                    (str(item["kind"]), str(item["name"])): dict(item)
                    for item in exc.observed_owned
                    if (str(item["kind"]), str(item["name"]))
                    != removed_identity
                }
            )
            owned = owned_payload(
                before,
                before_complete=True,
                after=ordered(best_known),
                after_complete=False,
            )
            phase = _cleanup_terminal_phase(
                terminal, "post-remove inventory failed closed"
            )
            phase["started_at"] = cleanup_started_at
            return phase, owned
        actions.append(inventory_action_from_trace(
            post_trace,
            kind,
            name,
            stage="post_remove",
            present=any(
                item["kind"] == kind and item["name"] == name
                for item in post_all
            ),
            running=next(
                (
                    item.get("running") is True
                    for item in post_all
                    if item["kind"] == kind and item["name"] == name
                ),
                None,
            )
            if kind == "container"
            else None,
        ))
        if any(
            item["kind"] == kind and item["name"] == name
            for item in post_owned
        ):
            break
        remaining.pop((kind, name), None)

    final_trace: list[tuple[str, str, list[str], object]] = []
    try:
        _all_after, after = _inventory(
            runner, resources, root, trace=final_trace
        )
    except _InventoryFailure as exc:
        final_failure = _cleanup_inventory_failure_action(
            exc, resources, stage="final"
        )
        actions.append(final_failure)
        best_known = {
            **remaining,
            **{
                (str(item["kind"]), str(item["name"])): dict(item)
                for item in exc.observed_owned
            },
        }
        owned = owned_payload(
            before,
            before_complete=True,
            after=ordered(best_known),
            after_complete=False,
        )
        phase = _cleanup_terminal_phase(
            final_failure, "final cleanup inventory failed closed"
        )
        phase["started_at"] = cleanup_started_at
        return phase, owned

    if after and terminal is None:
        first = sorted(after, key=lambda item: (str(item["kind"]), str(item["name"])))[0]
        kind = str(first["kind"])
        name = str(first["name"])
        argv, result = next(
            (argv, result)
            for item_kind, item_name, argv, result in final_trace
            if item_kind == kind and item_name == name
        )
        terminal = _cleanup_failure_action(
            action_kind="retained_postcondition",
            kind=kind,
            name=name,
            resources=resources,
            execution="verifier_result",
            argv=argv,
            result=result,
            inventory_stage="final",
            failure_proof={
                "kind": "postcondition_mismatch",
                "expected": "empty_owned_inventory",
                "observed": "retained_owned_resource",
            },
        )
        actions.append(terminal)

    # Reaching the final inventory establishes its completeness even when a
    # preceding remove action failed or was interrupted.  A failed remove is
    # complete only when that inventory still contains the failed target; if
    # the target has disappeared, the producer cannot honestly claim a
    # complete after snapshot.  Inventory-construction failures return above
    # with ``after_complete=False`` and their best-known prefix.
    after_complete = True
    if (
        terminal is not None
        and terminal.get("action_kind") == "remove"
        and terminal.get("status") == "fail"
    ):
        after_complete = (
            terminal.get("resource_kind"), terminal.get("resource_name")
        ) in {
            (str(item.get("kind")), str(item.get("name")))
            for item in after
            if isinstance(item, Mapping)
        }
    owned = owned_payload(
        before,
        before_complete=True,
        after=after,
        after_complete=after_complete,
    )
    if terminal is not None:
        phase = _cleanup_phase_from_action(
            terminal, "owned resource cleanup failed"
        )
        phase["started_at"] = cleanup_started_at
        return phase, owned
    if not actions:
        empty_owned_phase = _not_run_record(
            "no owned resource required cleanup"
        )
        empty_owned_phase["started_at"] = cleanup_started_at
        return empty_owned_phase, owned
    last_mutation = next(
        action
        for action in reversed(actions)
        if action.get("action_kind") != "inventory"
    )
    completed_phase = _cleanup_phase_from_action(
        last_mutation, "all exact current-label resources removed"
    )
    completed_phase["started_at"] = cleanup_started_at
    return completed_phase, owned


def assert_no_name_collisions(
    command_runner: CommandRunner,
    *,
    expected: set[str],
    repo_root: Path | None = None,
) -> list[dict[str, object]]:
    root = Path.cwd() if repo_root is None else Path(repo_root)
    found: dict[tuple[str, str], dict[str, object]] = {}
    for name in sorted(expected):
        result = _run(command_runner, ["docker", "inspect", name], root)
        if getattr(result, "returncode", 1) != 0:
            if _is_exact_generic_inspect_absence(name, result):
                continue
            raise SafetyError("Docker collision inventory command failed")
        values = _result_json(result)
        if not isinstance(values, list):
            raise SafetyError("Docker inventory result must be a list")
        for raw in values:
            if not isinstance(raw, Mapping):
                raise SafetyError("Docker inventory entry must be an object")
            candidate_name = raw.get("name") or raw.get("Name")
            if isinstance(candidate_name, str):
                candidate_name = candidate_name.lstrip("/")
            if candidate_name not in expected:
                continue
            labels = raw.get("labels")
            if labels is None:
                config = raw.get("Config")
                if isinstance(config, Mapping):
                    labels = config.get("Labels")
            kind = raw.get("kind", "resource")
            entry = {
                "kind": str(kind),
                "name": candidate_name,
                "labels": dict(labels) if isinstance(labels, Mapping) else {},
            }
            found[(entry["kind"], candidate_name)] = entry
    collisions = list(found.values())
    if collisions:
        names = ", ".join(sorted(item["name"] for item in collisions))
        raise SafetyError(f"Docker resource name collision: {names}")
    return []


def _verify_live(
    repo_root: Path,
    evidence_root: Path,
    *,
    command_runner: CommandRunner = run_command,
    evidence_writer: Callable[[Path, object], None] | None = None,
    invocation_id: str | None = None,
    include_gui: bool = False,
    expected_root: Path | None = None,
) -> dict[str, object]:
    resolved_live_root = docker_status.resolve_protected_output_path(
        repo_root,
        evidence_root,
        expected_root=expected_root,
    )
    root = docker_status.validate_project_root(
        repo_root, expected_root=expected_root
    )
    canonical_live_root = (
        root / "output" / "evidence" / "docker" / "live"
    ).resolve()
    if resolved_live_root != canonical_live_root:
        raise SafetyError("evidence root must be the canonical live root")

    chosen_id = invocation_id or secrets.token_hex(6)
    resources = InvocationResources.from_id(chosen_id)
    task_env = {
        "COMPOSE_PROJECT_NAME": resources.compose_project,
        "JUDGE_IMAGE": resources.headless_image,
        "JUDGE_GUI_IMAGE": resources.gui_image,
        "TASK19_INVOCATION_ID": chosen_id,
    }

    payload = docker_status.new_evidence()
    payload["producer_contract"] = docker_status.LIVE_VERIFIER_CONTRACT
    payload["gui_requested"] = include_gui
    raw_runner = command_runner

    def runner(
        argv: Sequence[str], cwd: Path, *args: object,
        env: Mapping[str, str] | None = None,
    ) -> object:
        del env
        return raw_runner(list(argv), cwd, *args, env=dict(task_env))

    cli_argv = ["docker", "--version"]
    try:
        cli_result = _run(runner, cli_argv, root)
    except (OSError, subprocess.TimeoutExpired):
        cli_result = None
    except Exception:
        payload["cli"] = _capability_internal_failure_record(
            cli_argv, "Docker CLI capability probe raised an unexpected exception"
        )
        payload["status"] = "fail"
        payload["reason"] = "docker_cli_failed"
        docker_status.validate_live_verifier_evidence(payload)
        return payload
    if cli_result is None or getattr(cli_result, "returncode", 1) == 1:
        payload["reason"] = "docker_cli_unavailable"
        payload["cli"] = _command_record(
            "not_run",
            "Docker CLI unavailable",
            cli_argv,
            cli_result,
            root,
        )
        docker_status.validate_live_verifier_evidence(payload)
        return payload
    if getattr(cli_result, "returncode", 1) != 0:
        payload["status"] = "fail"
        payload["reason"] = "docker_cli_failed"
        payload["cli"] = _command_record(
            "fail",
            "Docker CLI capability probe failed",
            cli_argv,
            cli_result,
            root,
        )
        payload["cli"].update(
            {"execution": "command", "boundary": "capability"}
        )
        docker_status.validate_live_verifier_evidence(payload)
        return payload
    payload["cli"] = _command_record(
        "pass", "Docker CLI detected", cli_argv, cli_result, root
    )
    cli_text = _stream_text(getattr(cli_result, "stdout", b""))
    cli_match = re.search(r"(?i)docker version\s+([^,\s]+)", cli_text)
    cli_version = cli_match.group(1) if cli_match else "unknown"
    payload["cli"]["version"] = (
        cli_version
        if docker_status._STRICT_VERSION_PATTERN.fullmatch(cli_version)
        else "unknown"
    )

    daemon_argv = ["docker", "info", "--format", "{{json .ServerVersion}}"]
    try:
        daemon_result = _run(runner, daemon_argv, root)
    except (OSError, subprocess.TimeoutExpired):
        daemon_result = None
    except Exception:
        payload["daemon"] = _capability_internal_failure_record(
            daemon_argv,
            "Docker daemon capability probe raised an unexpected exception",
        )
        payload["status"] = "fail"
        payload["reason"] = "docker_daemon_failed"
        docker_status.validate_live_verifier_evidence(payload)
        return payload
    if daemon_result is None or getattr(daemon_result, "returncode", 1) == 1:
        payload["reason"] = "docker_daemon_unavailable"
        payload["daemon"] = _command_record(
            "not_run",
            "Docker daemon unavailable",
            daemon_argv,
            daemon_result,
            root,
        )
        docker_status.validate_live_verifier_evidence(payload)
        return payload
    if getattr(daemon_result, "returncode", 1) != 0:
        payload["status"] = "fail"
        payload["reason"] = "docker_daemon_failed"
        payload["daemon"] = _command_record(
            "fail",
            "Docker daemon capability probe failed",
            daemon_argv,
            daemon_result,
            root,
        )
        payload["daemon"].update(
            {"execution": "command", "boundary": "capability"}
        )
        docker_status.validate_live_verifier_evidence(payload)
        return payload
    payload["daemon"] = _command_record(
        "pass",
        "Docker daemon responded",
        daemon_argv,
        daemon_result,
        root,
    )
    daemon_text = _stream_text(getattr(daemon_result, "stdout", b""))
    daemon_match = re.search(r"([0-9]+(?:\.[0-9A-Za-z]+)+)", daemon_text)
    daemon_version = daemon_match.group(1) if daemon_match else "unknown"
    payload["daemon"]["version"] = (
        daemon_version
        if docker_status._STRICT_VERSION_PATTERN.fullmatch(daemon_version)
        else "unknown"
    )
    payload["platform"] = {"os": "linux", "architecture": "amd64"}

    expected = resources.expected_resources()
    payload["invocation_id"] = chosen_id
    payload["invocation"] = {
        "id": chosen_id,
        "compose_project": resources.compose_project,
        "headless_image": resources.headless_image,
        "gui_image": resources.gui_image,
        "imported_image": resources.imported_image,
        "ownership_label": {"key": _LABEL_KEY, "value": chosen_id},
    }
    payload["name_collisions"] = {
        "expected_resources": expected,
        "before": [],
    }
    payload["owned_resources"] = {
        "before_cleanup": [],
        "before_cleanup_complete": True,
        "after_cleanup": [],
        "after_cleanup_complete": True,
        "cleanup_actions": [],
    }

    collision_trace: list[tuple[str, str, list[str], object]] = []
    try:
        project_collision = _compose_project_inventory(runner, resources, root)
        collisions, _owned = _inventory(
            runner, resources, root, trace=collision_trace
        )
    except _InventoryFailure as exc:
        payload["name_collisions"]["before"] = exc.observed_all
        error = exc.error
        if error is None:
            record = _command_record(
                "fail",
                "collision inventory failed closed",
                exc.argv,
                exc.result,
                root,
            )
            record["boundary"] = "collision"
            if exc.semantic:
                record.update(
                    {
                        "execution": "verifier_result",
                        "failure_proof": {
                            "kind": "postcondition_mismatch",
                            "expected": "valid_exact_inventory_json",
                            "observed": "malformed_inventory_result",
                        },
                    }
                )
        elif isinstance(error, (subprocess.TimeoutExpired, OSError)):
            streams = _command_exception_streams(error)
            if streams is not None:
                stdout, stderr = streams
                partial = type(
                    "CollisionCommandExceptionResult",
                    (),
                    {
                        "returncode": None,
                        "stdout": stdout,
                        "stderr": stderr,
                    },
                )()
                record = _command_record(
                    "fail",
                    "collision inventory command raised a closed exception",
                    exc.argv,
                    partial,
                    root,
                )
                record.update(
                    {
                        "boundary": "collision",
                        "execution": "command_exception",
                        "failure_proof": {
                            "kind": "command_exception",
                            "exception_kind": (
                                "timeout"
                                if isinstance(error, subprocess.TimeoutExpired)
                                else "os_error"
                            ),
                        },
                    }
                )
            else:
                record = _not_run_record(
                    "collision inventory command exception evidence invalid"
                )
                record.update(
                    {
                        "status": "fail",
                        "boundary": "collision",
                        "execution": "internal_error",
                        "failure_proof": {"kind": "internal_error"},
                    }
                )
        elif isinstance(error, KeyboardInterrupt):
            record = _not_run_record("collision inventory interrupted")
            record.update(
                {
                    "status": "fail",
                    "boundary": "collision",
                    "execution": "interruption",
                    "failure_proof": {
                        "kind": "interruption",
                        "interruption_kind": "keyboard_interrupt",
                        "phase": "collision",
                    },
                }
            )
        elif isinstance(error, Exception):
            record = _not_run_record(
                "collision inventory raised an internal exception"
            )
            record.update(
                {
                    "status": "fail",
                    "boundary": "collision",
                    "execution": "internal_error",
                    "failure_proof": {"kind": "internal_error"},
                }
            )
        else:
            record = _not_run_record("collision inventory interrupted")
            record.update(
                {
                    "status": "fail",
                    "boundary": "collision",
                    "execution": "interruption",
                    "failure_proof": {
                        "kind": "interruption",
                        "interruption_kind": "base_exception",
                        "phase": "collision",
                    },
                }
            )
        payload["static_contract"] = record
        payload["status"] = "fail"
        payload["reason"] = "collision_failed"
        docker_status.validate_live_verifier_evidence(payload)
        return payload
    if project_collision is not None:
        argv, result = project_collision
        record = _command_record(
            "fail",
            "Compose project resource already exists",
            argv,
            result,
            root,
        )
        record.update(
            {
                "boundary": "collision",
                "execution": "verifier_result",
                "failure_proof": {
                    "kind": "postcondition_mismatch",
                    "expected": "no_compose_project_resources",
                    "observed": "compose_project_resources_present",
                },
            }
        )
        payload["static_contract"] = record
        payload["status"] = "fail"
        payload["reason"] = "collision_failed"
        docker_status.validate_live_verifier_evidence(payload)
        return payload
    if collisions:
        payload["name_collisions"]["before"] = collisions
        last = collisions[-1]
        traced = next(
            (
                (argv, result)
                for kind, name, argv, result in collision_trace
                if kind == last["kind"] and name == last["name"]
            ),
            None,
        )
        if traced is None:
            record = _not_run_record("collision evidence construction failed")
            record.update(
                {
                    "status": "fail",
                    "boundary": "collision",
                    "execution": "internal_error",
                    "failure_proof": {"kind": "internal_error"},
                }
            )
        else:
            argv, result = traced
            record = _command_record(
                "fail",
                "exact expected Docker resource already exists",
                argv,
                result,
                root,
            )
            record.update(
                {
                    "boundary": "collision",
                    "execution": "verifier_result",
                    "failure_proof": {
                        "kind": "collision_detected",
                        "collisions": collisions,
                    },
                }
            )
        payload["static_contract"] = record
        payload["status"] = "fail"
        payload["reason"] = "collision_failed"
        docker_status.validate_live_verifier_evidence(payload)
        return payload

    invocation_dir = canonical_live_root / chosen_id
    invocation_dir.mkdir(parents=True, exist_ok=False)
    relative_dir = f"output/evidence/docker/live/{chosen_id}"
    tar_path = f"{relative_dir}/headless-image.tar"
    compose_env = dict(task_env)
    compose_prefix = [
        "docker",
        "compose",
        "--project-name",
        resources.compose_project,
    ]
    if include_gui:
        compose_scope = [*compose_prefix, "--profile", "gui"]
    else:
        compose_scope = compose_prefix
    mutation_started = False
    current_boundary = "compose_contract"
    primary_failure = False
    writer = evidence_writer
    exported_contents: list[dict[str, object]] = []
    export_units: list[dict[str, object]] = []
    run_exports: list[dict[str, object]] = []
    last_argv: list[str] = []
    last_result: object | None = None
    save_stage_names = (
        "controlled_stop",
        "image_save",
        "image_load",
        "image_retag",
        "imported_container_create",
        "imported_container_start",
        "imported_docker_health",
        "imported_api_health",
        "imported_api_smoke",
    )
    save_load_proof: dict[str, object] | None = None

    def record_export_failure(attempt: Mapping[str, object]) -> None:
        nonlocal exported_contents
        attempt_value = dict(attempt)
        try:
            exported_contents = _walk_exported_regular_files(invocation_dir)
            completed_paths = {
                str(path)
                for unit in export_units
                for path in unit.get("content_paths", [])
            }
            attempt_value["partial_contents"] = [
                dict(entry)
                for entry in exported_contents
                if str(entry.get("path")) not in completed_paths
            ]
            attempt_value["partial_contents_sha256"] = _canonical_json_sha256(
                attempt_value["partial_contents"]
            )
        except Exception:
            attempt_value = _not_run_record(
                "export failure evidence construction failed"
            )
            attempt_value.update(
                {
                    "status": "fail",
                    "boundary": "evidence_export",
                    "execution": "internal_error",
                    "failure_proof": {"kind": "internal_error"},
                    "partial_contents": [],
                    "partial_contents_sha256": _canonical_json_sha256([]),
                }
            )
        except BaseException as exc:
            attempt_value = _not_run_record(
                "export failure evidence construction interrupted"
            )
            attempt_value.update(
                {
                    "status": "fail",
                    "boundary": "evidence_export",
                    "execution": "interruption",
                    "failure_proof": {
                        "kind": "interruption",
                        "interruption_kind": (
                            "keyboard_interrupt"
                            if isinstance(exc, KeyboardInterrupt)
                            else "base_exception"
                        ),
                        "phase": "exported_evidence",
                    },
                    "partial_contents": [],
                    "partial_contents_sha256": _canonical_json_sha256([]),
                }
            )
        payload["exported_evidence"] = {
            "status": "fail",
            "path": relative_dir,
            "contents": exported_contents,
            "run_exports": run_exports,
            "export_units": export_units,
            "attempt": attempt_value,
        }

    def link_save_failure(
        boundary: str, record: Mapping[str, object]
    ) -> bool:
        if save_load_proof is None or boundary not in save_stage_names:
            return False
        save_load_proof[boundary] = dict(record)
        payload["save_load"] = dict(record)
        return True

    def run_step(
        boundary: str,
        argv: Sequence[str],
        detail: str,
        *,
        env: Mapping[str, str] | None = None,
    ) -> tuple[object, dict[str, object]]:
        nonlocal current_boundary, last_argv, last_result
        current_boundary = boundary
        try:
            result, record = _execute(
                runner, argv, root, phase=boundary, detail=detail, env=env
            )
        except _StepFailure:
            raise
        except (subprocess.TimeoutExpired, OSError) as exc:
            streams = _command_exception_streams(exc)
            if streams is None:
                raise _InternalFailure(boundary) from exc
            raise _CommandExceptionFailure(
                boundary, argv, exc, streams[0], streams[1]
            ) from exc
        except Exception as exc:
            raise _InternalFailure(boundary) from exc
        last_argv = list(argv)
        last_result = result
        return result, record

    def api_command(
        container: str,
        marker: str,
        run_id: str = "",
        image: str = "",
    ) -> list[str]:
        if marker == "api-health":
            return [
                "docker",
                "exec",
                container,
                "python",
                "-c",
                _API_HEALTH_SCRIPT,
                marker,
            ]
        if marker == "api-smoke":
            return [
                "docker",
                "exec",
                container,
                "python",
                "-c",
                _API_SMOKE_SCRIPT,
                container,
                image,
                run_id,
                marker,
                "--run-id",
                run_id,
            ]
        if marker == "gui-frames":
            return [
                "docker",
                "exec",
                container,
                "python",
                "-c",
                _GUI_FRAMES_SCRIPT,
                container,
                image,
                marker,
            ]
        raise SafetyError("unknown API probe marker")

    try:
        quiet_argv = [*compose_scope, "config", "--quiet"]
        _quiet_result, static_record = run_step(
            "compose_contract",
            quiet_argv,
            "Compose quiet contract passed",
            env=compose_env,
        )
        render_argv = [*compose_scope, "config", "--format", "json"]
        render_result, _render_record = run_step(
            "compose_contract",
            render_argv,
            "Compose rendered JSON captured",
            env=compose_env,
        )
        render_stdout = _stream_bytes(
            getattr(render_result, "stdout", b"")
        )
        if not render_stdout:
            raise SafetyError("Compose rendered JSON must be nonempty")
        facts = _selected_render_facts(
            _result_json(render_result), resources, include_gui
        )
        render_hash = hashlib.sha256(render_stdout).hexdigest()
        facts["source_stdout_sha256"] = render_hash
        static_record["render_proof"] = {
            "status": "pass",
            "argv": render_argv,
            "exit_code": 0,
            "stdout_sha256": render_hash,
            "selected_facts": facts,
        }
        payload["static_contract"] = static_record

        mutation_started = True
        build_argv = [*compose_prefix, "build", "judge"]
        _build_result, build_record = run_step(
            "headless_build",
            build_argv,
            "headless image built",
            env=compose_env,
        )
        metadata_argv = [
            "docker",
            "image",
            "inspect",
            resources.headless_image,
        ]
        metadata_result, _metadata_record = run_step(
            "image_identity",
            metadata_argv,
            "headless image identity captured",
        )
        metadata = _result_json(metadata_result)
        if (
            not isinstance(metadata, list)
            or len(metadata) != 1
            or not isinstance(metadata[0], Mapping)
        ):
            raise _SemanticFailure(
                "image_identity",
                metadata_argv,
                metadata_result,
                "one_image_identity_object",
                "malformed_image_identity",
            )
        try:
            image_identity = _parse_image_identity(
                metadata[0],
                expected_tag=resources.headless_image,
                invocation_id=chosen_id,
            )
        except SafetyError:
            raise _SemanticFailure(
                "image_identity",
                metadata_argv,
                metadata_result,
                "four_real_digests_and_current_label",
                "incomplete_or_unowned_image_identity",
            )
        inspected_rootfs_layers = list(image_identity.pop("rootfs_layers"))
        if image_identity.get("repository_digest") != image_identity.get(
            "headless_image_id"
        ):
            image_identity.pop("repository_digest", None)
        payload["invocation"].update(image_identity)
        payload["headless_build"] = build_record

        start_argv = [*compose_prefix, "up", "--detach", "--no-build", "judge"]
        run_step(
            "headless_start",
            start_argv,
            "headless service started",
            env=compose_env,
        )
        health_argv = [
            "docker",
            "inspect",
            "--format",
            "{{.State.Health.Status}}",
            resources.containers[0],
        ]
        health_result, health_record = run_step(
            "container_health",
            health_argv,
            "headless container health passed",
        )
        if (
            _stream_text(getattr(health_result, "stdout", b"")).strip()
            != "healthy"
        ):
            raise _SemanticFailure(
                "container_health",
                health_argv,
                health_result,
                "healthy",
                "unexpected_health_state",
            )
        api_health_argv = api_command(resources.containers[0], "api-health")
        api_health_result, api_health_record = run_step(
            "api_health", api_health_argv, "exact API health queried"
        )
        if _result_json(api_health_result) != {
            "status": "ok",
            "run_workers": 1,
        }:
            raise _SemanticFailure(
                "api_health",
                api_health_argv,
                api_health_result,
                "exact_status_ok_json",
                "unexpected_health_json",
            )
        health_record["api_health"] = api_health_record
        payload["headless_health"] = health_record

        headless_run = f"headless-run-{chosen_id}"
        smoke_result, _ = run_step(
            "primary_api_run",
            api_command(
                resources.containers[0],
                "api-smoke",
                headless_run,
                resources.headless_image,
            ),
            "primary API-created 100-step run completed",
        )
        headless_proof = _parse_api_proof(smoke_result, resources)
        payload["headless_smoke"] = _api_record(
            headless_proof, "primary API-created 100-step run completed"
        )
        payload["quick_smoke"] = dict(headless_proof)
        payload["quick_smoke"]["evidence_class"] = "quick_smoke"

        imported_container = resources.containers[2]
        save_load_proof = {
            "tar_path": tar_path,
            "imported_image": resources.imported_image,
            "imported_container": imported_container,
        }
        save_load_proof.update(
            {
                stage: _not_run_record(f"{stage} not reached")
                for stage in save_stage_names
            }
        )
        payload["save_load_proof"] = save_load_proof

        _stop_result, stop_record = run_step(
            "controlled_stop",
            ["docker", "container", "stop", resources.containers[0]],
            "primary container stopped under control",
        )
        save_load_proof["controlled_stop"] = stop_record
        save_argv = [
            "docker",
            "image",
            "save",
            "--output",
            tar_path,
            resources.headless_image,
        ]
        _save_result, save_record = run_step(
            "image_save", save_argv, "headless image saved"
        )
        try:
            archive_proof = _validate_saved_image_archive(
                invocation_dir / "headless-image.tar",
                expected_tag=resources.headless_image,
                expected_image_id=str(
                    payload["invocation"]["headless_image_id"]
                ),
                expected_rootfs_layers=inspected_rootfs_layers,
            )
        except SafetyError as exc:
            raise _LocalFailure(
                "image_save", "read_saved_image_archive"
            ) from exc
        payload["invocation"]["config_digest"] = archive_proof[
            "config_digest"
        ]
        save_load_proof = {
            "tar_path": tar_path,
            "tar_sha256": archive_proof["sha256"],
            "tar_byte_length": archive_proof["byte_length"],
            "imported_image": resources.imported_image,
            "imported_container": imported_container,
            **{
                stage: save_load_proof[stage]
                for stage in save_stage_names
            },
        }
        payload["save_load_proof"] = save_load_proof
        save_load_proof["image_save"] = save_record
        load_argv = ["docker", "image", "load", "--input", tar_path]
        _load_result, load_record = run_step(
            "image_load", load_argv, "headless image loaded"
        )
        save_load_proof["image_load"] = load_record
        tag_argv = [
            "docker",
            "image",
            "tag",
            resources.headless_image,
            resources.imported_image,
        ]
        _tag_result, tag_record = run_step(
            "image_retag", tag_argv, "loaded image independently retagged"
        )
        save_load_proof["image_retag"] = tag_record
        create_argv = [
            "docker",
            "container",
            "create",
            "--name",
            imported_container,
            "--label",
            resources.label,
            resources.imported_image,
        ]
        _create_result, create_record = run_step(
            "imported_container_create",
            create_argv,
            "imported-image container created",
        )
        save_load_proof["imported_container_create"] = create_record
        imported_start_argv = [
            "docker",
            "container",
            "start",
            imported_container,
        ]
        _imported_start_result, imported_start_record = run_step(
            "imported_container_start",
            imported_start_argv,
            "imported-image container started",
        )
        save_load_proof["imported_container_start"] = imported_start_record
        imported_health_argv = [
            "docker",
            "inspect",
            "--format",
            "{{.State.Health.Status}}",
            imported_container,
        ]
        imported_health_result, imported_health_record = run_step(
            "imported_docker_health",
            imported_health_argv,
            "imported-image health passed",
        )
        if (
            _stream_text(
                getattr(imported_health_result, "stdout", b"")
            ).strip()
            != "healthy"
        ):
            raise SafetyError("imported container health postcondition failed")
        save_load_proof["imported_docker_health"] = imported_health_record
        imported_api_health_result, imported_api_health_record = run_step(
            "imported_api_health",
            api_command(imported_container, "api-health"),
            "imported exact API health queried",
        )
        if _result_json(imported_api_health_result) != {
            "status": "ok",
            "run_workers": 1,
        }:
            raise SafetyError("imported exact API health JSON mismatched")
        save_load_proof["imported_api_health"] = imported_api_health_record
        imported_run = f"imported-run-{chosen_id}"
        imported_smoke_result, _ = run_step(
            "imported_api_smoke",
            api_command(
                imported_container,
                "api-smoke",
                imported_run,
                resources.imported_image,
            ),
            "imported API-created 100-step run completed",
        )
        imported_proof = _parse_api_proof(imported_smoke_result, resources)
        repeated_smoke = _api_record(
            imported_proof, "imported API-created 100-step run completed"
        )
        save_load_proof["imported_api_smoke"] = repeated_smoke
        payload["save_load"] = save_record

        gui_proof: dict[str, object] | None = None
        frame_files: list[tuple[dict[str, object], bytes]] = []
        if include_gui:
            gui_build_argv = [
                *compose_prefix,
                "--profile",
                "gui",
                "build",
                "judge-gui",
            ]
            _gui_build_result, gui_build_record = run_step(
                "gui_build", gui_build_argv, "GUI image built", env=compose_env
            )
            payload["gui_build"] = gui_build_record
            gui_start_argv = [
                *compose_prefix,
                "--profile",
                "gui",
                "up",
                "--detach",
                "--no-build",
                "judge-gui",
            ]
            run_step(
                "gui_start",
                gui_start_argv,
                "GUI service started",
                env=compose_env,
            )
            gui_container = resources.containers[1]
            gui_health_result, _ = run_step(
                "gui_health",
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Health.Status}}",
                    gui_container,
                ],
                "GUI container health passed",
            )
            if (
                _stream_text(
                    getattr(gui_health_result, "stdout", b"")
                ).strip()
                != "healthy"
            ):
                raise SafetyError("GUI container health postcondition failed")
            gui_api_health_result, _ = run_step(
                "gui_health",
                api_command(gui_container, "api-health"),
                "GUI exact API health queried",
            )
            if _result_json(gui_api_health_result) != {
                "status": "ok",
                "run_workers": 1,
            }:
                raise SafetyError("GUI exact API health JSON mismatched")
            frames_result, _ = run_step(
                "gui_frame_capture",
                api_command(
                    gui_container,
                    "gui-frames",
                    image=resources.gui_image,
                ),
                "GUI API run and two PNG frames captured",
            )
            combined_value = _result_json(frames_result)
            if not isinstance(combined_value, Mapping) or set(
                combined_value
            ) != {"api_proof", "active_observation", "frames"}:
                raise SafetyError("GUI combined probe result is malformed")
            proof_result = type(
                "GuiApiProofResult",
                (),
                {"stdout": json.dumps(combined_value["api_proof"])},
            )()
            gui_proof = _parse_api_proof(proof_result, resources)
            frames_value = combined_value["frames"]
            if not isinstance(frames_value, list) or len(frames_value) != 2:
                raise SafetyError(
                    "GUI frame capture requires exactly two frames"
                )
            previous_sequence = -1
            previous_time = -1.0
            portable_paths: set[str] = set()
            frame_proof: list[dict[str, object]] = []
            for index, raw in enumerate(frames_value):
                if not isinstance(raw, Mapping):
                    raise SafetyError("GUI frame metadata is malformed")
                path = str(raw.get("path", ""))
                identity = path.replace("\\", "/").casefold()
                if (
                    path != f"gui/frames/frame-000{index + 1}.png"
                    or "/./" in f"/{path}/"
                    or ".." in Path(path).parts
                    or identity in portable_paths
                ):
                    raise SafetyError("GUI frame path is unsafe or aliased")
                portable_paths.add(identity)
                sequence = raw.get("sequence")
                simulation_time = raw.get("simulation_time")
                if (
                    isinstance(sequence, bool)
                    or not isinstance(sequence, int)
                    or sequence <= previous_sequence
                    or isinstance(simulation_time, bool)
                    or not isinstance(simulation_time, (int, float))
                    or not math.isfinite(float(simulation_time))
                    or simulation_time <= previous_time
                ):
                    raise SafetyError(
                        "GUI frame sequence/time did not advance"
                    )
                previous_sequence = sequence
                previous_time = float(simulation_time)
                try:
                    data = base64.b64decode(
                        str(raw.get("png_base64", "")), validate=True
                    )
                except (ValueError, TypeError) as exc:
                    raise SafetyError(
                        "GUI frame bytes are not valid base64"
                    ) from exc
                _validate_png_bytes(data)
                entry = {
                    "path": path,
                    "byte_length": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "sequence": sequence,
                    "simulation_time": simulation_time,
                }
                frame_files.append((entry, data))
                frame_proof.append(entry)
            payload["gui_smoke"] = _api_record(
                gui_proof, "GUI API run and frame capture passed"
            )
            payload["gui_frame_proof"] = {
                "run_id": gui_proof["run_id"],
                "container": gui_proof["container"],
                "image": gui_proof["image"],
                "active_observation": dict(
                    combined_value["active_observation"]
                ),
                "frames": frame_proof,
            }

        current_boundary = "evidence_export"

        def current_contents() -> list[dict[str, object]]:
            return _walk_exported_regular_files(invocation_dir)

        def destination_paths(
            contents: Sequence[Mapping[str, object]], destination: str
        ) -> list[str]:
            prefix = destination + "/"
            return [
                str(entry["path"])
                for entry in contents
                if entry.get("path") == destination
                or str(entry.get("path", "")).startswith(prefix)
            ]

        initial_contents = current_contents()
        tar_entries = [
            entry
            for entry in initial_contents
            if entry.get("path") == "headless-image.tar"
        ]
        if tar_entries != [
            {
                "path": "headless-image.tar",
                "byte_length": save_load_proof["tar_byte_length"],
                "sha256": save_load_proof["tar_sha256"],
            }
        ]:
            raise SafetyError("validated saved image tar is not exportable")
        export_units.append(
            {
                "kind": "saved_image_tar",
                "scope": "shared",
                "status": "pass",
                "source": "headless-image.tar",
                "destination": "headless-image.tar",
                "content_paths": ["headless-image.tar"],
            }
        )

        proof_scopes: list[tuple[str, Mapping[str, object]]] = [
            ("headless", headless_proof),
            ("imported", imported_proof),
        ]
        if gui_proof is not None:
            proof_scopes.append(("gui", gui_proof))
        for scope, proof in proof_scopes:
            container = str(proof["container"])
            run_id = str(proof["run_id"])
            output = proof["output"]
            if not isinstance(output, Mapping):
                raise SafetyError("API output proof is malformed")
            run_path = str(output["path"])
            run_destination = f"{scope}/{run_path}"
            run_source = f"{container}:/app/output/{run_path}/."
            _copy_result, copy_record = run_step(
                "evidence_export",
                [
                    "docker",
                    "cp",
                    run_source,
                    f"{relative_dir}/{run_destination}",
                ],
                f"exported sealed run evidence for {run_id}",
            )
            host_run = invocation_dir.joinpath(*PurePosixPath(run_destination).parts)
            if EvidenceReader.validate(host_run):
                raise SafetyError("exported run evidence is not sealed")
            copied_contents = current_contents()
            copied_paths = destination_paths(
                copied_contents, run_destination
            )
            if not copied_paths:
                raise SafetyError("exported run evidence is empty")
            by_path = {
                str(entry["path"]): entry for entry in copied_contents
            }
            completion = proof["observed_completion"]
            if not isinstance(completion, Mapping):
                raise SafetyError("observed completion proof is malformed")
            step_path = f"{run_destination}/{completion['step_log_path']}"
            hashes_path = f"{run_destination}/{completion['hashes_path']}"
            if (
                by_path.get(step_path, {}).get("sha256")
                != completion.get("step_log_sha256")
                or by_path.get(hashes_path, {}).get("sha256")
                != completion.get("hashes_sha256")
            ):
                raise SafetyError("host run export does not match completion")
            export_units.append(
                {
                    "kind": "run_tree",
                    "scope": scope,
                    "status": "pass",
                    "source": run_source,
                    "destination": run_destination,
                    "content_paths": copied_paths,
                    "record": copy_record,
                }
            )
            run_exports.append(
                {
                    "scope": scope,
                    "container": container,
                    "image": proof["image"],
                    "run_id": run_id,
                    "output_path": run_path,
                    "host_prefix": run_destination,
                    "sealed": True,
                }
            )

            launcher_source = (
                f"{container}:/app/output/evidence/docker/launcher.json"
            )
            launcher_destination = f"{scope}/diagnostics/launcher.json"
            _launcher_result, launcher_record = run_step(
                "evidence_export",
                [
                    "docker",
                    "cp",
                    launcher_source,
                    f"{relative_dir}/{launcher_destination}",
                ],
                f"exported launcher diagnostics for {scope}",
            )
            launcher_contents = current_contents()
            launcher_paths = destination_paths(
                launcher_contents, launcher_destination
            )
            if launcher_paths != [launcher_destination]:
                raise SafetyError("launcher diagnostics export is incomplete")
            launcher_entry = next(
                item
                for item in launcher_contents
                if item["path"] == launcher_destination
            )
            export_units.append(
                {
                    "kind": "launcher_diagnostics",
                    "scope": scope,
                    "status": "pass",
                    "source": launcher_source,
                    "destination": launcher_destination,
                    "content_paths": launcher_paths,
                    "record": launcher_record,
                    "observed_content": dict(launcher_entry),
                }
            )

        for index, (entry, data) in enumerate(frame_files):
            destination = str(entry["path"])
            target = invocation_dir.joinpath(*PurePosixPath(destination).parts)
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            except OSError as exc:
                raise _LocalFailure(
                    "evidence_export", "write_exported_artifact"
                ) from exc
            frame_contents = current_contents()
            frame_paths = destination_paths(frame_contents, destination)
            if frame_paths != [destination]:
                raise SafetyError("captured GUI frame export is incomplete")
            actual_frame = next(
                item for item in frame_contents if item["path"] == destination
            )
            if (
                actual_frame["byte_length"] != entry["byte_length"]
                or actual_frame["sha256"] != entry["sha256"]
            ):
                raise SafetyError("captured GUI frame bytes changed")
            export_units.append(
                {
                    "kind": "gui_frame",
                    "scope": "gui",
                    "status": "pass",
                    "source": f"captured_gui_frame_{index}",
                    "destination": destination,
                    "content_paths": frame_paths,
                }
            )

        exported_contents = current_contents()
        described_paths = [
            path
            for unit in export_units
            for path in unit["content_paths"]
        ]
        if sorted(described_paths) != sorted(
            str(entry["path"]) for entry in exported_contents
        ):
            raise SafetyError("export units do not close over host contents")
        payload["exported_evidence"] = {
            "status": "pass",
            "path": relative_dir,
            "contents": exported_contents,
            "run_exports": run_exports,
            "export_units": export_units,
        }
    except _StepFailure as exc:
        primary_failure = True
        boundary = exc.phase
        if boundary == "evidence_export":
            attempt = _command_record(
                "fail", exc.detail, exc.argv, exc.result, root
            )
            attempt.update({"boundary": boundary, "execution": "command"})
            record_export_failure(attempt)
        else:
            owner = docker_status.FAILURE_BOUNDARY_OWNERS[boundary]
            failure_record = _command_record(
                "fail", exc.detail, exc.argv, exc.result, root
            )
            failure_record.update(
                {"boundary": boundary, "execution": "command"}
            )
            if not link_save_failure(boundary, failure_record):
                payload[owner] = failure_record
        payload["status"] = "fail"
        payload["reason"] = f"{boundary}_failed"
    except _SemanticFailure as exc:
        primary_failure = True
        boundary = exc.boundary
        owner = docker_status.FAILURE_BOUNDARY_OWNERS[boundary]
        record = _command_record("fail", str(exc), exc.argv, exc.result, root)
        record.update(
            {
                "boundary": boundary,
                "execution": "verifier_result",
                "failure_proof": {
                    "kind": "postcondition_mismatch",
                    "expected": exc.expected,
                    "observed": exc.observed,
                },
            }
        )
        if not link_save_failure(boundary, record):
            payload[owner] = record
        payload["status"] = "fail"
        payload["reason"] = f"{boundary}_failed"
    except _LocalFailure as exc:
        primary_failure = True
        boundary = exc.boundary
        if (
            boundary == "image_save"
            and exc.operation == "read_saved_image_archive"
            and last_result is not None
        ):
            record = _command_record(
                "fail",
                "saved image archive could not be validated",
                last_argv,
                last_result,
                root,
            )
        else:
            record = _not_run_record("local export operation failed")
        record.update(
            {
                "status": "fail",
                "boundary": boundary,
                "execution": "local_operation",
                "failure_proof": {
                    "kind": "local_operation",
                    "operation": exc.operation,
                },
            }
        )
        if boundary == "evidence_export":
            record_export_failure(record)
        else:
            if not link_save_failure(boundary, record):
                payload[docker_status.FAILURE_BOUNDARY_OWNERS[boundary]] = record
        payload["status"] = "fail"
        payload["reason"] = f"{boundary}_failed"
    except _CommandExceptionFailure as exc:
        primary_failure = True
        boundary = exc.boundary
        error = exc.error
        result = type(
            "CommandExceptionResult",
            (),
            {
                "returncode": None,
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            },
        )()
        record = _command_record(
            "fail", "Docker command raised a closed exception",
            exc.argv, result, root,
        )
        record.update(
            {
                "boundary": boundary,
                "execution": "command_exception",
                "failure_proof": {
                    "kind": "command_exception",
                    "exception_kind": (
                        "timeout"
                        if isinstance(error, subprocess.TimeoutExpired)
                        else "os_error"
                    )
                },
            }
        )
        if boundary == "evidence_export":
            record_export_failure(record)
        elif not link_save_failure(boundary, record):
            payload[docker_status.FAILURE_BOUNDARY_OWNERS[boundary]] = record
        payload["status"] = "fail"
        payload["reason"] = f"{boundary}_failed"
    except _InternalFailure as exc:
        primary_failure = True
        boundary = exc.boundary
        record = _not_run_record("verifier internal failure")
        record.update(
            {
                "status": "fail",
                "boundary": boundary,
                "execution": "internal_error",
                "failure_proof": {"kind": "internal_error"},
            }
        )
        if boundary == "evidence_export":
            record_export_failure(record)
        elif not link_save_failure(boundary, record):
            payload[docker_status.FAILURE_BOUNDARY_OWNERS[boundary]] = record
        payload["status"] = "fail"
        payload["reason"] = f"{boundary}_failed"
    except SafetyError:
        primary_failure = True
        boundary = current_boundary
        record = _command_record(
            "fail",
            "successful command produced an invalid postcondition",
            last_argv,
            last_result,
            root,
        )
        record.update(
            {
                "boundary": boundary,
                "execution": "verifier_result",
                "failure_proof": {
                    "kind": "postcondition_mismatch",
                    "expected": "valid_boundary_postcondition",
                    "observed": "invalid_boundary_result",
                },
            }
        )
        if boundary == "evidence_export":
            record_export_failure(record)
        elif not link_save_failure(boundary, record):
            payload[docker_status.FAILURE_BOUNDARY_OWNERS[boundary]] = record
        payload["status"] = "fail"
        payload["reason"] = f"{boundary}_failed"
    except Exception:
        primary_failure = True
        boundary = current_boundary
        owner = docker_status.FAILURE_BOUNDARY_OWNERS.get(boundary)
        if owner is None and boundary != "evidence_export":
            owner = "save_load"
            boundary = "controlled_stop"
        record = _not_run_record("verifier internal failure")
        record.update(
            {
                "status": "fail",
                "boundary": boundary,
                "execution": "internal_error",
                "failure_proof": {"kind": "internal_error"},
            }
        )
        if boundary == "evidence_export":
            record_export_failure(record)
        elif not link_save_failure(boundary, record):
            payload[owner] = record
        payload["status"] = "fail"
        payload["reason"] = f"{boundary}_failed"
    except BaseException as exc:
        primary_failure = True
        boundary = current_boundary
        owner = docker_status.FAILURE_BOUNDARY_OWNERS.get(boundary)
        if owner is None and boundary != "evidence_export":
            owner = "save_load"
            boundary = "controlled_stop"
        proof = {
            "kind": "interruption",
            "interruption_kind": (
                "keyboard_interrupt"
                if isinstance(exc, KeyboardInterrupt)
                else "base_exception"
            ),
            "phase": (
                "exported_evidence"
                if boundary == "evidence_export"
                else owner
            ),
        }
        record = _not_run_record("verifier boundary interrupted")
        record.update(
            {
                "status": "fail",
                "boundary": boundary,
                "execution": "interruption",
                "failure_proof": proof,
            }
        )
        if boundary == "evidence_export":
            record_export_failure(record)
        elif not link_save_failure(boundary, record):
            payload[owner] = record
        payload["status"] = "fail"
        payload["reason"] = f"{boundary}_failed"
    finally:
        if mutation_started:
            cleanup_state: dict[str, object] = {}
            try:
                cleanup_record, owned = _cleanup_owned(
                    runner, resources, root, state=cleanup_state
                )
            except BaseException as exc:
                cleanup_record, owned = _unexpected_cleanup_failure(
                    resources, exc, state=cleanup_state
                )
            payload["cleanup"] = cleanup_record
            payload["owned_resources"] = owned
            if cleanup_record["status"] == "fail":
                cleanup_record["boundary"] = "cleanup"
                payload["status"] = "fail"
                if not primary_failure:
                    payload["reason"] = "cleanup_failed"

    if not primary_failure and payload["cleanup"]["status"] == "pass":
        payload["status"] = "pass"
        payload["reason"] = docker_status.LIVE_PASS_REASON
    docker_status.validate_live_verifier_evidence(payload)
    if writer is not None:
        writer(invocation_dir / "docker-status.json", payload)
    return payload


def verify_live(
    repo_root: Path,
    evidence_root: Path,
    *,
    command_runner: CommandRunner = run_command,
    evidence_writer: Callable[[Path, object], None] | None = None,
    invocation_id: str | None = None,
    include_gui: bool = False,
    expected_root: Path | None = None,
) -> dict[str, object]:
    """Refuse direct mutation; the CLI owns the explicit live-execution gate."""
    del (
        repo_root,
        evidence_root,
        command_runner,
        evidence_writer,
        invocation_id,
        include_gui,
        expected_root,
    )
    raise SafetyError("live verification requires CLI --execute-live confirmation")


def main(
    argv: Sequence[str] | None = None,
    *,
    command_runner: CommandRunner = run_command,
    evidence_writer: Callable[[Path, object], None] | None = None,
    expected_root: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path("output/evidence/docker/live"),
    )
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--include-gui", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_live:
        return 2
    try:
        payload = _verify_live(
            args.repo_root,
            args.evidence_root,
            command_runner=command_runner,
            evidence_writer=(
                docker_status.write_evidence
                if evidence_writer is None
                else evidence_writer
            ),
            include_gui=args.include_gui,
            expected_root=expected_root,
        )
    except (SafetyError, docker_status.DockerStatusError, ValueError, OSError):
        return 1
    return 0 if payload.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
