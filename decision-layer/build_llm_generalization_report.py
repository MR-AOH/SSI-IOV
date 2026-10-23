"""
Builds llm_generalization_report.json from the 5 repeated trials already run
against Ollama (repeated_runs/run_1..5.json + repeated_runs_summary.json).

No new LLM calls are made and no decision is invented: for each of the 20
held-out scenarios, the reported llm_decision is the MAJORITY vote across
the 5 real trials (already computed in repeated_runs_summary.json), which is
the statistically defensible point estimate given temperature=0.3 sampling
noise. Confidence, response_time, and reasoning are averaged/taken from the
majority-aligned runs. This produces a single-file report in the same schema
as llm_evaluation_report.json / rule_based_generalization_report.json so the
existing comparison scripts (compare_generalization.py,
generate_figure5_replacement.py) run unmodified.
"""

import json
import glob
import statistics
from collections import Counter

with open("repeated_runs_summary.json") as f:
    summary = json.load(f)

runs = []
for path in sorted(glob.glob("repeated_runs/run_*.json")):
    with open(path) as f:
        runs.append(json.load(f)["detailed_results"])

by_scenario = {}
for run in runs:
    for r in run:
        by_scenario.setdefault(r["scenario_id"], []).append(r)

stability_by_id = {e["scenario_id"]: e for e in summary["per_scenario_stability"]}

detailed_results = []
for sid, trials in sorted(by_scenario.items()):
    stab = stability_by_id[sid]
    majority = stab["majority_decision"]
    # Use the reasoning/threat/confidence from a trial that actually produced
    # the majority decision (first match), so the qualitative fields are
    # internally consistent with the reported decision.
    matching = [t for t in trials if t["llm_decision"] == majority]
    rep = matching[0] if matching else trials[0]

    avg_conf = round(statistics.mean(t["llm_confidence"] for t in trials), 3)
    avg_rt = statistics.mean(t["response_time"] for t in trials)
    threat_votes = Counter(t["threat_detected"] for t in matching or trials)
    majority_threat = threat_votes.most_common(1)[0][0]

    detailed_results.append({
        "scenario_id": sid,
        "scenario_type": rep["scenario_type"],
        "sender_type": rep["sender_type"],
        "requested_data": rep["requested_data"],
        "is_emergency": rep["is_emergency"],
        "has_consent": rep["has_consent"],
        "policy_allows": rep["policy_allows"],
        "expected_decision": rep["expected_decision"],
        "expected_reason": rep.get("expected_reason"),
        "llm_decision": majority,
        "llm_confidence": avg_conf,
        "llm_reasoning": rep["llm_reasoning"],
        "threat_detected": majority_threat,
        "emergency_justified": rep["emergency_justified"],
        "recommended_data_scope": rep.get("recommended_data_scope", []),
        "is_correct": stab["majority_correct"],
        "response_time": avg_rt,
        "user_approval_required": rep["user_approval_required"],
        "agreement_pct": stab["agreement_pct"],
        "n_trials": len(trials),
    })

n = len(detailed_results)
n_correct = sum(1 for r in detailed_results if r["is_correct"])
accuracy = round(n_correct / n * 100, 2)

emer = [r for r in detailed_results if r["is_emergency"]]
emer_correct = sum(1 for r in emer if r["is_correct"])

insider = [r for r in detailed_results if r["scenario_type"] == "novel_unrecognized_entity"]
insider_correct = sum(1 for r in insider if r["is_correct"])

scenario_type_perf = {}
for st in sorted(set(r["scenario_type"] for r in detailed_results)):
    sub = [r for r in detailed_results if r["scenario_type"] == st]
    c = sum(1 for r in sub if r["is_correct"])
    scenario_type_perf[st] = {"n": len(sub), "correct": c, "accuracy_pct": round(c / len(sub) * 100, 2)}

report = {
    "evaluation_metadata": {
        "source": "majority vote across 5 repeated trials (repeated_runs/run_1..5.json)",
        "n_trials": 5,
        "n_scenarios": n,
        "model": "llama3.2",
        "note": "This is an aggregated point estimate, not a single raw run. See "
                "repeated_runs_summary.json for per-category mean +/- std across trials, "
                "which is the more statistically rigorous number to cite alongside this table.",
    },
    "overall_metrics": {
        "accuracy_percent": accuracy,
        "correct_decisions": n_correct,
        "incorrect_decisions": n - n_correct,
        "average_confidence": round(statistics.mean(r["llm_confidence"] for r in detailed_results), 3),
        "average_response_time_seconds": round(statistics.mean(r["response_time"] for r in detailed_results), 4),
    },
    "scenario_type_performance": scenario_type_perf,
    "emergency_detection": {
        "n": len(emer), "correct": emer_correct,
        "accuracy_pct": round(emer_correct / len(emer) * 100, 2) if emer else None,
    },
    "insider_attack_detection": {
        "n": len(insider), "correct": insider_correct,
        "accuracy_pct": round(insider_correct / len(insider) * 100, 2) if insider else None,
    },
    "detailed_results": detailed_results,
}

with open("llm_generalization_report.json", "w") as f:
    json.dump(report, f, indent=2)

print(f"Saved llm_generalization_report.json: {n_correct}/{n} correct ({accuracy}%)")
