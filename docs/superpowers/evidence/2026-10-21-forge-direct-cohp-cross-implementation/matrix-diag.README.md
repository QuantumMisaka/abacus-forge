# 矩阵级核查

在两条 direct NAO 路径读取各自输入后，抽取同一 36 k 点上的 Si1 `s/p`
`H(k)`/`S(k)` 子块比较。`abacus-cohp-lcao` 使用 ABACUS `data-*-H/S` 与 WFC 路径；
PyATB 使用同一 sparse `H(R)/S(R)` 重建。PyATB `HR_unit=Ry`，比较前统一为 eV。

[.matrix-diag.json](matrix-diag.json) 记录：

- selected `H` block：`max_abs=1.493e-6 eV`，`rms=4.943e-7 eV`；
- selected `S` block：`max_abs=5.468e-9`；
- 该核查独立确认 sparse HR/SR 重建不是通过复用 WFC 输出伪装，也不是逐字节同一矩阵。

差异量级与两条实现的离散 ICOHP `1.409e-3 eV` 残差一致，不构成方法阻断。
