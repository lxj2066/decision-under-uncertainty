#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
decision_calc.py — 不确定性决策计算器（v1.0.0）

子命令：
  bayes       贝叶斯更新（LR 截断 / 可靠性加权 / 相关证据合并 / 敏感性）
  options     方案排序（EV / 期望效用 / 风险破产 / MCDA / 敏感性）
  attempts    重复尝试（独立 vs 相关 / 预算约束 / 期望成本）
  kelly       仓位与增长率（Kelly / 半 Kelly / 对数增长）
  faulttree   故障树（串联/并联 / 关键度 / 单点故障）
  montecarlo  蒙特卡洛（分布输入 → EV 分位数）
  journal     决策日志与校准（Brier 分数）

用法：
  python decision_calc.py bayes spec.json
  python decision_calc.py options spec.json --out result.json

所有输出为 UTF-8 JSON，便于下游报告或复算。
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

VERSION = "1.0.0"


# ------------------------------------------------------------------ helpers
def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def odds(p):
    p = clamp(p, 1e-9, 1 - 1e-9)
    return p / (1 - p)


def inv_odds(o):
    return o / (1 + o)


def logit(p):
    return math.log(odds(p))


def expit(x):
    return 1 / (1 + math.exp(-x))


def load_spec(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("spec 必须是 JSON 对象")
    return data


def emit(result, out=None):
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    print(text)


# ------------------------------------------------------------------ bayes
def evidence_effective_lr(item, cap, mode_default="reliability"):
    """返回 (lr_eff, notes)。reliability ∈ [0,1]，把 LR 向 1 收缩。"""
    lr = float(item.get("lr", 1.0))
    rel = item.get("reliability", 1.0)
    try:
        rel = float(rel)
    except (TypeError, ValueError):
        rel = 1.0
    rel = clamp(rel, 0.0, 1.0)
    notes = []
    if lr <= 0:
        notes.append("LR<=0 非法，按 1 处理")
        lr = 1.0
    if rel < 1.0:
        lr = lr ** rel
        notes.append(f"按可靠性 {rel:.2f} 收缩")
    lo, hi = cap
    if lr < lo:
        notes.append(f"截断到下限 {lo}")
        lr = lo
    if lr > hi:
        notes.append(f"截断到上限 {hi}")
        lr = hi
    return lr, notes


def cluster_merge(lrs, mode):
    if len(lrs) == 1:
        return lrs[0]
    if mode == "max":
        return max(lrs, key=lambda x: abs(math.log(x)))
    geo = math.exp(sum(math.log(x) for x in lrs) / len(lrs))
    if mode == "geomean":
        return geo
    # 默认 sqrt：相关证据叠加时按 sqrt(n) 折减
    return 1.0 + (geo - 1.0) / math.sqrt(len(lrs))


def cmd_bayes(spec):
    prior = float(spec.get("prior", 0.5))
    prior = clamp(prior, 1e-6, 1 - 1e-6)
    cap = spec.get("lr_cap", [0.1, 10.0])
    cap = (float(cap[0]), float(cap[1]))
    mode = spec.get("cluster_mode", "sqrt")

    clusters = {}
    detail = []
    for item in spec.get("evidence", []):
        lr_eff, notes = evidence_effective_lr(item, cap)
        cid = item.get("cluster") or item.get("id") or "default"
        clusters.setdefault(cid, []).append(lr_eff)
        detail.append({
            "id": item.get("id"),
            "cluster": cid,
            "lr_raw": item.get("lr"),
            "lr_eff": round(lr_eff, 4),
            "notes": notes,
            "note": item.get("note", ""),
        })

    merged = {cid: cluster_merge(v, mode) for cid, v in clusters.items()}
    lo = odds(prior)
    for cid, lr in merged.items():
        lo *= lr
    posterior = inv_odds(lo)

    # 先验敏感性
    pr = spec.get("prior_range") or [max(1e-4, prior / 2), min(1 - 1e-4, prior * 2)]
    post_lo = inv_odds(odds(float(pr[0])) * math.prod(merged.values()))
    post_hi = inv_odds(odds(float(pr[1])) * math.prod(merged.values()))

    # LR ±20% 敏感性
    post_min = posterior
    post_max = posterior
    for cid, lr in merged.items():
        others = math.prod(v for k, v in merged.items() if k != cid)
        for factor in (0.8, 1.2):
            p = inv_odds(odds(prior) * others * clamp(lr * factor, cap[0], cap[1]))
            post_min = min(post_min, p)
            post_max = max(post_max, p)

    warnings = []
    if len(clusters) == 0:
        warnings.append("没有证据，后验等于先验")
    if spec.get("prior") is None:
        warnings.append("未提供先验：默认 0.5，请说明理由")
    if any(abs(math.log(x)) > math.log(5) for x in merged.values()):
        warnings.append("存在强证据（|log LR|>log 5），确认它真的独立且可靠")
    if len(merged) < len(detail):
        warnings.append(f"{len(detail) - len(merged)} 条证据因同簇被合并，避免重复计算")

    return {
        "tool": "decision_calc",
        "version": VERSION,
        "command": "bayes",
        "prior": round(prior, 6),
        "posterior": round(posterior, 6),
        "posterior_pct": f"{posterior * 100:.1f}%",
        "log_odds": round(math.log(lo), 4),
        "clusters": {k: round(v, 4) for k, v in merged.items()},
        "evidence": detail,
        "sensitivity": {
            "prior_range": [round(float(pr[0]), 4), round(float(pr[1]), 4)],
            "posterior_from_prior_range": [round(post_lo, 6), round(post_hi, 6)],
            "posterior_from_lr_pm20pct": [round(post_min, 6), round(post_max, 6)],
        },
        "warnings": warnings,
    }


# ------------------------------------------------------------------ options
def utility(x, a):
    """指数效用：a=0 风险中性；a>0 风险厌恶。"""
    if a <= 0:
        return x
    return (1 - math.exp(-a * x)) / a


def normalize_criteria(opts, weights):
    """把原始分映射到 0-100；direction=cost 的取反。"""
    out = {}
    for key, w in weights.items():
        raw = []
        for o in opts:
            c = (o.get("criteria") or {}).get(key)
            raw.append(float(c) if c is not None else None)
        vals = [x for x in raw if x is not None]
        lo, hi = (min(vals), max(vals)) if vals else (0, 1)
        for o, v in zip(opts, raw):
            if v is None:
                continue
            direction = (o.get("criteria_direction") or {}).get(key)
            if direction is None:
                direction = "cost" if key.lower() in ("risk", "cost", "time", "风险", "成本") else "benefit"
            s = 50.0 if hi == lo else (v - lo) / (hi - lo) * 100
            if direction == "cost":
                s = 100 - s
            out.setdefault(o["name"], {})[key] = round(s, 1)
    return out


def cmd_options(spec):
    capital = float(spec.get("capital", 0) or 0)
    a = float(spec.get("risk_aversion", 0) or 0)
    opts = spec.get("options", [])
    weights = spec.get("weights") or {}
    norm = normalize_criteria(opts, weights) if weights else {}

    rows = []
    for o in opts:
        p = clamp(float(o.get("p", 0)), 0, 1)
        q = clamp(float(o.get("impl_prob", 1.0)), 0, 1)
        p_eff = p * q
        gain = float(o.get("gain", 0))
        loss = float(o.get("loss", 0))
        cost = float(o.get("cost", 0))
        ev = p_eff * gain - (1 - p_eff) * loss - cost
        eu = p_eff * utility(gain - cost, a) + (1 - p_eff) * utility(-loss - cost, a)
        max_loss = loss + cost
        ruin = capital > 0 and max_loss >= capital
        breakeven = (loss + cost) / (gain + loss) if (gain + loss) > 0 else None
        mcda = None
        if weights and o["name"] in norm:
            mcda = sum(norm[o["name"]].get(k, 50) * w for k, w in weights.items())
        rows.append({
            "name": o.get("name"),
            "p": round(p, 4),
            "impl_prob": round(q, 4),
            "p_effective": round(p_eff, 4),
            "gain": gain, "loss": loss, "cost": cost,
            "max_loss": max_loss,
            "ev": round(ev, 2),
            "expected_utility": round(eu, 2),
            "break_even_p": round(breakeven, 4) if breakeven is not None else None,
            "risk_of_ruin": bool(ruin),
            "mcda_score": round(mcda, 1) if mcda is not None else None,
            "criteria_scores": norm.get(o.get("name")),
        })

    by = spec.get("rank_by", "ev")
    key = "mcda_score" if by == "mcda" else ("expected_utility" if by == "utility" else "ev")
    ranked = sorted(rows, key=lambda r: (r[key] is None, -(r[key] or 0)))

    # 单因素敏感性：p / gain / loss 各 ±20%
    sens = []
    for o in opts:
        p = float(o.get("p", 0)); q = float(o.get("impl_prob", 1.0))
        gain = float(o.get("gain", 0)); loss = float(o.get("loss", 0)); cost = float(o.get("cost", 0))
        base = p * q * gain - (1 - p * q) * loss - cost
        swings = {}
        for name, f in (("p+20%", (min(1, p * 1.2), q, gain, loss)),
                        ("p-20%", (max(0, p * 0.8), q, gain, loss)),
                        ("gain+20%", (p, q, gain * 1.2, loss)),
                        ("gain-20%", (p, q, gain * 0.8, loss)),
                        ("loss+20%", (p, q, gain, loss * 1.2)),
                        ("loss-20%", (p, q, gain, loss * 0.8))):
            pp, qq, gg, ll = f
            swings[name] = round(pp * qq * gg - (1 - pp * qq) * ll - cost, 2)
        worst = min(swings.values()); best = max(swings.values())
        sens.append({"name": o.get("name"), "base_ev": round(base, 2), "swings": swings,
                     "range": [worst, best], "range_width": round(best - worst, 2)})
    sens.sort(key=lambda x: -x["range_width"])

    warnings = []
    for r in rows:
        if r["risk_of_ruin"]:
            warnings.append(f"{r['name']}：最大损失 {r['max_loss']} ≥ 可承受资本 {capital}，存在破产风险")
        if r["break_even_p"] is not None and r["p_effective"] < r["break_even_p"]:
            warnings.append(f"{r['name']}：有效成功率低于盈亏平衡点")
        if r["p"] >= 0.95:
            warnings.append(f"{r['name']}：成功率 ≥95%，检查是否存在过度自信")
    if capital <= 0:
        warnings.append("未提供 capital，无法评估破产风险")

    return {
        "tool": "decision_calc", "version": VERSION, "command": "options",
        "capital": capital,
        "risk_aversion": a,
        "ranked": ranked,
        "sensitivity": sens,
        "warnings": warnings,
        "notes": [
            "EV = p_eff*gain - (1-p_eff)*loss - cost",
            "p_eff = p * impl_prob；impl_prob 是计划按预期执行的概率",
            "max_loss = loss + cost；≥ capital 判破产风险",
            "MCDA 只在提供 weights 时计算；权重和应为 1",
        ],
    }


# ------------------------------------------------------------------ attempts
def cmd_attempts(spec):
    p = clamp(float(spec.get("p", 0)), 0, 1)
    n = int(spec.get("attempts", 1))
    rho = clamp(float(spec.get("correlation", 0) or 0), 0, 0.999)
    cost = float(spec.get("cost_per_attempt", 0))
    gain = float(spec.get("gain", 0))
    loss = float(spec.get("loss", 0))
    budget = spec.get("budget")
    capital = float(spec.get("capital", 0) or 0)

    p_ind = 1 - (1 - p) ** n
    # 相关性的混合近似：ρ 比例的尝试共享同一结果，其余独立
    p_corr = rho * p + (1 - rho) * p_ind
    expected_attempts = 1 / p if p > 0 else float("inf")
    expected_cost = cost * min(expected_attempts, n)

    n_budget = n
    if budget is not None and cost > 0:
        n_budget = min(n, int(float(budget) // cost))
    p_budget = 1 - (1 - p) ** n_budget
    p_budget_corr = rho * p + (1 - rho) * p_budget

    ev = p_budget_corr * gain - (1 - p_budget_corr) * loss - expected_cost
    breakeven = (loss + cost * expected_attempts) / (gain + loss) if (gain + loss) > 0 else None
    ruin = capital > 0 and loss >= capital

    warnings = []
    if rho > 0:
        warnings.append(f"相关性 ρ={rho}：独立同分布假设不成立，已用混合模型折减")
    if n > 10 and rho > 0.1:
        warnings.append("尝试次数多且相关性强：结果高度依赖单次质量，堆次数收益有限")
    if p <= 0:
        warnings.append("单次成功率必须 >0")
    if breakeven is not None and p < breakeven:
        warnings.append("单次成功率低于盈亏平衡点")

    return {
        "tool": "decision_calc", "version": VERSION, "command": "attempts",
        "p_per_attempt": round(p, 4),
        "attempts": n,
        "correlation": rho,
        "p_success_independent": round(p_ind, 6),
        "p_success_correlated": round(p_corr, 6),
        "expected_attempts": None if math.isinf(expected_attempts) else round(expected_attempts, 2),
        "expected_cost": round(expected_cost, 2),
        "budget_limited_attempts": n_budget,
        "p_success_within_budget": round(p_budget_corr, 6),
        "ev": round(ev, 2),
        "break_even_p": round(breakeven, 4) if breakeven is not None else None,
        "risk_of_ruin": bool(ruin),
        "warnings": warnings,
    }


# ------------------------------------------------------------------ kelly
def cmd_kelly(spec):
    p = clamp(float(spec.get("p", 0.5)), 1e-6, 1 - 1e-6)
    gain = float(spec.get("gain", 1.0))
    loss = float(spec.get("loss", 1.0))
    b = gain / loss if loss > 0 else None
    if not b or b <= 0:
        raise ValueError("gain/loss 必须 >0")
    f_full = (p * b - (1 - p)) / b
    f_full = max(0.0, f_full)
    cap = float(spec.get("fraction_cap", 0.25))
    f_used = min(f_full, cap)
    growth = p * math.log(1 + f_used * b) + (1 - p) * math.log(max(1e-9, 1 - f_used))
    return {
        "tool": "decision_calc", "version": VERSION, "command": "kelly",
        "p": round(p, 4), "b": round(b, 4),
        "kelly_full": round(f_full, 4),
        "kelly_half": round(f_full / 2, 4),
        "kelly_quarter": round(f_full / 4, 4),
        "recommended_fraction": round(f_used, 4),
        "fraction_cap": cap,
        "expected_log_growth_per_bet": round(growth, 6),
        "warnings": (["全 Kelly 波动极大，实盘建议 ≤ 半 Kelly"] if f_full > 0 else ["负期望，不应下注"]),
    }


# ------------------------------------------------------------------ fault tree
def eval_tree(node):
    if "id" in node:
        return float(node.get("r", 1.0))
    mode = node.get("mode", "serial")
    children = [eval_tree(c) for c in node.get("children", [])]
    if not children:
        return 1.0
    if mode == "parallel":
        return 1 - math.prod(1 - r for r in children)
    return math.prod(children)


def collect_leaves(node, path=""):
    if "id" in node:
        return [(node["id"], node, path)]
    out = []
    for c in node.get("children", []):
        out.extend(collect_leaves(c, path + "/" + c.get("id", c.get("mode", "?"))))
    return out


def cmd_faulttree(spec):
    tree = spec.get("tree")
    if not tree:
        raise ValueError("缺少 tree")
    base = eval_tree(tree)
    leaves = collect_leaves(tree)
    criticality = []
    for lid, leaf, path in leaves:
        old = leaf.get("r", 1.0)
        leaf["r"] = 1.0
        r_perfect = eval_tree(tree)
        leaf["r"] = 0.0
        r_failed = eval_tree(tree)
        leaf["r"] = old
        criticality.append({
            "id": lid, "path": path, "reliability": old,
            "if_perfect_delta": round(r_perfect - base, 6),
            "if_failed_delta": round(r_failed - base, 6),
            "single_point_of_failure": (r_failed < 0.5),
        })
    criticality.sort(key=lambda x: x["if_failed_delta"])
    return {
        "tool": "decision_calc", "version": VERSION, "command": "faulttree",
        "system_reliability": round(base, 6),
        "system_failure_probability": round(1 - base, 6),
        "criticality": criticality,
        "warnings": ["关键度用留一法（单点移除）计算，不假设各环节独立贡献可相加",
                     "single_point_of_failure = 该环节失效后系统可靠度 < 0.5"],
    }


# ------------------------------------------------------------------ monte carlo
def sample(dist):
    kind = dist.get("dist", "triangular")
    if kind == "triangular":
        return random.triangular(dist["low"], dist["high"], dist["mode"])
    if kind == "normal":
        return random.gauss(dist["mean"], dist["sd"])
    if kind == "lognormal":
        return random.lognormvariate(dist["mu"], dist["sigma"])
    if kind == "uniform":
        return random.uniform(dist["low"], dist["high"])
    raise ValueError(f"未知分布 {kind}")


def percentile(vals, q):
    vals = sorted(vals)
    if not vals:
        return None
    k = (len(vals) - 1) * q
    f = math.floor(k); c = math.ceil(k)
    return vals[f] if f == c else vals[f] * (c - k) + vals[c] * (k - f)


def cmd_montecarlo(spec):
    n = int(spec.get("n", 10000))
    seed = int(spec.get("seed", 42))
    random.seed(seed)
    out = []
    for o in spec.get("options", []):
        evs = []
        for _ in range(n):
            p = clamp(sample(o["p"]), 0, 1)
            q = clamp(sample(o.get("impl_prob", {"dist": "uniform", "low": 1, "high": 1})), 0, 1)
            gain = sample(o["gain"]); loss = sample(o["loss"]); cost = sample(o.get("cost", {"dist": "uniform", "low": 0, "high": 0}))
            evs.append(p * q * gain - (1 - p * q) * loss - cost)
        out.append({
            "name": o.get("name"),
            "mean": round(statistics.fmean(evs), 2),
            "p5": round(percentile(evs, 0.05), 2),
            "p50": round(percentile(evs, 0.50), 2),
            "p95": round(percentile(evs, 0.95), 2),
            "p_ev_positive": round(sum(1 for x in evs if x > 0) / n, 4),
            "min": round(min(evs), 2),
            "max": round(max(evs), 2),
        })
    out.sort(key=lambda x: -(x["p50"] or 0))
    return {"tool": "decision_calc", "version": VERSION, "command": "montecarlo",
            "n": n, "seed": seed, "options": out,
            "warnings": ["结果依赖输入分布；分布本身是估计，不是事实"]}


# ------------------------------------------------------------------ journal
def cmd_journal(spec):
    path = Path(spec.get("path", "decision_journal.json"))
    action = spec.get("action", "list")
    data = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {"entries": []}
    entries = data.setdefault("entries", [])

    if action == "add":
        e = spec.get("entry") or {}
        e.setdefault("id", f"D{len(entries) + 1:04d}")
        entries.append(e)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"tool": "decision_calc", "command": "journal", "action": "add",
                "id": e["id"], "count": len(entries), "path": str(path)}

    if action == "evaluate":
        eid = spec.get("id")
        outcome = 1 if spec.get("outcome") else 0
        for e in entries:
            if e.get("id") == eid:
                e["outcome"] = outcome
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                scored = [x for x in entries if "outcome" in x and "p" in x]
                brier = sum((float(x["p"]) - x["outcome"]) ** 2 for x in scored) / len(scored) if scored else None
                return {"tool": "decision_calc", "command": "journal", "action": "evaluate",
                        "id": eid, "outcome": outcome, "brier": round(brier, 4) if brier is not None else None,
                        "scored": len(scored)}
        raise ValueError(f"找不到 {eid}")

    scored = [x for x in entries if "outcome" in x and "p" in x]
    brier = sum((float(x["p"]) - x["outcome"]) ** 2 for x in scored) / len(scored) if scored else None
    buckets = {}
    for x in scored:
        b = f"{int(float(x['p']) * 10) * 10}-{int(float(x['p']) * 10) * 10 + 10}%"
        buckets.setdefault(b, []).append(x["outcome"])
    calib = {k: round(sum(v) / len(v), 3) for k, v in sorted(buckets.items())}
    return {"tool": "decision_calc", "command": "journal", "entries": entries,
            "scored": len(scored), "brier": round(brier, 4) if brier is not None else None,
            "calibration_by_bucket": calib,
            "note": "Brier 越低越好；0.25 相当于一直猜 50%"}


# ------------------------------------------------------------------ main
COMMANDS = {
    "bayes": cmd_bayes,
    "options": cmd_options,
    "attempts": cmd_attempts,
    "kelly": cmd_kelly,
    "faulttree": cmd_faulttree,
    "montecarlo": cmd_montecarlo,
    "journal": cmd_journal,
}


def main():
    ap = argparse.ArgumentParser(description="不确定性决策计算器")
    ap.add_argument("command", choices=sorted(COMMANDS))
    ap.add_argument("spec", help="JSON 输入文件")
    ap.add_argument("--out", default=None, help="把结果写入文件")
    args = ap.parse_args()
    try:
        result = COMMANDS[args.command](load_spec(args.spec))
    except Exception as e:
        print(json.dumps({"error": str(e), "command": args.command}, ensure_ascii=False, indent=2))
        return 1
    emit(result, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
