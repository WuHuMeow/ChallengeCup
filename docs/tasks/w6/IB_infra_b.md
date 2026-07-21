# 仿真基础设施 B（IB） W6 任务书

> 周期：8/24（周日）- 8/31（周六） | 核心目标：代码最终确认、接口文档定稿、协助最终提交与答辩

## 每日任务

### Day 1（8/24 周日）

- [ ] 参加全员 review 会议，记录与代码/接口相关的修改意见
- [ ] 把修改意见整理为 issue 清单（按文件分组：engine / cloud / docs）
- [ ] 评估每条意见的影响范围与修复优先级
- [ ] 与 TL 确认本周修复计划

```markdown
<!-- docs/w6_review_issues.md 模板 -->
| # | 文件 | 问题 | 优先级 | 状态 |
|---|------|------|--------|------|
| 1 | engine/traci_bridge.py | docstring 缺少异常说明 | 高 | 待修 |
| 2 | docs/interface.md | 消息流图与代码不一致 | 高 | 待修 |
```

**验证：** `docs/w6_review_issues.md` 已建立，所有 review 意见均有对应条目。

### Day 2（8/25 周一）

- [ ] 修复 review 中发现的代码问题（按优先级逐条处理）
- [ ] 最终确认：所有模块 docstring 完整、无 `TODO` / `FIXME` 注释残留
- [ ] 确认 `docs/interface.md` 与实际代码一致（字段、消息流图）
- [ ] 把 w6_review_issues.md 中所有条目标记为已修

```bash
# 最终静态检查
git grep -nE "TODO|FIXME|XXX" engine/ cloud/ experiments/ \
    && echo "FOUND TODO" || echo "no todo"
python -m flake8 engine/ cloud/ experiments/ --max-line-length=100
```

**验证：** `git grep` 输出 `no todo`；flake8 无 error。

### Day 3（8/26 周二）

- [ ] 最终功能验证：三种算法在路口 16 上各跑一次
- [ ] 确认输出完整（tripinfo / stats / traj / simulation_log / events），日志正确
- [ ] 确认 `experiments/runner.py --help` 输出清晰、参数说明完整
- [ ] 记录验证结果到 `docs/w6_final_verification.md`

```bash
for algo in fixed_time rule_adaptive ca_mp; do
  python experiments/runner.py --algorithm $algo --intersection 16 \
      --steps 1800 --seed 42 --output-dir output/w6_${algo}_16 \
      || echo "FAIL: $algo"
done
python experiments/runner.py --help
```

**验证：** 上述循环无 `FAIL`；`--help` 列出所有参数及说明。

### Day 4（8/27 周三）

- [ ] 协助 TL 做最终集成验证
- [ ] 确认 `README.md` 中的快速开始命令在全新环境可执行
- [ ] 确认 `docs/deployment.md` 中所有命令均可复现
- [ ] 修复最后发现的问题

```bash
# README 快速开始复现验证
git clone <repo> /tmp/final-check && cd /tmp/final-check
pip install -r requirements.txt
export SUMO_HOME=/path/to/sumo
python experiments/runner.py --intersection 1 --steps 600 --output-dir output/demo
```

**验证：** 上述命令链全部退出码 0，`output/demo/` 含完整输出文件。

### Day 5（8/28 周四）

- [ ] 准备代码仓库最终状态：确认所有文件已提交、分支干净
- [ ] 确认 tag `v1.0-final` 正确打在最终提交上
- [ ] 如需导出代码 zip，按主办方要求剔除大文件（data/ 原始数据按需保留）
- [ ] 与 TL 确认提交清单完整

```bash
git status                              # 期望: working tree clean
git tag -l "v1.0*"                      # 确认 tag 存在
git log --oneline -1 v1.0-final         # 确认 tag 指向最终提交
```

**验证：** `git status` 干净；`git tag -l` 含 `v1.0-final`；tag 指向最新提交。

### Day 6（8/29 周五）

- [ ] 参加模拟答辩，准备可能被问到的系统问题
- [ ] 准备问答要点："云-边-端通信延迟怎么模拟的？"（EdgeChannel 延迟队列）
- [ ] 准备问答要点："算法接口怎么做到标准化的？"（BaseControlAlgorithm + JointState/ControlAction）
- [ ] 准备问答要点："系统稳定性怎么保证的？"（TraCI 异常处理、可复现 seed、Docker 一致性）

```markdown
<!-- docs/w6_qa_prep.md 要点示例 -->
- 通信延迟：EdgeChannel 用 deque(maxlen=delay+1) 实现 1 步延迟
- 接口标准化：所有算法继承 BaseControlAlgorithm，输入 JointState、输出 List[ControlAction]
- 稳定性：FatalTraCIError 捕获 + try/finally 保证 close、seed 可复现
```

**验证：** `docs/w6_qa_prep.md` 完成，三个核心问题均有 1-2 句精炼回答。

### Day 7（8/30-8/31）

- [ ] 协助 TL 完成最终提交（仓库 / zip / 文档）
- [ ] Buffer：处理任何遗留问题
- [ ] 归档本周所有验证记录与 review 修复清单

```bash
git log --oneline -20                   # 回顾全程提交
git status                              # 最终确认干净
```

**验证：** `git status` 干净，提交历史完整可追溯。

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| 代码最终确认 | 8/25 | 无 TODO、无调试代码，docstring 完整 |
| 功能验证通过 | 8/26 | 路口 16 三算法可运行，输出完整 |
| 仓库最终状态 | 8/28 | 工作区干净、tag v1.0-final 正确 |

## 协作对接

- 与 **TL** 配合最终集成验证、tag 打点与提交清单确认。
- 与 **DA/DB** 配合答辩材料：提供系统稳定性、接口标准化、通信延迟的技术问答要点。
