"""配置加载工具。

默认加载 config/default.yaml，支持通过环境变量 CHALLENGE_CUP_CONFIG
指定额外覆盖文件。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


class Config:
    """全局配置访问对象。"""

    _instance: "Config" = None

    def __new__(cls, path: Path | None = None) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load(path)
        return cls._instance

    def _load(self, path: Path | None = None) -> None:
        if path is None:
            repo_root = Path(__file__).resolve().parent.parent
            path = repo_root / "config" / "default.yaml"

        if yaml is None:
            raise ImportError("PyYAML is required. Install: pip install pyyaml")

        with open(path, "r", encoding="utf-8") as f:
            self._data: Dict[str, Any] = yaml.safe_load(f) or {}

        # 允许通过环境变量覆盖数据根目录，方便队友使用不同路径。
        env_data_root = os.environ.get("CC_DATA_ROOT")
        if env_data_root:
            self._data.setdefault("paths", {})["data_root"] = env_data_root

    @property
    def data(self) -> Dict[str, Any]:
        return self._data

    def get(self, key: str, default: Any = None) -> Any:
        """支持点号分隔的键，例如 'sumo.step_length'。"""
        parts = key.split(".")
        value = self._data
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def path(self, key: str) -> Path:
        """获取路径并解析为相对于仓库根目录的绝对路径。"""
        repo_root = Path(__file__).resolve().parent.parent
        raw = self.get(key)
        if raw is None:
            raise KeyError(f"Config key '{key}' not found")
        p = Path(raw)
        if not p.is_absolute():
            p = repo_root / p
        return p.resolve()


# 便捷函数，避免到处 import Config()。
def get_config() -> Config:
    return Config()
