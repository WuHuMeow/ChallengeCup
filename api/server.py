"""FastAPI 服务骨架。

提供轻量 REST API 用于实验控制、场景管理和结果查询。
云-边-端协同接口以端点形式暴露，方便 Postman 测试与演示。
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import BaseModel

from core.types import ControlAction, JointState, PredictionResult, SceneMeta
from scenes.registry import SceneRegistry

app = FastAPI(title="雄安新区车路云协同管控算法平台", version="0.1.0")


class StartRequest(BaseModel):
    intersection_id: str
    algorithm: str = "fixed_time"
    steps: int = 3600


class SwitchRequest(BaseModel):
    algorithm: str


@app.get("/api/scenes", response_model=List[Dict[str, Any]])
def list_scenes() -> List[Dict[str, Any]]:
    """列出所有已注册路口场景。"""
    # TODO: 成员6 接入 scenes.registry.SceneRegistry
    return []


@app.post("/api/scenes/{intersection_id}/load")
def load_scene(intersection_id: str) -> Dict[str, str]:
    """加载指定场景。"""
    return {"scene": intersection_id, "status": "loaded"}


@app.post("/api/simulation/start")
def start_simulation(req: StartRequest) -> Dict[str, Any]:
    """启动单次仿真。"""
    return {"status": "started", "request": req.model_dump()}


@app.post("/api/simulation/stop")
def stop_simulation() -> Dict[str, str]:
    """停止当前仿真。"""
    return {"status": "stopped"}


@app.get("/api/algorithms")
def list_algorithms() -> List[str]:
    """列出可用算法。"""
    return ["fixed_time", "actuated", "ca_maxpressure"]


@app.post("/api/algorithm/switch")
def switch_algorithm(req: SwitchRequest) -> Dict[str, str]:
    """切换当前算法。"""
    return {"status": "switched", "algorithm": req.algorithm}


@app.get("/api/metrics/current")
def current_metrics() -> Dict[str, float]:
    """获取当前仿真指标快照。"""
    return {
        "avg_queue_length": 0.0,
        "max_queue_length": 0.0,
        "avg_delay": 0.0,
    }


# 云-边-端协同接口
@app.get("/api/cloud/predict")
def cloud_predict(state: Dict[str, Any]) -> Dict[str, Any]:
    """云端流量预测。"""
    # TODO: 成员6 接入 cloud.cloud_policy.CloudPolicy
    return {"predicted_flows": {}}


@app.post("/api/edge/control")
def edge_control(predictions: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """边缘控制决策。"""
    # TODO: 成员6 接入 algorithms.ca_max_pressure.CAMaxPressureAlgorithm
    return {"actions": []}


@app.get("/api/vehicle/status")
def vehicle_status() -> Dict[str, Any]:
    """车端/灯端状态快照。"""
    return {"tls_id": "", "current_phase": 0}


# ─── 根级接口（Task 9） ───────────────────────────────────────────────

_run_state: Dict[str, Any] = {"run_id": None, "status": "idle"}


@app.get("/health")
def health() -> Dict[str, str]:
    """健康检查。"""
    return {"status": "ok"}


@app.get("/scenes")
def scenes_list() -> List[Dict[str, Any]]:
    """返回场景列表。"""
    try:
        registry = SceneRegistry()
        return [
            {"intersection_id": m.intersection_id, "name": m.name}
            for m in registry.list_scenes()
        ]
    except Exception:
        return []


@app.post("/run")
def start_run(req: StartRequest) -> Dict[str, Any]:
    """启动一次仿真（MVI：记录状态，不实际运行）。"""
    run_id = str(uuid.uuid4())[:8]
    _run_state["run_id"] = run_id
    _run_state["status"] = "started"
    _run_state["request"] = req.model_dump()
    return {"run_id": run_id, "status": "started"}


@app.get("/status")
def run_status() -> Dict[str, Any]:
    """返回当前运行状态。"""
    return {"run_id": _run_state["run_id"], "status": _run_state["status"]}
