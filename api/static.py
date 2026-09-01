"""Containment-safe serving of the built judge console."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def _contained_file(root: Path, relative_path: str) -> Path | None:
    resolved_root = root.resolve()
    try:
        candidate = (resolved_root / relative_path).resolve()
        candidate.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate if candidate.is_file() else None


def install_static_routes(application: FastAPI, dist_root: Path) -> None:
    root = Path(dist_root)

    @application.get("/", include_in_schema=False)
    def serve_index() -> FileResponse:
        path = _contained_file(root, "index.html")
        if path is None:
            raise HTTPException(status_code=404, detail="web build unavailable")
        return FileResponse(path)

    @application.get("/{asset_path:path}", include_in_schema=False)
    def serve_asset(asset_path: str) -> FileResponse:
        path = _contained_file(root, asset_path)
        if path is None:
            raise HTTPException(status_code=404, detail="static asset not found")
        return FileResponse(path)
