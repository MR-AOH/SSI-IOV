import json
import time
import requests
from datetime import datetime
from typing import Dict, Any, List
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

class LLMEvaluator:
    def __init__(self, model_name: str = "llama3.2:latest", ollama_url: str = "http://localhost:11434"):
        """
        Initialize LLM Evaluator with local Llama model

        Args:
            model_name: Name of the Ollama model to use
            ollama_url: URL of the Ollama API endpoint

        Note: this class previously supported three prompt variants (v1/v2/v3) for an
        ablation study. That's been dropped in favor of a single canonical prompt - the
        one below (principle-based framing + explicit contextual-plausibility rule) is now
        the ONE prompt used for every evaluation (main 100-scenario dataset and the
        generalization set alike), so all results in the paper come from the same system
        description. If you have old report files generated under the previous v1/v2/v3
        naming, re-run them through this evaluator to keep everything consistent.
        """
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.api_endpoint = f"{ollama_url}/api/generate"
        self.results = []

    def create_prompt(self, scenario: Dict[str, Any]) -> str:
        """
        Create the evaluation prompt for a scenario: principle-based, role-specific framing
        (IoV-SSI principles named explicitly, per-role contextual notes) combined with an
        explicit rule requiring the model to cross-check the requester's claimed action
        against the vehicle's real, current sensor state and stated purpose - not just
        whether the requested field name is on a static allow-list.
        """

        sender_type = scenario.get("sender_type")

        role_notes = {
            "MECHANIC": (
                "This request is from a MECHANIC. It's crucial to understand whether the "
                "requested data is necessary for vehicle diagnostics or repair happening "
                "RIGHT NOW. Prioritize requests that directly relate to identified issues or "
                "safety concerns. A mechanic physically servicing a vehicle implies the "
                "vehicle should be stationary or idle - if sensor data shows the vehicle "
                "currently in motion (speed significantly above 0), a mechanic's request is "
                "operationally implausible regardless of which field is requested, and should "
                "be treated with suspicion rather than approved on field-whitelist grounds "
                "alone."
            ),
            "INSURANCE_PROVIDER": (
                "This request is from an INSURANCE_PROVIDER. Insurance providers request data "
                "for risk assessment, claims processing, or usage-based insurance programs. "
                "Ensure the data requested is directly relevant to an active policy/claim and "
                "that the stated purpose is consistent with underwriting or claims handling, "
                "not resale, marketing, or unrelated analytics products."
            ),
            "EMERGENCY_SERVICE": (
                "This request is from an EMERGENCY_SERVICE. In genuine emergencies, prioritize "
                "approval of critical data even against policy, but validate the emergency "
                "using ALL available evidence - sensor thresholds AND free-text context "
                "together. Do not require every sensor field to hit a rigid threshold "
                "simultaneously: a rollover with no frontal airbag deployment, a manually "
                "triggered medical-distress signal with no collision, or impact force just "
                "under a nominal cutoff can all still be genuine emergencies. Weigh the whole "
                "picture, not a single boolean AND condition."
            ),
            "ROADSIDE_UNIT": (
                "This request is from a ROADSIDE_UNIT (RSU). RSUs typically request data for "
                "traffic management, safety alerts, or infrastructure monitoring. Verify "
                "plausibility via the RSU's stated purpose; require explicit consent for "
                "location tracking or personally identifiable behavioral data."
            ),
            "CAR": (
                "This is a vehicle-to-vehicle (V2V) request. Share only necessary "
                "safety-related data (e.g. speed, location, braking status) to prevent "
                "collisions, and respect both parties' privacy settings."
            ),
        }

        default_note = (
            f"This request is from a sender type ('{sender_type}') that may not have a "
            "predefined role profile. Do not assume legitimacy just because policy_allows or "
            "has_consent happen to be True - reason about whether this sender plausibly has a "
            "real, current, operational relationship to this specific vehicle that would "
            "justify the requested data, the same way you would for a recognized role."
        )

        role_note = role_notes.get(sender_type, default_note)

        prompt = f"""You are an AI security agent for a Self-Sovereign Identity (SSI) based Internet of Vehicles (IoV) system. Evaluate this data sharing request by reasoning about it holistically - not by mechanically matching field names against an allow-list.

**IoV-SSI PRINCIPLES TO APPLY:**
1. Decentralized Identity Verification - does the sender have a real, current, legitimate relationship to this vehicle?
2. User Consent and Control - is consent genuine and specific to this purpose, not just a stale or bundled flag?
3. Privacy Protection - err toward denial when purpose or plausibility is unclear.
4. Selective Disclosure - only the minimum data necessary for the legitimate purpose.
5. Contextual Integrity - a request can be technically "allowed" by a static policy and still be illegitimate if the situational context, current vehicle state, or stated purpose doesn't actually support it right now.

**REQUEST DETAILS:**
- Request ID: {scenario.get('scenario_id')}
- Sender Type: {sender_type}
- Sender DID: {scenario.get('sender_did')}
- Recipient Type: {scenario.get('recipient_type')}
- Requested Data: {', '.join(scenario.get('requested_data', []))}
- Is Emergency (claimed): {scenario.get('is_emergency')}
- Has User Consent (flag): {scenario.get('has_consent')}
- Policy Allows (flag): {scenario.get('policy_allows')}
- Stated Context / Purpose: {scenario.get('context')}

**CURRENT VEHICLE SENSOR DATA (the ground truth for what's actually happening right now):**
{json.dumps(scenario.get('sensor_data', {}), indent=2)}

**ROLE-SPECIFIC CONTEXTUAL NOTE:**
{role_note}

**CONSENT MATRIX (necessary but NOT sufficient - a field being listed here does not make a specific request legitimate; you must still apply the principles above):**
- MECHANIC: Allowed [battery, fuel, tire_pressure, brake_status, temperature] | Forbidden [location, speed, user_behavior, trip_history]
- INSURANCE_PROVIDER: Allowed [speed, trip_history, mileage] | Forbidden [location, user_behavior, real_time_tracking]
- EMERGENCY_SERVICE: Allowed [all data during verified emergencies] | Forbidden [none during emergencies]
- Any other sender type: no predefined allow-list exists - reason from the principles above instead of defaulting to approve.

**EVALUATION RULES:**
1. Emergency Override: if the totality of sensor evidence and context supports a genuine emergency (not necessarily every threshold simultaneously - see role note above), approve even if policy says no.
2. Insider Attack / Scope-Creep: deny if a trusted entity requests data outside its authorized scope.
3. False Emergency: deny if emergency is claimed but the totality of evidence contradicts it.
4. Contextual Plausibility: even when the field is allowed and flags are satisfied, deny if the CURRENT vehicle state (e.g. speed/motion) or the stated purpose is inconsistent with the sender's claimed legitimate action happening right now.
5. Purpose Limitation: deny if the stated purpose reveals a use outside the sender's legitimate role function (resale, marketing, unrelated disputes), even for an allowed field.
6. Policy + Consent Fallback: if none of the above concerns apply, and policy_allows and has_consent are both true and reflect a real current relationship, approve.
7. Scope Minimization: always recommend sharing only the minimum data necessary.

**YOUR TASK:**
Analyze this request and provide your decision in the following JSON format ONLY (no additional text):

{{
  "decision": "approve" or "deny",
  "confidence": 0.0 to 1.0,
  "reasoning": "Brief explanation grounded in the principles and evidence above",
  "threat_detected": "none", "insider_attack", "false_emergency", "unauthorized_access", "context_implausible", "purpose_drift", or "policy_violation",
  "emergency_justified": true or false,
  "recommended_data_scope": ["list", "of", "data", "types", "to", "share"] or []
}}"""

        return prompt

    def query_llm(self, prompt: str, max_retries: int = 3) -> Dict[str, Any]:
        """Query the local Llama model via Ollama API"""
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,  # Lower temperature for more consistent decisions
                "top_p": 0.9,
                "max_tokens": 500
            }
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.post(self.api_endpoint, json=payload, timeout=160)
                response.raise_for_status()
                
                result = response.json()
                llm_response = result.get("response", "").strip()
                
                # Try to parse JSON from response
                try:
                    # Extract JSON if wrapped in markdown code blocks
                    if "```json" in llm_response:
                        llm_response = llm_response.split("```json")[1].split("```")[0].strip()
                    elif "```" in llm_response:
                        llm_response = llm_response.split("```")[1].split("```")[0].strip()
                    
                    parsed_response = json.loads(llm_response)
                    return parsed_response
                except json.JSONDecodeError:
                    print(f"Failed to parse JSON response (attempt {attempt + 1}): {llm_response[:200]}")
                    if attempt == max_retries - 1:
                        # Return a default deny response if parsing fails
                        return {
                            "decision": "deny",
                            "confidence": 0.5,
                            "reasoning": "Failed to parse LLM response",
                            "threat_detected": "parse_error",
                            "emergency_justified": False,
                            "recommended_data_scope": []
                        }
                    time.sleep(1)
                    
            except requests.exceptions.RequestException as e:
                print(f"API request failed (attempt {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:
                    return {
                        "decision": "deny",
                        "confidence": 0.0,
                        "reasoning": f"LLM API error: {str(e)}",
                        "threat_detected": "api_error",
                        "emergency_justified": False,
                        "recommended_data_scope": []
                    }
                time.sleep(2)
        
        return None

    def evaluate_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a single scenario using the LLM"""
        
        print(f"Evaluating Scenario {scenario.get('scenario_id')}: {scenario.get('scenario_type')}")
        
        start_time = time.time()
        prompt = self.create_prompt(scenario)
        llm_response = self.query_llm(prompt)
        response_time = time.time() - start_time
        
        # Compare LLM decision with expected decision
        expected_decision = scenario.get('expected_decision', 'deny')
        llm_decision = llm_response.get('decision', 'deny')
        is_correct = (expected_decision == llm_decision)
        
        result = {
            "scenario_id": scenario.get('scenario_id'),
            "scenario_type": scenario.get('scenario_type'),
            "sender_type": scenario.get('sender_type'),
            "requested_data": scenario.get('requested_data'),
            "is_emergency": scenario.get('is_emergency'),
            "has_consent": scenario.get('has_consent'),
            "policy_allows": scenario.get('policy_allows'),
            
            # Expected values
            "expected_decision": expected_decision,
            "expected_reason": scenario.get('expected_reason'),
            
            # LLM response
            "llm_decision": llm_decision,
            "llm_confidence": llm_response.get('confidence', 0.0),
            "llm_reasoning": llm_response.get('reasoning', ''),
            "threat_detected": llm_response.get('threat_detected', 'none'),
            "emergency_justified": llm_response.get('emergency_justified', False),
            "recommended_data_scope": llm_response.get('recommended_data_scope', []),
            
            # Evaluation
            "is_correct": is_correct,
            "response_time": response_time,
            "timestamp": datetime.now().isoformat()
        }
        
        return result

    def evaluate_dataset(self, dataset_file: str = "/Users/ahsan/Downloads/SSI-IOV-main/ssi_iov_test_dataset.json"):
        """Evaluate entire dataset"""
        
        print(f"\n{'='*60}")
        print(f"Starting LLM Evaluation")
        print(f"Model: {self.model_name}")
        print(f"{'='*60}\n")
        
        # Load dataset
        with open(dataset_file, 'r') as f:
            dataset = json.load(f)
        
        scenarios = dataset.get('scenarios', [])
        total_scenarios = len(scenarios)
        
        print(f"Loaded {total_scenarios} scenarios\n")
        
        # Evaluate each scenario
        for i, scenario in enumerate(scenarios, 1):
            print(f"Progress: {i}/{total_scenarios}", end="\r")
            result = self.evaluate_scenario(scenario)
            self.results.append(result)
            time.sleep(0.5)  # Small delay to avoid overwhelming the API
        
        print(f"\n\n{'='*60}")
        print("Evaluation Complete!")
        print(f"{'='*60}\n")
        
        return self.results

    def generate_report(self, output_file: str = "llm_evaluation_report.json"):
        """Generate comprehensive evaluation report"""
        
        if not self.results:
            print("No results to report!")
            return None
        
        df = pd.DataFrame(self.results)
        
        # Calculate metrics
        total = len(df)
        correct = df['is_correct'].sum()
        accuracy = (correct / total) * 100
        
        # Breakdown by scenario type
        scenario_accuracy = df.groupby('scenario_type').agg({
            'is_correct': ['sum', 'count']
        })
        scenario_accuracy.columns = ['correct', 'total']
        scenario_accuracy['accuracy'] = (scenario_accuracy['correct'] / scenario_accuracy['total']) * 100
        
        # Emergency detection
        emergency_scenarios = df[df['is_emergency'] == True]
        emergency_correct = emergency_scenarios['is_correct'].sum() if len(emergency_scenarios) > 0 else 0
        emergency_total = len(emergency_scenarios)
        emergency_accuracy = (emergency_correct / emergency_total * 100) if emergency_total > 0 else 0
        
        # Insider attack detection
        insider_attacks = df[df['scenario_type'] == 'insider_attack']
        insider_detected = insider_attacks['is_correct'].sum() if len(insider_attacks) > 0 else 0
        insider_total = len(insider_attacks)
        insider_detection_rate = (insider_detected / insider_total * 100) if insider_total > 0 else 0
        
        # False positive/negative analysis
        false_positives = len(df[(df['expected_decision'] == 'deny') & (df['llm_decision'] == 'approve')])
        false_negatives = len(df[(df['expected_decision'] == 'approve') & (df['llm_decision'] == 'deny')])
        
        # Average response time
        avg_response_time = df['response_time'].mean()
        
        # Confidence analysis
        avg_confidence = df['llm_confidence'].mean()
        
        report = {
            "evaluation_metadata": {
                "model_name": self.model_name,
                "total_scenarios": total,
                "evaluation_timestamp": datetime.now().isoformat()
            },
            "overall_metrics": {
                "accuracy_percent": round(accuracy, 2),
                "correct_decisions": int(correct),
                "incorrect_decisions": int(total - correct),
                "false_positives": int(false_positives),
                "false_negatives": int(false_negatives),
                "average_confidence": round(avg_confidence, 3),
                "average_response_time_seconds": round(avg_response_time, 3)
            },
            "scenario_type_performance": {
                scenario_type: {
                    "accuracy_percent": round(row['accuracy'], 2),
                    "correct": int(row['correct']),
                    "total": int(row['total'])
                }
                for scenario_type, row in scenario_accuracy.iterrows()
            },
            "emergency_detection": {
                "accuracy_percent": round(emergency_accuracy, 2),
                "correctly_handled": int(emergency_correct),
                "total_emergencies": int(emergency_total)
            },
            "insider_attack_detection": {
                "detection_rate_percent": round(insider_detection_rate, 2),
                "detected": int(insider_detected),
                "total_attacks": int(insider_total)
            },
            "detailed_results": self.results
        }
        
        # Save report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print(f"\n{'='*60}")
        print("EVALUATION REPORT SUMMARY")
        print(f"{'='*60}")
        print(f"Model: {self.model_name}")
        print(f"Total Scenarios: {total}")
        print(f"Overall Accuracy: {accuracy:.2f}%")
        print(f"False Positives: {false_positives} | False Negatives: {false_negatives}")
        print(f"Average Confidence: {avg_confidence:.3f}")
        print(f"Average Response Time: {avg_response_time:.3f}s")
        print(f"\nScenario Type Performance:")
        for scenario_type, metrics in report["scenario_type_performance"].items():
            print(f"  {scenario_type}: {metrics['accuracy_percent']:.1f}% ({metrics['correct']}/{metrics['total']})")
        print(f"\nEmergency Detection: {emergency_accuracy:.1f}% ({emergency_correct}/{emergency_total})")
        print(f"Insider Attack Detection: {insider_detection_rate:.1f}% ({insider_detected}/{insider_total})")
        print(f"{'='*60}\n")
        
        print(f"Report saved to: {output_file}")
        
        return report

    def create_visualizations(self, output_prefix: str = "llm_evaluation"):
        """Create comprehensive visualizations of evaluation results"""
        
        if not self.results:
            print("No results to visualize!")
            return
        
        df = pd.DataFrame(self.results)
        
        # Set style
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (16, 12)
        
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle(f'LLM Evaluation Results - {self.model_name}', fontsize=16, fontweight='bold')
        
        # 1. Overall Accuracy
        correct = df['is_correct'].sum()
        incorrect = len(df) - correct
        axes[0, 0].pie([correct, incorrect], labels=['Correct', 'Incorrect'], 
                       autopct='%1.1f%%', colors=['#2ecc71', '#e74c3c'], startangle=90)
        axes[0, 0].set_title(f'Overall Accuracy: {(correct/len(df)*100):.1f}%')
        
        # 2. Accuracy by Scenario Type
        scenario_accuracy = df.groupby('scenario_type')['is_correct'].mean() * 100
        scenario_accuracy.plot(kind='bar', ax=axes[0, 1], color='#3498db')
        axes[0, 1].set_title('Accuracy by Scenario Type')
        axes[0, 1].set_ylabel('Accuracy (%)')
        axes[0, 1].set_xlabel('Scenario Type')
        axes[0, 1].tick_params(axis='x', rotation=45)
        axes[0, 1].axhline(y=100, color='g', linestyle='--', alpha=0.3)
        
        # 3. Decision Distribution
        decision_counts = df.groupby(['expected_decision', 'llm_decision']).size().unstack(fill_value=0)
        decision_counts.plot(kind='bar', ax=axes[0, 2], color=['#e74c3c', '#2ecc71'])
        axes[0, 2].set_title('Expected vs LLM Decisions')
        axes[0, 2].set_ylabel('Count')
        axes[0, 2].set_xlabel('Expected Decision')
        axes[0, 2].legend(title='LLM Decision', labels=['Deny', 'Approve'])
        axes[0, 2].tick_params(axis='x', rotation=0)
        
        # 4. Threat Detection Analysis
        threat_counts = df['threat_detected'].value_counts()
        axes[1, 0].bar(range(len(threat_counts)), threat_counts.values, color='#e67e22')
        axes[1, 0].set_xticks(range(len(threat_counts)))
        axes[1, 0].set_xticklabels(threat_counts.index, rotation=45, ha='right')
        axes[1, 0].set_title('Threat Detection Distribution')
        axes[1, 0].set_ylabel('Count')
        
        # 5. Confidence Distribution
        axes[1, 1].hist(df['llm_confidence'], bins=20, color='#9b59b6', edgecolor='black', alpha=0.7)
        axes[1, 1].axvline(df['llm_confidence'].mean(), color='red', linestyle='--', 
                          label=f'Mean: {df["llm_confidence"].mean():.2f}')
        axes[1, 1].set_title('LLM Confidence Distribution')
        axes[1, 1].set_xlabel('Confidence Score')
        axes[1, 1].set_ylabel('Frequency')
        axes[1, 1].legend()
        
        # 6. Response Time Distribution
        axes[1, 2].hist(df['response_time'], bins=20, color='#1abc9c', edgecolor='black', alpha=0.7)
        axes[1, 2].axvline(df['response_time'].mean(), color='red', linestyle='--',
                          label=f'Mean: {df["response_time"].mean():.2f}s')
        axes[1, 2].set_title('Response Time Distribution')
        axes[1, 2].set_xlabel('Time (seconds)')
        axes[1, 2].set_ylabel('Frequency')
        axes[1, 2].legend()
        
        plt.tight_layout()
        filename = f"{output_prefix}_visualizations.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"Visualizations saved to: {filename}")
        plt.show()
        
        # Create additional confusion matrix
        self._create_confusion_matrix(df, output_prefix)
    
    def _create_confusion_matrix(self, df: pd.DataFrame, output_prefix: str):
        """Create confusion matrix visualization"""
        from sklearn.metrics import confusion_matrix
        import numpy as np
        
        # Convert decisions to binary
        y_true = (df['expected_decision'] == 'approve').astype(int)
        y_pred = (df['llm_decision'] == 'approve').astype(int)
        
        cm = confusion_matrix(y_true, y_pred)
        
        fig, ax = plt.subplots(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                    xticklabels=['Deny', 'Approve'], 
                    yticklabels=['Deny', 'Approve'],
                    cbar_kws={'label': 'Count'})
        ax.set_title('Confusion Matrix: Expected vs LLM Decisions', fontweight='bold', fontsize=14)
        ax.set_ylabel('Expected Decision', fontsize=12)
        ax.set_xlabel('LLM Decision', fontsize=12)
        
        # Add metrics
        tn, fp, fn, tp = cm.ravel()
        metrics_text = f'True Negatives: {tn}\nFalse Positives: {fp}\nFalse Negatives: {fn}\nTrue Positives: {tp}'
        ax.text(1.5, 0.5, metrics_text, transform=ax.transAxes, 
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
                verticalalignment='center')
        
        plt.tight_layout()
        filename = f"{output_prefix}_confusion_matrix.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"Confusion matrix saved to: {filename}")
        plt.show()

def main():
    """Main execution function"""
    
    print("\n" + "="*60)
    print("SSI-IoV LLM EVALUATION SYSTEM")
    print("="*60 + "\n")
    
    # Initialize evaluator
    evaluator = LLMEvaluator(
        model_name="llama3.2:latest",
        ollama_url="http://localhost:11434"
    )
    
    # Check if dataset exists
    dataset_file = "ssi_iov_test_dataset.json"
    try:
        with open(dataset_file, 'r') as f:
            json.load(f)
    except FileNotFoundError:
        print(f"Dataset file '{dataset_file}' not found!")
        print("Please run the dataset generator first.")
        return
    
    # Evaluate dataset
    print("Starting evaluation...")
    evaluator.evaluate_dataset(dataset_file)
    
    # Generate report
    print("\nGenerating report...")
    report = evaluator.generate_report("llm_evaluation_report.json")
    
    # Create visualizations
    print("\nCreating visualizations...")
    evaluator.create_visualizations("llm_evaluation")
    
    print("\n" + "="*60)
    print("EVALUATION COMPLETE!")
    print("="*60)
    print("\nGenerated files:")
    print("  - llm_evaluation_report.json (detailed results)")
    print("  - llm_evaluation_visualizations.png (charts)")
    print("  - llm_evaluation_confusion_matrix.png (accuracy matrix)")
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()