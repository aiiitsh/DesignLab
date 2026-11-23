"""The wizard's decision engine. All logic lives in data/flowchart.json; this file only walks it."""
from __future__ import annotations

import json
import os
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
TREE_PATH = os.path.join(HERE, "..", "data", "flowchart.json")


@lru_cache(maxsize=1)
def load_tree() -> dict:
    with open(TREE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _option(node: dict, value):
    for o in node.get("options", []):
        if str(o.get("value")) == str(value):
            return o
    return None


def walk(answers: dict) -> tuple[list[str], str | None, str | None]:
    """Follow the answers from the start. Returns (path of answered nodes, next node id, outcome id)."""
    tree = load_tree()
    nodes = tree["nodes"]
    cur = tree["start"]
    path = []
    while cur:
        node = nodes[cur]
        if cur not in answers:
            return path, cur, None
        path.append(cur)
        if node["type"] in ("question",):
            opt = _option(node, answers[cur])
            if opt is None:
                return path[:-1], cur, None
            if "outcome" in opt:
                return path, None, opt["outcome"]
            cur = opt.get("next")
        else:
            cur = node.get("next")
    return path, None, None


def next_node(answers: dict) -> dict:
    tree = load_tree()
    path, nxt, outcome = walk(answers)
    if outcome:
        return {"done": True, "path": path, "outcome": outcome, **recommend(answers)}
    node = dict(tree["nodes"][nxt])
    node["id"] = nxt
    return {"done": False, "path": path, "node": node, "candidates": candidates_from(nxt)}


def candidates_from(node_id: str) -> list[str]:
    """Every outcome still reachable from a node (the live recommendation narrows as answers come in)."""
    tree = load_tree()
    nodes = tree["nodes"]
    seen, out, stack = set(), [], [node_id]
    while stack:
        n = stack.pop()
        if n in seen or n not in nodes:
            continue
        seen.add(n)
        node = nodes[n]
        for o in node.get("options", []):
            if "outcome" in o and o["outcome"] not in out:
                out.append(o["outcome"])
            elif o.get("next"):
                stack.append(o["next"])
        if node.get("next"):
            stack.append(node["next"])
    return out


def recommend(answers: dict) -> dict:
    tree = load_tree()
    path, nxt, outcome = walk(answers)
    if not outcome:
        return {"analysis_id": None, "candidates": candidates_from(nxt) if nxt else []}
    o = dict(tree["outcomes"][outcome])
    o["outcome"] = outcome
    o["design_name"] = design_name(outcome, answers)
    flags = []
    if answers.get("plan_manip") == "quasi":
        flags.append("Quasi-experiment: weaker causal claim (no random assignment).")
    if answers.get("A_nfactors") and int(answers["A_nfactors"]) >= 4:
        flags.append("Four-way and higher interactions are very hard to explain.")
    o["flags"] = flags
    o["tails"] = answers.get("plan_hyp", "two")
    return o


def design_name(outcome: str, answers: dict) -> str:
    tree = load_tree()
    base = tree["outcomes"][outcome]["design"]
    vars_ = answers.get("plan_vars") or {}
    ivs = vars_.get("ivs") if isinstance(vars_, dict) else None
    if not ivs:
        return base
    parts = []
    for iv in ivs:
        n = len(iv.get("levels") or []) or iv.get("n_levels") or "?"
        parts.append((str(n), iv.get("name", "IV"), iv.get("role", "")))
    dims = " × ".join(p[0] for p in parts)
    roles = ", ".join(f"{p[1]} {p[2]}".strip() for p in parts)
    label = {"ttest_ind": "between-subjects", "ttest_paired": "within-subjects", "anova_oneway": "between-subjects",
             "anova_rm1": "within-subjects", "anova_factorial": "between-subjects", "anova_rm": "within-subjects",
             "anova_mixed": "mixed"}.get(outcome)
    if label and len(parts) == 1:
        return f"{label[0].upper() + label[1:]} design: {parts[0][1]} with {parts[0][0]} levels"
    if label:
        return f"{dims} {label} design: {roles}"
    return base


def all_paths() -> list[tuple[dict, str]]:
    """Enumerate every route through the tree (used by the tests): (answers, outcome)."""
    tree = load_tree()
    nodes = tree["nodes"]
    out = []

    def rec(cur, answers):
        node = nodes[cur]
        if node["type"] == "question":
            for o in node["options"]:
                a = {**answers, cur: o["value"]}
                if "outcome" in o:
                    out.append((a, o["outcome"]))
                else:
                    rec(o["next"], a)
        else:
            val = {"text": "RQ", "form": {}, "multi": [], "numeric": node.get("default", 2)}[node["type"]]
            rec(node["next"], {**answers, cur: val})

    rec(tree["start"], {})
    return out


def suggest_within(learning_effects: bool, long_session: bool, few_people: bool, person_attribute: bool,
                   large_individual_diff: bool = False) -> dict:
    """The "Not sure?" helper for within vs between (Meetings 2, 5)."""
    if person_attribute:
        return {"suggest": "between", "why": "The IV is a person attribute (e.g. gender, age): it cannot be "
                                             "manipulated within a person, so it must be between-subject."}
    score = 0
    why = []
    if learning_effects:
        score -= 2
        why.append("large learning/carryover effects that are hard to counterbalance favour between")
    if long_session:
        score -= 1
        why.append("long sessions risk fatigue, which favours between")
    if few_people:
        score += 2
        why.append("few available participants favour within (fewer people, more power)")
    if large_individual_diff:
        score += 1
        why.append("large individual differences favour within (they are removed from the error)")
    s = "within" if score > 0 else "between" if score < 0 else "within (counterbalance the order)"
    return {"suggest": s, "why": "; ".join(why) or "No strong reason either way; within gives more power if "
                                                   "carryover can be counterbalanced."}
