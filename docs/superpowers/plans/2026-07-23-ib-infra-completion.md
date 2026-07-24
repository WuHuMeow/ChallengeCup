# IB（仿真基础设施 B）全量补齐实施计划

> **历史快照：** 本计划保留目录重组前的文件声明和原始实施范围。旧路径不是当前运行命令；现行代码、测试与文档入口分别见 `scripts/README.md`、`tests/README.md` 和 `docs/README.md`。
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 docs/tasks/w1-w6/IB_infra_b.md 中全部可执行项：TraCIBridge 增强（capacity/进口道/seed/韧性/采样）、experiments CLI、CloudPolicy 压力分档、EdgeChannel、日志输出（simulation_log/events）、压力实测与文档定稿。

**Architecture:** 在现有 MVI 骨架上向后兼容地增量扩展：所有新字段/参数带默认值，不破坏 7/23 接口冻结；依赖 AB 算法侧的项（溢出门控、EWMA 接入）只建机制。测试以 MockBridge 单测 + 真实 SUMO 实证结合。

**Tech Stack:** Python 3.12、SUMO 1.27.1（TraCI）、pytest、PyYAML、sumolib。环境已验证可用（`SUMO_HOME=C:\Program Files (x86)\Eclipse\Sumo`）。

**设计文档:** `docs/superpowers/specs/2026-07-23-ib-infra-completion-design.md`

## Global Constraints

- 所有变更向后兼容：只新增可选字段/参数（带默认值），不修改现有签名语义。
- 现有 31 个测试必须保持全过：`python -m pytest tests/ -q`。
- 代码风格：中文 docstring、4 空格缩进、行宽 100（flake8 `--max-line-length=100`）。
- TraCI 订阅批量读取优化**不做**（IA 实测 20 路口 3600 步合计 59s，无瓶颈）。
- 不新建 `scripts/scale_flow.py`（复用 `scenes/variant.py` 扩展）。
- **git commit 步骤统一留待用户确认后由协调者执行；实现者不要自行 `git commit`。**
- 验证命令中的路径均为仓库根目录相对路径；Windows Git Bash 环境下 `taskkill` 写法为 `taskkill //F //IM sumo.exe`。

---

### Task 1: core/types.py 新增字段（capacity / VehicleState / vehicles / arrival_history）

**Files:**
- Modify: `core/types.py:66-91`
- Test: `tests/test_types_fields.py`（新建）

**Interfaces:**
- Produces:
  - `QueueState(..., capacity: float = 0.0)` — 车道容量（辆）= 长度/7.5m；0 表示未知
  - `VehicleState(vehicle_id: str, lane_id: str, speed: float)`
  - `JointState(..., vehicles: List[VehicleState] = [], arrival_history: List[int] = [])`

- [ ] **Step 1: 写失败测试**

```python
"""core/types.py 新增字段契约测试（IB W1/W4）。"""
from core.types import JointState, QueueState, VehicleState


def test_queue_state_capacity_defaults_zero():
    q = QueueState(direction="north", queue_length=3.0, waiting_time=5.0, vehicle_count=4)
    assert q.capacity == 0.0


def test_vehicle_state_fields():
    v = VehicleState(vehicle_id="veh_1", lane_id="-E2_0", speed=8.5)
    assert v.vehicle_id == "veh_1"
    assert v.lane_id == "-E2_0"
    assert v.speed == 8.5


def test_joint_state_new_fields_default_empty():
    state = JointState(
        step=0, timestamp=0.0, tls_id="tls_0",
        current_phase=0, current_phase_name="p0", elapsed_phase_time=0.0,
        queues=[], flows={},
    )
    assert state.vehicles == []
    assert state.arrival_history == []
    assert state.detector_values == {}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_types_fields.py -q`
Expected: FAIL（`VehicleState` 不存在 / `capacity` 意外关键字）

- [ ] **Step 3: 修改 core/types.py**

`QueueState` 增加字段（保持原有四字段顺序与语义不变）：

```python
@dataclass
class QueueState:
    """某进口道的排队状态。"""

    direction: str  # 例如 "north", "south", "east, "west" 或 lane_id
    queue_length: float
    waiting_time: float
    vehicle_count: int
    capacity: float = 0.0  # 车道容量（辆）= 车道长度 / 7.5m；0 表示未知
```

在 `JointState` 之前新增 `VehicleState`，并给 `JointState` 追加两个带默认值字段：

```python
@dataclass
class VehicleState:
    """单辆车快照（高流量下按 vehicle_sample_rate 采样）。"""

    vehicle_id: str
    lane_id: str
    speed: float


@dataclass
class JointState:
    """云-边-端协同的联合状态，作为算法 step() 的输入。

    云端预测服务、边缘控制算法、车端/灯端执行均围绕该状态交互。
    """

    step: int
    timestamp: float
    tls_id: str
    current_phase: int
    current_phase_name: str
    elapsed_phase_time: float
    queues: List[QueueState]
    flows: Dict[str, float]  # 方向 ->  vehicles / hour
    detector_values: Dict[str, float] = field(default_factory=dict)
    vehicles: List[VehicleState] = field(default_factory=list)  # 采样后的车辆快照
    arrival_history: List[int] = field(default_factory=list)  # 最近 300 步每步进入路网车辆数
```

- [ ] **Step 4: 跑测试确认通过 + 全量回归**

Run: `python -m pytest tests/ -q`
Expected: 34 passed（31 旧 + 3 新）

---

### Task 2: TraCIBridge.get_lane_capacity + QueueState.capacity 填充

**Files:**
- Modify: `engine/traci_bridge.py:32-116`
- Modify: `engine/mock_bridge.py`
- Test: `tests/test_mock_bridge.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `QueueState.capacity`
- Produces:
  - `TraCIBridge.get_lane_capacity(lane_id: str) -> float`（容量 = 长度/7.5m）
  - `TraCIBridge.LANE_CAPACITY_METERS = 7.5`（类常量）
  - `MockBridge.get_lane_capacity(lane_id: str) -> float`（确定性返回 20.0）
  - `MockBridge.get_state()` 返回的 `QueueState.capacity == 20.0`

- [ ] **Step 1: 写失败测试（追加到 tests/test_mock_bridge.py）**

```python
def test_mock_bridge_lane_capacity_deterministic():
    bridge = MockBridge()
    bridge.start()
    assert bridge.get_lane_capacity("north") == 20.0


def test_mock_bridge_queue_state_has_capacity():
    bridge = MockBridge()
    bridge.start()
    state = bridge.get_state()
    assert all(q.capacity == 20.0 for q in state.queues)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_mock_bridge.py -q`
Expected: FAIL（MockBridge 无 `get_lane_capacity`）

- [ ] **Step 3: 实现**

`engine/traci_bridge.py` — 类常量与方法（放在 `apply_actions` 之后）：

```python
class TraCIBridge:
    """SUMO 仿真与算法之间的桥接器。"""

    LANE_CAPACITY_METERS = 7.5  # 5m 车长 + 2.5m 间距，CA-MP 压力归一化分母
    MAX_VEHICLES = 500  # JointState.vehicles 硬上限（W4）
```

```python
    def get_lane_capacity(self, lane_id: str) -> float:
        """车道容量（辆）= 车道长度 / 7.5m（5m 车长 + 2.5m 间距）。

        CA-MP 容量归一化压力 pressure = queue / capacity 的分母。
        """
        return traci.lane.getLength(lane_id) / self.LANE_CAPACITY_METERS
```

`get_state()` 中 `queues.append(...)` 处为 `QueueState` 增加 `capacity=self.get_lane_capacity(lane_id)`。

`engine/mock_bridge.py` — 在 `apply_actions` 后追加：

```python
    def get_lane_capacity(self, lane_id: str) -> float:
        """确定性容量：20 辆（对应 150m 车道 / 7.5m）。"""
        return 20.0
```

`MockBridge.get_state()` 的 `QueueState(...)` 增加 `capacity=self.get_lane_capacity(direction)`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/ -q`
Expected: 36 passed

- [ ] **Step 5: 真实 SUMO 冒烟（路口 1，100 步，验证 capacity 非零）**

Run: `python -c "
import sys; sys.path.insert(0, '.')
from scenes.registry import SceneRegistry
from engine.traci_bridge import TraCIBridge
scene = SceneRegistry().get_scene('1')
b = TraCIBridge(scene.meta.sumo_cfg)
b.start()
b.step()
state = b.get_state()
caps = {q.direction: q.capacity for q in state.queues}
print(caps)
assert all(c > 0 for c in caps.values()), 'capacity 应大于 0'
b.close()
print('OK capacity filled')
"`
Expected: 打印各 lane 的容量字典 + `OK capacity filled`

---

### Task 3: edge_mapping.json 生成 + TraCIBridge 进口道筛选

**Files:**
- Modify: `scripts/generate_edge_mapping.py`（新增结构化输出）
- Create: `data/intersection_data/metadata/edge_mapping.json`（运行脚本生成）
- Modify: `engine/traci_bridge.py`
- Test: `tests/test_edge_mapping.py`（新建）

**Interfaces:**
- Consumes: `scripts/generate_edge_mapping.py` 现有 `edge_rows(net)` 逻辑
- Produces:
  - JSON 结构：`{"1": {"edges": {"-E2": {"direction": "东", "kind": "entry", "lanes": 3}}}, ...}`（kind ∈ entry/exit/unassigned）
  - `edge_data(net) -> dict[str, dict]`（generate_edge_mapping.py 中的结构化函数）
  - `TraCIBridge.lane_directions: Dict[str, str]`（lane_id → 方位，如 `"-E2_0" -> "东"`）
  - `TraCIBridge._apply_edge_mapping(edges: dict) -> None`（纯方法，可单测）
  - get_state 只统计进口道（mapping 不可用时回退 `getControlledLanes` 并 warning）

- [ ] **Step 1: 写失败测试**

```python
"""edge_mapping 结构化生成与 TraCIBridge 进口道筛选测试（IB W1 Day 5）。"""
from pathlib import Path

import pytest

from engine.traci_bridge import TraCIBridge


def test_edge_mapping_json_exists_and_structured():
    import json
    path = Path("data/intersection_data/metadata/edge_mapping.json")
    assert path.exists(), "先运行 python scripts/data/generate_edge_mapping.py"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "1" in data and "edges" in data["1"]
    entry = {e: i for e, i in data["1"]["edges"].items() if i["kind"] == "entry"}
    assert entry, "路口 1 应有进口边"
    for info in entry.values():
        assert info["lanes"] >= 1 and info["direction"]


def test_apply_edge_mapping_filters_inbound():
    bridge = TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"))
    bridge._controlled_lanes = ["-E2_0", "-E2_1", "E4_0"]
    bridge._apply_edge_mapping({
        "-E2": {"direction": "东", "kind": "entry", "lanes": 2},
        "E4": {"direction": "西", "kind": "exit", "lanes": 1},
    })
    assert bridge._inbound_lanes == ["-E2_0", "-E2_1"]
    assert bridge.lane_directions == {"-E2_0": "东", "-E2_1": "东"}


def test_apply_edge_mapping_no_entry_falls_back():
    bridge = TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"))
    bridge._controlled_lanes = ["E4_0"]
    bridge._apply_edge_mapping({"E4": {"direction": "西", "kind": "exit", "lanes": 1}})
    assert bridge._inbound_lanes is None  # 无进口边 → 回退 getControlledLanes
```

注：`TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"))` 不调用 `start()`，纯构造无副作用。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/integration/test_edge_mapping.py -q`
Expected: FAIL（JSON 不存在 / 无 `_apply_edge_mapping`）

- [ ] **Step 3: 修改 scripts/generate_edge_mapping.py**

在 `edge_rows` 前新增结构化函数，`edge_rows` 改为消费它（Markdown 输出保持不变）：

```python
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
```

把 `edge_rows` 里从 `tls_junctions = ...` 到传播循环结束的代码抽成 `_classify(net) -> tuple[dict, dict, list]`，`edge_rows` 与 `edge_data` 共用。`main()` 末尾追加 JSON 输出：

```python
import json

JSON_OUT = DATA / "metadata" / "edge_mapping.json"

# main() 中：
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
    OUT.write_text("\n".join(lines), encoding="utf-8")
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已写入 {OUT} 与 {JSON_OUT}")
```

- [ ] **Step 4: 修改 engine/traci_bridge.py**

顶部 import 增加 `import json`、`import re`。`__init__` 增加属性：

```python
        self._inbound_lanes: Optional[List[str]] = None  # edge_mapping 进口道筛选结果
        self.lane_directions: dict[str, str] = {}  # lane_id -> 方位（供 AB 压力映射）
```

`start()` 在 `self._controlled_lanes = ...` 之后调用 `self._load_edge_mapping()`。新增两个方法：

```python
    def _load_edge_mapping(self) -> None:
        """加载 data/intersection_data/metadata/edge_mapping.json 并筛选进口道。

        路口编号从 sumocfg 文件名 demo_<n>.sumocfg 解析；JSON 缺失/无匹配时
        回退 getControlledLanes（打 warning，不中断）。
        """
        match = re.search(r"demo_(\d+)", self.sumo_cfg.stem)
        if not match:
            logger.warning("无法从 %s 解析路口编号，回退 getControlledLanes", self.sumo_cfg)
            return
        from core.config import get_config
        path = Path(get_config().path("paths.data_root")) / "metadata" / "edge_mapping.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("edge_mapping.json 不可用(%s)，回退 getControlledLanes: %s", path, exc)
            return
        edges = data.get(match.group(1), {}).get("edges", {})
        self._apply_edge_mapping(edges)

    def _apply_edge_mapping(self, edges: dict) -> None:
        """按 edge_mapping 筛选进口车道并建立 lane -> 方位映射（纯方法，可单测）。"""
        inbound: List[str] = []
        for edge_id, info in edges.items():
            if info.get("kind") != "entry":
                continue
            for i in range(int(info.get("lanes", 0))):
                lane_id = f"{edge_id}_{i}"
                if lane_id in self._controlled_lanes:
                    inbound.append(lane_id)
                    self.lane_directions[lane_id] = info.get("direction", "")
        if inbound:
            self._inbound_lanes = inbound
            logger.info("进口道筛选: %d/%d 车道", len(inbound), len(self._controlled_lanes))
```

`get_state()` 中循环对象改为 `lanes = self._inbound_lanes or self._controlled_lanes`。

- [ ] **Step 5: 生成 JSON 并跑测试**

Run: `python scripts/data/generate_edge_mapping.py`
Expected: 输出 `已写入 ...edge_mapping.md 与 ...edge_mapping.json`

Run: `python -m pytest tests/ -q`
Expected: 39 passed；同时确认 `docs/reference/edge-mapping.md` 内容与改动前一致（`git diff --stat docs/reference/edge-mapping.md` 应为空或无实质变化）

- [ ] **Step 6: 真实 SUMO 验证进口道筛选生效**

Run: `python -c "
import sys, logging; sys.path.insert(0, '.')
logging.basicConfig(level=logging.INFO)
from scenes.registry import SceneRegistry
from engine.traci_bridge import TraCIBridge
scene = SceneRegistry().get_scene('1')
b = TraCIBridge(scene.meta.sumo_cfg)
b.start()
print('lane_directions:', b.lane_directions)
assert b._inbound_lanes, '进口道筛选应生效'
b.step()
state = b.get_state()
assert all(q.direction in b._inbound_lanes for q in state.queues)
b.close()
print('OK inbound filter')
"`
Expected: 打印方位映射 + `OK inbound filter`

---

### Task 4: examples/run_ca_max_pressure.py + apply_actions 容错 + 路口 1 双算法 3600 步实证

**Files:**
- Create: `examples/run_ca_max_pressure.py`
- Modify: `engine/traci_bridge.py`（`apply_actions` 容错）

**Interfaces:**
- Consumes: `CAMaxPressureAlgorithm`（MVI 桩，`algorithms/ca_max_pressure.py`）、`SimulationRunner`
- Produces: `python examples/run_ca_max_pressure.py [intersection_id]` 可运行；`apply_actions` 对非法 set_phase 值打 warning 跳过（AB 的 MVI 桩当前把方向字符串当相位值，属已知问题，正式实现归 AB）

**背景（必须告知实现者）：** CA-MP MVI 桩输出 `ControlAction(action_type="set_phase", value=best_queue.direction)`，value 是 lane_id 字符串，`int(action.value)` 会 ValueError。这是 AB 侧桩的问题；IB 侧按任务书 Day 6「修复联调中发现的 bug」做容错：跳过并 warning，保证管道 3600 步跑通。

- [ ] **Step 1: apply_actions 容错（修改 engine/traci_bridge.py）**

```python
    def apply_actions(self, actions: List[ControlAction]) -> None:
        """将算法输出的控制动作写入 SUMO。

        set_phase 的 value 必须是相位索引 int；无法转换时打 warning 并跳过
        （已知：CA-MP MVI 桩把方向字符串当相位值，正式实现归 AB）。
        """
        for action in actions:
            if action.action_type == "set_phase":
                try:
                    phase_index = int(action.value)
                except (TypeError, ValueError):
                    logger.warning(
                        "set_phase 值非法，跳过: value=%r reason=%s", action.value, action.reason
                    )
                    continue
                traci.trafficlight.setPhase(action.tls_id, phase_index)
            elif action.action_type == "set_phase_duration":
                traci.trafficlight.setPhaseDuration(action.tls_id, float(action.value))
            elif action.action_type == "set_program":
                traci.trafficlight.setProgram(action.tls_id, str(action.value))
            else:
                logger.warning("未知控制动作类型: %s", action.action_type)
```

- [ ] **Step 2: 创建 examples/run_ca_max_pressure.py**

```python
"""最小可运行示例：路口 1 CA-MP（容量感知最大压力）仿真。

用法: python examples/run_ca_max_pressure.py [intersection_id] [steps]
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# 兼容直接运行示例脚本
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from engine.runner import SimulationRunner
from scenes.registry import SceneRegistry

logging.basicConfig(level=logging.INFO)


def main() -> None:
    intersection_id = sys.argv[1] if len(sys.argv) > 1 else "1"
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 3600

    registry = SceneRegistry()
    scene = registry.get_scene(intersection_id)
    print(f"运行路口 {scene.meta.intersection_id}: {scene.meta.name} (CA-MP)")

    runner = SimulationRunner(scene, CAMaxPressureAlgorithm())
    metrics = runner.run(steps=steps)

    print(f"仿真完成，共记录 {len(metrics)} 条指标快照")
    print(f"CSV 输出: {runner.output_csv}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 实证 — 路口 1 CA-MP 3600 步**

Run: `python examples/run_ca_max_pressure.py 1 3600`
Expected: 退出码 0；输出 `仿真完成，共记录 61 条指标快照`；warning 日志含 `set_phase 值非法，跳过`（MVI 桩已知行为）

- [ ] **Step 4: 检查输出 CSV**

Run: `python -c "
import csv
rows = list(csv.DictReader(open('output/csv/1_ca_maxpressure.csv', encoding='utf-8')))
queues = [float(r['avg_queue_length']) for r in rows]
assert any(q > 0 for q in queues), 'avg_queue 应有非零值'
print(f'rows={len(rows)} max_avg_queue={max(queues):.1f}')
"`
Expected: `rows=61` 且 max_avg_queue > 0

- [ ] **Step 5: 回归固定配时示例**

Run: `python examples/run_fixed_time.py 1`
Expected: 正常完成 3600 步（确认 Task 2-4 的 bridge 改动未破坏基线）

---

### Task 5: 真 seed 支持（TraCIBridge / SimulationRunner / run_batch 透传）

**Files:**
- Modify: `engine/traci_bridge.py`（`__init__` + `_build_cmd`）
- Modify: `engine/runner.py`（`__init__` 增加 `seed` 透传）
- Modify: `experiments/runner.py`（`run_batch` 透传 seed）
- Create: `scripts/check_seed_repro.py`
- Test: `tests/test_seed.py`（新建）

**Interfaces:**
- Produces:
  - `TraCIBridge(..., seed: Optional[int] = None)`；`TraCIBridge._build_cmd() -> List[str]`
  - `SimulationRunner(..., seed: Optional[int] = None)`
  - `run_batch(...)` 中 seed 传入 SimulationRunner

- [ ] **Step 1: 写失败测试**

```python
"""seed 透传测试（IB W2）：--seed 必须进入 traci.start 命令。"""
from pathlib import Path

from engine.traci_bridge import TraCIBridge


def test_build_cmd_without_seed():
    b = TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"))
    cmd = b._build_cmd()
    assert "--seed" not in cmd


def test_build_cmd_with_seed():
    b = TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"), seed=42)
    cmd = b._build_cmd()
    i = cmd.index("--seed")
    assert cmd[i + 1] == "42"


def test_runner_passes_seed_to_bridge():
    from unittest.mock import patch
    from algorithms.fixed_time import FixedTimeAlgorithm
    from core.types import Scene, SceneMeta
    from engine.runner import SimulationRunner

    meta = SceneMeta(
        intersection_id="1", name="t",
        sumo_net=Path("x.net.xml"), sumo_rou=Path("x.rou.xml"),
        sumo_flow=Path("x.flow.xml"), sumo_turn=Path("x.turn.xml"),
        sumo_cfg=Path("x.sumocfg"), timing_xlsx=Path("x.xlsx"),
    )
    with patch("engine.runner.TraCIBridge") as mock_cls:
        SimulationRunner(Scene(meta=meta), FixedTimeAlgorithm(), seed=42)
        assert mock_cls.call_args.kwargs.get("seed") == 42
```

注：`test_runner_passes_seed_to_bridge` 依赖 `engine/runner.py` 用关键字参数 `seed=seed` 构造 TraCIBridge。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/integration/test_seed.py -q`
Expected: FAIL（无 `_build_cmd` / runner 无 `seed` 参数）

- [ ] **Step 3: 实现**

`engine/traci_bridge.py` `__init__` 增加 `seed: Optional[int] = None` 参数并存 `self.seed = seed`；`start()` 改为：

```python
    def _build_cmd(self) -> List[str]:
        """组装 traci.start 命令（含可选 --seed 与 additional files）。"""
        cmd = [self.binary, "-c", str(self.sumo_cfg), "--no-step-log", "true"]
        if self.seed is not None:
            cmd += ["--seed", str(self.seed)]
        if self.additional_files:
            cmd += ["-a", ",".join(str(f) for f in self.additional_files)]
        return cmd

    def start(self) -> None:
        """启动 SUMO 仿真进程。"""
        if not self.sumo_cfg.exists():
            raise FileNotFoundError(f"SUMO 配置文件不存在: {self.sumo_cfg}")

        cmd = self._build_cmd()
        logger.info("启动 SUMO: %s", " ".join(cmd))
        traci.start(cmd)
        # ... 其余不变
```

`engine/runner.py` `__init__` 增加 `seed: Optional[int] = None`，存 `self.seed = seed`，构造 bridge 处改为：

```python
            self.bridge = TraCIBridge(
                cfg,
                binary=self.sumo_binary,
                additional_files=self.additional_files,
                seed=self.seed,
            )
```

`experiments/runner.py` `run_batch` 中 SimulationRunner 构造增加 `seed=seed`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/ -q`
Expected: 42 passed

- [ ] **Step 5: 创建 scripts/check_seed_repro.py 并实证**

```python
"""seed 复现性验证（IB W2）：同 seed 两次运行结果一致，异 seed 有差异。"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from algorithms.fixed_time import FixedTimeAlgorithm
from engine.runner import SimulationRunner
from scenes.registry import SceneRegistry

STEPS = 300


def run_once(seed: int, out: Path) -> list[dict]:
    scene = SceneRegistry().get_scene("1")
    runner = SimulationRunner(scene, FixedTimeAlgorithm(), output_csv=out, seed=seed)
    runner.run(STEPS)
    return list(csv.DictReader(open(out, encoding="utf-8")))


def main() -> None:
    out = Path("output/seed_check")
    a = run_once(42, out / "a.csv")
    b = run_once(42, out / "b.csv")
    c = run_once(7, out / "c.csv")
    assert a == b, "同 seed 两次运行应完全一致"
    assert a != c, "异 seed 应有差异"
    print(f"OK: seed=42 两次一致（{len(a)} 行），seed=7 有差异")


if __name__ == "__main__":
    main()
```

Run: `python scripts/validation/check_seed_repro.py`
Expected: `OK: seed=42 两次一致（6 行），seed=7 有差异`

---

### Task 6: VariantGenerator.generate_scaled 任意倍率

**Files:**
- Modify: `scenes/variant.py`
- Test: `tests/test_scenes.py`（追加）

**Interfaces:**
- Produces: `VariantGenerator.generate_scaled(scene_meta: SceneMeta, factor: float, output_dir: Path) -> Path`（factor <= 0 抛 ValueError；输出文件名 `*_x{factor:g}.flow.xml`）

- [ ] **Step 1: 写失败测试（追加到 tests/test_scenes.py）**

```python
def test_generate_scaled_arbitrary_factor(tmp_path):
    import xml.etree.ElementTree as ET
    from scenes.variant import VariantGenerator
    from scenes.registry import SceneRegistry

    meta = SceneRegistry().get_scene("1").meta
    out = VariantGenerator().generate_scaled(meta, 1.5, tmp_path)
    assert out.exists() and "x1.5" in out.name
    base = ET.parse(meta.sumo_flow).getroot()
    scaled = ET.parse(out).getroot()
    base_n = int(base.find("flow").get("number"))
    scaled_n = int(scaled.find("flow").get("number"))
    assert scaled_n == max(1, round(base_n * 1.5))


def test_generate_scaled_rejects_nonpositive(tmp_path):
    import pytest
    from scenes.variant import VariantGenerator
    from scenes.registry import SceneRegistry

    meta = SceneRegistry().get_scene("1").meta
    with pytest.raises(ValueError):
        VariantGenerator().generate_scaled(meta, 0.0, tmp_path)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/integration/test_scenes.py -q`
Expected: FAIL（无 `generate_scaled`）

- [ ] **Step 3: 实现（scenes/variant.py 追加方法）**

```python
    def generate_scaled(
        self,
        scene_meta: SceneMeta,
        factor: float,
        output_dir: Path,
    ) -> Path:
        """按任意倍率缩放 .flow.xml 的 <flow number> 属性，返回变体文件路径。

        Args:
            scene_meta: 场景元数据（提供基准 sumo_flow 路径）。
            factor: 流量倍率，必须 > 0（1.0 表示原始流量，调用方应直接跳过）。
            output_dir: 变体输出目录。

        Raises:
            ValueError: factor <= 0。
        """
        if factor <= 0:
            raise ValueError(f"流量倍率必须 > 0，收到: {factor}")
        output_dir.mkdir(parents=True, exist_ok=True)

        tree = ET.parse(scene_meta.sumo_flow)
        root = tree.getroot()
        for flow in root.findall("flow"):
            number_attr = flow.get("number")
            if number_attr is not None:
                scaled = max(1, int(round(int(number_attr) * factor)))
                flow.set("number", str(scaled))

        output_file = output_dir / f"{scene_meta.sumo_flow.stem}_x{factor:g}.flow.xml"
        tree.write(output_file, encoding="utf-8", xml_declaration=True)
        return output_file
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/ -q`
Expected: 44 passed

---

### Task 7: experiments/runner.py CLI（--seed/--flow-multiplier/--output-dir 等）

**Files:**
- Modify: `experiments/runner.py`（文件末尾追加）
- Test: `tests/test_experiments.py`（追加）

**Interfaces:**
- Consumes: Task 5 的 `SimulationRunner(seed=...)`、Task 6 的 `generate_scaled`
- Produces:
  - `parse_args(argv: list[str] | None = None) -> argparse.Namespace`
  - `run_single(args: argparse.Namespace) -> Path`（返回 CSV 路径）
  - `python experiments/runner.py --help` 可用

- [ ] **Step 1: 写失败测试（追加到 tests/test_experiments.py）**

```python
def test_parse_args_defaults():
    from experiments.runner import parse_args
    args = parse_args([])
    assert args.seed == 42
    assert args.flow_multiplier == 1.0
    assert args.output_dir is None
    assert args.intersection == "1"
    assert args.steps == 3600
    assert args.algorithm == "fixed_time"


def test_parse_args_custom():
    from experiments.runner import parse_args
    args = parse_args([
        "--seed", "7", "--flow-multiplier", "1.5",
        "--output-dir", "output/x", "--intersection", "16",
        "--steps", "100", "--algorithm", "ca_maxpressure",
    ])
    assert (args.seed, args.flow_multiplier, args.intersection) == (7, 1.5, "16")
    assert args.algorithm == "ca_maxpressure"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/integration/test_experiments.py -q`
Expected: FAIL（无 `parse_args`）

- [ ] **Step 3: 实现（experiments/runner.py 末尾追加）**

```python
def parse_args(argv: list[str] | None = None) -> "argparse.Namespace":
    """解析命令行参数（IB W2：--seed/--flow-multiplier/--output-dir）。"""
    import argparse

    p = argparse.ArgumentParser(description="单次/批量仿真实验入口")
    p.add_argument("--seed", type=int, default=42,
                   help="SUMO 随机种子（传入 traci.start --seed，保证可复现）")
    p.add_argument("--flow-multiplier", type=float, default=1.0,
                   help="流量倍率：1.0=原始流量，1.5=压力测试")
    p.add_argument("--output-dir", type=str, default=None,
                   help="输出根目录（CSV/变体写入其下），默认 config 的 paths.output_root")
    p.add_argument("--intersection", type=str, default="1", help="路口编号 1-20")
    p.add_argument("--steps", type=int, default=3600, help="仿真步数")
    p.add_argument("--algorithm", choices=list(ALGORITHM_MAP), default="fixed_time",
                   help="控制算法")
    return p.parse_args(argv)


def run_single(args: "argparse.Namespace") -> Path:
    """按 CLI 参数跑一次仿真，返回输出 CSV 路径。"""
    if args.flow_multiplier <= 0:
        raise ValueError(f"--flow-multiplier 必须 > 0，收到: {args.flow_multiplier}")

    registry = SceneRegistry()
    scene = registry.get_scene(args.intersection)
    output_root = Path(args.output_dir) if args.output_dir else get_config().path("paths.output_root")

    additional_files: List[Path] = []
    if args.flow_multiplier != 1.0:
        flow_file = VariantGenerator().generate_scaled(
            scene.meta, args.flow_multiplier,
            output_root / "variants" / args.intersection,
        )
        additional_files.append(flow_file)

    runner = SimulationRunner(
        scene=scene,
        algorithm=ALGORITHM_MAP[args.algorithm](),
        output_csv=output_root / "csv"
        / f"{args.intersection}_x{args.flow_multiplier:g}_{args.algorithm}_s{args.seed}.csv",
        additional_files=additional_files,
        seed=args.seed,
    )
    runner.run(args.steps)
    logger.info("实验完成: %s", runner.output_csv)
    return runner.output_csv


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    csv_path = run_single(parse_args())
    print(f"Done -> {csv_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试 + --help 自检**

Run: `python -m pytest tests/ -q`
Expected: 46 passed

Run: `python experiments/runner.py --help`
Expected: 打印全部 6 个参数及说明，退出码 0

- [ ] **Step 5: 真实仿真验证（带 seed + 倍率 + output-dir，300 步）**

Run: `python experiments/runner.py --intersection 1 --steps 300 --flow-multiplier 1.5 --seed 42 --output-dir output/cli_check`
Expected: 退出码 0，输出 `Done -> output/cli_check/csv/1_x1.5_fixed_time_s42.csv`；`output/cli_check/variants/1/` 下有 `*_x1.5.flow.xml`

---

### Task 8: CloudPolicy 压力分档 + 周期下发

**Files:**
- Modify: `cloud/cloud_policy.py`
- Test: `tests/test_cloud.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `QueueState.capacity`
- Produces:
  - `CloudPolicy.PRESSURE_TIERS`：`(阈值, {"min_green","max_green","base_green"})` 三档（>0.8 激进 / >0.4 中档 / 常规）
  - `CloudPolicy.avg_pressure(state: JointState) -> float`
  - `CloudPolicy.dispatch_params(state: JointState) -> dict`（每 update_interval=60 步重新分档，期间返回缓存；下发时 logger.info）
  - `dispatch_base_green(state)` 保持签名，内部走 dispatch_params（向后兼容）

- [ ] **Step 1: 写失败测试（追加到 tests/test_cloud.py）**

```python
def _make_pressured_state(queue: float, capacity: float, step: int = 100) -> JointState:
    return JointState(
        step=step, timestamp=float(step), tls_id="tls_0",
        current_phase=0, current_phase_name="p0", elapsed_phase_time=10.0,
        queues=[QueueState(direction="E0", queue_length=queue,
                           waiting_time=8.0, vehicle_count=6, capacity=capacity)],
        flows={"E0": 300.0},
    )


def test_pressure_tiers():
    policy = CloudPolicy()
    # avg_pressure = queue/capacity
    assert policy._compute_params(0.9)["min_green"] == 20.0   # 极高档
    assert policy._compute_params(0.5)["min_green"] == 15.0   # 中档
    assert policy._compute_params(0.1)["min_green"] == 10.0   # 常规档


def test_avg_pressure_uses_capacity():
    policy = CloudPolicy()
    state = _make_pressured_state(queue=9.0, capacity=10.0)
    assert abs(policy.avg_pressure(state) - 0.9) < 1e-9


def test_dispatch_params_interval_and_logging(caplog):
    import logging
    policy = CloudPolicy()
    with caplog.at_level(logging.INFO):
        p1 = policy.dispatch_params(_make_pressured_state(9.0, 10.0, step=0))
        p2 = policy.dispatch_params(_make_pressured_state(0.0, 10.0, step=30))  # 未到 60 步
        p3 = policy.dispatch_params(_make_pressured_state(0.0, 10.0, step=60))  # 重新分档
    assert p1["min_green"] == 20.0
    assert p2 == p1  # 周期内返回缓存
    assert p3["min_green"] == 10.0  # 压力回落 → 常规档
    assert any("云端下发参数" in r.message for r in caplog.records)


def test_dispatch_base_green_backward_compatible():
    policy = CloudPolicy()
    assert policy.dispatch_base_green(_make_state()) > 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_cloud.py -q`
Expected: FAIL（无 `_compute_params` / `avg_pressure` / `dispatch_params`）

- [ ] **Step 3: 实现（cloud/cloud_policy.py）**

`__init__` 增加：

```python
        self.update_interval: int = cfg.get("cloud_update_interval", 60)
        self._last_params: Optional[dict] = None
        self._last_dispatch_step: int = -10**9
```

新增类常量与方法，`dispatch_base_green` 重写：

```python
    # (avg_pressure 阈值, 下发参数)：>0.8 极高压力（更激进）/ >0.4 中档 / 常规
    PRESSURE_TIERS = (
        (0.8, {"min_green": 20.0, "max_green": 120.0, "base_green": 45.0}),
        (0.4, {"min_green": 15.0, "max_green": 90.0, "base_green": 35.0}),
        (0.0, {"min_green": 10.0, "max_green": 90.0, "base_green": 30.0}),
    )

    def avg_pressure(self, state: JointState) -> float:
        """全局平均压力 = 各进口道 queue/capacity 均值（capacity 缺失时退化估计）。"""
        pressures = [q.queue_length / q.capacity for q in state.queues if q.capacity > 0]
        if pressures:
            return sum(pressures) / len(pressures)
        max_q = max((q.queue_length for q in state.queues), default=0.0)
        return min(1.0, max_q / 50.0)  # 无容量信息时的粗估计

    def _compute_params(self, avg_pressure: float) -> dict:
        """按全局压力分档计算下发参数。"""
        for threshold, params in self.PRESSURE_TIERS:
            if avg_pressure > threshold:
                return dict(params)
        return dict(self.PRESSURE_TIERS[-1][1])

    def dispatch_params(self, state: JointState) -> dict:
        """周期性下发控制参数：每 update_interval 步按全局压力重新分档一次。

        周期内返回上次缓存；每次重新下发打日志（step/avg_pressure/params）。
        """
        pressure = self.avg_pressure(state)
        if self._last_params is None or state.step - self._last_dispatch_step >= self.update_interval:
            self._last_params = self._compute_params(pressure)
            self._last_dispatch_step = state.step
            logger.info("云端下发参数: step=%d avg_pressure=%.3f params=%s",
                        state.step, pressure, self._last_params)
        return dict(self._last_params)

    def dispatch_base_green(self, state: JointState) -> float:
        """周期性下发 base_green 参数（云端全局协调）。"""
        return float(self.dispatch_params(state)["base_green"])
```

`reset()` 追加 `self._last_params = None; self._last_dispatch_step = -10**9`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/ -q`
Expected: 50 passed

---

### Task 9: EdgeChannel（V2X 过滤 + 1 步延迟）

**Files:**
- Create: `engine/edge_channel.py`
- Test: `tests/test_edge_channel.py`（新建）

**Interfaces:**
- Consumes: `core.types.JointState`
- Produces:
  - `EdgeChannel(delay_steps: int = 1, allowed_directions: Optional[List[str]] = None)`
  - `.send(state: JointState) -> None`（可选方向过滤后入通道）
  - `.receive() -> Optional[JointState]`（延迟未满返回 None；否则返回 delay_steps 步前发送的状态）

- [ ] **Step 1: 写失败测试**

```python
"""EdgeChannel V2X 消息过滤与延迟测试（IB W2，PDF 加分项）。"""
from core.types import JointState, QueueState
from engine.edge_channel import EdgeChannel


def _state(step: int, directions=("north", "south")) -> JointState:
    return JointState(
        step=step, timestamp=float(step), tls_id="tls_0",
        current_phase=0, current_phase_name="p0", elapsed_phase_time=0.0,
        queues=[QueueState(direction=d, queue_length=1.0, waiting_time=0.0,
                           vehicle_count=1) for d in directions],
        flows={d: 100.0 for d in directions},
    )


def test_one_step_delay():
    ch = EdgeChannel(delay_steps=1)
    ch.send(_state(0))
    assert ch.receive() is None  # 延迟未满
    ch.send(_state(1))
    got = ch.receive()
    assert got is not None and got.step == 0  # 收到 1 步前的消息


def test_zero_delay_passthrough():
    ch = EdgeChannel(delay_steps=0)
    ch.send(_state(5))
    assert ch.receive().step == 5


def test_direction_filter():
    ch = EdgeChannel(delay_steps=0, allowed_directions=["north"])
    ch.send(_state(0, directions=("north", "south")))
    got = ch.receive()
    assert [q.direction for q in got.queues] == ["north"]
    assert list(got.flows.keys()) == ["north"]


def test_no_filter_keeps_all():
    ch = EdgeChannel(delay_steps=0)
    ch.send(_state(0))
    assert len(ch.receive().queues) == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_edge_channel.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 engine/edge_channel.py**

```python
"""V2X 边缘通道：消息过滤 + 固定步数延迟模拟（PDF 加分项）。

模拟 V2X 消息的发送、接收与简单延迟：
- 车端/灯端通过 send() 把 JointState 投入通道；
- 边缘控制器通过 receive() 取回 delay_steps 步前发送的消息（不足则 None）；
- allowed_directions 非空时，消息在入通道前按方向过滤（消息过滤）。
"""

from __future__ import annotations

import dataclasses
import logging
from collections import deque
from typing import Deque, List, Optional

from core.types import JointState

logger = logging.getLogger(__name__)


class EdgeChannel:
    """带过滤与固定延迟的 V2X 消息通道。"""

    def __init__(
        self,
        delay_steps: int = 1,
        allowed_directions: Optional[List[str]] = None,
    ) -> None:
        self.delay_steps = max(0, int(delay_steps))
        self.allowed_directions = allowed_directions
        self._buffer: Deque[JointState] = deque()

    def send(self, state: JointState) -> None:
        """发送状态消息入通道（可选方向过滤）。"""
        if self.allowed_directions is not None:
            allowed = set(self.allowed_directions)
            state = dataclasses.replace(
                state,
                queues=[q for q in state.queues if q.direction in allowed],
                flows={d: f for d, f in state.flows.items() if d in allowed},
            )
        self._buffer.append(state)

    def receive(self) -> Optional[JointState]:
        """接收 delay_steps 步前发送的消息；延迟未满返回 None。"""
        if len(self._buffer) <= self.delay_steps:
            return None
        return self._buffer.popleft()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/ -q`
Expected: 54 passed

---

### Task 10: simulation_log.csv 每步日志（StepLogger）

**Files:**
- Modify: `engine/collector.py`（新增 StepLogger 类）
- Modify: `engine/runner.py`（`step_log_csv` 参数 + `_tick` 记录）
- Test: `tests/test_step_log.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `QueueState.capacity`
- Produces:
  - `StepLogger(output_file: Path)`，`.record(step: int, state: JointState) -> None`，`.save() -> None`
  - 列：`step, timestamp, current_phase, queue_<dir>, pressure_<dir>`（pressure = queue/capacity，capacity=0 时记空）
  - `SimulationRunner(..., step_log_csv: Optional[Path] = None)`

- [ ] **Step 1: 写失败测试**

```python
"""simulation_log.csv 每步日志测试（IB W2 Day 5）。"""
import csv

from algorithms.fixed_time import FixedTimeAlgorithm
from core.types import Scene, SceneMeta
from engine.mock_bridge import MockBridge
from engine.runner import SimulationRunner


def _scene() -> Scene:
    meta = SceneMeta(
        intersection_id="1", name="t",
        sumo_net="x.net.xml", sumo_rou="x.rou.xml", sumo_flow="x.flow.xml",
        sumo_turn="x.turn.xml", sumo_cfg="x.sumocfg", timing_xlsx="x.xlsx",
    )
    return Scene(meta=meta)


def test_step_log_written_every_step(tmp_path):
    log = tmp_path / "simulation_log.csv"
    runner = SimulationRunner(
        _scene(), FixedTimeAlgorithm(),
        output_csv=tmp_path / "snap.csv",
        bridge=MockBridge(),
        step_log_csv=log,
    )
    runner.run(10)
    rows = list(csv.DictReader(open(log, encoding="utf-8")))
    assert len(rows) == 10  # 每步一行
    assert "queue_north" in rows[0] and "pressure_north" in rows[0]
    assert float(rows[0]["pressure_north"]) >= 0.0
```

注：SceneMeta 字段为 str 亦可（dataclass 不强制类型）。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/integration/test_step_log.py -q`
Expected: FAIL（无 `step_log_csv` 参数）

- [ ] **Step 3: 实现**

`engine/collector.py` 末尾追加：

```python
class StepLogger:
    """每步仿真日志（simulation_log.csv）：相位 + 各方向排队/压力。"""

    def __init__(self, output_file: Path) -> None:
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self._rows: List[dict] = []

    def record(self, step: int, state: JointState) -> None:
        """记录单步：pressure = queue_length / capacity（capacity=0 时记空）。"""
        row: dict = {
            "step": step,
            "timestamp": state.timestamp,
            "current_phase": state.current_phase,
        }
        for q in state.queues:
            row[f"queue_{q.direction}"] = q.queue_length
            row[f"pressure_{q.direction}"] = (
                round(q.queue_length / q.capacity, 4) if q.capacity > 0 else ""
            )
        self._rows.append(row)

    def save(self) -> None:
        """写入 CSV 文件。"""
        if not self._rows:
            return
        fieldnames = list(self._rows[0].keys())
        with open(self.output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self._rows)
        logger.info("已保存每步日志 %d 行到 %s", len(self._rows), self.output_file)
```

`engine/runner.py`：`__init__` 增加 `step_log_csv: Optional[Path] = None`，存 `self.step_logger = StepLogger(step_log_csv) if step_log_csv else None`；`_tick` 在记录快照之前加：

```python
        if self.step_logger:
            self.step_logger.record(step, state)
```

`run()` 的 finally 块中 `collector.save()` 后加：

```python
            if self.step_logger:
                self.step_logger.save()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/ -q`
Expected: 55 passed

---

### Task 11: FatalTraCIError 韧性 + 可选自动重连

**Files:**
- Modify: `engine/traci_bridge.py`（`step()` / `close()` / `__init__`）
- Modify: `engine/runner.py`（`_tick` 处理断开）
- Test: `tests/test_resilience.py`（新建）

**Interfaces:**
- Produces:
  - `TraCIBridge(..., max_restarts: int = 0)`
  - `TraCIBridge.step() -> Optional[float]`：断开时优雅关闭返回 None；重连成功返回新时间
  - runner 在 `bridge.step()` 返回 None 时 break 并正常收尾（退出码 0）

- [ ] **Step 1: 写失败测试**

```python
"""TraCI 断线韧性测试（IB W3）：FatalTraCIError 优雅退出与自动重连。"""
from pathlib import Path
from unittest.mock import patch

from engine.traci_bridge import TraCIBridge, traci


def _bridge(max_restarts: int = 0) -> TraCIBridge:
    return TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"), max_restarts=max_restarts)


def test_step_returns_none_on_fatal_error(caplog):
    bridge = _bridge()
    with patch.object(traci, "simulationStep",
                      side_effect=traci.exceptions.FatalTraCIError("connection closed")), \
         patch.object(traci, "isLoaded", return_value=False):
        import logging
        with caplog.at_level(logging.ERROR):
            assert bridge.step() is None
    assert any("closing gracefully" in r.message for r in caplog.records)


def test_step_restarts_when_allowed():
    bridge = _bridge(max_restarts=1)
    calls = {"n": 0}

    def flaky_step():
        calls["n"] += 1
        if calls["n"] == 1:
            raise traci.exceptions.FatalTraCIError("boom")

    with patch.object(traci, "simulationStep", side_effect=flaky_step), \
         patch.object(traci, "isLoaded", return_value=False), \
         patch.object(TraCIBridge, "start", autospec=True) as mock_start, \
         patch.object(traci.simulation, "getTime", return_value=0.0):
        assert bridge.step() == 0.0
        assert mock_start.call_count == 1  # 触发了一次重连


def test_close_idempotent():
    bridge = _bridge()
    with patch.object(traci, "isLoaded", side_effect=[True, False]), \
         patch.object(traci, "close") as mock_close:
        bridge.close()
        bridge.close()  # 第二次应为 no-op
        assert mock_close.call_count == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/integration/test_resilience.py -q`
Expected: FAIL（`max_restarts` 参数不存在 / step 抛异常）

- [ ] **Step 3: 实现（engine/traci_bridge.py）**

`__init__` 增加 `max_restarts: int = 0`，存 `self.max_restarts = max(0, int(max_restarts))` 与 `self._restarts = 0`。`step()` 改为：

```python
    def step(self) -> Optional[float]:
        """推进一个仿真步。

        Returns:
            当前仿真时间；FatalTraCIError（如 SUMO 进程被杀）时优雅关闭并
            返回 None；配置 max_restarts > 0 时先尝试自动重连。
        """
        try:
            traci.simulationStep()
            return traci.simulation.getTime()
        except traci.exceptions.FatalTraCIError as exc:
            logger.error("TraCI 连接断开: %s; closing gracefully", exc)
            if self._restarts < self.max_restarts:
                self._restarts += 1
                logger.info("尝试自动重连 (%d/%d)", self._restarts, self.max_restarts)
                self.close()
                self.start()
                return traci.simulation.getTime()
            self.close()
            return None
```

`close()` 保持 `isLoaded()` 守卫（已幂等），docstring 注明可重复调用。

`engine/runner.py` `_tick` 改为返回 bool：

```python
    def _tick(self, step: int) -> bool:
        """单个仿真步；返回 False 表示仿真已断开，应停止。"""
        state = self.bridge.get_state()
        actions: List[ControlAction] = self.algorithm.step(state)
        self.bridge.apply_actions(actions)
        sim_time = self.bridge.step()
        if sim_time is None:
            logger.warning("仿真在 step %d 断开，提前结束", step)
            return False
        # ... 快照/每步日志记录不变 ...
        return True
```

`run()` 循环改为：

```python
            for step in range(steps):
                if not self._tick(step):
                    break
```

- [ ] **Step 4: 跑测试确认通过 + 全量回归**

Run: `python -m pytest tests/ -q`
Expected: 58 passed

- [ ] **Step 5: 真实断线实证（taskkill）**

起一个后台仿真，杀掉 sumo 进程，验证优雅退出：

Run: `python examples/run_fixed_time.py 1 3600 & sleep 5 && taskkill //F //IM sumo.exe; wait $!; echo "exit=$?"`
Expected: 日志含 `closing gracefully` 与 `仿真在 step ... 断开，提前结束`；`exit=0`（无未捕获异常堆栈）

---

### Task 12: events.csv 事件日志（EventLogger）

**Files:**
- Create: `engine/events.py`
- Modify: `engine/runner.py`（`events_csv` 参数 + 生命周期/动作事件）
- Test: `tests/test_events.py`（新建）

**Interfaces:**
- Produces:
  - `EventLogger(output_file: Path)`，`.log(step: int, event_type: str, detail: str) -> None`，`.save() -> None`；列 `step, type, detail`
  - `SimulationRunner(..., events_csv: Optional[Path] = None)`：自动记录 `run_start`/`run_end` 与每个 ControlAction（type=action_type, detail=reason or value）——AB 的溢出门控实现后其动作自动进入事件流

- [ ] **Step 1: 写失败测试**

```python
"""events.csv 事件日志测试（IB W3 Day 2）。"""
import csv

from algorithms.fixed_time import FixedTimeAlgorithm
from core.types import ControlAction, Scene, SceneMeta
from engine.mock_bridge import MockBridge
from engine.runner import SimulationRunner


def _scene() -> Scene:
    meta = SceneMeta(
        intersection_id="1", name="t",
        sumo_net="x.net.xml", sumo_rou="x.rou.xml", sumo_flow="x.flow.xml",
        sumo_turn="x.turn.xml", sumo_cfg="x.sumocfg", timing_xlsx="x.xlsx",
    )
    return Scene(meta=meta)


class _ActionAlgo(FixedTimeAlgorithm):
    @property
    def name(self) -> str:
        return "action_algo"

    def step(self, state):
        return [ControlAction(tls_id=state.tls_id, action_type="set_phase",
                              value=1, reason="测试动作")]


def test_events_csv_lifecycle_and_actions(tmp_path):
    events = tmp_path / "events.csv"
    runner = SimulationRunner(
        _scene(), _ActionAlgo(), output_csv=tmp_path / "snap.csv",
        bridge=MockBridge(), events_csv=events,
    )
    runner.run(5)
    rows = list(csv.DictReader(open(events, encoding="utf-8")))
    types = [r["type"] for r in rows]
    assert types[0] == "run_start" and types[-1] == "run_end"
    assert "set_phase" in types
    detail = next(r["detail"] for r in rows if r["type"] == "set_phase")
    assert "测试动作" in detail
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/integration/test_events.py -q`
Expected: FAIL（无 `engine.events` / 无 `events_csv` 参数）

- [ ] **Step 3: 实现**

`engine/events.py`：

```python
"""仿真事件日志（events.csv）。

记录运行生命周期与算法控制动作；AB 实现溢出门控后，
其 ControlAction 会自动进入事件流（机制先行）。
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class EventLogger:
    """事件行：step / type / detail。"""

    def __init__(self, output_file: Path) -> None:
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self._rows: List[dict] = []

    def log(self, step: int, event_type: str, detail: str) -> None:
        """记录一条事件。"""
        self._rows.append({"step": step, "type": event_type, "detail": detail})

    def save(self) -> None:
        """写入 CSV 文件。"""
        if not self._rows:
            return
        with open(self.output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["step", "type", "detail"])
            writer.writeheader()
            writer.writerows(self._rows)
        logger.info("已保存 %d 条事件到 %s", len(self._rows), self.output_file)
```

`engine/runner.py`：`__init__` 增加 `events_csv: Optional[Path] = None`，存
`self.event_logger = EventLogger(events_csv) if events_csv else None`。

`run()` 在 `self.bridge.start()` 后加：

```python
            if self.event_logger:
                self.event_logger.log(
                    0, "run_start",
                    f"intersection={self.scene.meta.intersection_id} algorithm={self.algorithm.name}",
                )
```

`_tick` 在 `apply_actions` 后加：

```python
        if self.event_logger:
            for action in actions:
                self.event_logger.log(
                    step, action.action_type, action.reason or str(action.value)
                )
```

`run()` 的 finally 块中保存：

```python
            if self.event_logger:
                self.event_logger.log(
                    len(self.metrics_history), "run_end",
                    f"snapshots={len(self.metrics_history)}",
                )
                self.event_logger.save()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/ -q`
Expected: 59 passed

- [ ] **Step 5: CLI 接线（experiments/runner.py 的 run_single 增加日志输出）**

`run_single` 中 SimulationRunner 构造追加：

```python
        step_log_csv=output_root / "logs"
        / f"{args.intersection}_x{args.flow_multiplier:g}_{args.algorithm}_s{args.seed}_simulation_log.csv",
        events_csv=output_root / "logs"
        / f"{args.intersection}_x{args.flow_multiplier:g}_{args.algorithm}_s{args.seed}_events.csv",
```

Run: `python experiments/runner.py --intersection 1 --steps 100 --output-dir output/cli_check2`
Expected: `output/cli_check2/logs/` 下生成 simulation_log 与 events 两个 CSV

---

### Task 13: vehicles 采样/500 上限 + arrival_history

**Files:**
- Modify: `engine/traci_bridge.py`（`__init__` / `step` / `get_state` / `_collect_vehicles`）
- Modify: `engine/mock_bridge.py`（接口对齐）
- Test: `tests/test_vehicles.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `VehicleState`、`JointState.vehicles/arrival_history`
- Produces:
  - `TraCIBridge(..., vehicle_sample_rate: int = 1)`；`TraCIBridge.MAX_VEHICLES = 500`（Task 2 已加类常量）
  - `TraCIBridge._collect_vehicles(ids: List[str]) -> List[VehicleState]`（采样 → 超上限优先保留进口道车辆 → 截断；纯逻辑可传 ids 单测）
  - `JointState.arrival_history`：最近 300 步每步进入路网车辆数（`traci.simulation.getDepartedIDNumber()`）
  - `MockBridge(..., vehicle_sample_rate: int = 1)`，get_state 返回确定性 vehicles 与 arrival_history

- [ ] **Step 1: 写失败测试**

```python
"""车辆采样/上限与到达历史测试（IB W4）。"""
from engine.mock_bridge import MockBridge


def test_mock_vehicles_deterministic():
    bridge = MockBridge()
    bridge.start()
    bridge.step()
    state = bridge.get_state()
    assert state.vehicles, "应有车辆快照"
    assert all(v.lane_id for v in state.vehicles)


def test_mock_vehicle_sample_rate():
    full = MockBridge(vehicle_sample_rate=1)
    sampled = MockBridge(vehicle_sample_rate=3)
    full.start(); sampled.start()
    full.step(); sampled.step()
    n_full = len(full.get_state().vehicles)
    n_sampled = len(sampled.get_state().vehicles)
    assert n_sampled < n_full


def test_mock_arrival_history_rolls():
    bridge = MockBridge()
    bridge.start()
    for _ in range(5):
        bridge.step()
    state = bridge.get_state()
    assert state.arrival_history == [1, 1, 1, 1, 1]  # Mock: 每步 1 辆进入


def test_traci_collect_vehicles_cap_prefers_inbound():
    from pathlib import Path
    from unittest.mock import patch
    from engine.traci_bridge import TraCIBridge, traci

    bridge = TraCIBridge(sumo_cfg=Path("demo_1.sumocfg"))
    bridge._controlled_lanes = ["-E2_0"]
    ids = [f"v{i}" for i in range(600)]

    def lane_of(vid: str) -> str:
        return "-E2_0" if int(vid[1:]) < 100 else "E9_0"  # 前 100 辆在进口道

    with patch.object(traci.vehicle, "getLaneID", side_effect=lane_of), \
         patch.object(traci.vehicle, "getSpeed", return_value=5.0):
        vehicles = bridge._collect_vehicles(ids)
    assert len(vehicles) == 500
    inbound = [v for v in vehicles if v.lane_id == "-E2_0"]
    assert len(inbound) == 100  # 进口道车辆全部保留
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/unit/test_vehicles.py -q`
Expected: FAIL

- [ ] **Step 3: 实现**

`engine/traci_bridge.py`：顶部 `from collections import deque`，`from core.types import ... VehicleState`。`__init__` 增加：

```python
        self.vehicle_sample_rate = max(1, int(vehicle_sample_rate))
        self._arrival_window: deque[int] = deque(maxlen=300)  # 滚动 300 步到达历史
```

（`__init__` 签名加 `vehicle_sample_rate: int = 1`。）

`step()` 成功推进后（`traci.simulationStep()` 下一行）记录到达数：

```python
            self._arrival_window.append(traci.simulation.getDepartedIDNumber())
```

新增方法并在 `get_state()` 的 JointState 构造中加 `vehicles=self._collect_vehicles(list(traci.vehicle.getIDList()))` 与 `arrival_history=list(self._arrival_window)`：

```python
    def _collect_vehicles(self, ids: List[str]) -> List[VehicleState]:
        """采集车辆快照：先按 vehicle_sample_rate 采样，再按 MAX_VEHICLES 截断。

        超出上限时优先保留进口道（受控车道）上的车辆——CA-MP 只关心它们。
        """
        if self.vehicle_sample_rate > 1:
            ids = ids[:: self.vehicle_sample_rate]
        if len(ids) > self.MAX_VEHICLES:
            inbound = set(self._controlled_lanes)
            on_inbound = [v for v in ids if traci.vehicle.getLaneID(v) in inbound]
            rest = [v for v in ids if v not in set(on_inbound)]
            ids = (on_inbound + rest)[: self.MAX_VEHICLES]
        return [
            VehicleState(vehicle_id=v, lane_id=traci.vehicle.getLaneID(v),
                         speed=traci.vehicle.getSpeed(v))
            for v in ids
        ]
```

`engine/mock_bridge.py`：`__init__` 加 `vehicle_sample_rate: int = 1`（存 `self.vehicle_sample_rate`）与 `self._arrivals: List[int] = []`；`step()` 加 `self._arrivals.append(1)`（保持最近 300：`self._arrivals = self._arrivals[-300:]`）；`get_state()` 的 JointState 加：

```python
            vehicles=[
                VehicleState(vehicle_id=f"mock_{i}", lane_id=direction,
                             speed=10.0)
                for i, direction in enumerate(self.directions)
                for _ in range(0)  # 占位，见下
            ][:0] if False else self._mock_vehicles(),
            arrival_history=list(self._arrivals),
```

实际用干净的私有方法：

```python
    def _mock_vehicles(self) -> List[VehicleState]:
        """确定性车辆快照：每个方向 4 辆，按 sample_rate 抽稀。"""
        vehicles = [
            VehicleState(vehicle_id=f"mock_{d}_{i}", lane_id=d, speed=10.0)
            for d in self.directions
            for i in range(4)
        ]
        return vehicles[:: self.vehicle_sample_rate]
```

- [ ] **Step 4: 跑测试确认通过 + 真实 SUMO 冒烟**

Run: `python -m pytest tests/ -q`
Expected: 63 passed

Run: `python -c "
import sys; sys.path.insert(0, '.')
from scenes.registry import SceneRegistry
from engine.traci_bridge import TraCIBridge
b = TraCIBridge(SceneRegistry().get_scene('1').meta.sumo_cfg, vehicle_sample_rate=3)
b.start()
for _ in range(200): b.step()
s = b.get_state()
print(f'vehicles={len(s.vehicles)} arrivals={sum(s.arrival_history)} window={len(s.arrival_history)}')
assert len(s.arrival_history) == 200
b.close()
print('OK vehicles/arrivals')
"`
Expected: 打印非零 vehicles 与 arrivals，`OK vehicles/arrivals`

---

### Task 14: W3 日志审计（小子集批量实跑 + docs/w3_log_audit.md）

**Files:**
- Create: `docs/w3_log_audit.md`

**Interfaces:**
- Consumes: Task 7 CLI、Task 11 韧性

- [ ] **Step 1: 跑小子集批量（1 路口 × 3 算法 × 2 倍率 × 2 seed = 12 次，各 600 步）**

Run: `for algo in fixed_time actuated ca_maxpressure; do for mult in 1.0 1.5; do for seed in 42 7; do python experiments/runner.py --intersection 1 --steps 600 --algorithm $algo --flow-multiplier $mult --seed $seed --output-dir output/w3_audit || echo "FAILED: $algo $mult $seed"; done; done; done`
Expected: 无 `FAILED` 行；`output/w3_audit/csv/` 12 个 CSV、`output/w3_audit/logs/` 24 个日志 CSV

- [ ] **Step 2: 撰写 docs/w3_log_audit.md**

内容：日期、12 次运行表格（算法/倍率/seed/结果/CSV 行数）、崩溃与重连记录（预期全 0）、Task 11 断线测试结论引用、内存观察（任务管理器/tracemalloc 留待 W4）、遗留风险。

- [ ] **Step 3: 回归**

Run: `python -m pytest tests/ -q`
Expected: 63 passed

---

### Task 15: W4 压力实测（scripts/stress_memory.py + 1.5 倍 3600 步 + 内存）

**Files:**
- Create: `scripts/stress_memory.py`
- Create: `output/stress/`（运行产物）

**Interfaces:**
- Consumes: Task 7 的 `parse_args`/`run_single`

- [ ] **Step 1: 创建 scripts/stress_memory.py**

```python
"""1.5 倍流量压力测试 + 内存峰值测量（IB W4 Day 1）。

用法: python scripts/validation/stress_memory.py [intersection] [steps]
验收: 完整跑完，tracemalloc 峰值 < 1GB。
"""
import sys
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.runner import parse_args, run_single


def main() -> None:
    intersection = sys.argv[1] if len(sys.argv) > 1 else "1"
    steps = sys.argv[2] if len(sys.argv) > 2 else "3600"
    tracemalloc.start()
    args = parse_args([
        "--intersection", intersection, "--steps", steps,
        "--flow-multiplier", "1.5", "--output-dir", "output/stress",
        "--algorithm", "ca_maxpressure", "--seed", "42",
    ])
    csv_path = run_single(args)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"tracemalloc peak: {peak / 1024 / 1024:.1f} MiB (Python 侧，不含 SUMO 进程)")
    assert peak < 1024**3, "峰值内存超 1GB"
    print(f"csv: {csv_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 实跑 1.5 倍 3600 步**

Run: `python scripts/validation/stress_memory.py 1 3600`
Expected: 退出码 0；打印 `tracemalloc peak: ... MiB`（< 1024）；`output/stress/csv/1_x1.5_ca_maxpressure_s42.csv` 与 logs 齐全

- [ ] **Step 3: 验证高流量下 vehicles 上限/采样生效**

Run: `python -c "
import sys; sys.path.insert(0, '.')
from scenes.registry import SceneRegistry
from scenes.variant import VariantGenerator
from engine.traci_bridge import TraCIBridge
scene = SceneRegistry().get_scene('1')
flow = VariantGenerator().generate_scaled(scene.meta, 1.5, __import__('pathlib').Path('output/stress/variants/1'))
b = TraCIBridge(scene.meta.sumo_cfg, additional_files=[flow], vehicle_sample_rate=3)
b.start()
peak = 0
for _ in range(3600):
    b.step()
    peak = max(peak, len(b.get_state().vehicles))
print(f'vehicles 峰值(采样后): {peak}')
assert peak <= 500
b.close()
print('OK cap respected')
"`
Expected: `OK cap respected`

- [ ] **Step 4: 验证 1.5 倍流量下云端参数切换可见**

Run: `python -c "
import sys, logging; sys.path.insert(0, '.')
logging.basicConfig(level=logging.INFO)
from cloud.cloud_policy import CloudPolicy
from core.types import JointState, QueueState
p = CloudPolicy()
for step in range(0, 181, 60):
    load = 45.0 if step < 120 else 2.0  # 前 2 分钟高压，随后回落
    state = JointState(step=step, timestamp=float(step), tls_id='t',
                       current_phase=0, current_phase_name='p0', elapsed_phase_time=0.0,
                       queues=[QueueState(direction='E0', queue_length=load,
                                          waiting_time=0.0, vehicle_count=int(load),
                                          capacity=50.0)],
                       flows={'E0': load * 36})
    print(step, p.dispatch_params(state))
"`
Expected: 日志含 4 次 `云端下发参数`；step 0/60 为激进/中档（min_green>=15），step 120/180 回到常规档 min_green=10.0

---

### Task 16: 代码清理 + lint_check.sh + docstring 补全

**Files:**
- Modify: `engine/traci_bridge.py`、`engine/runner.py`、`engine/collector.py`、`engine/events.py`、`engine/edge_channel.py`、`cloud/cloud_policy.py`、`experiments/runner.py`（docstring 补全：参数/返回/异常）
- Create: `scripts/lint_check.sh`

**Interfaces:**
- Produces: `bash scripts/quality/lint_check.sh` 输出 `clean` 且 flake8 无 error

- [ ] **Step 1: 创建 scripts/lint_check.sh**

```bash
#!/usr/bin/env bash
# IB W5 清理检查：flake8 + 调试残留 + TODO 残留
set -e
cd "$(dirname "$0")/.."
python -m flake8 engine/ cloud/ experiments/ --max-line-length=100
git grep -nE "breakpoint\(\)|pdb\.set_trace" engine/ cloud/ experiments/ \
    && echo "FOUND DEBUG CODE" && exit 1 || true
git grep -nE "TODO|FIXME|XXX" engine/ cloud/ experiments/ \
    && echo "FOUND TODO" && exit 1 || true
echo "clean"
```

注：若环境无 flake8，先 `pip install flake8`（装到当前 Python 环境即可，属开发工具）。

- [ ] **Step 2: 跑 lint 并修掉所有 error**

Run: `bash scripts/quality/lint_check.sh`
Expected: `clean`；如有 flake8 error（行宽/未用 import 等）逐个修复后重跑

- [ ] **Step 3: docstring 抽查补全**

逐个文件确认：模块 docstring、每个公共类的 docstring 含 Args/Returns/Raises（有参数/返回/异常时）。重点：`TraCIBridge`（Raises: FileNotFoundError/RuntimeError）、`SimulationRunner.run`（Returns）、`CloudPolicy.dispatch_params`、`EdgeChannel`、`StepLogger`、`EventLogger`、`parse_args`/`run_single`。

验证: `python -m pydoc engine.traci_bridge.TraCIBridge` 输出完整文档

- [ ] **Step 4: 全量回归**

Run: `python -m pytest tests/ -q`
Expected: 63 passed

---

### Task 17: 文档定稿 + 最终验证矩阵

**Files:**
- Modify: `docs/interface.md`（新增字段/类/CLI 与消息流同步）
- Modify: `docs/deployment.md`（修正 `experiments/runner.py --help` 失效引用 → 真实可用的 CLI 说明）
- Create: `docs/w5_verification.md`
- Create: `docs/w6_review_issues.md`

**Interfaces:**
- Consumes: Task 1-16 全部产物

- [ ] **Step 1: 更新 docs/interface.md**

新增/修订小节（与实际代码逐条核对）：
- `QueueState.capacity`（float，默认 0.0，= 车道长/7.5m）
- `VehicleState` 与 `JointState.vehicles`（采样快照）、`JointState.arrival_history`（最近 300 步 departed 数）
- `TraCIBridge` 新参数：`seed / vehicle_sample_rate / max_restarts`；新方法 `get_lane_capacity`；属性 `lane_directions`；`step()` 断开返回 None 的语义
- `EdgeChannel`（send/receive/delay/filter）使用示例
- `CloudPolicy.dispatch_params` 压力三档表（>0.8 / >0.4 / 常规，各档 min/max/base_green）
- `SimulationRunner` 新参数：`seed / step_log_csv / events_csv`
- `experiments/runner.py` CLI 用法示例（含 --help 输出摘要）
- 输出文件表：快照 CSV / simulation_log.csv / events.csv 的列说明

- [ ] **Step 2: 修正 docs/deployment.md**

把"完整实验复现"一节中失效的 `python experiments/runner.py --help` 相关描述替换为真实 CLI：

```bash
# 单次实验（路口 1，CA-MP，1.5 倍流量，seed=42）
python experiments/runner.py --intersection 1 --algorithm ca_maxpressure \
    --flow-multiplier 1.5 --seed 42 --steps 3600 --output-dir output/exp1
```

并注明输出结构：`<output-dir>/csv/*.csv`（快照）、`<output-dir>/logs/*_simulation_log.csv`（每步）、`<output-dir>/logs/*_events.csv`（事件）、`<output-dir>/variants/`（流量变体）。

- [ ] **Step 3: 创建 docs/w5_verification.md（验证矩阵）**

| # | 任务 | 验证命令 | 结果 |
|---|------|----------|------|
| W1 | capacity/进口道/CA-MP 示例 | pytest tests/ + examples/run_ca_max_pressure.py 1 3600 | 按实际填写 |
| W2 | CLI 三参数/真 seed/分档/EdgeChannel/simulation_log | 各 Task 验证命令 | 按实际填写 |
| W3 | 断线韧性/events/日志审计 | taskkill 测试 + output/w3_audit | 按实际填写 |
| W4 | 采样/上限/arrival/压力实测 | scripts/stress_memory.py | 按实际填写 |
| W5 | lint/docstring/文档一致 | scripts/lint_check.sh | 按实际填写 |

- [ ] **Step 4: 创建 docs/w6_review_issues.md（模板 + 当前已知项）**

| # | 文件 | 问题 | 优先级 | 状态 |
|---|------|------|--------|------|
| 1 | algorithms/ca_max_pressure.py | MVI 桩 set_phase 值为方向字符串（非法相位索引），正式实现归 AB；IB 已在 bridge 容错跳过 | 高 | 待 AB 实现 |
| 2 | docker/Dockerfile | 镜像内 runner 一致性未实机验证（IA 交付，待回填） | 中 | 待验证 |
| 3 | experiments/metrics.py | throughput/travel_time 为占位（需 tripinfo 二次校准，EX 协同） | 中 | 待 EX |

- [ ] **Step 5: 最终全量回归 + 双算法实证**

Run: `python -m pytest tests/ -q && bash scripts/quality/lint_check.sh`
Expected: 63 passed + `clean`

Run: `python examples/run_fixed_time.py 1 && python examples/run_ca_max_pressure.py 1 3600`
Expected: 两者均 3600 步完成，退出码 0

---

## Self-Review 记录

- Spec 覆盖：spec 阶段 1→Task 1-4；阶段 2→Task 5-10（EdgeChannel=Task 9，simulation_log=Task 10，分档=Task 8）；阶段 3→Task 11/12/14；阶段 4→Task 13/15；阶段 5→Task 16/17。TraCI 订阅优化按 spec 明确不做。
- 已知取舍：`apply_actions` 容错（Task 4）是机制性兜底，CA-MP MVI 桩的相位值问题记入 w6_review_issues.md 归 AB。
- 类型一致性：`VehicleState`/`capacity`/`seed`/`vehicle_sample_rate`/`step_log_csv`/`events_csv`/`dispatch_params`/`PRESSURE_TIERS` 在各 Task 间签名一致。
