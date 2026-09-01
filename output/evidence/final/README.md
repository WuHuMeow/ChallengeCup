# 最终发布验证证据

本目录保存 Task 23 的冻结验证产物。`release-manifest.json` 绑定发布副本
（`output/release-candidate/`）的清单哈希、代码提交、环境版本、测试命令结果、
Docker 状态（`not_run`）与运行时验证（native 发布副本 headless 模式）的逐项
`pass`/`fail`/`not_run` 结论。

- 运行时验证命令：
  `python scripts/release/verify_package.py package output/release-candidate`
  `python scripts/release/verify_package.py runtime --base-url http://127.0.0.1:8801 --gui-mode headless`
- 未执行的轴一律 `not_run`，不得由静态检查推断为 pass。
