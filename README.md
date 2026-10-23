# SSI-IoV

Code accompanying the paper **"SSI-IoV: Self-Sovereign Identity Framework for
User-Controlled Privacy and Context-Aware Security in Internet of Vehicles."**

This repository contains the three pieces of evaluation code referenced in
Section VII of the paper:

1. **`ns3-simulation/`** — the NS-3 module that benchmarks real cryptographic
   (EdDSA / Ed25519), zero-knowledge-proof (Pedersen commitment + Schnorr),
   and blockchain-anchored DID/VC operations across network sizes from 50 to
   500 vehicles.
2. **`blockchain/`** — the Solidity DID registry contract, its compile/deploy
   tooling, and a standalone JSON-RPC client used to verify on-chain storage
   independently of the simulation.
3. **`decision-layer/`** — the LLM-based context-aware decision layer
   (`llama3.2`, run locally via Ollama) and the rule-based baseline it is
   compared against, including the accuracy/generalization evaluation
   pipeline behind Tables V–VI of the paper.

`results/` and `decision-layer/*.json` hold the actual output data and
figures these runs produced — the real numbers reported in the paper, not
regenerated/synthetic placeholders.

---

## Repository layout

```
SSI-IoV/
├── ns3-simulation/
│   └── scratch/
│       ├── ssi-simulation.cc     # drop into ns-3.45/scratch/
│       └── CMakeLists.txt        # ns-3's scratch build file, extended to
│                                 # link libsodium, libcurl, nlohmann-json
├── blockchain/
│   ├── DIDRegistry.sol           # on-chain DID/VC document store
│   ├── compile.js                # compiles DIDRegistry.sol with solc
│   ├── deploy.sh                 # deploys to a running Ganache instance
│   ├── did_registry_client.cpp   # standalone store/retrieve test client
│   └── abi.json                  # contract ABI (for reference/other tooling)
├── decision-layer/
│   ├── datasetgenerator.py              # builds the 100-scenario test set
│   ├── llm_evaluator.py                 # runs the LLM decision layer (Ollama)
│   ├── rule_based_evaluator.py          # the rule-based baseline
│   ├── compare_llm_vs_rule.py           # Table V metrics + comparison chart
│   ├── generate_generalization_set.py   # builds the 20-scenario held-out set
│   ├── run_llm_generalization.py        # single LLM run on the held-out set
│   ├── run_llm_generalization_repeated.py # 5 repeated trials (temp=0.3)
│   ├── build_llm_generalization_report.py # majority-vote aggregation
│   ├── compare_generalization.py        # Table VI metrics + comparison chart
│   ├── generate_figure5_replacement.py  # combined generalization/latency figure
│   ├── user_control_privacy_analysis.py # user-approval-fidelity re-analysis
│   ├── ssi_iov_test_dataset.json        # 100-scenario standard test set
│   ├── generalization_test_dataset.json # 20-scenario held-out set
│   ├── repeated_runs/                   # raw output of the 5 repeated trials
│   └── *.json / *.csv / *.png / *.pdf   # real reports and figures this
│                                         # pipeline produced
├── results/
│   ├── ssi_iov_chain_results.csv        # blockchain-anchored timings (real)
│   ├── ssi_iov_security_results.csv     # pure crypto timings (real)
│   ├── ssi_iov_network_results.csv      # see "Known limitation" below
│   └── figures/                         # the paper's Figures 3/3b/4/5
├── figures/
│   └── make_paper_figures.py            # regenerates results/figures/*.png
└── requirements.txt
```

---

## Prerequisites

| Component | Needed for | Version used |
|---|---|---|
| [ns-3](https://www.nsnam.org/releases/ns-3-45/) | network simulation | 3.45 |
| [libsodium](https://doc.libsodium.org/installation) | Ed25519 / ZKP primitives | any recent |
| libcurl + [nlohmann/json](https://github.com/nlohmann/json) | JSON-RPC to Ganache | any recent |
| [Ganache](https://trufflesuite.com/ganache/) | local Ethereum testnet | v2.7.1 (Desktop app) |
| Node.js + `solc` (`npm install solc`) | compiling the contract | any recent LTS |
| Python 3.10+ | figures + decision-layer | — |
| [Ollama](https://ollama.com) + `llama3.2` (`ollama pull llama3.2`) | LLM decision layer | — |

Install the Python dependencies with:

```bash
pip install -r requirements.txt
```

---

## 1. NS-3 simulation (cryptographic + blockchain-anchored benchmarks)

1. Download and extract [ns-3.45](https://www.nsnam.org/releases/ns-3-45/).
2. Copy this repo's `ns3-simulation/scratch/` contents into `ns-3.45/scratch/`
   (merge with, don't overwrite, the stock `CMakeLists.txt` boilerplate if
   you've already modified it — the version here is the exact one used for
   the paper's results, which only *adds* the linking block at the bottom).
3. Configure and build:
   ```bash
   cd ns-3.45
   ./ns3 configure --enable-modules=core,network,internet,mobility,wifi,applications,flow-monitor
   ./ns3 build scratch/ssi-simulation
   ```
4. Start Ganache (see step 2 below) and deploy the contract **before**
   running the simulation — the blockchain-anchored benchmark needs a real
   account + contract address.
5. Run:
   ```bash
   ./ns3 run "scratch/ssi-simulation --account=<ACCOUNT> --contract=<CONTRACT> --rpcPort=7545"
   ```
   This produces `ssi_iov_security_results.csv` (pure crypto, 1000
   iterations/size), `ssi_iov_chain_results.csv` (blockchain-anchored, 20
   iterations/size), and `ssi_iov_network_results.csv` in the ns-3 root —
   copy these into `results/` to regenerate the figures (step 3).

**Note on timing stability:** the benchmark warms up the blockchain
connection (40 throwaway requests) before measuring, to remove a cold-start
/ JIT bias in the first network size tested. If you see one network size as
a clear outlier, confirm the warmup ran (printed at startup).

---

## 2. Blockchain: DID registry contract

1. Start Ganache (Desktop app default RPC port: **7545**; CLI `ganache`
   default: 8545 — pass the right port to every step below).
2. Compile the contract:
   ```bash
   cd blockchain
   npm install solc
   node compile.js
   ```
   This tries six EVM targets (istanbul → cancun) since Ganache builds vary
   in which hardfork they emulate, and writes `bytecode_<version>.txt` for
   each, plus `abi.json` / `selectors.json`.
3. Deploy:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh 7545
   ```
   This tries each compiled bytecode variant against your live Ganache node
   until one deploys successfully, and prints the account + contract address
   to use in steps 1 and 4 below.
4. (Optional) Verify independently with the standalone client:
   ```bash
   g++ -std=c++17 -O2 did_registry_client.cpp -o did_registry_client \
       -lcurl $(pkg-config --cflags nlohmann_json 2>/dev/null)
   ./did_registry_client <ACCOUNT> <CONTRACT> 7545
   ```

---

## 3. Generating the paper's figures

Once `results/` holds a real `ssi_iov_chain_results.csv` and
`ssi_iov_security_results.csv` (either the ones already in this repo, or a
fresh run's output):

```bash
cd figures
python3 make_paper_figures.py
```

This regenerates `results/figures/fig3_akli_crossover_repeat_auth.png`
(Figure 3), `fig3b_akli_crossover_full_lifecycle.png`, `fig_side_references.png`
(Figure 4), and `fig_stability.png`, using the same verified comparator
numbers (Akli et al., Parameswarath et al., Borges et al. — sourced inline
in the script's comments) used in the paper. Pass a directory argument to
point it at different CSVs: `python3 make_paper_figures.py /path/to/results`.

---

## 4. Decision layer: LLM vs. rule-based evaluation

All scripts in `decision-layer/` are run from inside that directory and
read/write files in the same flat layout they were produced with.

1. Start Ollama and pull the model:
   ```bash
   ollama serve &
   ollama pull llama3.2
   ```
2. Main 100-scenario evaluation (Table V):
   ```bash
   cd decision-layer
   python3 llm_evaluator.py              # -> llm_evaluation_report.json
   python3 rule_based_evaluator.py       # -> rule_based_evaluation_report.json
   python3 compare_llm_vs_rule.py        # -> llm_vs_rule_comparison.{json,png}
   ```
3. Held-out generalization set (Table VI), run 5 times to account for
   sampling noise at temperature=0.3:
   ```bash
   python3 run_llm_generalization_repeated.py   # -> repeated_runs/run_1..5.json
   python3 build_llm_generalization_report.py   # -> llm_generalization_report.json (majority vote)
   python3 rule_based_evaluator.py generalization_test_dataset.json rule_based_generalization_report.json
   python3 compare_generalization.py            # -> generalization_per_scenario_comparison.csv, chart
   ```
4. User-controlled-privacy re-analysis and the combined figure:
   ```bash
   python3 user_control_privacy_analysis.py     # -> user_controlled_privacy_report.json
   python3 generate_figure5_replacement.py      # -> fig5_replacement_generalization_vs_baseline.{png,pdf}
   ```

The `.json`/`.csv`/`.png` files already in this directory are the actual
output of these runs — the numbers reported in the paper (Table V/VI) come
directly from them, not from re-running anything.

---

## Known limitation (documented, not hidden)

`results/ssi_iov_network_results.csv` is produced by a **fallback formula**
in the NS-3 simulation, not by real FlowMonitor-measured throughput/
latency/packet-delivery-ratio — this was verified by exact formula-matching
against the simulation's source. For that reason, the paper does **not**
report network-layer throughput/PDR claims from this file, and
`make_paper_figures.py` does not plot it (`PLOT_NETWORK_PERFORMANCE = False`).
Real network-layer characterization (actual FlowMonitor output under the
802.11p mobility model already implemented in `ssi-simulation.cc`) is left
as future work. Every other result in this repository — the cryptographic
timings, the blockchain-anchored timings, and the LLM/rule-based decision
metrics — is a genuine, measured result, not estimated or fabricated.

---

## Citation

If you use this code, please cite the paper:

```bibtex
@article{ssiiov2026,
  title   = {SSI-IoV: Self-Sovereign Identity Framework for User-Controlled Privacy and Context-Aware Security in Internet of Vehicles},
  author  = {Altaf, Ahsan and Anjum, Adeel and Syed, Madiha Haider and Rehman, Semeen},
  journal = {IEEE Transactions on Information Forensics and Security},
  year    = {2026}
}
```
