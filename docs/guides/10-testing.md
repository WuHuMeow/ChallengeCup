# 如何跑测试 / 代码质量检查

## 目的

验证代码修改没有破坏现有功能，保持代码质量。

## 前置条件

- 已安装项目依赖：`pip install -e .`
- 已安装 pytest：`pip install pytest`

## 操作步骤

### 运行全部测试

```bash
python -m pytest tests/ -q
```

当前基线预期：198 个测试全部通过。测试数以后如有变化，以实际无失败输出为准。

### 按模块运行

```bash
python -m pytest tests/test_algorithms.py tests/test_cloud.py -q
```

### 跑单个测试文件

```bash
python -m pytest tests/test_algorithms.py -q
```

### 代码质量检查（lint）

```bash
bash scripts/quality/lint_check.sh
```

检查内容：
- flake8 静态分析（`engine/`、`cloud/`、`experiments/`）
- 调试代码残留（`breakpoint()`、`pdb.set_trace`）
- TODO/FIXME 标记

输出 `clean` 表示通过。

## 示例

修改了 CA-MP 算法后验证：
```bash
python -m pytest tests/test_algorithms.py tests/test_cloud.py -v
bash scripts/quality/lint_check.sh
```

## 常见问题

**Q: 测试报 ImportError？**
A: 确认已执行 `pip install -e .`，使 `项目包`可导入。

**Q: 集成测试需要 SUMO 吗？**
A: 自动化回归以 MockBridge 和静态契约为主，不等于本地 SUMO、Docker live 或第二机器
复现证据。真实 IA/IB 验收使用 `scripts/verify_ia_ib.py`，未执行的外部轴必须为 `not_run`。

**Q: 新增了模块，lint 没覆盖到？**
A: `lint_check.sh` 目前只检查 `engine/`、`cloud/`、`experiments/`。如需扩展，编辑该脚本。
