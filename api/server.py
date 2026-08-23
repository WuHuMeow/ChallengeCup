"""FastAPI application for simulations and cloud-edge control contracts."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket
from fastapi.responses import Response

from algorithms.registry import get_algorithm_registry
from api.models import (
    ControlActionModel,
    ControlActionsModel,
    LegacyRunRequestModel,
    NativeGuiResponseModel,
    PredictionResultModel,
    ResultDetailModel,
    ResultListItemModel,
    ResultListModel,
    RunRequestModel,
    RunResultModel,
    SafetyModel,
    SceneManifestModel,
    StateRequestModel,
)
from api.static import install_static_routes
from api.websocket import stream_run_events
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


def _validated_evidence_result(service, result):
    if result.status not in TERMINAL_STATUSES:
        return None
    try:
        output_root = Path(service.output_root).resolve()
        run_dir = Path(result.run_dir).resolve()
        relative = run_dir.relative_to(output_root)
    except (AttributeError, OSError, RuntimeError, ValueError):
        return None
    if not relative.parts:
        return None
    evidence = EvidenceReader.load_result_evidence(result.run_dir)
    if evidence is None:
        return None
    summary, manifest = evidence
    scene_id = manifest.get("scene_id")
    if not isinstance(scene_id, str) or not scene_id:
        return None
    return replace(result, summary=summary), scene_id


def create_app(
    run_service: RunService | None = None,
    *,
    web_dist: Path | None = None,
) -> FastAPI:
    """Create an application whose run lifecycle is backed by RunService."""
    service = run_service or RunService()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            yield
        finally:
            shutdown = getattr(application.state.run_service, "shutdown", None)
            if callable(shutdown):
                shutdown(wait=True)

    application = FastAPI(
        title="雄安车路云协同管控平台",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.run_service = service

    @application.get("/api/health")
    def health() -> dict[str, Any]:
        service = application.state.run_service
        return {"status": "ok", "run_workers": getattr(service, "max_workers", 1)}

    @application.get("/api/scenes", response_model=list[SceneManifestModel])
    def list_scenes() -> list[SceneManifestModel]:
        service = application.state.run_service
        return [
            SceneManifestModel(
                scene_id=meta.scene_id,
                intersection_id=meta.intersection_id,
                name=meta.name,
                description=meta.description,
                source_files=dict(meta.source_files),
                sha256=dict(meta.sha256),
                step_length=meta.step_length,
                tls_ids=list(meta.tls_ids),
                lane_ids=list(meta.lane_ids),
                movement_count=meta.movement_count,
                validation_status=meta.validation_status,
                warnings=list(meta.warnings),
            )
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

    @application.get(
        "/api/runs/{run_id}/frame",
        response_class=Response,
        response_model=None,
        responses={
            200: {
                "content": {
                    "image/png": {
                        "schema": {"type": "string", "format": "binary"}
                    }
                },
                "headers": {
                    "X-Run-Id": {"schema": {"type": "string"}},
                    "X-Frame-Sequence": {"schema": {"type": "integer"}},
                    "X-Simulation-Time": {"schema": {"type": "number"}},
                },
            },
            404: {"description": "run or frame unavailable"},
        },
    )
    def get_frame(
        run_id: str,
        sequence: int | None = Query(default=None, ge=0),
    ) -> Response:
        service = application.state.run_service
        if service.get(run_id) is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        frame = service.frame_publisher.consume(run_id, after_sequence=sequence)
        if frame is None:
            raise HTTPException(status_code=404, detail="frame unavailable")
        return Response(
            content=frame.png,
            media_type="image/png",
            headers={
                "X-Run-Id": frame.run_id,
                "X-Frame-Sequence": str(frame.sequence),
                "X-Simulation-Time": str(frame.simulation_time),
            },
        )

    @application.get("/api/results", response_model=ResultListModel)
    def list_results() -> ResultListModel:
        service = application.state.run_service
        results = []
        for result in service.list_results():
            validated = _validated_evidence_result(service, result)
            if validated is not None:
                evidence_result, scene_id = validated
                results.append(
                    ResultListItemModel.from_domain(
                        evidence_result,
                        scene_id=scene_id,
                    )
                )
        return ResultListModel(items=results, count=len(results))

    @application.get(
        "/api/results/{run_id}",
        response_model=ResultDetailModel,
        responses={404: {"description": "validated result unavailable"}},
    )
    def get_result(run_id: str) -> ResultDetailModel:
        result = application.state.run_service.get(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        validated = _validated_evidence_result(application.state.run_service, result)
        if validated is None:
            raise HTTPException(status_code=404, detail="validated evidence unavailable")
        evidence_result, scene_id = validated
        return ResultDetailModel.from_domain(evidence_result, scene_id=scene_id)

    @application.get(
        "/api/runs/{run_id}/safety",
        response_model=SafetyModel,
        responses={404: {"description": "validated safety unavailable"}},
    )
    def get_safety(run_id: str) -> SafetyModel:
        service = application.state.run_service
        result = service.get(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        validated = _validated_evidence_result(service, result)
        if validated is None:
            raise HTTPException(status_code=404, detail="validated safety unavailable")
        evidence_result, _scene_id = validated
        if evidence_result.summary is None:
            raise HTTPException(status_code=404, detail="validated safety unavailable")
        metrics = evidence_result.summary.get("metrics")
        if not isinstance(metrics, dict):
            raise HTTPException(status_code=404, detail="validated safety unavailable")
        keys = (
            "collision",
            "red_light",
            "illegal_transition",
            "harsh_braking",
            "teleport",
            "potential_conflict",
        )
        try:
            return SafetyModel(
                **{key: metrics[f"{key}_count"] for key in keys}
            )
        except (KeyError, TypeError, ValueError):
            raise HTTPException(
                status_code=404,
                detail="validated safety unavailable",
            ) from None

    @application.post("/api/runs/{run_id}/stop", response_model=RunResultModel)
    def stop_run(run_id: str) -> RunResultModel:
        service = application.state.run_service
        _result_or_404(service, run_id)
        if not service.stop(run_id):
            raise HTTPException(status_code=409, detail="run cannot be stopped")
        return RunResultModel.from_domain(_result_or_404(service, run_id))

    @application.post(
        "/api/runs/{run_id}/native-gui",
        response_model=NativeGuiResponseModel,
        responses={
            404: {"description": "unknown run_id"},
            409: {"description": "native SUMO-GUI unavailable"},
        },
    )
    def show_native_gui(run_id: str) -> NativeGuiResponseModel:
        service = application.state.run_service
        if service.get(run_id) is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        launcher = getattr(service, "native_gui", None)
        if not callable(launcher):
            raise HTTPException(
                status_code=409,
                detail="native SUMO-GUI is unavailable: native launcher unavailable",
            )
        try:
            outcome = launcher(run_id)
        except Exception as exc:
            raise HTTPException(
                status_code=409,
                detail=f"native SUMO-GUI is unavailable: {exc}",
            ) from exc
        if isinstance(outcome, tuple):
            shown, reason = outcome
        else:
            shown, reason = bool(outcome), "native launcher unavailable"
        if not shown:
            raise HTTPException(
                status_code=409,
                detail=f"native SUMO-GUI is unavailable: {reason}",
            )
        return NativeGuiResponseModel(status="shown")

    @application.websocket("/api/runs/{run_id}/events")
    async def run_events(websocket: WebSocket, run_id: str) -> None:
        await stream_run_events(websocket, application.state.run_service, run_id)

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
    def legacy_scenes() -> list[SceneManifestModel]:
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

    install_static_routes(
        application,
        web_dist or Path(__file__).resolve().parent / "static" / "dist",
    )

    return application


app = create_app()
