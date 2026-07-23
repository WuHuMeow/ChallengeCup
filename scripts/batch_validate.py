"""批量 3600 步全量验证（IA W2 Day 3）。

对 20 个路口使用 `engine/configs/` 增强版配置各跑一次完整仿真（3600 仿真秒，
无 GUI），记录运行时间、完成车辆数（tripinfo 行数）、报错信息，
输出控制台汇总并写入 `docs/batch_validate_report.md`，
最后估算 360 次实验（20 路口 × 3 算法 × 2 流量 × 3 种子）总时长。

用法：
    python scripts/batch_validate.py            # 全部 20 路口
    python scripts/batch_validate.py 1 11 16    # 指定路口
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from defusedxml import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
CFG_DIR = ROOT / "engine" / "configs"
OUT_ROOT = ROOT / "output" / "validate"
REPORT = ROOT / "docs" / "batch_validate_report.md"


def run_one(n: int, steps: int = 3600) -> dict:
    cfg = CFG_DIR / f"demo_{n}.sumocfg"
    out = OUT_ROOT / str(n)
    out.mkdir(parents=True, exist_ok=True)
    # SUMO 会把 output-prefix 按配置文件所在目录拼接（不识别 Windows 盘符为
    # 绝对路径），因此传入相对 engine/configs/ 的相对路径。
    prefix = Path(*([".."] * len(CFG_DIR.relative_to(ROOT).parts))) / "output" / "validate" / str(n)
    t0 = time.perf_counter()
    r = subprocess.run(
        [
            "sumo", "-c", str(cfg), "--no-step-log", "true",
            "-e", str(steps), "--output-prefix", str(prefix).replace("\\", "/") + "/",
        ],
        capture_output=True,
        text=True,
        cwd=CFG_DIR,
    )
    tripinfo = out / "tripinfo.xml"
    finished = len(ET.parse(tripinfo).getroot()) if tripinfo.exists() else 0
    return {
        "id": n,
        "ok": r.returncode == 0 and "Error" not in r.stderr,
        "elapsed": time.perf_counter() - t0,
        "finished": finished,
        "err": r.stderr.strip().replace("\n", " ")[:150],
    }


def main() -> int:
    ids = [int(a) for a in sys.argv[1:]] or list(range(1, 21))
    rows = [run_one(n) for n in ids]
    total = sum(r["elapsed"] for r in rows)
    n_pass = sum(r["ok"] for r in rows)

    lines = []
    for r in rows:
        line = (
            f"路口 {r['id']:>2} {'PASS' if r['ok'] else 'FAIL'} "
            f"{r['elapsed']:7.1f}s finished={r['finished']:>5} {r['err']}"
        )
        print(line)
        lines.append(line)
    est_h = total * 18 / 3600  # 360 次实验 = 20 路口 × 18 次/路口
    summary = (
        f"{n_pass}/{len(rows)} PASS，20 路口合计 {total:.0f}s，"
        f"估算 360 次实验 ≈ {est_h:.1f}h"
    )
    print(summary)

    REPORT.write_text(
        "# 批量 3600 步验证报告（IA W2）\n\n"
        f"> 由 `scripts/batch_validate.py` 生成；输出目录 `output/validate/`。\n\n"
        "```text\n" + "\n".join(lines) + f"\n{summary}\n```\n",
        encoding="utf-8",
    )
    return 0 if n_pass == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
