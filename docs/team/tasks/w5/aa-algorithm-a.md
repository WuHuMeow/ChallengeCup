# 算法 A（AA） W5 任务书

> 周期：8/17（周日）- 8/23（周六） | 核心目标：基线算法代码最终清理、协助报告与 PPT 中算法部分

---

## 每日任务

### Day 1（8/17 周日）

**基线代码最终清理**

- [ ] 对 `fixed_time.py` / `rule_adaptive.py` 做最终 review
- [ ] 删除调试代码（临时 print、注释掉的实验逻辑），确认 docstring 完整
- [ ] 确认参数可配置（`min_green` / `max_green` / `queue_threshold` 来自 `config/default.yaml`）
- [ ] 提交给 TL

```python
# 清理后的 rule_adaptive.py 应保持简洁：
# - 模块 docstring 说明算法原理（排队延长/切换）
# - __init__ 参数从 get_config().get("algorithms.actuated", {}) 读取
# - step() 仅含核心三分支逻辑，无调试 print
```

**验证：** `pytest tests/unit/test_algorithms.py -q` → 全部 passed

### Day 2（8/18 周一）

**协助 DA 完善报告第三章"基线算法"**

- [ ] 提供感应控制的伪代码
- [ ] 提供参数选择依据（min_green=10 / max_green=60 / queue_threshold=5 的来源）
- [ ] 确认报告中的公式与描述准确
- [ ] Review DA 写的算法章节，纠正技术错误

```python
# 感应控制伪代码（供报告第三章）
# 每步：
#   if elapsed < min_green: 保持
#   elif max_queue > threshold and elapsed < max_green: 延长绿灯 +5s
#   else: 切换下一相位
```

**验证：** 人工 review，确认报告章节中感应控制描述与 `rule_adaptive.py` 实现一致

### Day 3（8/19 周二）

**协助 DA 完善 PPT 算法页（第 6-8 页）**

- [ ] 确认 MaxPressure 公式正确
- [ ] 确认感应控制描述准确
- [ ] 如 PPT 需要算法流程图素材，提供

```python
# PPT 算法页要点：
# - FixedTime：step() 返回 []，依赖 SUMO 默认配时
# - Actuated：基于排队长度的延长/切换三分支
# - CA-MP：基于压力差选相位 + CloudPolicy EWMA 调参
```

**验证：** 人工 review，确认 PPT 第 6-8 页公式与代码实现一致

### Day 4（8/20 周三）

**最终验证**

- [ ] 基线算法在 3 个代表性路口（如 1 / 11 / 16）上跑通
- [ ] 确认代码在 Docker 内也能运行
- [ ] 记录验证结果

```python
# 最终验证：3 代表路口
for iid in ["1", "11", "16"]:
    scene = SceneRegistry().get_scene(iid)
    SimulationRunner(scene, FixedTimeAlgorithm()).run(steps=3600)
    SimulationRunner(scene, RuleAdaptiveAlgorithm()).run(steps=3600)
```

**验证：** `python examples/run_fixed_time.py 1 && python examples/run_rule_adaptive.py 16` → 均输出 `仿真完成`

### Day 5（8/21 周四）

**协助 TL 最终 review + 答辩准备**

- [ ] 协助 TL 做最终 review
- [ ] 准备答辩可能被问到的基线问题：
  - "为什么选感应控制作为基线？"
  - "感应控制的参数怎么确定的？"
  - "Webster 公式你了解吗？"

```python
# 答辩口径要点：
# - 感应控制是经典自适应基线，比固定配时"聪明"但非全局最优，正好衬托 CA-MP
# - 参数来自 config/default.yaml（min_green=10/max_green=60/queue_threshold=5）
# - Webster：C0=(1.5L+5)/(1-Y)，因时间未实现，两基线已足够对比
```

**验证：** 人工准备，3 个问题各有明确答案

### Day 6（8/22 周五）

**Buffer / 协助**

- [ ] Buffer：处理遗留问题
- [ ] 协助其他组

```python
# 提交前自检
# pytest tests/ -q
```

**验证：** `pytest tests/ -q` → 全部 passed

### Day 7（8/23 周六）

**Buffer**

- [ ] Buffer：处理任何遗留问题
- [ ] 待命支援答辩材料

```python
# 待命，无强制代码改动
```

**验证：** 无强制验证（buffer 日）

---

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | 基线代码清理完成 | 8/17 | 无调试代码 |
| 2 | 报告算法章节 review | 8/18 | 技术准确 |
| 3 | PPT 算法页 review | 8/19 | 公式正确 |
| 4 | 最终验证通过 | 8/20 | 3 路口可运行 |

## 协作对接

- 与 **DA** 对接报告第三章与 PPT 算法页的技术准确性。
- 与 **TL** 对接最终 review。
- 与 **AB** 对齐答辩中算法部分的口径。
