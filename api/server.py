"""FastAPI application for simulations and cloud-edge control contracts."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from api.models import (
    ControlActionModel,
    ControlActionsModel,
    PredictionResultModel,
    RunRequestModel,
    RunResultModel,
    StateRequestModel,
)
from cloud.cloud_policy import CloudPolicy
from engine.run_service import RunService


def _result_or_404(run_service: RunService, run_id: str):
    result = run_service.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    return result


def create_app(run_service: RunService | None = None) -> FastAPI:
    """Create an application whose run lifecycle is backed by RunService."""
    application = FastAPI(
        title="雄安车路云协同管控平台",
        version="1.0.0",
    )
    application.state.run_service = run_service or RunService()

    @application.get("/api/health")
    def health() -> dict[str, Any]:
        service = application.state.run_service
        return {"status": "ok", "run_workers": getattr(service, "max_workers", 1)}

    @application.get("/api/scenes")
    def list_scenes() -> list[dict[str, str]]:
        service = application.state.run_service
        return [
            {
                "intersection_id": meta.intersection_id,
                "name": meta.name,
                "description": meta.description,
            }
            for meta in service.registry.list_scenes()
        ]

    @application.post(
        "/api/runs",
        response_model=RunResultModel,
        status_code=202,
    )
    def submit_run(payload: RunRequestModel) -> RunResultModel:
        try:
            result = application.state.run_service.submit(payload.to_domain())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return RunResultModel.from_domain(result)

    @application.get("/api/runs/{run_id}", response_model=RunResultModel)
    def get_run(run_id: str) -> RunResultModel:
        result = _result_or_404(application.state.run_service, run_id)
        return RunResultModel.from_domain(result)

    @application.get("/api/runs/{run_id}/metrics")
    def get_run_metrics(run_id: str) -> dict[str, Any]:
        result = _result_or_404(application.state.run_service, run_id)
        if result.summary is None:
            raise HTTPException(status_code=404, detail="run metrics are not available")
        metrics = result.summary.get("metrics", result.summary)
        if not isinstance(metrics, dict):
            raise HTTPException(status_code=500, detail="invalid metrics summary")
        return metrics

    @application.post("/api/runs/{run_id}/stop", response_model=RunResultModel)
    def stop_run(run_id: str) -> RunResultModel:
        service = application.state.run_service
        _result_or_404(service, run_id)
        if not service.stop(run_id):
            raise HTTPException(status_code=409, detail="run cannot be stopped")
        return RunResultModel.from_domain(_result_or_404(service, run_id))

    @application.post(
        "/api/cloud/predict",
        response_model=PredictionResultModel,
    )
    def cloud_predict(payload: StateRequestModel) -> PredictionResultModel:
        prediction = CloudPolicy().predict(payload.state.to_domain())
        return PredictionResultModel.from_domain(prediction)

    @application.post(
        "/api/edge/control",
        response_model=ControlActionsModel,
    )
    def edge_control(payload: StateRequestModel) -> ControlActionsModel:
        actions = CAMaxPressureAlgorithm().step(payload.state.to_domain())
        return ControlActionsModel(
            actions=[ControlActionModel.from_domain(action) for action in actions]
        )

    @application.get("/health", deprecated=True)
    def legacy_health() -> dict[str, Any]:
        return health()

    @application.get("/scenes", deprecated=True)
    def legacy_scenes() -> list[dict[str, str]]:
        return list_scenes()

    @application.post("/run", deprecated=True, status_code=202)
    def legacy_run(payload: RunRequestModel) -> RunResultModel:
        return submit_run(payload)

    @application.get("/status", deprecated=True)
    def legacy_status(run_id: str) -> RunResultModel:
        return get_run(run_id)

    @application.post("/api/simulation/start", deprecated=True, status_code=202)
    def legacy_simulation_start(payload: RunRequestModel) -> RunResultModel:
        return submit_run(payload)

    @application.post("/api/simulation/stop", deprecated=True)
    def legacy_simulation_stop(run_id: str) -> RunResultModel:
        return stop_run(run_id)

    return application


app = create_app()
