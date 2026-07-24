"""生成 docs/reference/edge-mapping.md：20 路口的边 ID → 方向映射表（IA W1 Day 5）。

方法：
- 用 sumolib 读取每个路口的 .net.xml；
- 找到所有 traffic_light 类型的节点（信号控制节点）；
- 对每条外部边（非 internal），按其所连信号节点分组：
  - 边的终点是信号节点 → 进口道；起点是信号节点 → 出口道；
- 方向由几何方位推断：信号节点指向边远端节点的向量，按 8 方位
  （东/东北/北/西北/西/西南/南/东南）命名；
- 不直接连信号节点的外部边（如分流路段）归入"未归属边"并标注最近信号节点。

产物供 AA/AB 计算压力时做方向映射，也可用于核对 TraCI 车道 ID。

用法：python scripts/data/generate_edge_mapping.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import sumolib

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "intersection_data"
OUT = ROOT / "docs" / "reference" / "edge-mapping.md"
JSON_OUT = DATA / "metadata" / "edge_mapping.json"

WINDS = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]


def compass(dx: float, dy: float) -> str:
    """向量 (dx, dy) → 8 方位（0°=北，顺时针）。"""
    bearing = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0
    return WINDS[int((bearing + 22.5) // 45.0) % 8]


def _classify(net: sumolib.net.Net) -> tuple[dict, dict, list]:
    """沿连接传播，把外部边分类为进口/出口，返回 (entry, exit_, external)。

    entry/exit_: edge_id → 对应信号节点；external: 非 internal 边列表。
    """
    tls_junctions = {j.getID(): j for j in net.getNodes() if j.getType() == "traffic_light"}

    external = [e for e in net.getEdges() if e.getFunction() != "internal"]
    ext_ids = {e.getID() for e in external}

    # 进口边集 / 出口边集：沿"连接（connection）"传播，而非节点邻接，
    # 确保分类遵守转向权限（如对向车道 E4 不会被误判为进口）。
    entry: dict[str, sumolib.net.node.Node] = {}  # edge_id → 对应信号节点
    exit_: dict[str, sumolib.net.node.Node] = {}
    for edge in external:
        if edge.getToNode().getID() in tls_junctions:
            entry[edge.getID()] = edge.getToNode()
        elif edge.getFromNode().getID() in tls_junctions:
            exit_[edge.getID()] = edge.getFromNode()

    connections = [
        (c.getFrom().getID(), c.getTo().getID())
        for node in net.getNodes()
        for c in node.getConnections()
    ]
    for _ in range(len(external) + 2):
        changed = False
        for e1, e2 in connections:
            if e2 in entry and e1 in ext_ids and e1 not in entry and e1 not in exit_:
                entry[e1] = entry[e2]
                changed = True
            if e1 in exit_ and e2 in ext_ids and e2 not in exit_ and e2 not in entry:
                exit_[e2] = exit_[e1]
                changed = True
        if not changed:
            break
    return entry, exit_, external


def edge_data(net: sumolib.net.Net) -> dict[str, dict]:
    """返回 {edge_id: {"direction": 方位, "kind": entry/exit/unassigned, "lanes": n}}。

    分类逻辑与 edge_rows 一致（沿 connection 传播，遵守转向权限）。
    """
    # —— 复用 edge_rows 中的 entry/exit_ 传播计算，抽为内部函数 _classify(net) ——
    entry, exit_, external = _classify(net)
    data: dict[str, dict] = {}
    tls_junctions = {j.getID() for j in net.getNodes() if j.getType() == "traffic_light"}
    for edge in external:
        eid = edge.getID()
        from_j, to_j = edge.getFromNode(), edge.getToNode()
        if eid in entry:
            tls = entry[eid]
            far = from_j.getCoord()
            kind = "entry"
        elif eid in exit_:
            tls = exit_[eid]
            far = to_j.getCoord()
            kind = "exit"
        else:
            data[eid] = {"direction": "", "kind": "unassigned", "lanes": len(edge.getLanes())}
            continue
        d = compass(far[0] - tls.getCoord()[0], far[1] - tls.getCoord()[1])
        data[eid] = {"direction": d, "kind": kind, "lanes": len(edge.getLanes())}
    return data


def edge_rows(net: sumolib.net.Net) -> tuple[list[str], list[str]]:
    """返回 (已归属边表行, 未归属边表行)。

    除直接连信号节点的边外，还沿 SUMO 连接（connection，含转向权限）
    把多级分流路段归入对应信号节点（如路口 16 的 -E5 → -E4 → -E2 链），
    方向相对对应信号节点计算；对向车道不会被误判。
    """
    tls_junctions = {j.getID(): j for j in net.getNodes() if j.getType() == "traffic_light"}
    entry, exit_, external = _classify(net)
    rows: list[str] = []
    orphans: list[str] = []

    for edge in external:
        eid = edge.getID()
        from_j, to_j = edge.getFromNode(), edge.getToNode()
        n_lanes = len(edge.getLanes())
        length = f"{edge.getLength():.2f}"
        if eid in entry:
            tls = entry[eid]
            star = "" if to_j.getID() in tls_junctions else "*"
            far = from_j.getCoord()
            d = compass(far[0] - tls.getCoord()[0], far[1] - tls.getCoord()[1])
            rows.append(f"| {eid} | {d}进口{star} | 进口{star} | {n_lanes} | {length} |")
        elif eid in exit_:
            tls = exit_[eid]
            star = "" if from_j.getID() in tls_junctions else "*"
            far = to_j.getCoord()
            d = compass(far[0] - tls.getCoord()[0], far[1] - tls.getCoord()[1])
            rows.append(f"| {eid} | {d}出口{star} | 出口{star} | {n_lanes} | {length} |")
        else:
            orphans.append(f"| {eid} | - | 未归属 | {n_lanes} | {length} |")
    return rows, orphans


def main() -> None:
    lines = [
        "# 边 ID → 方向映射表（IA W1 Day 5）",
        "",
        "> 由 `scripts/data/generate_edge_mapping.py` 自动生成，请勿手改。",
        "> 方向按 8 方位几何推断（信号节点 → 边远端向量）；",
        "> 进口 = 终点为信号节点的边，出口 = 起点为信号节点的边。",
        "> 带 * 的边经一个普通子节点连接到路口（延续边，如路口 16 的 -E4/-E5），",
        "> 方向相对对应信号节点计算；仍标 \"未归属\" 的边与信号节点无连通关系。",
        "> 算法组（AA/AB）计算压力时以此表做车道 → 方向映射。",
        "",
    ]
    mapping: dict[str, dict] = {}
    for n in range(1, 21):
        net = sumolib.net.readNet(str(DATA / str(n) / "sumo工程" / f"demo_{n}.net.xml"))
        rows, _ = edge_rows(net)
        mapping[str(n)] = {"edges": edge_data(net)}
        lines += [
            f"## 路口 {n}",
            "",
            "| 边 ID | 方向 | 类型 | 车道数 | 长度(m) |",
            "|-------|------|------|--------|---------|",
            *rows,
            "",
        ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已写入 {OUT} 与 {JSON_OUT}")


if __name__ == "__main__":
    main()
