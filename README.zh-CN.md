# 不确定性决策分析（Decision Under Uncertainty）

> 版本：1.0.0 ｜ 内嵌技能：`decision-under-uncertainty` v1.0.0

把「我觉得值」变成**可复算的概率、期望值和停止条件**。

大多数决策提示词是"数学表演"：向用户要一个他给不出的基准率、模拟一群必然趋同的专家、把同源证据当独立证据相乘，最后来一句没有阈值的「Go / No-go」。

这个包反过来做：**七步流程 + 一个拒绝编数字的计算器。**

## 修复的十个问题

| # | 原问题 | 本包做法 |
|---|---|---|
| 1 | 要用户直接给成功定义、LR、最大损失 | 结构化提问，最多 8 问 |
| 2 | 没有「信息不足先反问」 | 硬门：四项缺一不可 |
| 3 | 模拟专家委员会 + 德尔菲 | 删除；改为证据分级与独立性判定 |
| 4 | 没有基准率时编一个 | `UNKNOWN` + 宽区间 + 敏感性 |
| 5 | LR 无截断、相关证据重复乘 | 截断 0.1–10、可靠性收缩、同簇合并 |
| 6 | 串联法 Δp 相加 | 故障树 + 留一法关键度 |
| 7 | 排序公式未定义 | EV / 效用 / MCDA 事先声明 |
| 8 | 尝试次数假设独立同分布 | 定义一次尝试 + 相关性 ρ + 预算上限 |
| 9 | Go/No-go 阈值未定义 | 五条阈值预注册 |
| 10 | 模块松散、无顺序、无自检 | 固定七步 + 退出自检 |

## 七步流程

1. **定义**：决策、选项（含「什么都不做」）、时间窗、成功标准、最大损失
2. **基准率**：参考类预测；没数据就 `UNKNOWN`
3. **证据**：对数几率贝叶斯更新，LR 截断、可靠性加权、相关去重
4. **失败链**：故障树 + 留一法，找单点故障
5. **方案**：EV、期望效用、破产风险、盈亏平衡、MCDA、敏感性
6. **尝试**：定义一次尝试、相关性、预算约束、期望成本
7. **决策**：预注册阈值 → `Go` / `No-go` / `Conditional` + 停止规则 + 复盘日

## 计算器

```bash
python scripts/decision_calc.py bayes       spec.json
python scripts/decision_calc.py options     spec.json
python scripts/decision_calc.py attempts    spec.json
python scripts/decision_calc.py kelly       spec.json
python scripts/decision_calc.py faulttree   spec.json
python scripts/decision_calc.py montecarlo  spec.json
python scripts/decision_calc.py journal     spec.json
```

全部读取 JSON、输出 UTF-8 JSON，蒙特卡洛固定 seed。

自检：

```bash
python tests/selftest.py
```

## 设计原则

- **不编数字**：缺输入写 `UNKNOWN` + 原因
- **不藏权重**：排序规则在看结果前声明
- **相关性显式**：同源证据合并；尝试可以共享结果
- **敏感性必做**：单点估计不算结论
- **每条建议都带停止规则**
- **确定性**：同输入同输出

## 安装

- **Claude Code**：把 `skills/decision-under-uncertainty` 放进 `~/.claude/skills/`
- **WorkBuddy / CodeBuddy**：导入本仓库

## 适用范围

要不要做、值不值得投、成功率多少、方案怎么排、预算够试几次、哪里该停。

**不适用**：纯事实查询、已决定只要执行、价值观选择。

## 局限

- 概率质量取决于你给的证据与基准率
- 尝试次数的相关性模型是近似，不是结构模型
- 不做资产定价，不给投资建议
- 样本少时校准分数噪声大

## 许可

[PolyForm Noncommercial License 1.0.0](LICENSE)。商用需单独授权，见 [COMMERCIAL.md](COMMERCIAL.md)。

作者：李献杰 Lyon
