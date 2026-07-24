# 算法 A（AA） W6 任务书

> 周期：8/24（周日）- 8/31（周六） | 核心目标：基线代码最终确认、答辩准备

---

## 每日任务

### Day 1（8/24 周日）

**全员 review 会议**

- [ ] 参加全员 review 会议
- [ ] 记录与基线算法相关的修改意见
- [ ] 评估每条意见的改动成本

```python
# 会议记录关注点：
# - fixed_time.py / rule_adaptive.py 是否需要调整
# - 答辩中基线相关问题的口径是否统一
```

**验证：** 人工记录，形成修改意见清单

### Day 2（8/25 周一）

**修复 review 问题 + 最终确认**

- [ ] 修复 review 中发现的问题（如有）
- [ ] 最终确认：`fixed_time.py` / `rule_adaptive.py` 代码干净、docstring 完整
- [ ] 跑一遍接口契约测试确认无回归

```python
# 最终确认检查点：
# - 模块/类/方法 docstring 完整
# - 无调试 print、无注释掉的死代码
# - 参数从 config/default.yaml 读取
```

**验证：** `pytest tests/unit/test_algorithms.py -q` → 全部 passed

### Day 3（8/26 周二）

**最终验证（路口 16 + Docker）**

- [ ] 基线算法在路口 16（5 进口道）上跑通
- [ ] 确认代码在 Docker 内可运行
- [ ] 记录验证结果

```python
# 路口 16 最终验证（5 进口道，相位取模逻辑需正确）
scene = SceneRegistry().get_scene("16")
SimulationRunner(scene, FixedTimeAlgorithm()).run(steps=3600)
SimulationRunner(scene, RuleAdaptiveAlgorithm()).run(steps=3600)
```

**验证：** `python examples/run_fixed_time.py 16 && python examples/run_rule_adaptive.py 16` → 均输出 `仿真完成`

### Day 4（8/27 周三）

**协助 TL 最终集成验证**

- [ ] 协助 TL 做最终集成验证
- [ ] 确认无遗留 bug
- [ ] 确认三种算法在 `experiments/runner.py` 中均可调度

```python
# 最终集成验证：三种算法在 ALGORITHM_MAP 中均可用
# fixed_time / actuated / ca_maxpressure
# pytest tests/integration/test_experiments.py -q
```

**验证：** `pytest tests/integration/test_experiments.py -q` → 全部 passed

### Day 5（8/28 周四）

**答辩 Q&A 准备**

- [ ] 准备答辩 Q&A：
  - "感应控制的参数怎么调的？"
  - "固定配时方案从哪来的？"
  - "为什么不做 Webster 基线？"（答：时间不够，两个基线已足够对比）
- [ ] 与 AB 对齐答辩口径

```python
# 答辩口径：
# - 感应控制参数来自 config/default.yaml（min_green=10/max_green=60/queue_threshold=5）
# - 固定配时来自 SUMO net.xml 默认程序，可选 Excel 配时（use_excel_timing）
# - Webster 因时间未实现，两基线已足够支撑对比
```

**验证：** 人工准备，3 个问题各有明确答案，与 AB 口径一致

### Day 6（8/29 周五）

**模拟答辩**

- [ ] 参加模拟答辩
- [ ] 记录回答不好的问题，补充准备

```python
# 模拟答辩后补充：
# - 记录被问倒的问题
# - 复核基线算法相关数据与公式
```

**验证：** 人工参与，全程在场

### Day 7（8/30-8/31）

**协助最终提交**

- [ ] 协助最终提交
- [ ] Buffer：处理任何遗留问题

```python
# 最终提交前自检
# pytest tests/ -q  # 全量回归确认无回归
```

**验证：** `pytest tests/ -q` → 全部 passed

---

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | 基线代码最终确认 | 8/25 | 干净、完整 |
| 2 | 答辩 Q&A 准备 | 8/28 | 3 个问题有答案 |
| 3 | 模拟答辩参与 | 8/29 | 全程参与 |

## 协作对接

- 与 **TL** 对接最终集成验证。
- 与 **AB** 对齐答辩口径。
- 配合全员完成最终提交。
