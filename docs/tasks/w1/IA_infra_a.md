# 仿真基础设施 A（IA） W1 任务书

> 周期：7/20（周日）- 7/26（周六） | 核心目标：将 20 个路口全部迁移到统一 SUMO 版本，确保可运行

## 本周背景

主办方提供的 20 个路口（位于 `data/intersection_data/{1-20}/sumo工程/`）使用了至少 5 个 SUMO 版本（1.13.0 / 1.18.0 / 1.23.1 / 1.26.0 / 1.27.1），步长分两档：路口 1-10、14 为 1s，路口 11-13、15-20 为 0.1s。本周需要统一到新版 SUMO（建议 1.26.0 或 1.27.1），让所有路口能用同一套环境跑通。

`scenes/registry.py` 中的 `SceneRegistry` 会自动扫描 `data/intersection_data/` 下的数字目录并构建 `SceneMeta`，迁移完成后用它做端到端校验最方便。

## 每日任务

### Day 1（7/20 周日）— 环境搭建 + 单路口验证

- [ ] 安装 SUMO 最新版（推荐 1.27.1），Windows 从 https://sumo.dlr.de/docs/Downloads.html 下载安装包
- [ ] 设置环境变量 `SUMO_HOME=C:\Program Files\Eclipse\Sumo`（或实际安装路径），并将 `%SUMO_HOME%\bin` 加入 PATH
- [ ] 验证 Python 接口可用（`traci` / `libsumo`）
- [ ] 用 SUMO-GUI 打开路口 1，能正常运行则记为"兼容"，否则记录错误信息
- [ ] 在 `docs/` 下创建 `migration_log.md` 迁移记录表

```markdown
<!-- docs/migration_log.md -->
| 路口 | 原始版本 | 步长 | 迁移状态 | 问题记录 |
|------|----------|------|----------|----------|
| 1    | 1.18.0   | 1s   | 待验证   |          |
| 2    | ?        | ?    | 待验证   |          |
| ...  |          |      |          |          |
```

**验证：** `sumo --version` 输出 `Eclipse SUMO sumo Version 1.27.1`；`python -c "import traci; print(traci.__version__)"` 输出版本号；`sumo-gui -c data/intersection_data/1/sumo工程/demo_1.sumocfg` 能正常加载并播放。

### Day 2（7/21 周一）— 批量验证脚本（不修改文件）

- [ ] 编写 `scripts/validate_all.py`，遍历 `data/intersection_data/{1-20}/sumo工程/demo_N.sumocfg`
- [ ] 对每个路口执行 `sumo -c demo_N.sumocfg --no-step-log -e 100`，记录成功/失败、错误信息、运行时间
- [ ] 输出汇总表（控制台 + 写入 `docs/migration_log.md`）
- [ ] 根据运行结果回填每个路口的"原始版本"列（从 `.net.xml` 头部 `<net version="...">` 提取）

```python
# scripts/validate_all.py
import subprocess, time, re
from pathlib import Path

ROOT = Path("data/intersection_data")

def detect_version(net_xml: Path) -> str:
    m = re.search(r'<net[^>]*version="([^"]+)"', net_xml.read_text(encoding="utf-8"))
    return m.group(1) if m else "?"

def validate(n: int) -> dict:
    cfg = ROOT / str(n) / "sumo工程" / f"demo_{n}.sumocfg"
    t0 = time.perf_counter()
    r = subprocess.run(
        ["sumo", "-c", str(cfg), "--no-step-log", "-e", "100"],
        capture_output=True, text=True,
    )
    return {"id": n, "ok": r.returncode == 0,
            "elapsed": time.perf_counter() - t0,
            "err": r.stderr.strip()[:200],
            "version": detect_version(cfg.parent / f"demo_{n}.net.xml")}

if __name__ == "__main__":
    for n in range(1, 21):
        res = validate(n)
        print(f"[{ 'PASS' if res['ok'] else 'FAIL' }] 路口 {n:>2} "
              f"ver={res['version']:<8} {res['elapsed']:.2f}s {res['err']}")
```

**验证：** `python scripts/validate_all.py` 输出 20 行 `[PASS|FAIL] 路口 N ver=... Xs`，预期大部分 PASS；将结果同步到 `docs/migration_log.md`。

### Day 3（7/22 周二）— 处理不兼容路口

- [ ] 对报错路口分类：XML schema 变化 / 缺文件 / 已废弃属性
- [ ] XML schema 问题用 `netconvert -s old.net.xml -o new.net.xml` 重新生成
- [ ] **不修改 `data/intersection_data/` 原始文件**——修复方案与 TL 确认（在原目录覆盖 vs 在 `engine/configs/` 另建）
- [ ] 每修复一个路口立即跑 `validate_all.py` 中该路口子集回归

```bash
# 用新版 netconvert 重新生成路网（修复旧版本 schema）
netconvert -s data/intersection_data/N/sumo工程/demo_N.net.xml \
           -o data/intersection_data/N/sumo工程/demo_N.net.xml.new

# 单路口回归（无 GUI，跑 100 步）
sumo -c data/intersection_data/N/sumo工程/demo_N.sumocfg --no-step-log -e 100
```

**验证：** 对每个修复后的路口执行 `sumo -c ...demo_N.sumocfg --no-step-log -e 100`，退出码为 0 且 stderr 无 `Error:` 行。

### Day 4（7/23 周三）— 步长差异 + metadata 补全

- [ ] 确认步长分布：路口 1-10、14 为 1s；路口 11-13、15-20 为 0.1s（**不统一步长**，算法按仿真步调用即可）
- [ ] 在 `data/intersection_data/metadata/intersections.yaml` 中补全 20 个路口的 `timestep_s` / `sumo_versions`（统一后版本）/ `flow_count` / `has_queues` / `edge_naming`
- [ ] 写一个一次性脚本从 `.sumocfg` 的 `<step-length>` 与 `.rou.xml` 的 vehicle 数自动提取，避免手填出错

```yaml
# data/intersection_data/metadata/intersections.yaml
intersections:
  "1":
    timestep_s: 1.0
    sumo_versions: ["1.27.1"]
    flow_count: 1234
    has_queues: true
    edge_naming: "E0/-E1/-E2/-E3"
  "11":
    timestep_s: 0.1
    sumo_versions: ["1.27.1"]
    flow_count: 2048
    has_queues: true
    edge_naming: "W_car/E_car/S_car/N_car"
  # ... 共 20 条
```

**验证：** `python -c "import yaml; d=yaml.safe_load(open('data/intersection_data/metadata/intersections.yaml',encoding='utf-8')); print(len(d['intersections']))"` 输出 `20`。

### Day 5（7/24 周四）— 边命名标准化文档

- [ ] 编写 `docs/edge_mapping.md`，记录每个路口的边 ID → 方向（东/西/南/北）映射
- [ ] 覆盖典型差异：路口 1（`E0/-E1/-E2/-E3`）、路口 11（`W_car/E_car/S_car/N_car`）、路口 16（含 `-E5`，5 进口道）
- [ ] 字段：边 ID、方向、类型（进口/出口）、车道数、长度（从 `.net.xml` 提取）
- [ ] 该映射表后续算法组（AA/AB）计算压力时直接使用

```markdown
<!-- docs/edge_mapping.md -->
## 路口 1
| 边 ID | 方向   | 类型 | 车道数 | 长度(m) |
|-------|--------|------|--------|---------|
| -E1   | 西进口 | 进口 | 2      | 76.92   |
| E1    | 东出口 | 出口 | 2      | 76.92   |
| -E2   | 南进口 | 进口 | 3      | 101.28  |
```

**验证：** `docs/edge_mapping.md` 包含 20 个 `## 路口 N` 小节；`grep -c "^## 路口" docs/edge_mapping.md` 输出 `20`。

### Day 6（7/25 周五）— 全量验证 + 提交

- [ ] 再次运行 `scripts/validate_all.py`，目标 20/20 PASS
- [ ] 用 `SceneRegistry` 端到端校验：能列出 20 个 scene
- [ ] 将迁移结果（migration_log + edge_mapping + intersections.yaml）提交给 TL
- [ ] 仍失败的路口记录原因并告知 TL（备选方案：跳过该路口或用原始版本单独跑）

```python
# 端到端校验
from scenes.registry import SceneRegistry
reg = SceneRegistry()
scenes = reg.list_scenes()
assert len(scenes) == 20, f"期望 20 个路口，实际 {len(scenes)}"
print([s.intersection_id for s in scenes])
```

**验证：** `python scripts/validate_all.py | grep -c PASS` 输出 `20`；上述 `SceneRegistry` 脚本无 AssertionError。

### Day 7（7/26 周六）— Buffer / 协助

- [ ] 协助 IB 调试 TraCIBridge（IB 需要调用你验证过的路口）
- [ ] 若 W1 任务提前完成，开始编写 `scripts/migrate.py`（自动化迁移脚本，供报告使用）
- [ ] 整理本周遗留问题清单同步到 TL

**验证：** `python -c "from engine.traci_bridge import TraCIBridge; print('ok')"` 输出 `ok`（IB 侧导入不报错）。

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| SUMO 环境 | 7/20 | `sumo --version` 输出 1.27.1，`SUMO_HOME` 已设置 |
| `docs/migration_log.md` | 7/21 | 20 路口原始版本/步长/迁移状态完整 |
| `scripts/validate_all.py` | 7/21 | 能批量验证 20 路口，输出 PASS/FAIL 汇总 |
| `data/intersection_data/metadata/intersections.yaml` | 7/23 | 20 路口信息完整（5 个字段齐全） |
| `docs/edge_mapping.md` | 7/24 | 20 路口边-方向映射表 |
| 20 路口可运行 | 7/25 | `validate_all.py` 输出 20/20 PASS |

## 协作对接

- 与 **TL** 确认不兼容路口的修复策略（原目录覆盖 vs `engine/configs/` 另建）；每日同步 `migration_log.md`。
- 与 **IB** 对接 TraCIBridge 调试，提供已验证可跑的路口清单。
- 向 **AA/AB** 交付 `docs/edge_mapping.md`，作为压力计算的方向映射依据。

## 注意事项

- **不修改原始数据**——如需修复，先与 TL 确认方案。
- 优先保证路口 1、11、16 能跑（重点路口）。
- 遇到 SUMO 版本兼容问题，先查 https://sumo.dlr.de/docs/ChangeLog.html。
