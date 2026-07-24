"""批量验证 20 个路口在新版 SUMO 下的兼容性（IA W1 Day 2）。

对每个路口执行 `sumo -c demo_N.sumocfg --no-step-log -e 100`（不修改任何原始文件），
记录成功/失败、错误信息、运行时间，并从 `.net.xml` 提取原始版本信息。

用法：
    python scripts/validation/validate_all.py            # 验证全部 20 个路口
    python scripts/validation/validate_all.py 1 11 16    # 只验证指定路口
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "intersection_data"


def detect_app_version(net_xml: Path) -> str:
    """从 net.xml 头部注释提取生成该文件的 SUMO/netedit 应用版本。"""
    head = net_xml.read_text(encoding="utf-8", errors="replace")[:2000]
    m = re.search(r"netedit\s+Version\s+([\d.]+)", head) or re.search(
        r"netedit\s+([\d.]+)", head
    )
    return m.group(1) if m else "?"


def detect_net_version(net_xml: Path) -> str:
    """提取 <net version="..."> 路网格式版本。"""
    m = re.search(
        r'<net[^>]*version="([^"]+)"',
        net_xml.read_text(encoding="utf-8", errors="replace"),
    )
    return m.group(1) if m else "?"


def detect_step_length(cfg: Path) -> str:
    """从 sumocfg 提取 <step-length>，缺省为 SUMO 默认 1.0s。"""
    m = re.search(r'<step-length\s+value="([^"]+)"', cfg.read_text(encoding="utf-8"))
    return m.group(1) if m else "1.0 (默认)"


def validate(n: int, end: int = 100) -> dict:
    cfg = DATA / str(n) / "sumo工程" / f"demo_{n}.sumocfg"
    net_xml = cfg.parent / f"demo_{n}.net.xml"
    # 输出文件（tripinfo 等）写到 output/validate_quick/，保持原始数据目录只读。
    # SUMO 把 --output-prefix 按配置文件目录拼接，故用相对路径（四级回退到仓库根）。
    scratch = ROOT / "output" / "validate_quick" / str(n)
    scratch.mkdir(parents=True, exist_ok=True)
    prefix = Path(*([".."] * len(cfg.parent.relative_to(ROOT).parts)))
    prefix = prefix / "output" / "validate_quick" / str(n)
    t0 = time.perf_counter()
    r = subprocess.run(
        ["sumo", "-c", str(cfg), "--no-step-log", "true", "-e", str(end),
         "--output-prefix", str(prefix).replace("\\", "/") + "/"],
        capture_output=True,
        text=True,
        cwd=cfg.parent,
    )
    return {
        "id": n,
        "ok": r.returncode == 0 and "Error" not in r.stderr,
        "elapsed": time.perf_counter() - t0,
        "err": r.stderr.strip().replace("\n", " ")[:200],
        "app_version": detect_app_version(net_xml),
        "net_version": detect_net_version(net_xml),
        "step_length": detect_step_length(cfg),
    }


def main() -> int:
    ids = [int(a) for a in sys.argv[1:]] or list(range(1, 21))
    results = [validate(n) for n in ids]
    n_pass = 0
    for res in results:
        n_pass += res["ok"]
        print(
            f"[{'PASS' if res['ok'] else 'FAIL'}] 路口 {res['id']:>2} "
            f"app={res['app_version']:<8} net={res['net_version']:<5} "
            f"step={res['step_length']:<10} {res['elapsed']:5.1f}s {res['err']}"
        )
    print(f"\n{n_pass}/{len(results)} PASS")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
