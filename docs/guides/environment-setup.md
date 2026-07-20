---
title: 环境配置指南
author: D组
created: 2026-07-20
group: D
status: final
---

# 环境配置指南

## 必需软件

| 软件 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 算法开发、数据处理 |
| SUMO | 1.26+ | 交通仿真 |
| Git | 2.x | 版本控制 |

## SUMO 安装

### Windows

1. 下载：https://sumo.dlr.de/docs/Downloading.php
2. 运行安装包，默认路径 `C:\Program Files\Eclipse\Sumo`
3. 设置环境变量：
   - 变量名：`SUMO_HOME`
   - 变量值：`C:\Program Files\Eclipse\Sumo`
4. 验证：打开新终端，运行 `sumo --version`

### 注意

- 项目数据由多个 SUMO 版本生成（1.13~1.27），建议安装 1.26+ 以获得最好兼容性
- 如果某些路口报错，记录到 `docs/faq/sumo-pitfalls.md`

## Python 环境

### 方式一：venv + pip

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### 方式二：conda

```bash
conda env create -f environment.yml
conda activate xiong-an-traffic
```

## 验证环境

```bash
python -c "import traci; import sumolib; import pandas; print('OK')"
sumo --version
git --version
```

## 常见问题

- SUMO_HOME 未设置：Python 中 `import traci` 会报错
- pip 安装 traci 失败：确保 Python 版本 >= 3.8
- conda 和 pip 混用：建议只用一种
