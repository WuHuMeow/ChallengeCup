# 算法 B（AB） W6 任务书

> 周期：8/24（周日）- 8/31（周六） | 核心目标：CA-MP 代码最终确认、答辩主力准备

## 每日任务

### Day 1（8/24 周日）

- [ ] 参加全员 review 会议
- [ ] 记录与 CA-MP/EWMA 相关的修改意见

```bash
python -m pytest tests/ -q   # review 前确认当前基线全绿
```

**验证：** 形成 CA-MP/EWMA 相关修改意见清单（无遗漏项）。

### Day 2（8/25 周一）

- [ ] 修复 review 中发现的问题（如有）
- [ ] 最终确认：`ca_max_pressure.py` / `ewma_predictor.py` 代码干净
- [ ] 确认所有参数默认值合理

```yaml
# config/default.yaml 默认值最终核对
algorithms:
  ca_maxpressure:
    overflow_occupancy_threshold: 0.9
    base_green: 30
    min_green: 10
    max_green: 90
    ewma_alpha: 0.3
    prediction_horizon: 300
```

**验证：** `python -m pytest tests/ -q` 全绿，配置默认值与代码读取一致。

### Day 3（8/26 周二）

- [ ] 最终验证：CA-MP（含 EWMA）在路口 16 上跑通
- [ ] 确认溢出门控触发、EWMA 预测工作
- [ ] 确认 Docker 内可运行

```bash
python examples/run_demo.py 16 ca_maxpressure --sumo
```

**验证：** 路口 16 跑通 3600 步，日志出现 `overflow gating`，EWMA 预测生效，Docker 内可运行。

### Day 4（8/27 周三）

- [ ] 协助 TL 做最终集成验证
- [ ] 确认无遗留 bug

```bash
python -m pytest tests/ -q
```

**验证：** 全量测试通过，TL 确认无遗留 bug。

### Day 5（8/28 周四）

- [ ] 答辩主力准备（算法核心，答辩中算法问题主要由你回答）：MaxPressure 理论基础？容量归一化创新在哪？溢出门控阈值怎么确定？EWMA 为什么不用 LSTM？与强化学习比有什么优势？云-边-端怎么体现？
- [ ] 每个问题准备 2-3 句话精简回答

```text
MaxPressure：Varaiya 2013，对任意网络吞吐量最优
容量归一化：解决窄路短车道被忽视的问题
云-边-端：边缘=本地压力计算，云端=参数下发（CloudPolicy）
```

**验证：** 6 个问题各有 2-3 句话精简答案，可流畅作答。

### Day 6（8/29 周五）

- [ ] 参加模拟答辩（主讲算法部分）
- [ ] 记录回答不好的问题，补充

```bash
python examples/run_demo.py 16 ca_maxpressure   # 演示链路备用
```

**验证：** 模拟答辩算法部分主讲流畅，薄弱问题已补充答案。

### Day 7（8/30-8/31）

- [ ] 协助最终提交
- [ ] Buffer

**验证：** 最终提交完成，代码与文档状态稳定。

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | CA-MP 代码最终确认 | 8/25 | 干净、完整，默认值合理 |
| 2 | 答辩 Q&A 准备 | 8/28 | 6 个问题有答案 |
| 3 | 模拟答辩主讲 | 8/29 | 算法部分流畅 |

## 协作对接

- 与 **TL** 完成最终集成验证与提交。
- 与 **DA/DB** 对齐答辩与演示口径，主讲算法部分。
