# Scripts

仓库脚本按职责分为四类。所有命令均可从仓库根目录执行；Python 脚本会根据自身位置解析仓库根目录，不依赖当前工作目录。

## 分类职责

| 目录 | 职责 |
| --- | --- |
| `data/` | 从原始路口数据提取元数据，并生成边方向映射。 |
| `simulation/` | 生成 SUMO 仿真配置，并拆分实验任务。 |
| `validation/` | 验证 SUMO 数据、批量运行、输出完整性、随机种子复现性和内存压力。 |
| `quality/` | 执行 Python 静态检查并扫描调试代码和待办标记。 |

## 文件索引

| 文件 | 命令 | 输入 | 输出 |
| --- | --- | --- | --- |
| `data/extract_metadata.py` | `python scripts/data/extract_metadata.py` | `data/intersection_data/{1..20}/sumo工程/` | `data/intersection_data/metadata/intersections.yaml` |
| `data/generate_edge_mapping.py` | `python scripts/data/generate_edge_mapping.py` | 20 个路口的 `demo_N.net.xml` | `docs/reference/edge-mapping.md`、`data/intersection_data/metadata/edge_mapping.json` |
| `simulation/generate_configs.py` | `python scripts/simulation/generate_configs.py` | 20 个原始 `demo_N.sumocfg` | `engine/configs/demo_N.sumocfg` |
| `simulation/split_jobs.py` | `python scripts/simulation/split_jobs.py` | 脚本内置实验矩阵 | 控制台 A/B 机器任务汇总 |
| `simulation/split_jobs.py` | `python scripts/simulation/split_jobs.py --machine a` | 脚本内置实验矩阵 | A 机逐行任务清单；将 `a` 改为 `b` 可输出 B 机清单 |
| `validation/validate_all.py` | `python scripts/validation/validate_all.py` | 20 个原始 SUMO 配置及 `sumo` 命令 | 控制台 PASS/FAIL；临时文件写入 `output/validate_quick/` |
| `validation/validate_all.py` | `python scripts/validation/validate_all.py 1 11 16` | 指定路口 ID | 指定路口的验证结果 |
| `validation/batch_validate.py` | `python scripts/validation/batch_validate.py` | `engine/configs/` 及 `sumo` 命令 | `output/validate/`、`docs/reports/batch-validation-report.md` |
| `validation/batch_validate.py` | `python scripts/validation/batch_validate.py 1 11 16` | 指定路口 ID | 指定路口的批量验证结果和报告 |
| `validation/check_outputs.py` | `python scripts/validation/check_outputs.py` | `experiments/results/` | 控制台缺失或空 XML 文件清单 |
| `validation/check_outputs.py` | `python scripts/validation/check_outputs.py --root experiments/results/stress_1.5x` | 指定结果目录 | 控制台缺失或空 XML 文件清单 |
| `validation/check_seed_repro.py` | `python scripts/validation/check_seed_repro.py` | 路口 1、固定时制算法、seed 42 和 7 | `output/seed_check/*.csv` 及复现性断言结果 |
| `validation/stress_memory.py` | `python scripts/validation/stress_memory.py 1 100` | 路口 ID、步数、1.5 倍流量 | `output/stress/`、CSV 路径和 Python 内存峰值 |
| `quality/lint_check.sh` | `bash scripts/quality/lint_check.sh` | `engine/`、`cloud/`、`experiments/` 中跟踪和未跟踪的源码 | 成功时仅打印 `clean` |

## 依赖

- 使用项目 Python 环境安装的依赖；专用包包括 PyYAML、`sumolib`、`defusedxml` 和 `flake8`。
- `validate_all.py` 与 `batch_validate.py` 要求 `sumo` 可执行文件位于 `PATH`。
- `lint_check.sh` 要求 Bash、Git 和可通过 `python -m flake8` 调用的 flake8。
- 复现性和压力脚本依赖仓库内的 `algorithms`、`engine`、`experiments` 与 `scenes` 模块及其运行时配置。

## 已知限制

- 数据生成脚本固定处理路口 1 到 20，并假设原始工程目录名为 `sumo工程`；生成文件会被覆盖。
- 配置生成器固定写入 `engine/configs/`，并按该目录深度生成到原始数据的相对路径。
- 任务拆分矩阵和两台机器的路口分配写在脚本中，不能通过命令行调整。
- 输出检查器只检查 `intersection/algo/seed` 三层目录中的 `tripinfo.xml`、`stats.xml` 和 `traj.xml`。
- 快速验证和批量验证会写入 `output/`；批量验证会重写验证报告。
- 内存压力检查只统计 Python 进程的 `tracemalloc` 峰值，不包含外部 SUMO 进程。
- lint 仅覆盖 `engine/`、`cloud/` 和 `experiments/`，不会检查仓库中的所有 Python 文件。
