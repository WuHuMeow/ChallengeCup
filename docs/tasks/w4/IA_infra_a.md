# 仿真基础设施 A（IA） W4 任务书

> 周期：8/10（周日）- 8/16（周六） | 核心目标：完成 Docker 打包并保障 1.5 倍流量压力测试运行

## 每日任务

### Day 1（8/10 周日）— 1.5 倍压力测试环境保障

- [ ] 保障 1.5 倍流量压力测试运行环境稳定
- [ ] 监控高流量下 SUMO 内存占用（1.5× 流量车辆数显著增加）
- [ ] 若 1.5 倍流量导致某些路口车辆数暴增、运行极慢，与 EX 协调减少步数
- [ ] 复用 W3 的内存监控脚本持续观察

```bash
# 1.5 倍流量单次实验
python experiments/runner.py --intersection 16 --algo ca_maxpressure \
    --flow-multiplier 1.5 --seed 0 \
    --output-dir experiments/results/stress_1.5x/16
```

**验证：** 路口 16 在 `--flow-multiplier 1.5` 下完整跑完，`experiments/results/stress_1.5x/16/` 三件输出齐全；SUMO 进程 RSS 无持续增长。

### Day 2（8/11 周一）— 完善 Dockerfile

- [ ] 完善 `docker/Dockerfile`：设置 `SUMO_HOME`、分层 COPY 减小镜像、清理 apt 缓存
- [ ] 仅 COPY 必要目录（`core/ algorithms/ engine/ cloud/ experiments/ data/intersection_data/`），避免把 `output/`、`__pycache__/` 打入镜像
- [ ] 构建镜像并测试单路口运行
- [ ] 记录镜像大小（目标 < 2GB）

```dockerfile
# docker/Dockerfile
FROM ubuntu:22.04

ENV SUMO_HOME=/usr/share/sumo
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    sumo sumo-tools python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY core/ ./core/
COPY algorithms/ ./algorithms/
COPY engine/ ./engine/
COPY cloud/ ./cloud/
COPY experiments/ ./experiments/
COPY data/intersection_data/ ./data/intersection_data/

ENTRYPOINT ["python3", "engine/runner.py"]
CMD ["1"]
```

**验证：** `docker build -t ca-mp:latest -f docker/Dockerfile .` 构建成功；`docker run --rm ca-mp:latest 1` 退出码 0；`docker images ca-mp:latest --format "{{.Size}}"` < 2GB。

### Day 3（8/12 周二）— docker-compose 编排

- [ ] 编写 `docker-compose.yml`（简化版，单容器），把 `experiments/results` 挂载到宿主机
- [ ] 测试 `docker-compose up` 能跑通指定路口
- [ ] 确认输出文件正确落到宿主机目录
- [ ] 验证不同 `command` 参数（路口 ID）能切换运行目标

```yaml
# docker-compose.yml
version: "3.8"
services:
  simulation:
    build:
      context: .
      dockerfile: docker/Dockerfile
    volumes:
      - ./experiments/results:/app/experiments/results
    command: ["16"]
```

**验证：** `docker-compose up --build` 跑完后，宿主机 `experiments/results/` 下出现路口 16 的输出文件；`docker-compose down` 正常退出。

### Day 4（8/13 周三）— 部署文档（PDF 硬性要求）

- [ ] 完善 `docs/deployment.md`：添加 Docker 部署章节
- [ ] 添加常见问题：`SUMO_HOME` 未设置、端口冲突、镜像拉取慢等
- [ ] 添加 Windows / Mac / Linux 差异说明（路径分隔符、卷挂载语法）
- [ ] 这是 PDF 硬性要求的"详细的部署运行说明文档"——必须完整

```markdown
<!-- docs/deployment.md 章节骨架 -->
## 1. 本地部署（Windows / Mac / Linux）
## 2. Docker 部署
   - docker build / docker run / docker-compose up
## 3. 常见问题
   - SUMO_HOME 未设置 → ...
   - Windows 卷挂载需绝对路径 → ...
## 4. 输出文件说明
```

**验证：** `docs/deployment.md` 包含上述 4 个一级章节；按文档 Docker 章节命令能在全新环境跑通路口 1。

### Day 5（8/14 周四）— 协助 1.5 倍压力测试

- [ ] 协助 EX 处理 1.5 倍压力测试中的技术问题
- [ ] 检查所有 1.5× 输出文件完整性（复用 W3 的 `check_outputs.py`）
- [ ] 标记并补跑失败实验

**验证：** `python scripts/check_outputs.py --root experiments/results/stress_1.5x` 输出 `缺失/空文件: 0`。

### Day 6（8/15 周五）— Docker 最终验证

- [ ] 在全新环境（无 SUMO 的机器）执行 `docker build` + `docker run`，确认跑通
- [ ] 记录镜像大小、构建时间到 `docs/deployment.md`
- [ ] 提交 `Dockerfile + docker-compose.yml + deployment.md` 给 TL

```bash
# 全新环境验证流程
git clone <repo> && cd challenge-cup
docker build -t ca-mp:latest -f docker/Dockerfile .
docker run --rm -v ${PWD}/experiments/results:/app/experiments/results ca-mp:latest 1
ls experiments/results/1   # 应有输出文件
```

**验证：** 上述流程在全新机器上端到端跑通；镜像大小 < 2GB；构建时间记录在案。

### Day 7（8/16 周六）— Buffer / 协助

- [ ] 修复本周遗留问题
- [ ] 协助其他组（EX/DA/DB）的环境相关问题

**验证：** 本周交付物清单全部勾选完成，TL 确认收到 Docker 三件套。

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| `docker/Dockerfile` | 8/11 | 构建成功、容器内可运行、镜像 < 2GB |
| `docker-compose.yml` | 8/12 | `docker-compose up` 可运行，输出正确挂载 |
| `docs/deployment.md` 完整版 | 8/13 | 含 Docker 章节 + 常见问题 + 三平台差异 |
| 1.5 倍测试环境保障 | 8/10-8/13 | 无崩溃，输出完整 |

## 协作对接

- 与 **EX** 协调 1.5× 流量下的步数/并发调整。
- 与 **TL** 交付 Docker 三件套（Dockerfile / docker-compose.yml / deployment.md）。
- 与 **DA** 同步部署文档章节，供报告"系统部署"部分引用。
