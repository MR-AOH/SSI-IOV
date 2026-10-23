"""
Generates the paper's comparison figures from:
  1. This simulation's real CSV output (crypto-only, blockchain-anchored,
     and network-layer results), and
  2. Verified numbers transcribed directly from the comparator papers'
     own tables/text (sources noted inline -- do not edit these without
     re-checking the source).

METHODOLOGY NOTE -- read before editing anything below:
All comparisons against Akli et al. use the REPEAT-AUTHENTICATION metric
(DID Verify + VC Verify only), NOT the full-lifecycle metric (which also
includes DID Generation + VC Issuance, i.e. one-time registration costs).
This is not a favorable-looking shortcut: Parameswarath et al. explicitly
state their own reported 28.0ms/45.95ms figures exclude registration
("omitting the computation cost during the initial registration"), which
makes repeat-authentication the methodologically consistent basis for
every comparison in this script, Akli included. The full-lifecycle
totals are still computed and available (full_lifecycle_totals()) for
transparency in the paper's text/tables, but are not used in any figure
here, since plotting both metrics inconsistently across figures is what
caused an earlier version's bar chart to show Ours losing to Akli on
average (35.36ms vs 29.54ms) while the line chart, right next to it,
showed Ours winning beyond ~126 nodes -- the same underlying data telling
two different stories only because of an inconsistent metric choice.

IMPORTANT -- read before using ssi_iov_network_results.csv for anything:
Every value in that file currently comes from a fallback FORMULA in the
simulation code, not from real NS-3 FlowMonitor measurement (verified by
exact formula matching). This script does not plot it for that reason --
see PLOT_NETWORK_PERFORMANCE below. Fix at the simulation level first.

Usage:
    python3 make_paper_figures.py [results_directory]

    Run with no arguments from inside figures/ to read/write ../results
    (the default layout of this repo). Pass a directory explicitly to
    point at a different results folder (e.g. a fresh run's output).
"""

import sys
import os
import csv
import matplotlib.pyplot as plt
import numpy as np

PLOT_NETWORK_PERFORMANCE = False  # keep False until FlowMonitor issue is fixed

# ---------------------------------------------------------------------
# Verified reference data, transcribed directly from the source papers.
# ---------------------------------------------------------------------

# Akli, A. and Chougdali, K., "IOTA-Assisted Self-Sovereign Identity
# Framework for Decentralized Authentication and Secure Data Sharing,"
# IEEE Access, vol. 13, 2025. Tables 4-6 (real NS-3 measurements).
AKLI_NODES = [50, 100, 150, 200, 250]
AKLI_DID_GEN = [1.84, 3.82, 5.52, 7.30, 10.13]        # Table 4 (registration -- not used in repeat-auth figures)
AKLI_VC_ISS  = [2.648, 5.244, 11.059, 12.610, 20.564]  # Table 5 (registration -- not used in repeat-auth figures)
AKLI_VC_VER  = [3.534, 7.119, 14.118, 14.835, 22.431]  # Table 6
# DID Verification has NO table in the source paper -- only two values
# appear in the running text: 0.17 ms (50 nodes) and 1.79 ms (250 nodes).
# The 100/150/200-node points below are linearly interpolated and are
# NOT independently sourced; flagged wherever used.
AKLI_DID_VER_KNOWN = {50: 0.17, 250: 1.79}
AKLI_DID_VER = [AKLI_DID_VER_KNOWN[50] +
                 (AKLI_DID_VER_KNOWN[250] - AKLI_DID_VER_KNOWN[50]) * (n - 50) / (250 - 50)
                 for n in AKLI_NODES]
AKLI_REPEAT_AUTH = [v + w for v, w in zip(AKLI_DID_VER, AKLI_VC_VER)]
AKLI_FULL_LIFECYCLE = [g + v + i + w for g, v, i, w in
                       zip(AKLI_DID_GEN, AKLI_DID_VER, AKLI_VC_ISS, AKLI_VC_VER)]

# Parameswarath, R.P., Gope, P., and Sikdar, B., "A Privacy-Preserving
# Authenticated Key Exchange Protocol for V2G Communications Using SSI,"
# IEEE Trans. Veh. Technol., vol. 72, no. 11, 2023. Section VII-B text:
# "the total computation costs at the EV and SP/CS are ... 28.0 ms and
# 45.95 ms, respectively" -- an arithmetic estimate (unit-benchmarked
# primitives summed by count), NOT a live simulation. This IS ALREADY a
# repeat-authentication-only figure in the source paper (their own words:
# "omitting the computation cost during the initial registration"), so it
# is used as-is, with no adjustment. No per-network-size breakdown exists
# in this paper -- a single aggregate figure, used only as a side
# reference point, not a row-by-row series.
PARAMESWARATH_TOTAL_MS = 28.0  # EV-side; SP/CS-side is 45.95 ms

# Borges, V.E.F. da C. et al., "A Self-Sovereign Identity-Based
# Authentication and Reputation Protocol for IoV Applications," IEEE
# Access, vol. 13, 2025. Table 3: R2 (in-coverage authentication),
# 95% CI [28.5701, 29.1640] ms, midpoint used below. From a Timed
# Coloured Petri Net formal model calibrated with hardware benchmarks,
# NOT a live network simulation or blockchain -- their own paper states
# these are "indicative of expected behavior rather than guarantees of
# performance." Also a single aggregate figure -- side reference only.
BORGES_TOTAL_MS = 28.87


def read_csv_as_dicts(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return [{k: (float(v) if k != "NodeCount" else int(v)) for k, v in row.items()} for row in reader]


def load_data(data_dir):
    sec = read_csv_as_dicts(os.path.join(data_dir, "ssi_iov_security_results.csv"))
    chain_path = os.path.join(data_dir, "ssi_iov_chain_results.csv")
    chain = read_csv_as_dicts(chain_path) if os.path.exists(chain_path) else None
    net_path = os.path.join(data_dir, "ssi_iov_network_results.csv")
    net = read_csv_as_dicts(net_path) if os.path.exists(net_path) else None
    return sec, chain, net


def repeat_auth_totals(chain):
    """DID Verify + VC Verify only, chain-anchored, per row. PRIMARY metric --
    matches Parameswarath's own exclusion of registration cost."""
    return [row["DIDVerChain_Avg(ms)"] + row["VCVerChain_Avg(ms)"] for row in chain]


def full_lifecycle_totals(chain):
    """DID Gen + DID Verify + VC Issue + VC Verify, chain-anchored, per row.
    SECONDARY metric, kept for transparency in tables/text -- not used in
    any figure here, to avoid the inconsistent-metric problem this file
    previously had."""
    return [row["DIDGenChain_Avg(ms)"] + row["DIDVerChain_Avg(ms)"] +
            row["VCIssChain_Avg(ms)"] + row["VCVerChain_Avg(ms)"] for row in chain]


# ---------------------------------------------------------------------
# Figure 3 (primary): row-by-row repeat-authentication crossover chart
# against Akli -- the real per-operation comparator, real tables, and
# the methodologically consistent metric.
# ---------------------------------------------------------------------
def figure_akli_crossover_repeat_auth(chain, out_path):
    if chain is None:
        print("No chain CSV -- skipping Akli repeat-auth crossover figure.")
        return

    nodes = [row["NodeCount"] for row in chain]
    ours = dict(zip(nodes, repeat_auth_totals(chain)))
    ours_at_akli_sizes = [ours[n] for n in AKLI_NODES]

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(AKLI_NODES, AKLI_REPEAT_AUTH, marker='o', linewidth=2,
            label='ISIF [Akli et al.] -- real NS-3\n(DID Verify + VC Verify)', color='#e74c3c')
    ax.plot(nodes, [ours[n] for n in nodes], marker='s', linewidth=2,
            label='SSI-IoV (ours) -- blockchain-anchored\n(DID Verify + VC Verify)', color='#2ecc71')

    crossover_n = None
    for i in range(len(AKLI_NODES) - 1):
        n0, n1 = AKLI_NODES[i], AKLI_NODES[i + 1]
        a0, a1 = AKLI_REPEAT_AUTH[i], AKLI_REPEAT_AUTH[i + 1]
        o0, o1 = ours_at_akli_sizes[i], ours_at_akli_sizes[i + 1]
        if (a0 - o0) * (a1 - o1) < 0:
            frac = (o0 - a0) / ((a1 - a0) - (o1 - o0))
            crossover_n = n0 + frac * (n1 - n0)
            break

    if crossover_n:
        ax.axvline(crossover_n, color='gray', linestyle='--', alpha=0.5)
        ax.annotate(f'Crossover ~{crossover_n:.0f} nodes', xy=(crossover_n, ax.get_ylim()[1] * 0.9),
                    fontsize=9, ha='center', style='italic', color='#555555')

    ax.set_xlabel('Network Size (Nodes)')
    ax.set_ylabel('Repeat-Authentication Time: DID Verify + VC Verify (ms)')
    ax.set_title('Repeat-Authentication Time vs. Network Size')
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    for x, y in zip(AKLI_NODES, AKLI_REPEAT_AUTH):
        ax.annotate(f'{y:.1f}', (x, y), textcoords="offset points", xytext=(0, 8), fontsize=8, color='#e74c3c')
    for x in nodes:
        ax.annotate(f'{ours[x]:.1f}', (x, ours[x]), textcoords="offset points", xytext=(0, -14), fontsize=8, color='#2ecc71')
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")
    if crossover_n:
        print(f"  Crossover point: ~{crossover_n:.0f} nodes")
    for n in AKLI_NODES:
        print(f"  {n} nodes: Akli={AKLI_REPEAT_AUTH[AKLI_NODES.index(n)]:.2f}ms  Ours={ours[n]:.2f}ms")


# ---------------------------------------------------------------------
# Figure 3b (secondary, transparency only): full-lifecycle version.
# NOT the headline figure -- include in the paper only as a supplementary
# table/figure alongside a clear label, per the text already drafted.
# ---------------------------------------------------------------------
def figure_akli_crossover_full_lifecycle(chain, out_path):
    if chain is None:
        print("No chain CSV -- skipping Akli full-lifecycle crossover figure.")
        return

    nodes = [row["NodeCount"] for row in chain]
    ours = dict(zip(nodes, full_lifecycle_totals(chain)))
    ours_at_akli_sizes = [ours[n] for n in AKLI_NODES]

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(AKLI_NODES, AKLI_FULL_LIFECYCLE, marker='o', linewidth=2,
            label='ISIF [Akli et al.] -- real NS-3\n(full lifecycle)', color='#e74c3c')
    ax.plot(nodes, [ours[n] for n in nodes], marker='s', linewidth=2,
            label='SSI-IoV (ours) -- blockchain-anchored\n(full lifecycle)', color='#2ecc71')

    crossover_n = None
    for i in range(len(AKLI_NODES) - 1):
        n0, n1 = AKLI_NODES[i], AKLI_NODES[i + 1]
        a0, a1 = AKLI_FULL_LIFECYCLE[i], AKLI_FULL_LIFECYCLE[i + 1]
        o0, o1 = ours_at_akli_sizes[i], ours_at_akli_sizes[i + 1]
        if (a0 - o0) * (a1 - o1) < 0:
            frac = (o0 - a0) / ((a1 - a0) - (o1 - o0))
            crossover_n = n0 + frac * (n1 - n0)
            break

    if crossover_n:
        ax.axvline(crossover_n, color='gray', linestyle='--', alpha=0.5)
        ax.annotate(f'Crossover ~{crossover_n:.0f} nodes', xy=(crossover_n, ax.get_ylim()[1] * 0.9),
                    fontsize=9, ha='center', style='italic', color='#555555')

    ax.set_xlabel('Network Size (Nodes)')
    ax.set_ylabel('Total Time: DID Gen + DID Verify + VC Issue + VC Verify (ms)')
    ax.set_title('Total Authentication Time vs. Network Size')
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")
    if crossover_n:
        print(f"  Crossover point: ~{crossover_n:.0f} nodes")


# ---------------------------------------------------------------------
# Bar chart: side-reference comparison. Uses repeat-authentication for
# BOTH bars (ours and Akli), consistent with Figure 3 and with
# Parameswarath/Borges, which are already repeat-authentication-only
# figures in their own source papers.
# ---------------------------------------------------------------------
def figure_side_references(chain, out_path):
    """
    Parameswarath et al. is deliberately NOT included here. Their reported
    28.0ms/45.95ms figures are an isolated CPU computation-cost estimate
    (Section VII-B of their paper is titled "Analysis of Computation Cost"
    and explicitly measures cryptographic-primitive execution time on a
    single machine, with no network communication). That is a different
    category of measurement from the other two bars here, which both
    include genuine network/system-level round-trip cost (real for Akli
    et al. and for this framework; Petri-net-estimated for Borges et al.).
    Putting Parameswarath's number on the same ms-of-authentication-time
    axis as these two would compare CPU-only cost against network-
    inclusive latency -- not a stylistic mismatch, a categorical one.
    """
    if chain is None:
        print("No chain CSV -- skipping side-reference figure.")
        return

    our_avg = float(np.mean(repeat_auth_totals(chain)))
    akli_avg = float(np.mean(AKLI_REPEAT_AUTH))

    labels = ['SSI-IoV\n(Proposed)', 'ISIF\n[Akli et al.]', 'RepuAuth-IoV\n[Borges et al.]']
    values = [our_avg, akli_avg, BORGES_TOTAL_MS]
    colors = ['#2ecc71', '#5d6d7e', '#34495e']

    fig, ax = plt.subplots(figsize=(9, 6))
    bars = ax.bar(labels, values, color=colors, edgecolor='black', linewidth=0.7, width=0.5)
    ax.set_ylabel('Authentication Time (ms)')
    ax.set_title('Authentication Time Comparison')
    for bar, val in zip(bars, values):
        ax.annotate(f'{val:.2f} ms', xy=(bar.get_x() + bar.get_width() / 2, val),
                    xytext=(0, 5), textcoords='offset points', ha='center', fontsize=11)
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved {out_path}")
    print(f"  Ours: {our_avg:.2f} ms   Akli: {akli_avg:.2f} ms   Borges: {BORGES_TOTAL_MS:.2f} ms   "
          f"({'Ours faster than Akli by ' + str(round((1-our_avg/akli_avg)*100)) + '%' if our_avg < akli_avg else 'Akli faster'})")


# ---------------------------------------------------------------------
# Stability figure: shows all four real operations (not just the
# repeat-auth two) across all ten network sizes, since this figure makes
# no comparative claim against Akli -- it is about this framework's own
# internal scaling behavior.
# ---------------------------------------------------------------------
def figure_stability(chain, out_path):
    if chain is None:
        print("No chain CSV -- skipping stability figure.")
        return
    nodes = [row["NodeCount"] for row in chain]
    did_gen = [row["DIDGenChain_Avg(ms)"] for row in chain]
    did_ver = [row["DIDVerChain_Avg(ms)"] for row in chain]
    vc_iss = [row["VCIssChain_Avg(ms)"] for row in chain]
    vc_ver = [row["VCVerChain_Avg(ms)"] for row in chain]
    totals = full_lifecycle_totals(chain)

    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.plot(nodes, did_gen, marker='o', label='DID Generation (chain)')
    ax.plot(nodes, did_ver, marker='s', label='DID Verification (chain)')
    ax.plot(nodes, vc_iss, marker='^', label='VC Issuance (chain)')
    ax.plot(nodes, vc_ver, marker='d', label='VC Verification (chain)')
    ax.set_xlabel('Network Size (Total Nodes)')
    ax.set_ylabel('Processing Time (ms)')
    cov = float(np.std(totals) / np.mean(totals) * 100)
    ax.set_title('Blockchain-Anchored Operation Timing Across Network Sizes')
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    print(f"Saved {out_path}  (coefficient of variation: {cov:.1f}%)")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_results_dir = os.path.join(script_dir, "..", "results")
    data_dir = sys.argv[1] if len(sys.argv) > 1 else default_results_dir
    out_dir = os.path.join(data_dir, "figures")
    os.makedirs(out_dir, exist_ok=True)

    security, chain, network = load_data(data_dir)

    figure_akli_crossover_repeat_auth(chain, os.path.join(out_dir, "fig3_akli_crossover_repeat_auth.png"))
    print()
    figure_akli_crossover_full_lifecycle(chain, os.path.join(out_dir, "fig3b_akli_crossover_full_lifecycle.png"))
    print()
    figure_side_references(chain, os.path.join(out_dir, "fig_side_references.png"))
    print()
    figure_stability(chain, os.path.join(out_dir, "fig_stability.png"))

    if not PLOT_NETWORK_PERFORMANCE:
        print("\nSkipped network-performance figure: ssi_iov_network_results.csv is still "
              "formula-derived (fallback formulas in RunNetworkSimulation), not real FlowMonitor "
              "output. This is a known, documented limitation -- see README. Fix at the simulation "
              "level, then set PLOT_NETWORK_PERFORMANCE = True.")
