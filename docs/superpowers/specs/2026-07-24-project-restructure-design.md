# 项目结构优化与文档更新设计

日期：2026-07-24
状态：已批准

## 目标

1. 将 9 个顶层代码模块收拢到 `ca_mp/` 包下，顶层目录从 15 个降至 9 个
2. 新增 `pyproject.toml`，解决 cwd 依赖问题
3. 清理 `sys.path.insert` hack
4. 简化 Docker 构建
5. 新增 11 篇面向团队的操作指南，更新所有活跃文档

## 约束

- `data/` 目录完全不动（比赛原始材料）
- `docs/team/tasks/` 历史文档不更新路径
- 每阶段独立 commit，可单独回滚
- 迁移后 66 个测试必须全部通过

## 新目录结构

```
challenge-cup/
├── ca_mp/                      # 核心代码包
│   ├── __init__.py
│   ├── algorithms/             # 信号控制算法库
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── fixed_time.py
│   │   ├── rule_adaptive.py
│   │   └── ca_max_pressure.py
│   ├── api/                    # REST API 服务
│   │   ├── __init__.py
│   │   └── server.py
│   ├── cloud/                  # 云端协调策略
│   │   ├── __init__.py
│   │   └── cloud_policy.py
│   ├── core/                   # 共享数据契约 & 配置加载
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── types.py
│   ├── engine/                 # SUMO 仿真引擎
│   │   ├── __init__.py
│   │   ├── runner.py
│   │   ├── traci_bridge.py
│   │   ├── mock_bridge.py
│   │   ├── edge_channel.py
│   │   ├── collector.py
│   │   ├── events.py
│   │   └── configs/            # 生成的 demo_N.sumocfg（20个）
│   ├── experiments/            # 实验框架
│   │   ├── __init__.py
│   │   ├── runner.py
│   │   └── metrics.py
│   ├── ml/                     # ML 模块
│   │   ├── __init__.py
│   │   ├── train.py
│   │   ├── features.py
│   │   └── evaluate.py
│   ├── scenes/                 # 路口场景管理
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── variant.py
│   │   └── timing_loader.py
│   └── visualization/          # 可视化出图
│       ├── __init__.py
│       └── plots.py
├── config/                     # 全局运行配置（default.yaml）
├── data/                       # 原始比赛数据（不动）
│   └── intersection_data/
├── docs/                       # 文档（重构）
├── examples/                   # 可运行示例入口
├── output/                     # 运行时输出（gitignore）
├── scripts/                    # 工具脚本
├── tests/                      # 测试
├── docker/                     # Dockerfile
├── pyproject.toml              # 新增：打包 & 工具配置
├── requirements.txt            # 保留（Docker/CI 用）
├── docker-compose.yml
├── README.md
└── LICENSE
```

## pyproject.toml

```toml
[project]
name = "ca-mp"
version = "1.0.0"
description = "Capacity-Aware MaxPressure 信号控制平台"
requires-python = ">=3.10"
dependencies = []  # 运行时依赖通过 requirements.txt 管理

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

## 文档体系

```
docs/
├── README.md                       # 文档总索引（更新）
├── guides/                         # 操作指南（核心新增）
│   ├── README.md                   # 指南索引
│   ├── 01-algorithm-config.md      # 如何配置算法参数
│   ├── 02-import-intersection.md   # 如何导入新路口数据
│   ├── 03-run-simulation.md        # 如何运行单路口仿真
│   ├── 04-batch-experiments.md     # 如何跑批量实验（360组）
│   ├── 05-cloud-coordinator.md     # 如何配置云端协调器
│   ├── 06-generate-configs.md      # 如何生成仿真配置文件
│   ├── 07-view-results.md          # 如何查看/导出结果
│   ├── 08-visualization.md         # 如何生成图表
│   ├── 09-docker-deploy.md         # Docker 部署与运行
│   ├── 10-testing.md               # 如何跑测试/质量检查
│   ├── 11-new-algorithm.md         # 如何实现新算法
│   ├── git-workflow.md             # 已有，保留
│   └── citation-guide.md           # 已有，保留
├── architecture/                   # 架构设计（更新路径引用）
│   ├── README.md
│   ├── interface.md
│   └── images/
├── operations/                     # 环境搭建（补 README）
│   ├── README.md
│   ├── deployment.md
│   └── sumo-environment-setup.md
├── reports/                        # 实验/审计报告（补 README）
│   ├── README.md
│   └── ...
├── team/                           # 团队任务（不动）
│   ├── project-roadmap.md
│   └── tasks/
├── reference/                      # 参考资料（补 README）
│   ├── README.md
│   ├── edge-mapping.md
│   └── competition/
└── notes/                          # 调研笔记（补 README）
    ├── README.md
    └── docker-sumo-research.md
```

### 操作指南统一结构

每篇指南遵循：**目的 → 前置条件 → 操作步骤 → 示例 → 常见问题**

语言：中文为主，代码/命令/路径保留英文。

### 文档边界

- 模块 README（`ca_mp/algorithms/README.md` 等）= 简短概述 + 接口说明
- `docs/guides/` = 面向任务的 step-by-step 操作手册

## 迁移策略

### 阶段 1：模块迁移

- `git mv` 将 9 个模块（algorithms、api、cloud、core、engine、experiments、ml、scenes、visualization）移入 `ca_mp/`
- 创建 `ca_mp/__init__.py`
- 验证：目录结构正确

### 阶段 2：import 路径替换

- 全局替换 `from algorithms.` → `from ca_mp.algorithms.`，其余 8 个模块同理
- 涉及 37 个 .py 文件，93 处替换
- 删除 6 个文件中的 `sys.path.insert` hack：
  - `examples/run_demo.py`
  - `examples/run_fixed_time.py`
  - `examples/run_ca_max_pressure.py`
  - `experiments/runner.py`（已移入 ca_mp/）
  - `scripts/validation/stress_memory.py`
  - `scripts/validation/check_seed_repro.py`
- 验证：`pytest` 66 个测试全过

### 阶段 3：配置与脚本更新

- 更新 `scripts/` 中的模块引用（约 12 处）
- 更新 `examples/` 中的引用
- 更新 `config/default.yaml`（2 处）
- 验证：`python examples/run_demo.py` 成功运行

### 阶段 4：Docker 更新

- Dockerfile：9 行 `COPY xxx/ ./xxx/` 简化为 `COPY ca_mp/ ./ca_mp/` + 其余目录
- `docker-compose.yml`：`./experiments/results` 挂载改为 `./output/experiments`
- ENTRYPOINT 路径更新
- 验证：`docker compose build` 成功

### 阶段 5：pyproject.toml

- 新增 `pyproject.toml`
- `pip install -e .` 验证 import 不依赖 cwd
- 验证：从任意目录 `python -c "from ca_mp.core import types"` 成功

### 阶段 6：文档更新

- 新增 11 篇操作指南
- 更新 `docs/architecture/interface.md`（24 处路径）
- 更新各模块 README（import 路径）
- 补齐 `operations/`、`reports/`、`reference/`、`notes/` 的 README
- 删除 `docs/guides/markdown-guide.md`
- 更新 `docs/README.md` 总索引
- 验证：人工审阅

### 阶段 7：根 README 重写

- 反映新结构、新 import 路径、快速上手指南
- 验证：最终检查

## 不改动项

- `data/` 目录（比赛原始材料）
- `docs/team/tasks/` 历史文档（约 300+ 处旧路径引用，保持原样）
- `output/` 目录结构（运行时生成物）
- `.gitignore` 中已有的 XML 输出忽略规则

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| import 替换遗漏 | 全量 pytest + grep 残留旧路径 |
| Docker 构建失败 | 阶段 4 独立验证 |
| 脚本路径断裂 | 阶段 3 逐个运行验证 |
| 团队成员本地分支冲突 | 迁移在独立分支完成，合并前通知团队 |
