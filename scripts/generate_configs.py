"""生成 engine/configs/ 下的增强版 sumocfg（IA W2 Day 2）。

每个 `engine/configs/demo_N.sumocfg`：
- 以相对路径引用 `data/intersection_data/` 原始文件（原始目录保持只读）；
- 保留原始配置的时间参数（begin/end/step-length）与 ignore-route-errors；
- 统一输出 tripinfo（EX 采集）、fcd（DB 时空轨迹）、summary 三类文件，
  原始配置含 queue-output 的路口（11-13、15-20）保留 queues.xml 输出。

用法：python scripts/generate_configs.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "intersection_data"
OUT_DIR = ROOT / "engine" / "configs"

TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!-- 增强版配置：由 scripts/generate_configs.py 生成，引用原始数据（只读） -->
<configuration>
    <input>
        <net-file value="{net}"/>
        <route-files value="{rou}"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="3600"/>
{step_length}    </time>
{ignore_route_errors}    <output>
        <tripinfo-output value="tripinfo.xml"/>
        <fcd-output value="traj.xml"/>
        <summary-output value="stats.xml"/>
{queue_output}    </output>
    <!-- sumo-gui 打开后自动开始播放，步间隔 50ms。
         命令行 sumo 会忽略本节，不影响批量跑批。 -->
    <gui_only>
        <start value="true"/>
        <delay value="50"/>
    </gui_only>
</configuration>
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for n in range(1, 21):
        src_dir = DATA / str(n) / "sumo工程"
        original = (src_dir / f"demo_{n}.sumocfg").read_text(encoding="utf-8")

        m = re.search(r'<step-length\s+value="([^"]+)"', original)
        step_length = (
            f'        <step-length value="{m.group(1)}"/>\n' if m else ""
        )
        ignore = (
            "    <processing>\n"
            '        <ignore-route-errors value="true"/>\n'
            "    </processing>\n"
            if "ignore-route-errors" in original
            else ""
        )
        queue = (
            '        <queue-output value="queues.xml"/>\n'
            if "queue-output" in original
            else ""
        )

        cfg = TEMPLATE.format(
            net=f"../../data/intersection_data/{n}/sumo工程/demo_{n}.net.xml",
            rou=f"../../data/intersection_data/{n}/sumo工程/demo_{n}.rou.xml",
            step_length=step_length,
            ignore_route_errors=ignore,
            queue_output=queue,
        )
        (OUT_DIR / f"demo_{n}.sumocfg").write_text(cfg, encoding="utf-8")
    print(f"已生成 20 个增强版配置到 {OUT_DIR}")


if __name__ == "__main__":
    main()
