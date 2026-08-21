import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from algorithms.fixed_time_plan import FixedTimePlanError, FixedTimePlanResolver
from algorithms.fixed_time import FixedTimeAlgorithm
from core.types import JointState, Scene, SceneMeta


def _scene(tmp_path: Path, *, config: dict | None = None) -> Scene:
    net = tmp_path / "network.net.xml"
    net.write_text(
        "<net><tlLogic id='tls0' programID='network'>"
        "<phase duration='20' state='Gr'/><phase duration='3' state='yr'/>"
        "</tlLogic></net>",
        encoding="utf-8",
    )
    return Scene(
        SceneMeta(
            intersection_id="test",
            name="test",
            sumo_net=net,
            sumo_rou=tmp_path / "routes.rou.xml",
            sumo_flow=tmp_path / "flow.xml",
            sumo_turn=tmp_path / "turn.xml",
            sumo_cfg=tmp_path / "run.sumocfg",
            timing_xlsx=tmp_path / "timing.xlsx",
        ),
        config=config or {},
    )


def _write_excel(path: Path) -> None:
    rows = [
        ["metadata"],
        ["metadata"],
        ["morning", "", 1, "main", 30, 3, 2],
    ]
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([["flow"]]).to_excel(writer, index=False, header=False)
        pd.DataFrame(rows).to_excel(writer, sheet_name="timing", index=False, header=False)


def test_fixed_time_plan_prefers_standardized_scene_plan_and_records_hash(tmp_path):
    scene_plan = tmp_path / "standardized-timing.json"
    scene_plan.write_text(
        json.dumps(
            {
                "program_id": "standardized",
                "phases": [
                    {"duration": 31, "state": "Gr"},
                    {"duration": 3, "state": "yr"},
                ],
            }
        ),
        encoding="utf-8",
    )
    scene = _scene(tmp_path, config={"timing_plan": scene_plan})
    _write_excel(scene.meta.timing_xlsx)

    resolved = FixedTimePlanResolver().resolve(scene)

    assert resolved.source_kind == "standardized_scene"
    assert not Path(resolved.source_path).is_absolute()
    assert (Path.cwd() / resolved.source_path).resolve() == scene_plan.resolve()
    assert resolved.source_sha256 == hashlib.sha256(scene_plan.read_bytes()).hexdigest()
    assert resolved.program_id == "standardized"


def test_fixed_time_plan_uses_official_excel_before_network_plan(tmp_path):
    scene = _scene(tmp_path)
    _write_excel(scene.meta.timing_xlsx)

    resolved = FixedTimePlanResolver().resolve(scene)

    assert resolved.source_kind == "official_excel"
    assert resolved.source_path == str(
        scene.meta.timing_xlsx.resolve().relative_to(Path.cwd())
    ).replace("\\", "/")
    assert resolved.source_sha256
    assert resolved.program_id == "excel:morning"
    assert [(phase.duration, phase.state) for phase in resolved.phases] == [
        (30.0, "Gr"),
        (3.0, "yr"),
        (2.0, "rr"),
    ]


def test_fixed_time_step_installs_the_frozen_program_once(tmp_path):
    scene_plan = tmp_path / "standardized-timing.json"
    scene_plan.write_text(
        json.dumps(
            {
                "program_id": "standardized",
                "phases": [
                    {"duration": 31, "state": "Gr"},
                    {"duration": 3, "state": "yr"},
                ],
            }
        ),
        encoding="utf-8",
    )
    algorithm = FixedTimeAlgorithm()
    algorithm.init(_scene(tmp_path, config={"timing_plan": scene_plan}))
    state = JointState(
        step=0,
        timestamp=0.0,
        tls_id="tls0",
        current_phase=0,
        current_phase_name="phase_0",
        elapsed_phase_time=0.0,
    )

    actions = algorithm.step(state)

    assert len(actions) == 1
    assert actions[0].action_type == "set_program"
    assert actions[0].value == {
        "program_id": "standardized",
        "phases": [
            {"duration": 31.0, "state": "Gr"},
            {"duration": 3.0, "state": "yr"},
        ],
    }
    assert actions[0].issued_at == state.timestamp
    assert actions[0].expires_at == state.timestamp + 60.0
    assert algorithm.step(state) == []


def test_fixed_time_rejects_scene_without_a_legal_plan(tmp_path):
    scene = _scene(tmp_path)
    scene.meta.sumo_net.write_text("<net/>", encoding="utf-8")

    with pytest.raises(FixedTimePlanError, match="timing plan"):
        FixedTimePlanResolver().resolve(scene)


def test_fixed_time_rejects_an_empty_official_excel_instead_of_falling_back(tmp_path):
    scene = _scene(tmp_path)
    with pd.ExcelWriter(scene.meta.timing_xlsx) as writer:
        pd.DataFrame([["flow"]]).to_excel(writer, index=False, header=False)
        pd.DataFrame([["metadata"]]).to_excel(
            writer, sheet_name="timing", index=False, header=False
        )

    with pytest.raises(FixedTimePlanError, match="timing plan"):
        FixedTimePlanResolver().resolve(scene)


def test_fixed_time_rejects_an_official_excel_with_an_illegal_phase(tmp_path):
    scene = _scene(tmp_path)
    rows = [
        ["metadata"],
        ["metadata"],
        ["morning", "", 1, "main", -1, 3, 2],
    ]
    with pd.ExcelWriter(scene.meta.timing_xlsx) as writer:
        pd.DataFrame([["flow"]]).to_excel(writer, index=False, header=False)
        pd.DataFrame(rows).to_excel(writer, sheet_name="timing", index=False, header=False)

    with pytest.raises(FixedTimePlanError, match="timing plan"):
        FixedTimePlanResolver().resolve(scene)


def test_fixed_time_manifest_contains_the_frozen_resolved_plan(tmp_path):
    scene_plan = tmp_path / "standardized-timing.json"
    scene_plan.write_text(
        json.dumps(
            {
                "program_id": "standardized",
                "phases": [{"duration": 31, "state": "Gr"}],
            }
        ),
        encoding="utf-8",
    )
    algorithm = FixedTimeAlgorithm()
    algorithm.init(_scene(tmp_path, config={"timing_plan": scene_plan}))

    assert algorithm.manifest["timing_plan"] == {
        "source_kind": "standardized_scene",
        "source_path": str(scene_plan.resolve().relative_to(Path.cwd())).replace("\\", "/"),
        "source_sha256": hashlib.sha256(scene_plan.read_bytes()).hexdigest(),
        "program_id": "standardized",
    }
