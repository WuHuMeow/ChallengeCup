# 仿真基础设施 B（IB） W5 任务书

> 周期：8/17（周日）- 8/23（周六） | 核心目标：代码最终清理、接口文档定稿、协助交付物准备

## 每日任务

### Day 1（8/17 周日）

- [ ] 对 `engine/traci_bridge.py` / `engine/runner.py` / `cloud/cloud_policy.py` 做最终 review
- [ ] 删除所有调试代码（临时 `print`、注释掉的旧实现、`breakpoint()`）
- [ ] 确认异常处理完整：TraCI 断开、文件不存在、参数非法等场景都有清晰报错
- [ ] 确认所有模块、类、公共方法的 docstring 完整（参数、返回、异常）

```python
# 清理检查清单（自查脚本）
# scripts/lint_check.sh
python -m flake8 engine/ cloud/ experiments/ --max-line-length=100
git grep -nE "breakpoint\(\)|pdb\.set_trace|^\s*print\(" engine/ cloud/ \
    && echo "FOUND DEBUG CODE" || echo "clean"
```

**验证：** `bash scripts/lint_check.sh` 输出 `clean`，flake8 无 error。

### Day 2（8/18 周一）

- [ ] 定稿 `docs/interface.md`：核对消息流图（云 → 边 → 端）与实际代码一致
- [ ] 确认每个数据类（`JointState / ControlAction / SimulationMetrics / QueueState`）字段说明完整
- [ ] 为每个核心类添加使用示例代码片段（`TraCIBridge` / `SimulationRunner` / `CloudPolicy`）
- [ ] 这是 PDF 评分"设计文档规范性（5 分）"的关键材料，必须图文一致

```markdown
<!-- docs/interface.md 片段示例 -->
## 消息流
```
[SUMO] --get_state()--> [TraCIBridge] --JointState--> [Algorithm]
                                                        |
                                          List[ControlAction]
                                                        v
[SUMO] <--apply_actions()-- [TraCIBridge] <-------------+
                                ^
                                | 每 60 步下发参数
                          [CloudPolicy]
```
```

**验证：** 让 TL 或 IA 对照 `docs/interface.md` 检查代码，无"文档与实现不符"的反馈。

### Day 3（8/19 周二）

- [ ] 协助 DB 录制视频：用 `simulation_log.csv` 生成"云-边-端消息流"动画数据（按 step 切片）
- [ ] 提供消息流动画所需的中间数据格式（JSON 序列：每帧含 step / phase / queues / cloud_params）
- [ ] 协助 DA：补充报告"系统实现"章节中关于仿真封装、消息流的描述
- [ ] 与 DB 确认动画数据帧率与字段满足视频需求

```python
# scripts/export_message_flow.py
import csv, json
rows = list(csv.DictReader(open("output/run1/simulation_log.csv")))
frames = [{"step": int(r["step"]), "phase": int(r["phase"]),
           "queues": {k: float(v) for k, v in r.items() if k.startswith("queue_")}}
          for r in rows]
json.dump(frames, open("output/run1/message_flow.json", "w"))
print(f"exported {len(frames)} frames")
```

**验证：** `python scripts/export_message_flow.py` 输出 `exported N frames`，`message_flow.json` 可被 DB 的动画脚本读取。

### Day 4（8/20 周三）

- [ ] 最终功能验证：三种算法在路口 1、11、16 上各跑一次（共 9 组）
- [ ] 确认每组输出完整（tripinfo / stats / traj / simulation_log / events），无报错
- [ ] 确认 Docker 内行为与本地一致（同 seed 输出相同）
- [ ] 把 9 组验证结果记录到 `docs/w5_verification.md`

```bash
# 最终功能验证脚本
for algo in fixed_time rule_adaptive ca_mp; do
  for iid in 1 11 16; do
    python experiments/runner.py --algorithm $algo --intersection $iid \
        --steps 1800 --seed 42 --output-dir output/final_${algo}_${iid} \
        || echo "FAIL: $algo @ $iid"
  done
done
ls output/final_*/stats.xml | wc -l   # 期望: 9
```

**验证：** 上述循环无 `FAIL` 输出；`stats.xml` 计数为 9。

### Day 5（8/21 周四）

- [ ] 编写 `README.md` 最终版：项目简介、目录结构说明、快速开始（3 步）、团队信息
- [ ] 快速开始必须能在 3 条命令内跑通一个路口
- [ ] 目录结构说明覆盖 `engine/ / cloud/ / algorithms/ / experiments/ / data/ / docs/`
- [ ] 提交给 TL 审阅

```markdown
<!-- README.md 快速开始示例 -->
## 快速开始
```bash
pip install -r requirements.txt          # 1. 安装依赖
export SUMO_HOME=/path/to/sumo           # 2. 配置 SUMO
python experiments/runner.py --intersection 1 --steps 600 --output-dir output/demo  # 3. 运行
```
```

**验证：** 按 README 快速开始 3 步执行，`output/demo/` 下生成完整输出文件。

### Day 6（8/22 周五）

- [ ] 协助 TL 做最终集成验证
- [ ] 确认代码可复现：全新 clone + 按 README/deployment.md 跑通
- [ ] 修复集成验证暴露的最后问题
- [ ] 提交代码给 TL

```bash
git clone <repo> /tmp/final && cd /tmp/final
pip install -r requirements.txt
python experiments/runner.py --intersection 1 --steps 600 --output-dir output/repro
```

**验证：** 上述命令链全部退出码 0，输出完整。

### Day 7（8/23 周六）

- [ ] Buffer：处理 W5 遗留问题
- [ ] 整理本周验证记录与文档定稿状态，归档到 `docs/w5_summary.md`
- [ ] 准备 W6 最终提交清单

```bash
git status
git log --oneline -10
```

**验证：** `git status` 干净，本周提交完整。

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| 代码清理完成 | 8/17 | 无调试代码、无 TODO，docstring 完整 |
| `docs/interface.md` 定稿 | 8/18 | 消息流图与数据类字段说明完整、与代码一致 |
| 功能验证通过 | 8/20 | 3 路口 × 3 算法共 9 组无报错，Docker 一致 |
| `README.md` 最终版 | 8/21 | 含项目简介、目录结构、3 步快速开始、团队信息 |

## 协作对接

- 与 **DB** 配合视频录制，提供消息流动画数据；与 **DA** 配合报告"系统实现"章节。
- 与 **TL** 配合最终集成验证与 README 审阅。
