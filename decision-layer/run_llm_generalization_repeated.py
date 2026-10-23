"""
Repeated-Trials Runner for the Generalization Set
====================================================

Why this exists: single runs of llm_evaluator.py against
generalization_test_dataset.json have produced noticeably different accuracy
numbers on the same 5-scenario categories across separate runs. Ollama is
called with temperature=0.3 (see LLMEvaluator.query_llm), so the model
doesn't return the same decision every time, and with only 5 scenarios per
category, a single flipped decision swings the reported accuracy by 20
points. A single run is not a statistically defensible number to put in a
Transactions-level paper.

This script runs the evaluator N times (default 5) over the same 20-scenario
generalization set, saves each run separately, and reports:
  - per-scenario decision stability (how many of the N runs agreed, and what
    the majority decision was)
  - per-category mean accuracy ± standard deviation across the N runs
  - overall mean accuracy ± standard deviation

Usage:
    python run_llm_generalization_repeated.py 5

Output:
    repeated_runs/run_1.json ... run_N.json  (raw per-run reports)
    repeated_runs_summary.json               (aggregated stats)
    repeated_runs_summary.txt                (human-readable table)

Run this locally where Ollama is running (same as run_llm_generalization.py).
"""

import sys
import os
import json
import statistics
from collections import Counter, defaultdict

from llm_evaluator import LLMEvaluator

OUT_DIR = "repeated_runs"


def run_trials(n_trials: int, dataset_file: str = "generalization_test_dataset.json"):
    os.makedirs(OUT_DIR, exist_ok=True)

    run_reports = []
    for trial in range(1, n_trials + 1):
        print(f"\n{'='*60}\nTRIAL {trial}/{n_trials}\n{'='*60}")
        evaluator = LLMEvaluator(model_name="llama3.2:latest", ollama_url="http://localhost:11434")
        evaluator.evaluate_dataset(dataset_file)
        report = evaluator.generate_report(os.path.join(OUT_DIR, f"run_{trial}.json"))
        run_reports.append(report)

    return run_reports


def aggregate(run_reports):
    # Per-scenario decisions across all runs
    per_scenario = defaultdict(list)  # scenario_id -> [decision, decision, ...]
    scenario_meta = {}  # scenario_id -> (scenario_type, expected_decision)

    for report in run_reports:
        for r in report["detailed_results"]:
            sid = r["scenario_id"]
            per_scenario[sid].append(r["llm_decision"])
            scenario_meta[sid] = (r["scenario_type"], r["expected_decision"])

    stability_rows = []
    majority_correct = defaultdict(lambda: [0, 0])  # scenario_type -> [correct, total]
    for sid, decisions in sorted(per_scenario.items()):
        scenario_type, expected = scenario_meta[sid]
        counts = Counter(decisions)
        majority_decision, majority_count = counts.most_common(1)[0]
        agreement_pct = majority_count / len(decisions) * 100
        is_majority_correct = majority_decision == expected
        stability_rows.append({
            "scenario_id": sid,
            "scenario_type": scenario_type,
            "expected_decision": expected,
            "decisions_across_runs": decisions,
            "majority_decision": majority_decision,
            "agreement_pct": round(agreement_pct, 1),
            "majority_correct": is_majority_correct,
        })
        majority_correct[scenario_type][1] += 1
        if is_majority_correct:
            majority_correct[scenario_type][0] += 1

    # Per-run, per-category accuracy (for mean/std across runs)
    per_run_category_acc = defaultdict(list)  # scenario_type -> [acc_run1, acc_run2, ...]
    per_run_overall_acc = []
    for report in run_reports:
        per_run_overall_acc.append(report["overall_metrics"]["accuracy_percent"])
        for scenario_type, perf in report["scenario_type_performance"].items():
            per_run_category_acc[scenario_type].append(perf["accuracy_percent"])

    category_stats = {
        cat: {
            "mean_accuracy_pct": round(statistics.mean(accs), 1),
            "std_dev_pct": round(statistics.stdev(accs), 1) if len(accs) > 1 else 0.0,
            "runs": accs,
            "majority_vote_accuracy_pct": round(
                majority_correct[cat][0] / majority_correct[cat][1] * 100, 1
            ) if majority_correct[cat][1] else None,
        }
        for cat, accs in per_run_category_acc.items()
    }

    overall_stats = {
        "mean_accuracy_pct": round(statistics.mean(per_run_overall_acc), 1),
        "std_dev_pct": round(statistics.stdev(per_run_overall_acc), 1) if len(per_run_overall_acc) > 1 else 0.0,
        "runs": per_run_overall_acc,
    }

    summary = {
        "n_trials": len(run_reports),
        "overall": overall_stats,
        "per_category": category_stats,
        "per_scenario_stability": stability_rows,
    }

    return summary


def print_summary(summary):
    print("\n" + "=" * 80)
    print(f"REPEATED-TRIALS SUMMARY: n_trials={summary['n_trials']}")
    print("=" * 80)
    ov = summary["overall"]
    print(f"\nOverall accuracy: {ov['mean_accuracy_pct']}% ± {ov['std_dev_pct']} "
          f"(individual runs: {ov['runs']})")

    print("\nPer-category (mean ± std across runs, plus majority-vote accuracy):")
    for cat, stats in summary["per_category"].items():
        print(f"  {cat:<32} {stats['mean_accuracy_pct']:>5.1f}% ± {stats['std_dev_pct']:<5.1f}  "
              f"majority-vote: {stats['majority_vote_accuracy_pct']}%   runs={stats['runs']}")

    print("\nPer-scenario stability (low agreement_pct = the model flip-flops on this one):")
    for row in summary["per_scenario_stability"]:
        flag = "  <-- UNSTABLE" if row["agreement_pct"] < 80 else ""
        print(f"  id={row['scenario_id']:<4} {row['scenario_type']:<30} "
              f"expected={row['expected_decision']:<8} majority={row['majority_decision']:<8} "
              f"agreement={row['agreement_pct']:>5.1f}%{flag}")


def main():
    n_trials = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    run_reports = run_trials(n_trials)
    summary = aggregate(run_reports)

    with open("repeated_runs_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print_summary(summary)

    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_summary(summary)
    with open("repeated_runs_summary.txt", "w") as f:
        f.write(buf.getvalue())

    print("\nSaved: repeated_runs_summary.json / .txt")
    print(f"Raw per-run reports in: {OUT_DIR}/")


if __name__ == "__main__":
    main()
