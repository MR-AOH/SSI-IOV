"""
Generates the proposed replacement for the paper's Figure 5.

The old Figure 5 (Section VII-D) is purely descriptive: it shows how the LLM's
own decisions broke down on the 100-scenario dataset (30 policy-allowed
approvals / 15 emergency overrides / 10 false-emergency blocks / 45 policy
denials), with no baseline to compare against - exactly the gap the
supervisor's review flagged (an assertion, not a comparison).

This replacement keeps the paper visually anchored on the emergency-override
narrative (consistent with Sections IV-B, VI-C, and the old Figure 5) but
makes it an actual empirical comparison:
  Panel A: Rule-based vs. LLM accuracy on the held-out generalization set,
           by category (the headline new result - Section VII-G)
  Panel B: Decision latency trade-off, log scale (Section VII-F)

Output: fig5_replacement_generalization_vs_baseline.{png,pdf}
"""

import json
import numpy as np
import matplotlib.pyplot as plt

from compare_llm_vs_rule import load_report, compute_metrics, per_task_metrics, display_name

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 11


def main():
    # --- Panel A data: generalization set, rule vs LLM, by category ---
    rule_gen_report, rule_gen_df = load_report("rule_based_generalization_report.json", "rule_decision")
    llm_gen_report, llm_gen_df = load_report("llm_generalization_report.json", "llm_decision")

    cat_rule = per_task_metrics(rule_gen_df, "Rule-Based")
    cat_llm = per_task_metrics(llm_gen_df, "LLM-Based (Proposed)")
    categories = sorted(set(cat_rule) | set(cat_llm))
    rule_acc = [cat_rule.get(c, {}).get("accuracy_pct", 0) for c in categories]
    llm_acc = [cat_llm.get(c, {}).get("accuracy_pct", 0) for c in categories]

    overall_rule_gen = compute_metrics(rule_gen_df, "Rule-Based")
    overall_llm_gen = compute_metrics(llm_gen_df, "LLM-Based (Proposed)")

    # --- Panel B data: latency, from the main 100-scenario comparison ---
    rule_main_report, rule_main_df = load_report("rule_based_evaluation_report.json", "rule_decision")
    llm_main_report, llm_main_df = load_report("llm_generalization_report.json", "llm_decision")
    rule_latency_ms = rule_main_df["response_time"].mean() * 1000
    llm_latency_ms = llm_main_df["response_time"].mean() * 1000

    # --- Figure ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

    # Panel A
    ax = axes[0]
    x = np.arange(len(categories))
    width = 0.35
    bars_rule = ax.bar(x - width / 2, rule_acc, width, label="Rule-Based Baseline",
                        color="#95a5a6", edgecolor="black", linewidth=1)
    bars_llm = ax.bar(x + width / 2, llm_acc, width, label="Proposed (LLM-Based)",
                       color="#2980b9", edgecolor="black", linewidth=1)
    for bars in (bars_rule, bars_llm):
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 1.5, f"{h:.0f}%",
                    ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([display_name(c).replace(" ", "\n", 1) for c in categories], fontsize=9)
    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 115)
    ax.set_title(f"(a) Generalization to Novel Request Patterns",
                 fontsize=10.5)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    # Panel B
    ax2 = axes[1]
    systems = ["Rule-Based\nBaseline", "Proposed\n(LLM-Based)"]
    latencies = [rule_latency_ms, llm_latency_ms]
    bars = ax2.bar(systems, latencies, color=["#95a5a6", "#2980b9"], edgecolor="black", linewidth=1, width=0.5)
    ax2.set_yscale("log")
    ax2.set_ylabel("Avg. Decision Latency (ms, log scale)")
    ax2.set_title("(b) Decision Latency Trade-off", fontsize=10.5)
    ax2.grid(axis="y", alpha=0.3, which="both")
    for bar, val in zip(bars, latencies):
        label = f"{val:.4f} ms" if val < 1 else f"{val:,.0f} ms"
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), label,
                  ha="center", va="bottom", fontsize=9, fontweight="bold")

    fig.suptitle("Rule-Based Baseline vs. Proposed LLM-Based Decision Layer",
                  fontsize=12, fontweight="bold", y=1.03)

    plt.tight_layout()
    plt.savefig("fig5_replacement_generalization_vs_baseline.png", dpi=300, bbox_inches="tight")
    plt.savefig("fig5_replacement_generalization_vs_baseline.pdf", bbox_inches="tight")
    print("Saved: fig5_replacement_generalization_vs_baseline.png / .pdf")


if __name__ == "__main__":
    main()
