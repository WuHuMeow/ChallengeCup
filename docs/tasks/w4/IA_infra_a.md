# W4 任务书：仿真基础设施 A（IA）

> 周期：8/10（周日）- 8/16（周六）
> 核心目标：完成 Docker 打包、保障 1.5 倍压力测试运行

---

## 每日任务

### Day 1（8/10 周日）
1. 保障 1.5 倍压力测试运行环境
2. 高流量下 SUMO 可能内存占用更高——监控并处理
3. 如果 1.5 倍流量导致某些路口车辆数暴增、运行极慢，与 EX 协调减少步数

### Day 2（8/11 周一）
1. 完善 Dockerfile：
   ```dockerfile
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
2. 构建镜像：`docker build -t ca-mp:latest .`
3. 测试运行：`docker run --rm ca-mp:latest 1`

### Day 3（8/12 周二）
1. 编写 `docker-compose.yml`（简化版，单容器）：
   ```yaml
   version: "3.8"
   services:
     simulation:
       build: .
       volumes:
         - ./experiments/results:/app/experiments/results
       command: ["16"]
   ```
2. 测试 `docker-compose up`
3. 确认输出文件正确挂载到宿主机

### Day 4（8/13 周三）
1. 完善 `docs/deployment.md`：
   - 添加 Docker 部署章节
   - 添加常见问题（SUMO_HOME 未设置、端口冲突等）
   - 添加 Windows/Mac/Linux 差异说明
2. 这是 PDF 硬性要求的"详细的部署运行说明文档"——必须完整

### Day 5（8/14 周四）
1. 协助 EX 处理 1.5 倍压力测试中的技术问题
2. 检查所有输出文件完整性

### Day 6（8/15 周五）
1. 最终 Docker 验证：
   - 在全新环境（无 SUMO）中 `docker run` 能否跑通
   - 记录镜像大小（目标 < 2GB）
2. 提交 Dockerfile + docker-compose.yml + deployment.md 给 TL

### Day 7（8/16 周六）
1. Buffer：修复遗留问题
2. 协助其他组

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | Dockerfile | 8/11 | 构建成功、可运行 |
| 2 | docker-compose.yml | 8/12 | docker-compose up 可运行 |
| 3 | `docs/deployment.md` 完整版 | 8/13 | 含 Docker 章节 |
| 4 | 1.5 倍测试环境保障 | 8/10-8/13 | 无崩溃 |
