# SUMO 环境安装指南（IA W2 Day 5）

> 目标：在一台干净机器上装出与本项目一致的仿真环境（SUMO 1.27.1 + Python 接口）。
> 本项目 20 个路口已在 SUMO 1.27.1 下全部验证通过（见 `docs/reports/sumo-migration-log.md`）。

## 1. Windows 安装

1. 打开 [SUMO 官方下载页](https://sumo.dlr.de/docs/Downloads.html)，下载 Windows 安装包（`sumo-win64-1.27.1.msi` 或更新）。
2. 运行安装包，默认安装到 `C:\Program Files (x86)\Eclipse\Sumo`。
3. 验证：新开终端执行

```bash
sumo --version
# 期望输出：Eclipse SUMO sumo 1.27.1（或更高）
```

## 2. 环境变量（SUMO_HOME / PATH）

Windows（系统属性 → 环境变量，或用管理员 PowerShell 永久写入）：

```powershell
[Environment]::SetEnvironmentVariable("SUMO_HOME", "C:\Program Files (x86)\Eclipse\Sumo", "User")
[Environment]::SetEnvironmentVariable("PATH", "$env:PATH;C:\Program Files (x86)\Eclipse\Sumo\bin", "User")
```

Linux/macOS（写入 `~/.bashrc` 或 `~/.zshrc`）：

```bash
export SUMO_HOME=/usr/share/sumo        # apt 安装时
export PATH="$SUMO_HOME/bin:$PATH"
```

> 注意：`SUMO_HOME` 必须指向**安装根目录**（包含 `bin/`、`tools/` 的那一级），不是 `bin/` 本身。

## 3. Python 接口（traci / libsumo / sumolib）

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
python -c "import traci; print('traci ok')"
python -c "import sumolib; print('sumolib ok')"
```

- pip 版 `traci`/`sumolib` 与 SUMO 版本解耦，`requirements.txt` 锁定 `>=1.18.0`。
- `engine/traci_bridge.py` 会在存在 `SUMO_HOME` 时把 `$SUMO_HOME/tools` 加入 `sys.path`，两种方式任选其一即可。

## 4. 常见报错

| 报错 | 原因 | 解决 |
|------|------|------|
| `无法导入 traci。请安装 SUMO 并设置 SUMO_HOME…` | 未装 pip 依赖且 `SUMO_HOME` 未设置 | `pip install -r requirements.txt`，并按第 2 节设置环境变量 |
| `sumo: command not found` | `bin/` 未加入 PATH | 见第 2 节；设置后**重开终端** |
| `Error: The network file format version '1.20' is not supported` | SUMO 版本过旧（< 1.20） | 升级到 1.27.1；Ubuntu 不要用默认 apt 源（只有 1.12.0），用 `ppa:sumo/stable`（见 `docs/notes/docker-sumo-research.md`） |
| `Warning: Unsafe green phase …` | 主办方原始路网遗留（路口 11/12/18） | 不影响运行，保留即可（见 `docs/reports/sumo-migration-log.md`） |
| `Warning: Missing yellow phase …` | 路口 9 原始配时缺黄灯相位 | 同上，不影响运行 |
| 输出文件写到错误目录 | SUMO 把 `--output-prefix` 当相对路径拼到配置文件目录 | 传**相对配置文件的相对路径**（参考 `scripts/validation/batch_validate.py`） |

## 5. 安装后自检

```bash
python scripts/validation/validate_all.py     # 期望 20/20 PASS
```
