from pathlib import Path


def test_dockerfile_copies_every_runtime_package():
    text = Path("docker/Dockerfile").read_text(encoding="utf-8")
    for package in ["algorithms", "cloud", "core", "engine", "experiments", "scenes"]:
        assert f"COPY {package}/ ./{package}/" in text
    assert 'ENTRYPOINT ["python3", "examples/run_fixed_time.py"]' in text
    assert "RUN python3 -m compileall -q" in text


def test_compose_mounts_output_and_uses_current_dockerfile():
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "dockerfile: docker/Dockerfile" in text
    assert "./output:/app/output" in text
    assert "init: true" in text


def test_dockerignore_keeps_required_source():
    text = Path(".dockerignore").read_text(encoding="utf-8")
    assert "data/intersection_data" not in text
    assert "engine/configs" not in text
