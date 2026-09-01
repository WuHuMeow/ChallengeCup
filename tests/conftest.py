

import pytest


@pytest.fixture(autouse=True)
def _isolate_default_cloud_model(monkeypatch, tmp_path):
    """Unit tests must not load the repository's real ml/model.pkl by default.

    Tests that exercise the trained model pass an explicit model_path; the
    default CloudPolicy() constructor resolves to a missing path here.
    """
    from cloud.cloud_policy import CloudPolicy

    original = CloudPolicy.__init__

    def patched_init(self, model_path=None):
        if model_path is None:
            model_path = tmp_path / "no-default-model.pkl"
        original(self, model_path=model_path)

    monkeypatch.setattr("cloud.cloud_policy.CloudPolicy.__init__", patched_init)
