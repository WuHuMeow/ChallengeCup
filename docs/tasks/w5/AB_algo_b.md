# 算法 B（AB） W5 任务书

> 周期：8/17（周日）- 8/23（周六） | 核心目标：CA-MP 代码最终清理、协助报告和 PPT 中创新点部分

## 每日任务

### Day 1（8/17 周日）

- [ ] CA-MP + EWMA 代码最终清理：`ca_max_pressure.py` / `ewma_predictor.py` 最终 review
- [ ] 删除调试代码、确认 docstring 完整
- [ ] 确认所有参数可通过 CloudPolicy 调整，提交给 TL

```python
# 清理后 ca_max_pressure.py 的参数应全部来自配置（无硬编码）
cfg = get_config().get("algorithms.ca_maxpressure", {})
self.overflow_threshold = cfg.get("overflow_occupancy_threshold", 0.9)
self.base_green = cfg.get("base_green", 30)
```

**验证：** `grep -rn "print(" algorithms/ca_max_pressure.py` 无调试输出，`python -m pytest tests/ -q` 全绿。

### Day 2（8/18 周一）

- [ ] 协助 DA 完善报告第三章"CA-MP 算法"：提供容量归一化公式和推导、溢出门控伪代码、EWMA 公式和参数选择依据、算法整体流程图
- [ ] Review DA 写的创新点章节，确保技术准确

```text
改进1 容量归一化:  pressure = queue / capacity
改进2 溢出门控:    if occupancy > 0.9: 强制放行该方向
改进3 动态绿灯:    duration = base_green × (phase_pressure / avg_pressure)
```

**验证：** 报告第三章创新点公式与 `ca_max_pressure.py` 实现逐条核对一致。

### Day 3（8/19 周二）

- [ ] 协助 DA 完善 PPT 创新点页（第 7-8 页、第 18 页）：确认三个创新点描述精准、提供"改进前 vs 改进后"对比示意
- [ ] 为视频"方案概述"段落提供算法动画素材（流程图/伪代码）

```text
改进前: pressure = queue_up − queue_down   （忽视车道容量）
改进后: pressure = queue / capacity        （短车道自动高优先级）
```

**验证：** PPT 创新点页三个改进点描述与代码实现一致，DA 确认无误。

### Day 4（8/20 周三）

- [ ] 最终验证：CA-MP（含 EWMA）在路口 1、11、16 上跑通
- [ ] 确认溢出门控在路口 16 触发
- [ ] 确认 Docker 内行为一致

```bash
for id in 1 11 16; do python examples/run_demo.py $id ca_maxpressure --sumo; done
```

**验证：** 路口 1 / 11 / 16 三路口均跑通 3600 步，路口 16 日志出现 `overflow gating`，Docker 内结果一致。

### Day 5（8/21 周四）

- [ ] 准备答辩创新点问题：容量归一化的理论依据？溢出门控阈值 0.9 怎么确定？EWMA 和 LSTM 比有什么优势？MaxPressure 的稳定性证明你了解吗？为什么不用强化学习？
- [ ] 每个问题准备 2-3 句话简洁回答

```text
阈值 0.9：参数敏感性实验（0.8/0.85/0.9/0.95）中 0.9 综合最优
EWMA vs LSTM：轻量、无需训练、3 行代码、适合边缘部署
```

**验证：** 5 个常见问题各有 2-3 句话答案，可与 TL/DA 模拟问答通过。

### Day 6（8/22 周五）

- [ ] Buffer：处理遗留问题
- [ ] 协助 TL 做最终 review

```bash
python -m pytest tests/ -q
```

**验证：** `python -m pytest tests/ -q` 全绿，TL review 无阻塞性问题。

### Day 7（8/23 周六）

- [ ] Buffer

**验证：** 无新增缺陷，待提交状态稳定。

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | CA-MP 代码清理完成 | 8/17 | 无调试代码，docstring 完整 |
| 2 | 报告创新点章节 review | 8/18 | 技术准确 |
| 3 | PPT 创新点页 review | 8/19 | 描述精准 |
| 4 | 最终验证通过 | 8/20 | 路口 1/11/16 可运行，Docker 一致 |
| 5 | 答辩 Q&A 准备 | 8/21 | 5 个常见问题有答案 |

## 协作对接

- 与 **DA** 对接报告第三章与 PPT 创新点页的技术准确性。
- 与 **DB** 对接视频"方案概述"算法动画素材。
- 与 **TL** 完成最终 review 与答辩 Q&A 演练。
