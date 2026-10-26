#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decision-under-uncertainty 自检：不依赖网络，固定输入 → 固定输出。"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dc", ROOT / "scripts" / "decision_calc.py")
dc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dc)

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}  {detail}")
        failures.append(name)


# 1. Bayes：相关证据合并 + 可靠性收缩
r = dc.cmd_bayes({
    "prior": 0.3,
    "evidence": [
        {"id": "E1", "lr": 3.0, "reliability": 0.8, "cluster": "market"},
        {"id": "E2", "lr": 1.5, "reliability": 0.9, "cluster": "team"},
        {"id": "E3", "lr": 0.8, "reliability": 1.0, "cluster": "market"},
    ],
    "lr_cap": [0.1, 10],
    "cluster_mode": "sqrt",
})
check("bayes.posterior", 0.35 <= r["posterior"] <= 0.55, r["posterior"])
check("bayes.cluster_merged", len(r["clusters"]) == 2, r["clusters"])

# 2. Bayes：LR 截断
r = dc.cmd_bayes({"prior": 0.5, "evidence": [{"id": "X", "lr": 1000}], "lr_cap": [0.1, 10]})
check("bayes.lr_cap", list(r["clusters"].values())[0] == 10.0, r["clusters"])
check("bayes.capped_posterior", abs(r["posterior"] - 10 / 11) < 0.01, r["posterior"])

# 3. Options：排序 + 破产 + 盈亏平衡
r = dc.cmd_options({
    "capital": 100000,
    "options": [
        {"name": "A", "p": 0.3, "impl_prob": 0.9, "gain": 100000, "loss": 50000, "cost": 10000},
        {"name": "B", "p": 0.6, "impl_prob": 1.0, "gain": 50000, "loss": 20000, "cost": 5000},
    ],
})
check("options.rank", r["ranked"][0]["name"] == "B", [x["name"] for x in r["ranked"]])
check("options.ev_a", abs(r["ranked"][1]["ev"] - (-19500)) < 1, r["ranked"][1]["ev"])
check("options.ev_b", abs(r["ranked"][0]["ev"] - 17000) < 1, r["ranked"][0]["ev"])

r = dc.cmd_options({
    "capital": 10000,
    "options": [{"name": "Ruin", "p": 0.5, "gain": 100000, "loss": 50000, "cost": 10000}],
})
check("options.ruin", r["ranked"][0]["risk_of_ruin"] is True)

# 4. Attempts：独立 vs 相关
r = dc.cmd_attempts({"p": 0.05, "attempts": 20, "correlation": 0.2,
                     "cost_per_attempt": 1000, "gain": 100000, "loss": 5000})
check("attempts.independent", abs(r["p_success_independent"] - 0.6415) < 0.01, r["p_success_independent"])
check("attempts.correlated", abs(r["p_success_correlated"] - 0.5232) < 0.02, r["p_success_correlated"])

# 5. Kelly
r = dc.cmd_kelly({"p": 0.55, "gain": 1.0, "loss": 1.0, "fraction_cap": 0.25})
check("kelly.full", abs(r["kelly_full"] - 0.10) < 0.001, r["kelly_full"])

# 6. Fault tree：串联/并联 + 关键度
r = dc.cmd_faulttree({
    "tree": {"mode": "serial", "children": [
        {"id": "A", "r": 0.9},
        {"mode": "parallel", "children": [{"id": "B", "r": 0.8}, {"id": "C", "r": 0.85}]},
        {"id": "D", "r": 0.95},
    ]}
})
check("faulttree.system", abs(r["system_reliability"] - 0.82935) < 0.001, r["system_reliability"])
check("faulttree.criticality_count", len(r["criticality"]) == 4)

# 7. Monte Carlo：同 seed 同结果
spec_mc = {"n": 2000, "seed": 7, "options": [{
    "name": "M",
    "p": {"dist": "triangular", "low": 0.2, "mode": 0.3, "high": 0.45},
    "gain": {"dist": "triangular", "low": 80000, "mode": 100000, "high": 130000},
    "loss": {"dist": "triangular", "low": 30000, "mode": 50000, "high": 70000},
    "cost": {"dist": "uniform", "low": 8000, "high": 12000},
}]}
a = dc.cmd_montecarlo(spec_mc)
b = dc.cmd_montecarlo(spec_mc)
check("montecarlo.deterministic", a["options"][0]["p50"] == b["options"][0]["p50"], a["options"][0])

# 8. Journal：追加 + 评估 Brier
with tempfile.TemporaryDirectory() as td:
    jp = str(Path(td) / "journal.json")
    dc.cmd_journal({"action": "add", "path": jp, "entry": {"id": "D1", "p": 0.7, "decision": "test"}})
    rj = dc.cmd_journal({"action": "evaluate", "path": jp, "id": "D1", "outcome": 1})
    check("journal.brier", abs(rj["brier"] - 0.09) < 0.001, rj["brier"])

print()
if failures:
    print(f"FAILED: {len(failures)} -> {failures}")
    sys.exit(1)
print("ALL PASS")
