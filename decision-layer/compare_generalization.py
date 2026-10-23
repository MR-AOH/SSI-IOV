"""
Generalization Comparison: Rule-Based vs LLM on Held-Out Novel Scenarios
==========================================================================

Merges rule_based_generalization_report.json (already produced - just run
`python rule_based_evaluator.py generalization_test_dataset.json
rule_based_generalization_report.json`, no LLM needed) with
llm_generalization_report.json (produced by running run_llm_generalization.py
locally against Ollama).

Produces:
  - Overall + per-novelty-category accuracy for both systems
  - A per-scenario table showing exactly which of the 20 held-out cases each
    system got right/wrong, so you can pull concrete examples for the paper
  - A bar chart: accuracy by novelty category, rule-based vs LLM
  - A paper-ready draft section (Section VII-G style)

Run this AFTER both rule_based_generalization_report.json and
llm_generalization_report.json exist.
"""

import json
import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from compare_llm_vs_rule import load_report, compute_metrics, per_task_metrics, display_name


def main():
    rule_path = "rule_based_generalization_report.json"
    llm_path = "llm_generalization_report.json"

    if not os.path.exists(rule_path):
        print(f"Missing {rule_path}. Run: python rule_based_evaluator.py "
              f"generalization_test_dataset.json {rule_path}")
        sys.exit(1)
    if not os.path.exists(llm_path):
        print(f"Missing {llm_path}. Run locally (needs Ollama): python run_llm_generalization.py")
        sys.exit(1)

    rule_report, rule_df = load_report(rule_path, "rule_decision")
    llm_report, llm_df = load_report(llm_path, "llm_decision")

    with open("generalization_test_dataset.json") as f:
        meta = json.load(f)["metadata"]
    control_ids = set(meta.get("control_case_ids", []))

    overall_rule = compute_metrics(rule_df, "Rule-Based")
    overall_llm = compute_metrics(llm_df, "LLM-Based (Proposed)")

    cat_rule = per_task_metrics(rule_df.rename(columns={"scenario_type": "scenario_type"}), "Rule-Based")
    cat_llm = per_task_metrics(llm_df.rename(columns={"scenario_type": "scenario_type"}), "LLM-Based (Proposed)")

    print("\n" + "=" * 90)
    print("GENERALIZATION TEST: RULE-BASED vs LLM-BASED (20 held-out novel scenarios)")
    print("=" * 90)
    print(f"Rule-Based Accuracy: {overall_rule['accuracy_pct']}%  "
          f"({overall_rule['confusion_matrix']['tn']+overall_rule['confusion_matrix']['tp']}/20 correct)")
    print(f"LLM-Based  Accuracy: {overall_llm['accuracy_pct']}%  "
          f"({overall_llm['confusion_matrix']['tn']+overall_llm['confusion_matrix']['tp']}/20 correct)")

    print("\nPer-Novelty-Category Accuracy:")
    for cat in sorted(set(cat_rule) | set(cat_llm)):
        rb = cat_rule.get(cat, {})
        lm = cat_llm.get(cat, {})
        print(f"  {display_name(cat):<32} Rule: {rb.get('accuracy_pct')}%   LLM: {lm.get('accuracy_pct')}%")

    # Per-scenario side-by-side table
    merged = rule_df[["scenario_id", "scenario_type", "expected_decision", "rule_decision", "is_correct"]].rename(
        columns={"is_correct": "rule_correct"}
    )
    llm_small = llm_df[["scenario_id", "llm_decision", "is_correct"]].rename(columns={"is_correct": "llm_correct"})
    merged = merged.merge(llm_small, on="scenario_id", how="outer")
    merged["is_control_case"] = merged["scenario_id"].isin(control_ids)
    merged.to_csv("generalization_per_scenario_comparison.csv", index=False)
    print("\nPer-scenario comparison saved to: generalization_per_scenario_comparison.csv")

    # Cases where rule is wrong but LLM is right = the concrete "generalization wins"
    llm_wins = merged[(merged["rule_correct"] == False) & (merged["llm_correct"] == True)]
    print(f"\nCases where LLM succeeded and rule engine failed: {len(llm_wins)}/20")
    if len(llm_wins) > 0:
        print(llm_wins[["scenario_id", "scenario_type", "expected_decision", "rule_decision", "llm_decision"]]
              .to_string(index=False))

    # Chart: accuracy by category
    categories = sorted(set(cat_rule) | set(cat_llm))
    rule_acc = [cat_rule.get(c, {}).get("accuracy_pct", 0) for c in categories]
    llm_acc = [cat_llm.get(c, {}).get("accuracy_pct", 0) for c in categories]

    fig, ax = plt.subplots(figsize=(11, 6))
    x = np.arange(len(categories))
    width = 0.35
    ax.bar(x - width / 2, rule_acc, width, label="Rule-Based", color="#95a5a6", edgecolor="black")
    ax.bar(x + width / 2, llm_acc, width, label="LLM-Based (Proposed)", color="#3498db", edgecolor="black")
    ax.set_xticks(x)
    ax.set_xticklabels([display_name(c).replace(" ", "\n", 1) for c in categories])
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 110)
    ax.set_title("Generalization to Held-Out Novel Scenarios\n(patterns not used to design the rule engine)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig("generalization_comparison.png", dpi=300, bbox_inches="tight")
    print("\nChart saved to: generalization_comparison.png")

    # Paper section
    total_correct_rule = overall_rule["confusion_matrix"]["tn"] + overall_rule["confusion_matrix"]["tp"]
    total_correct_llm = overall_llm["confusion_matrix"]["tn"] + overall_llm["confusion_matrix"]["tp"]

    text = f"""
VII-G. Generalization to Novel, Unanticipated Request Patterns

Section VII-F showed that on the standard 100-scenario test set, the rule-
based baseline matches the LLM's accuracy - unsurprising, since that dataset's
patterns are exactly what a competent rule author would anticipate. To test
whether context-aware reasoning generalizes BEYOND anticipated patterns, we
constructed a separate, hand-crafted set of 20 held-out scenarios
(generalization_test_dataset.json) spanning four categories that were NOT
used to design the rule engine: (1) context-implausible requests where the
data field is authorized but the situational context contradicts legitimate
use, (2) purpose-drift requests where an authorized field is requested for an
unstated, illegitimate purpose, (3) ambiguous/partial emergency evidence that
does not clear the rule engine's rigid sensor-threshold condition, and (4)
requester types entirely absent from the rule engine's hardcoded consent
matrix. Four of the twenty cases are deliberately "control" cases where the
correct decision matches what the rule engine actually produces, so this
experiment is not rigged to make the baseline fail on everything.

Results:
  Rule-Based Accuracy: {overall_rule['accuracy_pct']}% ({total_correct_rule}/20)
  LLM-Based Accuracy:  {overall_llm['accuracy_pct']}% ({total_correct_llm}/20)

Per-category breakdown:
"""
    for cat in categories:
        rb = cat_rule.get(cat, {})
        lm = cat_llm.get(cat, {})
        text += f"  {display_name(cat):<32} Rule: {rb.get('accuracy_pct')}%   LLM: {lm.get('accuracy_pct')}%\n"

    rule_wins = merged[(merged["rule_correct"] == True) & (merged["llm_correct"] == False)]

    if total_correct_llm > total_correct_rule:
        divergence_text = (
            f"{len(llm_wins)} of the 20 cases were ones where the rule engine's static conditions "
            f"produced the wrong decision while the LLM's reasoning produced the correct one, "
            f"versus only {len(rule_wins)} case(s) where the rule engine was right and the LLM was "
            f"wrong. Decision quality does not merely match the rule baseline on foreseeable inputs "
            f"- it diverges materially in the LLM's favor specifically on inputs the rule author did "
            f"not anticipate."
        )
    elif total_correct_llm < total_correct_rule:
        divergence_text = (
            f"Contrary to the paper's hypothesis, the rule engine actually scored higher on this "
            f"held-out set ({total_correct_rule}/20 vs {total_correct_llm}/20). {len(rule_wins)} "
            f"case(s) were ones where the rule engine was right and the LLM was wrong, versus "
            f"{len(llm_wins)} the other way. This should be reported honestly rather than reframed "
            f"- see CAVEAT below."
        )
    else:
        divergence_text = (
            f"Both systems scored identically overall ({total_correct_llm}/20), though on different "
            f"cases: the LLM got {len(llm_wins)} right that the rule engine missed, and the rule "
            f"engine got {len(rule_wins)} right that the LLM missed. See per-category breakdown above "
            f"for where each system's errors concentrate."
        )

    text += f"""
{divergence_text}

Combined with Section VII-F's latency result (~{overall_rule['avg_latency_ms']:.4f} ms per rule-based
decision vs. LLM inference latency), the honest framing for the paper is:
the rule-based system is faster and fully deterministic/auditable, and matches
LLM accuracy on anticipated inputs; the LLM-based system trades that speed
and determinism for {"materially better" if total_correct_llm > total_correct_rule else "different"}
generalization to novel, unanticipated request patterns.

"""

    # Identify the LLM's strongest/weakest categories dynamically rather than assuming -
    # which specific category is strongest/weakest can change between runs (see the
    # repeated-trials tooling, run_llm_generalization_repeated.py), so this text should
    # never hardcode a category name.
    llm_cat_acc = {cat: cat_llm.get(cat, {}).get("accuracy_pct", 0) for cat in categories}
    strongest_cat = max(llm_cat_acc, key=llm_cat_acc.get)
    weakest_cat = min(llm_cat_acc, key=llm_cat_acc.get)

    if llm_cat_acc[strongest_cat] > llm_cat_acc[weakest_cat]:
        spread_text = (
            f"Per-category, the LLM's strongest performance is on {display_name(strongest_cat)} "
            f"({llm_cat_acc[strongest_cat]}%); its weakest is {display_name(weakest_cat)} "
            f"({llm_cat_acc[weakest_cat]}%). This is worth stating explicitly in the paper: LLM "
            f"reasoning is not uniformly better across every category of novelty, and reporting "
            f"the weaker category honestly is more credible than only reporting the average."
        )
    else:
        spread_text = (
            f"The LLM performed uniformly ({llm_cat_acc[strongest_cat]}%) across all four "
            f"novelty categories in this run."
        )

    text += f"""
{spread_text}

NOTE ON RUN-TO-RUN VARIANCE: the LLM is queried at temperature=0.3, and each category here
has only 5 scenarios, so a single run's per-category accuracy can swing significantly
between runs (one flipped decision = a 20-point swing). Before finalizing these numbers for
submission, consider running run_llm_generalization_repeated.py (N=5 or more) and reporting
mean accuracy ± standard deviation per category instead of a single run's point estimate -
this is the more defensible number for a Transactions-level evaluation and directly
addresses the kind of reproducibility question a reviewer is likely to raise.

CAVEAT: verify all numbers above against rule_based_generalization_report.json
and llm_generalization_report.json before submission, and pull 2-3 concrete
scenario_id examples from generalization_per_scenario_comparison.csv (the
"LLM succeeded, rule failed" list printed above) to use as worked examples in
the text, the way Section VI-C already does for the mechanic-on-highway case.
"""
    with open("generalization_paper_section.txt", "w") as f:
        f.write(text)
    print("\nDraft paper section saved to: generalization_paper_section.txt")
    print("\nIMPORTANT: read the CAVEAT at the bottom of that file before using it.")


if __name__ == "__main__":
    main()
