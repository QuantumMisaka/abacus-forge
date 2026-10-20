# Forge 有限能力元数据与 property manifest 消费

状态：2026-10-21 用户授权按讨论方向推进的有限切片。实施见
[接续计划](../plans/2026-10-21-forge-consumption-followup.md)。
本文件细化已有 discovery 和 legacy diagnostics 的消费，不批准
[旧 Contract System Draft](2026-09-29-forge-contract-system-design.html)
的全量知识库、M4 查询 operation 或依赖图。

## 能力发现

`capabilities_document()` 保留已有 schema_version/capabilities；新增可选
`contracts` 映射，首批只含 `cohp` 与 `pyatb-cohp`。未列出的 capability
不代表没有契约，也不代表无法消费；调用方继续使用既有 request schema。

这两个条目说明 IAO 与 direct NAO 的方法、输入来源和关键数值约定，避免
调用者因名称相似而把两者当作数值等价方法。实际 operation 列表来自现有
descriptor，字段、默认值、合法值来自请求类型与对应 schema，不另写一份
参数默认值表。方法说明不替代实际输入校验或安装版本验证。

`request_schema_document()` 沿用既有入口，为新增 PyATB COHP 参数说明
矩阵单位、EF、显式 k 点/权重和路径含义；不增加运行副作用，也不创建 workspace
或 operation event。未知参数和不支持的请求仍按当前请求解码规则拒绝。

解析器标记由实际 parser（包含独立 abacuslite）维护，本切片不复制正则。
不把“可能由 SCF 生成的输入”声明成“必须由 Forge 执行 SCF”的 workflow 前提。
不为 metadata 查询加入新的 execution 状态机。

## Property manifest

沿用 [现有规范形态](2026-09-10-forge-property-manifest-design.html)：
`TaskResult.diagnostics.property_manifest`，首批 charge-density、spin-density、
charge-diff，保留既有 `forge.property-manifest/v1` 的 path、role、origin、
spin、artifact facts、missing 和同结果内 source refs。用户本次推进授权采用
这个有界消费形态；不据此将 legacy property 转为 typed capability 或 stable。

不重新实现已经存在的 builder。用一条真实调用方路径验证其价值：

1. 已有 property CLI 的 `post --json` 生成结果；
2. 独立消费示例解析 `PropertyManifest`，按角色选取派生 cube；
3. 由 `source_artifact_ids` 找出实际源文件，不根据 `SPIN1`/`chgs1` 文件名猜测；
4. 在调用方给出的 workspace 内解析路径、核对文件仍可用且与 manifest 对应，
   然后读取 cube 网格。缺输入/缺投影/改变的文件不能被当作成功交接；
5. 这条示例展示 Python 消费和 CLI 交付的组合，不定义新稳定结果协议。

当前 Paimon property adapter 仍有自己的消费路径。本轮不改写其并行 Benchmark
候选，不宣称这些 adapter 已迁移到 property_manifest。是否进一步下沉重复的
cube 处理，以实际输入与行为对照决定，不由存在一个 manifest 强制推动。

## 验证

- 原有 capability/operation/schema 字段保持；新增 metadata 可 JSON 序列化，
  每次返回脱离内部可变状态的副本；实际 schema 和方法说明相符。
- IAO 请求仍只接受 `method=iao`；PyATB 路径显式声明 direct NAO。
- 使用真实 property API/CLI 及小型 cube fixture 执行消费者；派生数值与
  source refs 对上，缺一个源文件时拒绝，文件交接后被移走/改写时拒绝。
- 测试与示例不运行 ABACUS；fixture 消费不代替材料科学或 Paimon 平台验收。
