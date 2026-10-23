"""
Run the LLM decision layer on the held-out generalization_test_dataset.json.

This has to be run locally (wherever Ollama + llama3.2 are running) since the
LLM is not reachable from a sandboxed environment. It reuses the exact same
LLMEvaluator/prompt from llm_evaluator.py so the methodology is identical to
the main 100-scenario evaluation - only the input dataset changes.

Usage:
    python run_llm_generalization.py
    (requires Ollama running locally: `ollama serve`, model `llama3.2:latest` pulled)

Output:
    llm_generalization_report.json  (same schema as llm_evaluation_report.json)

After this finishes, run:
    python compare_generalization.py
to merge it with rule_based_generalization_report.json and produce the final
comparison table/chart/paper section for Section VII-G.
"""

from llm_evaluator import LLMEvaluator


def main():
    evaluator = LLMEvaluator(model_name="llama3.2", ollama_url="http://localhost:11434")
    evaluator.evaluate_dataset("generalization_test_dataset.json")
    evaluator.generate_report("llm_generalization_report.json")
    print("\nDone. Now run: python compare_generalization.py")


if __name__ == "__main__":
    main()

