"""路口场景注册与索引。

负责把本地 `路口数据/` 目录下的 20 个路口统一注册为 `SceneMeta`，
屏蔽文件路径差异和命名不一致问题。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from core.config import get_config
from core.types import Scene, SceneMeta

logger = logging.getLogger(__name__)


class SceneRegistry:
    """场景注册表，管理 20 个路口的元数据。"""

    def __init__(self, data_root: Path | str | None = None) -> None:
        if data_root is None:
            data_root = get_config().path("paths.data_root")
        self.data_root = Path(data_root).resolve()
        self._scenes: Dict[str, SceneMeta] = {}
        self._discover()

    def _discover(self) -> None:
        """扫描 data_root 下的数字编号目录。"""
        if not self.data_root.exists():
            raise FileNotFoundError(f"数据根目录不存在: {self.data_root}")

        for item in sorted(self.data_root.iterdir(), key=lambda p: p.name):
            if not item.is_dir() or not item.name.isdigit():
                continue
            intersection_id = item.name
            meta = self._build_meta(intersection_id)
            if meta is not None:
                self._scenes[intersection_id] = meta

        logger.info("发现 %d 个路口场景", len(self._scenes))

    def _build_meta(self, intersection_id: str) -> Optional[SceneMeta]:
        """为单个路口构建 SceneMeta，兼容 `高精地图` / `高清地图` 等命名差异。"""
        scene_dir = self.data_root / intersection_id
        sumo_dir = scene_dir / "sumo工程"
        data_dir = scene_dir / "路口数据"

        # 处理地图目录命名不一致：大多数是 `高精地图`，路口 11 是 `高清地图`。
        map_dir = scene_dir / "高精地图"
        if not map_dir.exists():
            map_dir = scene_dir / "高清地图"

        if not sumo_dir.exists() or not data_dir.exists():
            logger.warning("路口 %s 缺少必要子目录，跳过", intersection_id)
            return None

        prefix = f"demo_{intersection_id}"
        net_file = sumo_dir / f"{prefix}.net.xml"
        rou_file = sumo_dir / f"{prefix}.rou.xml"
        flow_file = sumo_dir / f"{prefix}.flow.xml"
        turn_file = sumo_dir / f"{prefix}.turn.xml"
        cfg_file = sumo_dir / f"{prefix}.sumocfg"
        xlsx_file = data_dir / f"{prefix}流量和交叉口配时方案.xlsx"
        map_file = map_dir / f"{prefix}.png" if map_dir.exists() else None

        required = [net_file, rou_file, flow_file, cfg_file, xlsx_file]
        if not all(f.exists() for f in required):
            missing = [f.name for f in required if not f.exists()]
            logger.warning("路口 %s 缺少文件: %s", intersection_id, missing)
            return None

        return SceneMeta(
            intersection_id=intersection_id,
            name=f"路口_{intersection_id}",
            sumo_net=net_file,
            sumo_rou=rou_file,
            sumo_flow=flow_file,
            sumo_turn=turn_file,
            sumo_cfg=cfg_file,
            timing_xlsx=xlsx_file,
            map_png=map_file,
            description=f"雄安新区路口 {intersection_id} 的 SUMO 仿真场景",
        )

    def list_scenes(self) -> List[SceneMeta]:
        """返回所有已注册场景的元数据列表。"""
        return list(self._scenes.values())

    def get_scene(self, intersection_id: str) -> Scene:
        """根据路口 ID 获取运行时场景对象。"""
        if intersection_id not in self._scenes:
            raise KeyError(f"未找到路口 {intersection_id}")
        return Scene(meta=self._scenes[intersection_id])

    def get_meta(self, intersection_id: str) -> SceneMeta:
        """根据路口 ID 获取场景元数据。"""
        if intersection_id not in self._scenes:
            raise KeyError(f"未找到路口 {intersection_id}")
        return self._scenes[intersection_id]
