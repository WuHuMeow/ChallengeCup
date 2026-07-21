# Tech Lead W4 任务书

> 周期：8/10–8/16 | 核心目标：1.5 倍压力测试完成，EWMA 接入验证，Docker 打包可复现

## 本周背景

本周首次涉及 Docker 容器化：将 SUMO + Python 环境打包为镜像，使评审方无需安装任何依赖即可复现实验。Dockerfile 由 IA 编写，你负责验证容器内运行结果与本地一致。另外本周接入 EWMA 预测到 CA-MP 决策链路，验证预测是否带来额外收益。

## 每日任务

### Day 1（8/10）

- [ ] 启动 1.5 倍压力测试：`run_batch(levels=[TrafficLevel.HIGH], steps=3600)`，共 180 组
- [ ] 确认 `VariantGenerator` 正确生成 1.5 倍流量文件（检查 `output/variants/` 目录）
- [ ] 监控运行状态，处理失败实验
- [ ] 确认 1.5 倍流量下 CSV 的 avg_queue_length 明显高于原始流量（否则流量倍率未生效）

**验证：** `python -c "from scenes.variant import VariantGenerator; print('VariantGenerator 可用')"` → 输出 `VariantGenerator 可用`

### Day 2（8/11）

- [ ] Review AB 的 EWMA 预测实现：确认 `CloudPolicy.predict()` 每步被调用、`_prev_predicted` 状态正确更新
- [ ] 在路口 1 上对比：有 EWMA vs 无 EWMA 的 CA-MP 表现（avg_travel_time）
- [ ] 如 EWMA 效果不明显或引入 bug，与 AB 讨论是否保留
- [ ] 记录结论到文档

**验证：** `python -m pytest tests/test_cloud.py -v` → 全部 passed

### Day 3（8/12）

- [ ] 检查 1.5 倍压力测试进度（目标完成过半）
- [ ] Review IA 的 Dockerfile：确认基于 `ubuntu:22.04`、安装了 SUMO 和 Python 依赖
- [ ] 构建镜像：`docker build -t ca-mp .`
- [ ] 容器内运行路口 1：`docker run ca-mp python examples/run_fixed_time.py 1`

**验证：** `docker run ca-mp python -c "import traci; print('容器内 traci 可用')"` → 输出 `容器内 traci 可用`

### Day 4（8/13）

- [ ] 确认 1.5 倍压力测试 180 组全部完成
- [ ] 用 `experiments/metrics.py` 采集结果
- [ ] 对比：原始流量 vs 1.5 倍流量下 CA-MP 相对 FixedTime 的优势是否更明显
- [ ] 将数据发给 DA 和 DB

**验证：** `ls output/csv/ | grep "high" | wc -l` → 输出 `180`

### Day 5（8/14）

- [ ] Review 全部代码质量：无未处理异常、无硬编码路径、关键函数有 docstring
- [ ] 确认 Docker 内运行结果与本地一致（同一路口同一算法的 avg_queue_length 差异 < 1%）
- [ ] 修复发现的问题
- [ ] 确认 `config/default.yaml` 中所有路径为相对路径

**验证：** `grep -r "C:\\\\" --include="*.py" . | grep -v __pycache__` → 无输出（无硬编码 Windows 路径）

### Day 6（8/15）

- [ ] 打 tag：`git tag v0.4-w4-complete`
- [ ] 编写 W4 周报
- [ ] 确认 W5 前置条件：所有实验数据齐全（原始 180 + 高压 180）、图表已生成、Docker 可复现
- [ ] 与 DA/DB 确认 W5 交付物制作计划

**验证：** `git tag -l "v0.4*"` → 输出 `v0.4-w4-complete`

### Day 7（8/16）

- [ ] 处理遗留问题
- [ ] 如 DB 的 PyQt 看板完成，做最终验证（能加载 CSV、显示对比曲线）
- [ ] 全员会议：确认 W5 分工和时间节点

**验证：** `ls output/csv/ | wc -l` → 输出 `360`（全量实验完成）

## 关键代码指引

```python
# 1.5 倍流量跑批（完整实现见 experiments/runner.py + scenes/variant.py）
from experiments.runner import run_batch
from core.types import TrafficLevel

results = run_batch(
    levels=[TrafficLevel.HIGH],  # 触发 VariantGenerator 生成 1.5x 流量文件
    steps=3600,
)
```

```python
# 流量变体生成（完整实现见 scenes/variant.py）
class VariantGenerator:
    def __init__(self):
        self.levels = {TrafficLevel.NORMAL: 1.0, TrafficLevel.HIGH: 1.5}

    def generate(self, scene_meta: SceneMeta, level: TrafficLevel, output_dir: Path) -> Path:
        factor = self.levels[level]  # HIGH → 1.5
        tree = ET.parse(scene_meta.sumo_flow)
        for flow in tree.getroot().findall("flow"):
            number_attr = flow.get("number")
            if number_attr:
                scaled = max(1, int(round(int(number_attr) * factor)))
                flow.set("number", str(scaled))  # 车辆数 × 1.5
        output_file = output_dir / f"{scene_meta.sumo_flow.stem}_{level.value}.flow.xml"
        tree.write(output_file, encoding="utf-8", xml_declaration=True)
        return output_file
```

```python
# 云端动态绿灯下发（完整实现见 cloud/cloud_policy.py）
class CloudPolicy:
    def predict(self, state: JointState) -> PredictionResult:
        # predicted(t+1) = α × observed(t) + (1-α) × predicted(t)，α=0.3
        ...

    def dispatch_base_green(self, state: JointState) -> float:
        # MVI：返回配置的固定 base_green（默认 30s）
        # TODO(AB): 根据全局压力评估动态调整
        #   高压时增大 base_green，低压时减小，实现自适应周期
        return float(get_config().get("algorithms.ca_maxpressure.base_green", 30))
```

## 交付物

| 文件 | 截止 | 验收标准 |
|------|------|----------|
| 1.5 倍压力测试 180 组 CSV | Day 4 | `output/csv/` 下含 "high" 的文件 180 个 |
| EWMA 接入验证结论 | Day 2 | 文档记录：效果提升/持平/退化的数据对比 |
| Docker 镜像 | Day 3 | `docker run ca-mp python examples/run_fixed_time.py 1` 无报错 |
| git tag v0.4 | Day 6 | `git tag -l "v0.4*"` 有输出 |

## 协作对接

- Day 2 将 EWMA 验证结论发给 AB
- Day 3 与 IA 确认 Dockerfile 和镜像构建
- Day 4 将高压实验数据发给 DA 和 DB
