# Task 19 报告 — Docker 判定环境部署（complete）

状态：`complete`（Step 9 pending 记录 `88505c8` 提交并通过 Step 10 后改写；
Step 12 提交本完成版本）。

## 提交链

| 单元 | 提交 | 说明 |
| --- | --- | --- |
| 设计/计划 | `68e3401` / `6479195`（基线 `816ed27` 前后） | design + agent routes |
| 19.0/19.A/19.B | 含于基线 `816ed27` | brief、container-gui launcher、detector/schema |
| 19.C | `e871c38` | `feat: add safe Docker live verifier`（4 项复审 Important 修复闭环） |
| 19.D | `9255a59` | `feat: build reproducible headless judge image` |
| 19.E | `2a03f64` | `feat: add optional container GUI deployment` |
| 便携性修复 | `5059dc5` | `fix: export canonical LF API contracts`（换机后全量套件归零所需） |

换机说明：原控制器（Windows，D:\WorkPlace）→ 新控制器（Windows，D:\Desktop\挑战杯项目）。
续作包 380/380 SHA 校验通过；仓库以 `core.autocrlf=false` 重建；253 个纯换行符差异
文件经验证零内容差异后恢复规范字节；三个 Task 19.C 候选与 git-state.txt 完全一致，
working-tree.patch blob 哈希（4b1f57b→d2c2d1e、71850f2→0361e2f）双向匹配。

## RED→GREEN 证据（19.A–19.E）

- 19.A/19.B：原控制器完成（台账 2026-08-24/26 记录；launcher `container-gui`、
  detector/schema 与保护门禁测试，含 `not_run` 信封契约）。
- 19.C 第一轮：4 个复审 Important 的 RED（复现 public `verify_live` 绕过门禁、
  collision preflight 与 workflow 共存、lifecycle/export/cleanup 时序缺口、
  health transcript 绑定缺失）→ 逐项 GREEN；cleanup fallback 1970 时间戳问题修复。
- 19.C 第二轮（4 项新 Important）：i1 严格 pass 导出命令成功语义、i2 隐私过滤
  token 级豁免、i3 cleanup 真实入口时间戳（10 处投影）、i4 嵌套 API-health
  串入 chronology 链；i3/i3b 测试经三轮复审强化（ticking runner + 锚定伪造值），
  在"回退修复"世界必然失败，判别裕度 ≥5x。
- 19.D：重写 `tests/test_docker_static.py`（13 失败 + 1 skip 的 RED）→ 14/14
  GREEN；替代复审直接解析 eclipse-sumo wheel 的 ELF 头发现 Critical C1（slim
  基础镜像缺 libX11/libXext/libXrender/libGL，门禁与运行必然失败）→ test-first
  修复（snapshot.debian.org 20260824T000000Z 安装四个 loader 库）+ M1/M2/M3
  测试强化，第 2 轮复审 CLEAN。
- 19.E：9 项新契约测试 RED → GREEN（Dockerfile.gui 快照钉定、精确 X 包、
  ldd 门禁、compose gui profile/additional_contexts、.dockerignore 边界、
  运维文档必含词与禁用声明扫描）；复审 F-1（GUI 直构建命令需
  `--build-context judge_base=docker-image://ca-mp:latest`）test-first 修复
  + M-1 多行感知断言，第 2 轮复审 CLEAN。

## 本轮门禁（exact HEAD `5059dc5`，除注明外）

- focused（docker_release + docker_static + judge_launcher）：**988 passed,
  1 skipped**（65.15s）
- affected（release_preflight/validation_scripts/api/run_service/runner_channel）：
  **145 passed**（134.18s）
- 全量 Python（项目默认 `--basetemp=output/tmp`）：**1889 passed, 1 skipped,
  exit 0**（619.96s）。首跑 5 failed 的归因与处置：4 个 fixed_time 系
  basetemp=D:\Temp 触发仓库路径包含性校验（改用项目默认配置后通过）；
  1 个 api_contract 系导出器 CRLF 翻译（`5059dc5` 修复后通过）。两次运行
  均如实记录，未合并表述。
- Web：`tsc --noEmit` exit 0；`vite build` exit 0；Playwright chromium
  `tests/judge-flow.spec.ts` **15 passed**（7.6s；浏览器 build v1148 按仓库
  playwright 版本安装）。
- compileall：venv Python 3.12.7 与系统 3.13.2 均 exit 0。
- flake8 `--ignore=E501,W503,E203`（run_judge/release 三脚本 + 三个测试文件）：
  exit 0。
- `git diff --check` exit 0；placeholder 扫描（TODO/TBD/FIXME/PLACEHOLDER/
  待定/待补/稍后 × docker、scripts/release、两测试文件、compose、.dockerignore、
  两文档）零命中。
- 依赖锁：uv 平台约束解析 + `--no-header` 双跑字节相等；46 包全哈希。pip 跨平台
  dry-run（supplemental）记 `not_run`：直连 PyPI 下载至 252MB nvidia-nccl 处
  停滞；期间实证 pip `--platform` 精确标签匹配与 uv glibc 兼容解析的差异，
  lock 本身经权威 PyPI 元数据核对无误。

## Detector 当前主机结果（诚实声明）

`output/evidence/docker/docker-status.json`：overall `not_run`，reason
`docker_daemon_unavailable`；CLI `pass`（29.6.2），daemon `not_run`（本机
Docker Desktop daemon 未运行）。detector 为非变更工具；从未运行
`docker_verify.py --execute-live`。

## 未执行的 live 轴（全部 not_run）

Docker live build、container health、100-step API smoke、save/load、GUI frames、
cleanup。本控制器不因静态测试成功而声称任何 live pass；第二环境复现亦为
`not_run`（Task 23 范围）。

## 复审状态

- 19.C/19.D/19.E：替代只读复审代理多轮迭代后均 **CLEAN**（本环境无 Terra/Sol
  模型路由；正式 Terra/max 复审待具备该工作流的环境补做，已在台账声明）。
- Step 9 后补提交：双轴复审要求的源码修复（software GL 钉定 + 静态测试加固）
  以 `56a46d9` (`fix: pin software GL and harden static contract tests`) 单独
  入库；Step 10 post-commit focused 于该 HEAD 重跑：**988 passed, 1 skipped**
  （62.23s），tracked 树干净（除本报告/台账），保护 diff 为空。
- 19.F 全量 closeout 双轴复审（两个独立只读代理，各两轮）：standards 轴
  1 Important（台账缺 19.E 小节）+ 4 Minor 全部修复或采纳后 **CLEAN**；spec 轴
  1 Important（5059dc5 未记录 allowlist 修正案）+ 5 Minor 全部修复或采纳后
  **CLEAN**（修正案与 allowlist 归属修正见"文件边界修正案"）。

## 保护边界

- `赛题资料.7z` 未随续作包转移、本机不存在：哈希门禁 `not_run`
  （archive_not_present_on_machine）。文件回位后必须重验
  `12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`。
- `data/intersection_data`：163 tracked = 163 disk（原机 232 disk 含 69 个
  未入库文件，不构成 tracked 官方集缺口；163 即仓库内完整官方 tracked 集）；
  worktree/index 保护 diff 均为空。

## 文件边界修正案（controller 记录）

1. `5059dc5`（export_api_contract.py 换行修复）超出 brief 文件清单：触发测试为
   全量首跑失败的 `test_checked_in_contracts_match_fresh_export`（报告上文如实
   记录）；修因为导出器在 Windows 上的换行翻译破坏跨平台确定性，属 Task 19.F
   全量门禁归零的必要修复；controller 审查通过并在此显式修正 allowlist（本环境
   无 Terra/Sol，正式补审随整体待办）。
2. `e871c38`（19.C）按 4 项复审 Important 的要求修改了
   `scripts/release/docker_status.py`（严格导出/隐私过滤/chronology 校验均在
   validator 侧），超出计划 19.C 的文件清单；属复审驱动的 file-boundary
   amendment，范围仍限 Task 19 允许路径。

## 精确 tracked 允许清单（Task 19 实现 + 本报告）

- 实现与测试（git 实证 816ed27..5059dc5 全窗口触达，无 19 窗口外路径）：
  `scripts/release/docker_status.py`、`scripts/release/docker_verify.py`、
  `scripts/run_judge.py`、`tests/test_docker_release.py`、
  `tests/test_docker_static.py`、`tests/test_judge_launcher.py`、
  `scripts/export_api_contract.py`。19.A/19.B 的 `api/realtime.py`、
  `api/server.py`、`engine/runner.py`、`web/src/*` 属 pre-Task-19 基线，
  非本任务输出。
- 19.D：`docker/requirements.in`、`docker/requirements.lock`、`docker/Dockerfile`、
  `docker-compose.yml`、`tests/test_docker_static.py`。
- 19.E：`docker/Dockerfile.gui`、`docker-compose.yml`、`.dockerignore`、
  `docker/README.md`、`docs/deployment.md`、`tests/test_docker_static.py`。
- 元数据：`task-19-report.md`（-f 添加，被 gitignore 的路径）与 `progress.md`。
- 保护路径（`赛题资料.7z`、`data/intersection_data/**`）从未进入任何提交；
  web 构建产物 `web/node_modules`、`web/test-results` 保持未跟踪。

## 冻结门禁值适配记录

- `data/intersection_data` 磁盘计数：brief 冻结值 232 系原机"163 tracked + 69
  未入库文件"的总和；本机为 163/163（tracked 集完整、保护 diff 为空）。门禁
  语义（tracked 集不可变更）未松动，数值适配在此显式记录，brief 重定基线待
  controller/用户确认。

## 遗留与移交

- Task 20–24 未开始（19.F 完成后按父计划推进；Task 20 计划已草拟于
  `docs/superpowers/plans/2026-08-28-judge-release-docs-task20.md`，该文件
  尚未入库，将随 Task 20 首个提交进入历史）。
- 已知限制：xgboost Linux 依赖链引入 nvidia-nccl（约 200MB 镜像体积）；
  pip 直连 dry-run 停滞已按计划记 not_run；正式 Terra/Sol 复审待补。
