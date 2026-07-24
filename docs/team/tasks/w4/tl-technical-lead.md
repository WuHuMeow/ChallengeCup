# Tech Lead W4 任务书

> 周期：8/10–8/16 | 核心目标：1.5 倍压力测试完成，EWMA 接入验证，Docker 打包可复现

## 本周背景

本周首次涉及 Docker 容器化：将 SUMO + Python 环境打包为镜像，使评审方无需安装任何依赖即可复现实验。Dockerfile 由 IA 编写，你负责验证容器内运行结果与本地一致。另外本周验证 EWMA 预测是否给 CA-MP 带来额外收益。

## 每日任务

### Day 1（8/10）

- [ ] 启动 1.5 倍压力测试：20 路口 × 3 算法 × 3 种子 = 180 组
- [ ] 确认 `VariantGenerator` 正确生成 1.5 倍流量文件
- [ ] 监控运行状态，处理失败实验
- [ ] 确认 1.5 倍流量下 avg_queue_length 明显高于原始流量

启动高压实验：

```python
from experiments.runner import run_batch
from core.types import TrafficLevel

results = run_batch(
    levels=[TrafficLevel.HIGH],  # 触发 VariantGenerator 生成 1.5x 流量文件
    steps=3600,
)
# 输出路径：output/csv/{路口}_high_{算法}_s{seed}.csv
```

VariantGenerator 的工作原理（完整实现见 `scenes/variant.py`）：

```python
class VariantGenerator:
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

**验证：** `python -c "from scenes.variant import VariantGenerator; print('VariantGenerator 可用')"` → 输出 `VariantGenerator 可用`

### Day 2（8/11）

- [ ] Review AB 的 EWMA 预测实现：确认 `CloudPolicy.predict()` 每步被调用
- [ ] 在路口 1 上对比：有 EWMA vs 无 EWMA 的 CA-MP 表现
- [ ] 如 EWMA 效果不明显或引入 bug，与 AB 讨论是否保留
- [ ] 记录结论到文档

EWMA 预测验证（完整实现见 `cloud/cloud_policy.py`）：

```python
from cloud.cloud_policy import CloudPolicy
from core.types import JointState, QueueState

policy = CloudPolicy()
# 模拟连续 3 步，观察预测值收敛
for i in range(3):
    state = JointState(step=i, timestamp=float(i), tls_id="tls_1",
                       current_phase=0, current_phase_name="NS_green",
                       elapsed_phase_time=float(i),
                       queues=[], flows={"north": 500.0, "south": 300.0})
    pred = policy.predict(state)
    print(f"Step {i}: predicted_flows = {pred.predicted_flows}")
# 期望：预测值逐步趋近观测值（alpha=0.3 的指数收敛）

# dispatch_base_green 当前返回固定值
base = policy.dispatch_base_green(state)
print(f"base_green = {base}")  # 应为 30.0（配置默认值）
```

**验证：** `python -m pytest tests/unit/test_cloud.py -v` → 全部 passed

### Day 3（8/12）

- [ ] 检查 1.5 倍压力测试进度（目标完成过半）
- [ ] Review IA 的 Dockerfile：确认基于 `ubuntu:22.04`、安装了 SUMO 和 Python 依赖
- [ ] 构建镜像并验证容器内可运行
- [ ] 确认容器内 traci 可用

Docker 验证流程：

```bash
# 构建镜像
docker build -t ca-mp .

# 验证 Python 环境
docker run ca-mp python -c "import traci, pandas, numpy; print('依赖完整')"

# 验证仿真可运行
docker run ca-mp python examples/run_fixed_time.py 1

# 对比本地 vs 容器结果（应一致）
docker run -v $(pwd)/output:/app/output ca-mp python examples/run_fixed_time.py 1
```

**验证：** `docker run ca-mp python -c "import traci; print('容器内 traci 可用')"` → 输出 `容器内 traci 可用`

### Day 4（8/13）

- [ ] 确认 1.5 倍压力测试 180 组全部完成
- [ ] 用 `experiments/metrics.py` 采集结果
- [ ] 对比：原始流量 vs 1.5 倍流量下 CA-MP 优势是否更明显
- [ ] 将数据发给 DA 和 DB

高压 vs 原始对比：

```python
import pandas as pd

# 路口 16 在两种流量下的 CA-MP 表现
normal = pd.read_csv("output/csv/16_normal_ca_maxpressure_s42.csv")
high = pd.read_csv("output/csv/16_high_ca_maxpressure_s42.csv")
print(f"原始流量 平均排队: {normal['avg_queue_length'].mean():.2f}")
print(f"1.5倍流量 平均排队: {high['avg_queue_length'].mean():.2f}")

# CA-MP 相对 FixedTime 的改善幅度
ft_normal = pd.read_csv("output/csv/16_normal_fixed_time_s42.csv")
ft_high = pd.read_csv("output/csv/16_high_fixed_time_s42.csv")
improve_normal = 1 - normal["avg_queue_length"].mean() / ft_normal["avg_queue_length"].mean()
improve_high = 1 - high["avg_queue_length"].mean() / ft_high["avg_queue_length"].mean()
print(f"原始流量下 CA-MP 改善: {improve_normal*100:.1f}%")
print(f"高压下 CA-MP 改善:    {improve_high*100:.1f}%")
# 期望：高压下改善更明显（CA-MP 的优势在拥堵时更突出）
```

**验证：** `ls output/csv/ | grep "high" | wc -l` → 输出 `180`

### Day 5（8/14）

- [ ] Review 全部代码质量：无未处理异常、无硬编码路径、关键函数有 docstring
- [ ] 确认 Docker 内运行结果与本地一致（差异 < 1%）
- [ ] 修复发现的问题
- [ ] 确认 `config/default.yaml` 中所有路径为相对路径

代码质量检查：

```bash
# 检查硬编码路径
grep -r "C:\\\\" --include="*.py" . | grep -v __pycache__
# 应无输出

# 检查语法错误
python -m py_compile core/types.py algorithms/base.py algorithms/ca_max_pressure.py
python -m py_compile engine/runner.py experiments/runner.py cloud/cloud_policy.py
# 应无报错

# 检查配置路径
grep -n "path" config/default.yaml
# 所有路径应为 ./ 开头的相对路径
```

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
