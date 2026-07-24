# 批量 3600 步验证报告（IA W2）

> 由 `scripts/validation/batch_validate.py` 生成；输出目录 `output/validate/`。

```text
路口  1 PASS     0.7s finished= 1664 
路口  2 PASS     0.4s finished=  998 
路口  3 PASS     0.5s finished= 1628 
路口  4 PASS     0.5s finished= 1315 
路口  5 PASS     0.3s finished=  987 
路口  6 PASS     0.8s finished=  959 
路口  7 PASS     0.4s finished=  985 
路口  8 PASS     0.8s finished= 1791 
路口  9 PASS     0.9s finished= 1841 Warning: Missing yellow phase in tlLogic 'J1', program '0' for tl-index 7 when switching to phase 4.
路口 10 PASS     0.4s finished=  916 
路口 11 PASS     8.3s finished= 2546 Warning: Unused states in tlLogic 'J2', program '0' in phase 0 after tl-index 17 Warning: Unsafe green phase 0 in tlLogic 'J2', program '0'. Lane '-E0
路口 12 PASS    12.0s finished= 2558 Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are
路口 13 PASS     7.4s finished= 1345 
路口 14 PASS     0.6s finished=  940 
路口 15 PASS     6.6s finished= 2607 
路口 16 PASS     5.3s finished= 2080 
路口 17 PASS     1.4s finished=  618 
路口 18 PASS     6.3s finished= 2707 Warning: Unsafe green phase 0 in tlLogic 'J1', program '0'. Lane '-E0_0' is targeted by 2 'G'-links. (use 'g' instead) Overall 4 lanes in 2 phases are
路口 19 PASS     2.4s finished= 1133 
路口 20 PASS     3.4s finished= 1365 
20/20 PASS，20 路口合计 59s，估算 360 次实验 ≈ 0.3h
```
