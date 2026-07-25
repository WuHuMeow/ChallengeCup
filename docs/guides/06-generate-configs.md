# 如何生成仿真配置文件

## 目的

从 20 个路口的原始 `.sumocfg` 生成增强版配置（统一输出格式、步长、容错参数）。

## 前置条件

- 已安装项目依赖：`pip install -e .`
- `data/intersection_data/{1..20}/sumo工程/demo_N.sumocfg` 存在

## 操作步骤

```bash
python scripts/simulation/generate_configs.py
```

输出：`ca_mp/engine/configs/demo_{1..20}.sumocfg`（覆盖已有文件）

## 生成规则

增强版配置相比原始配置的改动：

| 项目 | 原始 | 增强版 |
|------|------|--------|
| step-length | 不统一 | 统一 0.1s |
| tripinfo-output | 部分有 | 全部有 |
| fcd-output (traj) | 无 | 全部有 |
| summary-output (stats) | 无 | 全部有 |
| queue-output | 部分有 | 保留原有的（路口 11-13、15-20） |
| ignore-route-errors | 部分有 | 保留原有的 |
| 数据引用 | 本地相对路径 | 指向 `data/intersection_data/` 的相对路径 |

## 示例

生成后验证配置有效性：
```bash
python scripts/validation/batch_validate.py 1 16
```

## 常见问题

**Q: 修改了原始数据后需要重新生成吗？**
A: 是的。每次修改 `data/intersection_data/` 中的原始 `.sumocfg` 后都应重新运行此脚本。

**Q: 生成的配置能直接用 sumo-gui 打开吗？**
A: 可以。配置中包含 `<gui_only>` 节（自动播放、80ms 延迟），命令行 `sumo` 会忽略此节。
