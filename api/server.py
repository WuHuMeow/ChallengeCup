"""FastAPI application for simulations and cloud-edge control contracts."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from fastapi import FastAPI, HTTPException

from algorithms.registry import get_algorithm_registry
from api.models import (
    ControlActionModel,
    ControlActionsModel,
    LegacyRunRequestModel,
    PredictionResultModel,
    ResultDetailModel,
    ResultListItemModel,
    ResultListModel,
    RunRequestModel,
    RunResultModel,
    StateRequestModel,
)
from cloud.cloud_policy import CloudPolicy
from engine.run_service import RunService
from engine.run_state import TERMINAL_STATUSES
from experiments.evidence import EvidenceReader


def _validated_result(result):
    """Preserve lifecycle state while withholding unverified summaries."""
    if result.summary is not None:
        return replace(
            result,
            summary=EvidenceReader.load_summary(result.run_dir),
        )
    return result


def _result_or_404(run_service: RunService, run_id: str):
    result = run_service.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    return _validated_result(result)


def _validated_evidence_result(result):
    if result.status not in TERMINAL_STATUSES:
        return None
    summary = EvidenceReader.load_summary(result.run_dir)
    if summary is None:
        return None
    return replace(result, summary=summary)


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

    @application.get("/api/algorithms")
    def list_algorithms() -> dict[str, list[dict[str, object]]]:
        registry = get_algorithm_registry()

        def public_row(spec) -> dict[str, object]:
            return {
                "key": spec.key,
                "display_name": spec.display_name,
                "formal": spec.formal,
                "available": spec.available,
                "unavailable_reason": spec.unavailable_reason,
            }

        return {
            "formal": [public_row(spec) for spec in registry.list(formal_only=True)],
            "optional": [
                public_row(spec) for spec in registry.list() if not spec.formal
            ],
        }

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
        return RunResultModel.from_domain(_validated_result(result))

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

    @application.get("/api/results", response_model=ResultListModel)
    def list_results() -> ResultListModel:
        service = application.state.run_service
        results = []
        for result in service.list_results():
            validated = _validated_evidence_result(result)
            if validated is not None:
                results.append(ResultListItemModel.from_domain(validated))
        return ResultListModel(items=results, count=len(results))

    @application.get("/api/results/{run_id}", response_model=ResultDetailModel)
    def get_result(run_id: str) -> ResultDetailModel:
        result = application.state.run_service.get(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        validated = _validated_evidence_result(result)
        if validated is None:
            raise HTTPException(status_code=404, detail="validated evidence unavailable")
        return ResultDetailModel.from_domain(validated)

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
        algorithm = get_algorithm_registry().get(
            "capacity_aware_maxpressure"
        ).factory()
        actions = algorithm.step(payload.state.to_domain())
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
    def legacy_run(payload: LegacyRunRequestModel) -> RunResultModel:
        return submit_run(payload)

    @application.get("/status", deprecated=True)
    def legacy_status(run_id: str) -> RunResultModel:
        return get_run(run_id)

    @application.post("/api/simulation/start", deprecated=True, status_code=202)
    def legacy_simulation_start(payload: LegacyRunRequestModel) -> RunResultModel:
        return submit_run(payload)

    @application.post("/api/simulation/stop", deprecated=True)
    def legacy_simulation_stop(run_id: str) -> RunResultModel:
        return stop_run(run_id)

    return application


app = create_app()
