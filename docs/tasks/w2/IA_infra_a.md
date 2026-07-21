# 仿真基础设施 A（IA） W2 任务书

> 周期：7/27（周日）- 8/2（周六） | 核心目标：确保 20 路口在新版 SUMO 下稳定运行 3600 步，并协助实验组准备批量运行环境

## 每日任务

### Day 1（7/27 周日）— W1 迁移结果复查

- [ ] 重新运行 `scripts/validate_all.py`，复查 W1 迁移结果
- [ ] 对 W1 中标记为"有问题"的路口做最终修复
- [ ] 确保 20/20 路口在 3600 步内全部跑通（不再只是 100 步）
- [ ] 把 3600 步验证逻辑沉淀到 `scripts/batch_validate.py`（Day 3 完成）的早期版本

```bash
# 单路口 3600 步全量验证
sumo -c data/intersection_data/1/sumo工程/demo_1.sumocfg --no-step-log -e 3600
```

**验证：** 对 N=1..20 执行 `sumo -c data/intersection_data/N/sumo工程/demo_N.sumocfg --no-step-log -e 3600`，全部退出码为 0。

### Day 2（7/28 周一）— 增强版 sumocfg（不修改原始文件）

- [ ] 在 `engine/configs/` 下为每个路口生成增强版 `demo_N.sumocfg`，引用原始 `net.xml/rou.xml/flow.xml/turn.xml`
- [ ] 增加三类输出：`tripinfo-output`（EX 采集）、`fcd-output`（DB 时空轨迹图）、`summary-output`
- [ ] 更新 `engine/runner.py` 使用增强版 sumocfg（保持原始数据目录只读）
- [ ] 抽查路口 1、11、16 跑 100 步，确认三类输出文件都生成

```xml
<!-- engine/configs/demo_1.sumocfg -->
<configuration>
  <input>
    <net-file value="../../data/intersection_data/1/sumo工程/demo_1.net.xml"/>
    <route-files value="../../data/intersection_data/1/sumo工程/demo_1.rou.xml"/>
    <additional-files value="../../data/intersection_data/1/sumo工程/demo_1.flow.xml,../../data/intersection_data/1/sumo工程/demo_1.turn.xml"/>
  </input>
  <time>
    <step-length value="1.0"/>
  </time>
  <output>
    <tripinfo-output value="tripinfo.xml"/>
    <fcd-output value="traj.xml"/>
    <summary-output value="stats.xml"/>
  </output>
</configuration>
```

**验证：** `sumo -c engine/configs/demo_1.sumocfg --no-step-log -e 100 --output-prefix out/` 后 `ls out/` 包含 `tripinfo.xml`、`traj.xml`、`stats.xml` 三个文件。

### Day 3（7/29 周二）— 批量 3600 步验证脚本

- [ ] 编写 `scripts/batch_validate.py`：对 20 路口各跑 3600 步（无 GUI），使用 `engine/configs/` 下的增强版 cfg
- [ ] 记录每个路口：运行时间、完成车辆数（从 `tripinfo.xml` 行数）、是否有报错
- [ ] 输出汇总表（Markdown），并估算 360 次实验总时间
- [ ] 标记运行时间显著偏长的路口（多为 0.1s 步长的 11-13、15-20）

```python
# scripts/batch_validate.py
import subprocess, time
from pathlib import Path
from defusedxml import ElementTree as ET  # 禁用 DTD/外部实体，避免 XML 解析风险

CFG_DIR = Path("engine/configs")

def run_one(n: int, steps: int = 3600) -> dict:
    cfg = CFG_DIR / f"demo_{n}.sumocfg"
    out = Path(f"output/validate/{n}"); out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    r = subprocess.run(
        ["sumo", "-c", str(cfg), "--no-step-log", "-e", str(steps),
         "--output-prefix", str(out) + "/"],
        capture_output=True, text=True)
    tripinfo = out / "tripinfo.xml"
    finished = len(ET.parse(tripinfo).getroot()) if tripinfo.exists() else 0
    return {"id": n, "ok": r.returncode == 0,
            "elapsed": time.perf_counter() - t0, "finished": finished}

if __name__ == "__main__":
    rows = [run_one(n) for n in range(1, 21)]
    total = sum(r["elapsed"] for r in rows)
    for r in rows:
        print(f"路口 {r['id']:>2} {'PASS' if r['ok'] else 'FAIL'} "
              f"{r['elapsed']:6.1f}s finished={r['finished']}")
    print(f"20 路口合计 {total:.0f}s，估算 360 次实验 ≈ {total*18/3600:.1f}h")
```

**验证：** `python scripts/batch_validate.py` 输出 20 行 `路口 N PASS ...s finished=...` 且最后给出 360 次实验估算时长。

### Day 4（7/30 周三）— 协助 EX 调试 experiments/runner.py

- [ ] 确认 `--output-dir` 参数能正确输出 `tripinfo.xml` / `stats.xml` / `traj.xml`
- [ ] 确认 `--seed` 参数能改变 SUMO 随机种子（透传到 `--seed`）
- [ ] 确认 `--flow-multiplier` 参数能正确放大流量
- [ ] 在路口 1 上做一次完整"模拟实验"，验证输出文件完整

```bash
# 单次模拟实验（EX 侧入口）
python experiments/runner.py --intersection 1 --algo ca_maxpressure \
    --seed 42 --flow-multiplier 1.0 \
    --output-dir experiments/results/smoke_1
ls experiments/results/smoke_1   # 应包含 tripinfo.xml / stats.xml / traj.xml
```

**验证：** 上述命令退出码 0，`experiments/results/smoke_1/` 下三个 XML 文件齐全且非空；改用 `--seed 43` 重跑后 `tripinfo.xml` 内容不同。

### Day 5（7/31 周四）— 文档与元数据收尾

- [ ] 补全 `data/intersection_data/metadata/intersections.yaml`（如 W1 有遗漏）
- [ ] 更新 `docs/edge_mapping.md`（如 W1 有遗漏）
- [ ] 编写 `docs/sumo_env_setup.md`：SUMO 环境安装指南（Windows 安装步骤、环境变量配置、常见报错与解决）
- [ ] 该文档将作为 W4 部署文档的素材

```markdown
<!-- docs/sumo_env_setup.md 章节骨架 -->
## 1. Windows 安装
## 2. 环境变量（SUMO_HOME / PATH）
## 3. Python 接口（traci / libsumo）
## 4. 常见报错
   - "Could not find SUMO_HOME" → ...
   - net.xml schema 不兼容 → netconvert 重新生成
```

**验证：** `docs/sumo_env_setup.md` 存在且包含上述 4 个一级章节；按文档在一台干净 Windows 机器上能装出可用 SUMO。

### Day 6（8/1 周五）— 集成验证 + 第二台机器

- [ ] 协助 TL 做 W2 集成验证（算法 + 引擎 + 采集联调）
- [ ] 如有第二台机器，配置 SUMO 环境（为 W3 并行跑实验准备）
- [ ] 提交本周所有代码与文档给 TL

**验证：** TL 侧执行 W2 集成验证脚本通过；第二台机器 `sumo --version` 与主机一致。

### Day 7（8/2 周六）— Buffer + Docker 调研（W4 前置）

- [ ] 修复本周发现的问题
- [ ] 调研 Docker 中安装 SUMO 的方案：搜索 `sumo docker image`，确认是否有官方/社区镜像
- [ ] 记录基础镜像选择（默认 `ubuntu:22.04` + apt 安装 `sumo sumo-tools`）与备选方案
- [ ] 调研笔记落到 `docs/notes/docker_sumo_research.md`

**验证：** `docs/notes/docker_sumo_research.md` 存在，包含基础镜像结论与 apt 包名清单。

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| 20 路口 3600 步全通过 | 7/27 | `sumo -c ... -e 3600` 全部退出码 0 |
| `engine/configs/demo_{1-20}.sumocfg` | 7/28 | 含 tripinfo / fcd / summary 三类输出，引用原始数据 |
| `scripts/batch_validate.py` | 7/29 | 批量验证 + 运行时间统计 + 360 次实验估算 |
| `docs/sumo_env_setup.md` | 7/31 | 安装指南完整，外人可复现 |
| Docker 调研笔记 | 8/2 | 基础镜像确定（ubuntu:22.04） |

## 协作对接

- 与 **EX** 联调 `experiments/runner.py` 的 `--output-dir` / `--seed` / `--flow-multiplier` 参数。
- 与 **DB** 确认 `fcd-output (traj.xml)` 字段满足时空轨迹图需求。
- 与 **TL** 同步 W2 集成验证结果与第二台机器环境状态。
