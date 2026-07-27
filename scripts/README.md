# Scripts

仓库脚本按职责分为四类。所有命令均可从仓库根目录执行；Python 脚本会根据自身位置解析仓库根目录，不依赖当前工作目录。

## 分类职责

| 目录 | 职责 |
| --- | --- |
| 元数据脚本 | 从原始路口数据提取元数据，并生成边方向映射。 |
| 仿真脚本 | 生成 SUMO 仿真配置，并拆分实验任务。 |
| 验证脚本 | 验证 SUMO 数据、批量运行、输出完整性、随机种子复现性和内存压力。 |
| `quality/` | 执行 Python 静态检查并扫描调试代码和待办标记。 |

## 文件索引

| 文件 | 命令 | 输入 | 输出 |
| --- | --- | --- | --- |
| `scripts/extract_metadata.py` | `python scripts/extract_metadata.py` | `data/intersection_data/{1..20}/sumo工程/` | `data/intersection_data/metadata/intersections.yaml` |
| `scripts/generate_edge_mapping.py` | `python scripts/generate_edge_mapping.py` | 20 个路口的 `demo_N.net.xml` | `docs/edge_mapping.md`、`data/intersection_data/metadata/edge_mapping.json` |
| `scripts/generate_configs.py` | `python scripts/generate_configs.py` | 20 个原始 `demo_N.sumocfg` | `engine/configs/demo_N.sumocfg` |
| `scripts/split_jobs.py` | `python scripts/split_jobs.py` | 脚本内置实验矩阵 | 控制台 A/B 机器任务汇总 |
| `scripts/split_jobs.py` | `python scripts/split_jobs.py --machine a` | 脚本内置实验矩阵 | A 机逐行任务清单；将 `a` 改为 `b` 可输出 B 机清单 |
| `scripts/validate_all.py` | `python scripts/validate_all.py --steps 100 --output-root output/runs/validate-original` | 20 个原始 SUMO 配置及 `sumo` 命令 | 控制台 PASS/FAIL；运行时产物写入指定根目录 |
| `scripts/batch_validate.py` | `python scripts/batch_validate.py --steps 100 --output-root output/runs/validate-enhanced --no-report` | `engine/configs/` 及 `sumo` 命令 | 指定根目录下的增强配置验证结果 |
| `scripts/check_outputs.py` | `python scripts/check_outputs.py --root output/runs/matrix` | 含 `run_metadata.json` 的运行根目录 | 递归检查每个运行的 7 类必需输出 |
| `scripts/check_seed_repro.py` | `python scripts/check_seed_repro.py --steps 300 --output-root output/runs/seed-repro` | 路口 1、固定时制算法、seed 42 和 7 | 三个隔离运行目录及复现性断言 |
| `scripts/stress_memory.py` | `python scripts/stress_memory.py --algorithm actuated --intersections 1 11 16 --steps 3600 --output-root output/runs/stress` | 路口 ID、步数、1.5 倍流量 | `stress_results.json`、输出大小和 Python 峰值 |
| `scripts/run_pdf_matrix.py` | `python scripts/run_pdf_matrix.py --quick --output-root output/runs/matrix-quick` | 路口、3 算法、2 流量、3 种子 | 可恢复矩阵、`matrix.csv`、`matrix_state.json` 和隔离运行产物 |
| `scripts/run_pdf_matrix.py` | `python scripts/run_pdf_matrix.py --steps 36000 --output-root output/runs/matrix-full` | PDF 完整 360 组实验 | 360 个 `run_id` 目录与矩阵索引 |
| `scripts/package_offline.py` | `python scripts/package_offline.py --output-dir output/offline` | 仓库源码、依赖、可选 Docker 镜像和第二机器证据 | 源码 ZIP、SHA-256、`offline_manifest.json` |
| `scripts/verify_ia_ib.py` | `python scripts/verify_ia_ib.py --quick --output-root output/runs/ia-ib-quick` | IA/IB 全套验收命令 | `verification.json` 与最终 Markdown 报告 |
| `quality/lint_check.sh` | `bash scripts/quality/lint_check.sh` | `engine/`、`cloud/`、`experiments/` 中跟踪和未跟踪的源码 | 成功时仅打印 `clean` |

## 依赖

- 使用项目 Python 环境安装的依赖；专用包包括 PyYAML、`sumolib`、`defusedxml` 和 `flake8`。
- `validate_all.py` 与 `batch_validate.py` 要求 `sumo` 可执行文件位于 `PATH`。
- `run_pdf_matrix.py` 默认每次 `36000` 步；`--quick` 固定选择路口 1、11、16 并运行 100 步。
- `package_offline.py` 不要求 Docker；Docker 不可用或第二机器证据未提供时分别记录 `not_run`。
- `lint_check.sh` 要求 Bash、Git 和可通过 `python -m flake8` 调用的 flake8。
- 复现性和压力脚本依赖 `项目包`下的 `algorithms`、`engine`、`experiments` 与 `scenes` 模块及其运行时配置。

## 已知限制

- 数据生成脚本固定处理路口 1 到 20，并假设原始工程目录名为 `sumo工程`；生成文件会被覆盖。
- 配置生成器固定写入 `engine/configs/`，并按该目录深度生成到原始数据的相对路径。
- 任务拆分矩阵和两台机器的路口分配写在脚本中，不能通过命令行调整。
- 每次运行目录固定为 `<root>/i{id}/{algorithm}/x{flow}/s{seed}/{run_id}/`。
- 表中的 `output/runs/...` 是由命令创建的运行时根目录，不是当前保留的证据或归档目录。
- 输出检查器递归发现 `run_metadata.json`，并检查同一运行目录中的 `metrics.csv`、`simulation_log.csv`、`events.csv`、`tripinfo.xml`、`stats.xml` 和 `traj.xml`。
- 矩阵恢复只复用 `completed` 且七类必需产物均非空的 `run_id`，不会覆盖旧运行。
- 快速验证和批量验证必须显式传入 `--output-root`；验收器会把所有中间文件隔离到该目录。
- 内存压力检查只统计 Python 进程的 `tracemalloc` 峰值，不包含外部 SUMO 进程。
- lint 仅覆盖 `engine/`、`cloud/` 和 `experiments/`，不会检查仓库中的所有 Python 文件。
- 已记录的验收为 13 项 `pass`、0 项 `fail`，360 次矩阵为已审计通过；对应生成产物已清理，不能通过重新生成
  历史目录来证明该记录。Docker live 和第二机器复现均保持 `not_run`。
