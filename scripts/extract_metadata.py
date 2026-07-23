"""从原始数据自动提取 20 路口元数据并生成 intersections.yaml（IA W1 Day 4）。

提取规则：
- timestep_s     ← .sumocfg 的 <step-length>（缺省 1.0）
- sumo_versions  ← .net.xml 头部注释中的生成工具版本 + 统一目标版本 "1.27.1"
- flow_count     ← .flow.xml 中 <flow> 元素个数
- has_queues     ← .sumocfg 是否含 queue-output
- edge_naming    ← .net.xml 中外部边（非 internal）ID 列表
- map_folder     ← 实际存在的地图目录名（高精地图/高清地图）

用法：python scripts/extract_metadata.py
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent / "data" / "intersection_data"
OUT = ROOT / "metadata" / "intersections.yaml"
UNIFIED_VERSION = "1.27.1"

# 既有 notes 保留（验证后补充的信息）
NOTES = {
    1: "标准十字路口，边命名 E0/-E1/-E2/-E3",
    9: "配时缺黄灯相位（原始文件遗留，见 docs/migration_log.md）",
    11: "流ID为 W_car/E_car/S_car/N_car，方向映射与路口1不同；tlLogic 有 unsafe green warning",
    12: "tlLogic 有 unsafe green phase warning（原始文件遗留，见 docs/migration_log.md）",
    16: "含 -E5 进口道（5进口道路口）",
    18: "tlLogic 有 unsafe green phase warning（原始文件遗留，见 docs/migration_log.md）",
}


def app_version(net_xml: Path) -> str:
    head = net_xml.read_text(encoding="utf-8", errors="replace")[:2000]
    m = re.search(r"netedit\s+Version\s+([\d.]+)", head) or re.search(
        r"netedit\s+([\d.]+)", head
    )
    return m.group(1) if m else "?"


def main() -> None:
    entries = []
    for n in range(1, 21):
        d = ROOT / str(n) / "sumo工程"
        cfg = (d / f"demo_{n}.sumocfg").read_text(encoding="utf-8")
        net = (d / f"demo_{n}.net.xml").read_text(encoding="utf-8", errors="replace")
        flow = (d / f"demo_{n}.flow.xml").read_text(encoding="utf-8", errors="replace")

        m = re.search(r'<step-length\s+value="([^"]+)"', cfg)
        timestep = float(m.group(1)) if m else 1.0
        versions = sorted({app_version(d / f"demo_{n}.net.xml"), UNIFIED_VERSION})
        edge_ids = re.findall(r'<edge\s+id="([^":]+)"[^>]*from=', net)
        map_folder = "高清地图" if (ROOT / str(n) / "高清地图").is_dir() else "高精地图"

        entry = {
            "id": n,
            "timestep_s": timestep,
            "sumo_versions": versions,
            "flow_count": len(re.findall(r"<flow\b", flow)),
            "has_queues": "queue-output" in cfg,
            "edge_naming": "/".join(dict.fromkeys(edge_ids)),
            "map_folder": map_folder,
        }
        if n in NOTES:
            entry["notes"] = NOTES[n]
        entries.append(entry)

    header = (
        "# 20 路口元数据 - 供批量脚本读取\n"
        "# 维护者：A 组\n"
        "# 本文件由 scripts/extract_metadata.py 自动生成，请勿手改；"
        "更新规则：发现新信息时在脚本的 NOTES 中补充后重新生成\n\n"
    )
    OUT.write_text(
        header + yaml.safe_dump({"intersections": entries}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"已写入 {OUT}，共 {len(entries)} 条")


if __name__ == "__main__":
    main()
