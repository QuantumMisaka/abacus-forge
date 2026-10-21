# `forge-maturation-property-packs` stale branch disposition

日期：2026-10-21。对象：`origin/forge-maturation-property-packs` 的唯一提交
`a003c55787ed1cb1d031590e338b131e12e89d75`（2026-05-20）。

## 结论

**Superseded；不要 merge。** main 自 merge base 后已独立演进，分支涉及的生产
符号和测试函数均没有 branch-only 内容；当前 main 还额外引入 property manifest、
canonical cube path、parser validation 等更完整实现和 12 个新测试函数。若现在合并，
只会在 8 个文件中重新引入旧实现并产生冲突。

机械审计结果见 [audit.json](audit.json)。

## 处置

- 该分支视为历史实现快照，不是当前在途 SPEC/PLAN；
- 不作为 property packs、CubeData 或 vacancy 功能的 merge source；
- 是否删除远端历史分支由 owner 决定；删除前可保留本 evidence 作为溯源；
- 若未来确需 backport 某个行为，必须另立 approved SPEC/PLAN，并从 current main
  重新实现/测试，不得直接 merge 该旧分支。
