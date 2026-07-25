# 如何跑测试 / 代码质量检查

## 目的

验证代码修改没有破坏现有功能，保持代码质量。

## 前置条件

- 已安装项目依赖：`pip install -e .`
- 已安装 pytest：`pip install pytest`

## 操作步骤

### 运行全部测试

```bash
python -m pytest tests/ -v
```

预期：66 个测试全部通过。

### 只跑单元测试

```bash
python -m pytest tests/unit/ -v
```

### 只跑集成测试

```bash
python -m pytest tests/integration/ -v
```

### 跑单个测试文件

```bash
python -m pytest tests/unit/test_algorithms.py -v
```

### 代码质量检查（lint）

```bash
bash scripts/quality/lint_check.sh
```

检查内容：
- flake8 静态分析（`ca_mp/engine/`、`ca_mp/cloud/`、`ca_mp/experiments/`）
- 调试代码残留（`breakpoint()`、`pdb.set_trace`）
- TODO/FIXME 标记

输出 `clean` 表示通过。

## 示例

修改了 CA-MP 算法后验证：
```bash
python -m pytest tests/unit/test_algorithms.py tests/unit/test_cloud.py -v
bash scripts/quality/lint_check.sh
```

## 常见问题

**Q: 测试报 ImportError？**
A: 确认已执行 `pip install -e .`，使 `ca_mp` 包可导入。

**Q: 集成测试需要 SUMO 吗？**
A: 大部分集成测试使用 MockBridge，不需要 SUMO。标注了 `@pytest.mark.sumo` 的测试需要真实 SUMO。

**Q: 新增了模块，lint 没覆盖到？**
A: `lint_check.sh` 目前只检查 `ca_mp/engine/`、`ca_mp/cloud/`、`ca_mp/experiments/`。如需扩展，编辑该脚本。
