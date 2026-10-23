"""
Head-to-Head Comparison: LLM Decision Layer vs Rule-Based Baseline
====================================================================

Loads the existing LLM evaluation results (llm_evaluation_report.json,
produced by llm_evaluator.py on the 100-scenario dataset) and the new
rule-based baseline results (rule_based_evaluation_report.json, produced by
rule_based_evaluator.py on the SAME 100 scenarios), and produces:

  1. A metrics table: Accuracy / Precision / Recall / F1 / False Accept Rate /
     False Reject Rate / Avg Decision Latency, per system, overall AND split
     by task (emergency validation, insider-attack/scope-creep detection,
     false-emergency rejection, legitimate/policy-compliant handling).
  2. Confusion matrices for both systems.
  3. A comparison bar chart (accuracy/F1 + a log-scale latency chart).
  4. A paper-ready draft text section (Section VII-F style) with the honest
     framing: on hand-crafted, foreseeable scenarios both systems can score
     well because the rule engine's author anticipated these exact patterns;
     the real differentiators are (a) decision latency and (b) generalization
     to novel patterns the rule author did NOT anticipate (see the
     generalization_test_dataset.json companion experiment).
"""

import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, accuracy_score

# Paper-facing display names for scenario_type / category codes. These only affect chart
# labels and generated paper text - the underlying scenario_type values in the dataset
# JSON files are left untouched so all matching/grouping logic keeps working unchanged.
DISPLAY_NAMES = {
    # Main 100-scenario dataset (Sections VII-D/VII-F)
    "legitimate": "Legitimate Access",
    "emergency": "Verified Emergency",
    "insider_attack": "Insider Threat / Scope Creep",
    "policy_violation": "Policy Violation",
    # Held-out generalization set (Section VII-G)
    "novel_context_implausibility": "Contextual Implausibility",
    "novel_purpose_drift": "Purpose Drift",
    "novel_ambiguous_emergency": "Ambiguous Emergency Evidence",
    "novel_unrecognized_entity": "Unrecognized Requester Type",
}


def display_name(category: str) -> str:
    """Paper-appropriate label for a scenario_type/category code, falling back to a
    title-cased version of the raw code if it isn't in DISPLAY_NAMES."""
    return DISPLAY_NAMES.get(category, category.replace("novel_", "").replace("_", " ").title())


def load_report(path, decision_key):
    with open(path, "r") as f:
        report = json.load(f)
    df = pd.DataFrame(report["detailed_results"])
    df["decision"] = df[decision_key]
    return report, df


def compute_metrics(df: pd.DataFrame, label: str) -> dict:
    y_true = (df["expected_decision"] == "approve").astype(int)
    y_pred = (df["decision"] == "approve").astype(int)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])  # rows=true[deny,approve], cols=pred[deny,approve]
    tn, fp, fn, tp = cm.ravel()

    accuracy = accuracy_score(y_true, y_pred) * 100

    negatives = tn + fp  # expected deny total
    positives = fn + tp  # expected approve total

    # Precision/Recall/F1 are only meaningful when the "approve" (positive) class
    # is actually present in this subset. Single-class subsets (e.g. an
    # insider_attack slice where every expected label is "deny") make these
    # metrics undefined (0/0) rather than genuinely "0" - report None/"N/A"
    # instead of silently forcing 0, which would misleadingly read as failure.
    if positives > 0:
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average="binary", zero_division=0
        )
        precision, recall, f1 = round(precision, 4), round(recall, 4), round(f1, 4)
    else:
        precision = recall = f1 = None  # N/A: no positive-class examples in this subset

    # False Accept Rate: among requests that SHOULD be denied, fraction wrongly approved
    far = (fp / negatives * 100) if negatives else None

    # False Reject Rate: among requests that SHOULD be approved, fraction wrongly denied
    frr = (fn / positives * 100) if positives else None

    avg_latency_ms = df["response_time"].mean() * 1000

    return {
        "system": label,
        "accuracy_pct": round(accuracy, 2),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_accept_rate_pct": round(far, 2) if far is not None else None,
        "false_reject_rate_pct": round(frr, 2) if frr is not None else None,
        "avg_latency_ms": round(avg_latency_ms, 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "n": len(df),
        "n_positive_class": int(positives),
        "n_negative_class": int(negatives),
    }


def per_task_metrics(df: pd.DataFrame, label: str) -> dict:
    out = {}
    for task in sorted(df["scenario_type"].dropna().unique()):
        sub = df[df["scenario_type"] == task]
        if len(sub) == 0:
            continue
        out[task] = compute_metrics(sub, label)
    return out


def print_table(rows, title):
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)
    header = f"{'Metric':<28}{'Rule-Based':<20}{'LLM-Based (Proposed)':<25}"
    print(header)
    print("-" * 90)
    for name, key, fmt in rows:
        rb = fmt(rule_metrics[key]) if key in rule_metrics else "-"
        lm = fmt(llm_metrics[key]) if key in llm_metrics else "-"
        print(f"{name:<28}{str(rb):<20}{str(lm):<25}")


def make_bar_chart(rule_metrics, llm_metrics, out_file="llm_vs_rule_comparison.png"):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    metrics_names = ["Accuracy (%)", "Precision", "Recall", "F1"]
    rule_vals = [
        rule_metrics["accuracy_pct"],
        rule_metrics["precision"] * 100,
        rule_metrics["recall"] * 100,
        rule_metrics["f1"] * 100,
    ]
    llm_vals = [
        llm_metrics["accuracy_pct"],
        llm_metrics["precision"] * 100,
        llm_metrics["recall"] * 100,
        llm_metrics["f1"] * 100,
    ]

    x = np.arange(len(metrics_names))
    width = 0.35
    axes[0].bar(x - width / 2, rule_vals, width, label="Rule-Based", color="#95a5a6", edgecolor="black")
    axes[0].bar(x + width / 2, llm_vals, width, label="LLM-Based (Proposed)", color="#3498db", edgecolor="black")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(metrics_names)
    axes[0].set_ylabel("Score (%)")
    axes[0].set_ylim(0, 110)
    axes[0].set_title("Accuracy / Precision / Recall / F1\n(standard 100-scenario test set)")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.3)

    systems = ["Rule-Based", "LLM-Based\n(Proposed)"]
    latencies = [rule_metrics["avg_latency_ms"], llm_metrics["avg_latency_ms"]]
    bars = axes[1].bar(systems, latencies, color=["#95a5a6", "#3498db"], edgecolor="black")
    axes[1].set_yscale("log")
    axes[1].set_ylabel("Avg Decision Latency (ms, log scale)")
    axes[1].set_title("Decision Latency Trade-off")
    axes[1].grid(axis="y", alpha=0.3, which="both")
    for bar, val in zip(bars, latencies):
        axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                      f"{val:,.2f} ms", ha="center", va="bottom", fontweight="bold")

    plt.tight_layout()
    plt.savefig(out_file, dpi=300, bbox_inches="tight")
    print(f"\nComparison chart saved to: {out_file}")


def generate_paper_section(overall_rule, overall_llm, task_rule, task_llm, out_file="comparison_paper_section.txt"):
    speedup = overall_llm["avg_latency_ms"] / overall_rule["avg_latency_ms"] if overall_rule["avg_latency_ms"] else float("inf")
    import math
    speedup_order = math.floor(math.log10(speedup)) if speedup > 0 else 0

    text = f"""
VII-F. Comparison Against a Rule-Based Decision Baseline

To empirically substantiate the claim that context-aware LLM reasoning
outperforms static rule-based access control, we implemented a rule-based
baseline (see rule_based_evaluator.py) that mirrors the same decision logic
provided to the LLM: (1) a static emergency-override rule requiring
collision_detected=True AND airbag_status=deployed AND impact_force >
{5.0}g, (2) a false-emergency rejection rule, (3) a static consent-matrix
lookup for insider/scope-creep detection, and (4) a policy+consent boolean
fallback. This baseline is representative of how existing rule-based IoV
access-control architectures reason: static thresholds and policy/credential
matching, without semantic understanding of request context.

Both systems were evaluated on the identical 100-scenario test set used for
the LLM evaluation reported in Section VII-D.

Table X. Rule-Based vs. LLM-Based Decision Performance (100 scenarios)
  Metric                      Rule-Based          LLM-Based (Proposed)
  Accuracy                    {overall_rule['accuracy_pct']}%              {overall_llm['accuracy_pct']}%
  Precision                   {overall_rule['precision']}              {overall_llm['precision']}
  Recall                      {overall_rule['recall']}              {overall_llm['recall']}
  F1                          {overall_rule['f1']}              {overall_llm['f1']}
  False Accept Rate           {overall_rule['false_accept_rate_pct']}%              {overall_llm['false_accept_rate_pct']}%
  False Reject Rate           {overall_rule['false_reject_rate_pct']}%              {overall_llm['false_reject_rate_pct']}%
  Avg. Decision Latency       {overall_rule['avg_latency_ms']:.4f} ms         {overall_llm['avg_latency_ms']:.2f} ms

On this standard test set, both systems achieve comparable accuracy. This is
an expected and honestly-reported result, not a weakness: the rule engine's
four conditions were explicitly designed to cover exactly the scenario
patterns present in this dataset (emergency override, false-emergency claims,
consent-matrix scope-creep, and policy-compliant sharing), so a competent
rule author can match LLM accuracy on foreseeable inputs. The rule-based
system is also on the order of 10^{speedup_order} times faster per decision
({overall_rule['avg_latency_ms']:.4f} ms vs. {overall_llm['avg_latency_ms']:.2f} ms,
i.e. sub-millisecond vs. multi-second inference latency), fully deterministic,
and trivially auditable - properties we do not claim the LLM layer matches.

The meaningful difference between the two approaches is not accuracy on
anticipated inputs, but generalization to inputs the rule author did not
anticipate. We evaluate this directly in Section VII-G using a held-out set
of 20 novel scenarios constructed to be semantically outside the rule
engine's four hardcoded conditions (e.g., in-scope data requested under an
implausible operational context, purpose-drift within an authorized data
field, ambiguous partial-emergency evidence that does not clear the rigid
sensor-threshold AND-condition, and requester types absent from the static
consent matrix). See Section VII-G for results.
"""
    with open(out_file, "w") as f:
        f.write(text)
    print(f"Paper-ready draft section saved to: {out_file}")
    return text


if __name__ == "__main__":
    import sys

    llm_report_path = sys.argv[1] if len(sys.argv) > 1 else "llm_generalization_report.json"
    rule_report_path = sys.argv[2] if len(sys.argv) > 2 else "rule_based_evaluation_report.json"

    llm_report, llm_df = load_report(llm_report_path, "llm_decision")
    rule_report, rule_df = load_report(rule_report_path, "rule_decision")

    rule_metrics = compute_metrics(rule_df, "Rule-Based")
    llm_metrics = compute_metrics(llm_df, "LLM-Based (Proposed)")

    task_rule = per_task_metrics(rule_df, "Rule-Based")
    task_llm = per_task_metrics(llm_df, "LLM-Based (Proposed)")

    def _fmt(v, spec="{:.4f}"):
        return "N/A" if v is None else spec.format(v)

    rows = [
        ("Accuracy (%)", "accuracy_pct", lambda v: _fmt(v, "{:.2f}")),
        ("Precision", "precision", lambda v: _fmt(v)),
        ("Recall", "recall", lambda v: _fmt(v)),
        ("F1", "f1", lambda v: _fmt(v)),
        ("False Accept Rate (%)", "false_accept_rate_pct", lambda v: _fmt(v, "{:.2f}")),
        ("False Reject Rate (%)", "false_reject_rate_pct", lambda v: _fmt(v, "{:.2f}")),
        ("Avg Decision Latency (ms)", "avg_latency_ms", lambda v: _fmt(v)),
    ]
    print_table(rows, "OVERALL: RULE-BASED vs LLM-BASED (100-scenario test set)")

    print("\n\nPER-TASK BREAKDOWN")
    for task in sorted(set(task_rule) | set(task_llm)):
        print(f"\n--- {task} ---")
        rb = task_rule.get(task, {})
        lm = task_llm.get(task, {})
        print(f"  Rule-Based:  n={rb.get('n')}  acc={rb.get('accuracy_pct')}%  "
              f"F1={_fmt(rb.get('f1'))}  FAR={_fmt(rb.get('false_accept_rate_pct'), '{:.2f}')}%  "
              f"FRR={_fmt(rb.get('false_reject_rate_pct'), '{:.2f}')}%")
        print(f"  LLM-Based:   n={lm.get('n')}  acc={lm.get('accuracy_pct')}%  "
              f"F1={_fmt(lm.get('f1'))}  FAR={_fmt(lm.get('false_accept_rate_pct'), '{:.2f}')}%  "
              f"FRR={_fmt(lm.get('false_reject_rate_pct'), '{:.2f}')}%")

    # Save full comparison as JSON
    comparison = {
        "overall": {"rule_based": rule_metrics, "llm_based": llm_metrics},
        "per_task": {"rule_based": task_rule, "llm_based": task_llm},
    }
    with open("llm_vs_rule_comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)
    print("\nFull comparison saved to: llm_vs_rule_comparison.json")

    make_bar_chart(rule_metrics, llm_metrics)
    generate_paper_section(rule_metrics, llm_metrics, task_rule, task_llm)
