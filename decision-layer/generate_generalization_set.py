"""
Held-Out Generalization Test Set
==================================

This is a SEPARATE, hand-crafted set of 20 scenarios (scenario_id 101-120),
distinct from the auto-generated 100-scenario dataset used everywhere else
(ssi_iov_test_dataset.json). It exists to test ONE specific claim: that
context-aware LLM reasoning generalizes to request patterns that a rule
author did not anticipate, while a static rule engine (rule_based_evaluator.py)
does not.

None of these scenarios were used to design the four rules in
rule_based_evaluator.py. Each one is semantically outside at least one of
those rules:

  novel_context_implausibility - the requested field IS on the role's
      allow-list and policy/consent flags ARE set, but the situational
      context (e.g. vehicle at highway speed) makes the request implausible
      for its stated purpose. The rule engine has no notion of situational
      plausibility - it only checks field membership + boolean flags.

  novel_purpose_drift - same idea: authorized field, satisfied flags, but the
      free-text stated purpose reveals a use case outside the role's
      legitimate function (data monetization, unrelated disputes, etc). The
      rule engine cannot parse free text at all.

  novel_ambiguous_emergency - sensor evidence does not clear the rigid
      "collision_detected AND airbag_deployed AND impact_force>5g" bar, but
      the situational context (rollover, non-frontal impact, manually
      triggered medical distress, borderline impact force) describes a
      genuine emergency. The rule engine's threshold is a blunt instrument;
      it cannot weigh partial/ambiguous evidence.

  novel_unrecognized_entity - the sender_type does not exist in the rule
      engine's hardcoded CONSENT_MATRIX at all, so Rule 3 (scope-creep check)
      is silently skipped and the decision collapses to the raw policy/
      consent booleans with no scope check whatsoever. This demonstrates the
      maintenance burden / brittleness of enumerated rule systems: every new
      entity type requires a human to notice and add a rule branch.

Each category also includes 1-2 "control" cases where the correct decision
matches what a careful rule *should* produce even though the entity/pattern
is still novel, so this set is not artificially rigged to make the rule
engine fail 100% of the time - that would be exactly the strawman-baseline
problem this whole experiment is trying to avoid.

Expected decisions below are expert-labeled by hand based on the paper's own
stated principles (life-safety priority, purpose limitation, selective
disclosure, no legitimate-relationship = no access), NOT by running the rule
engine or the LLM. This is documented explicitly so the labeling process is
auditable/defensible to a reviewer.
"""

import json
from datetime import datetime

TIMESTAMP = datetime.now().isoformat()


def normal(speed=45, temperature=88, fuel="60%", battery="80%", brake="functional",
            tire=(32, 32, 31, 33), rpm=2000, extra=None):
    d = {
        "speed": speed,
        "location": {"latitude": 34.0522, "longitude": -118.2437},
        "temperature": temperature,
        "fuel": fuel,
        "battery": battery,
        "brake_status": brake,
        "tire_pressure": list(tire),
        "engine_rpm": rpm,
        "airbag_status": "not_deployed",
        "collision_detected": False,
        "acceleration": {"x": 0.5, "y": 0.2, "z": 9.8},
    }
    if extra:
        d.update(extra)
    return d


def accident(collision=True, airbag="deployed", impact_force=8.5, extra=None):
    d = {
        "speed": 0,
        "location": {"latitude": 34.0522, "longitude": -118.2437},
        "temperature": 105,
        "fuel": "45%",
        "battery": "50%",
        "brake_status": "emergency_engaged",
        "tire_pressure": [28, 0, 30, 32],
        "engine_rpm": 0,
        "airbag_status": airbag,
        "collision_detected": collision,
        "acceleration": {"x": -15.5, "y": -2.3, "z": 8.2},
        "impact_force": impact_force,
        "emergency_alert": True,
    }
    if extra:
        d.update(extra)
    return d


SCENARIOS = [
    # ---------------- Category A: novel_context_implausibility ----------------
    dict(
        scenario_id=101, scenario_type="novel_context_implausibility",
        sender_type="MECHANIC", sender_did="did:ssi:mechanic:shop1",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user1",
        requested_data=["brake_status"], is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(speed=115, rpm=3400),
        context="Mechanic requesting brake_status diagnostic read; vehicle sensors show it is "
                "currently being driven at 115 km/h on a highway, not at the repair shop.",
        expected_decision="deny",
        expected_reason="Field is on the mechanic's allow-list and consent/policy flags are set, "
                         "but a mechanic cannot be performing a brake diagnostic on a vehicle "
                         "traveling at highway speed. The operational context is inconsistent with "
                         "the stated purpose, suggesting credential misuse rather than an active "
                         "repair. A static field-whitelist check cannot detect this.",
    ),
    dict(
        scenario_id=102, scenario_type="novel_context_implausibility",
        sender_type="MECHANIC", sender_did="did:ssi:mechanic:shop2",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user2",
        requested_data=["tire_pressure"], is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(speed=102, rpm=3100),
        context="Mechanic requesting tire_pressure telemetry while vehicle sensors show 102 km/h "
                "highway travel, no service appointment on record.",
        expected_decision="deny",
        expected_reason="Same implausible-context pattern: allowed field, satisfied flags, but no "
                         "physical way to be servicing tires on a moving vehicle. Indicates "
                         "opportunistic remote data pull rather than legitimate repair access.",
    ),
    dict(
        scenario_id=103, scenario_type="novel_context_implausibility",
        sender_type="MECHANIC", sender_did="did:ssi:mechanic:shop1",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user1",
        requested_data=["battery", "temperature"], is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(speed=90, rpm=2800),
        context="Mechanic requesting battery and temperature readings; vehicle is on a highway at "
                "90 km/h with no active service ticket.",
        expected_decision="deny",
        expected_reason="Two allowed fields requested simultaneously under the same implausible "
                         "moving-vehicle context. Multiplicity of fields does not change the core "
                         "issue: no legitimate repair action can be occurring right now.",
    ),
    dict(
        scenario_id=104, scenario_type="novel_context_implausibility",
        sender_type="INSURANCE_PROVIDER", sender_did="did:ssi:insurance:company1",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user2",
        requested_data=["mileage"], is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(),
        context="Insurance provider requesting mileage under a consent record that has never been "
                "revoked, but context notes the vehicle was sold to an unrelated new owner 60 days "
                "ago and the policy has lapsed.",
        expected_decision="deny",
        expected_reason="Mileage is an allowed field and the stale consent flag is still technically "
                         "True, but the underlying insured relationship has ended. A static consent "
                         "flag with no expiry/relationship check cannot detect this - the rule engine "
                         "has no representation of 'is this authorization still valid'.",
    ),
    dict(
        scenario_id=105, scenario_type="novel_context_implausibility",
        sender_type="MECHANIC", sender_did="did:ssi:mechanic:shop2",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user1",
        requested_data=["fuel"], is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(speed=70, rpm=2500),
        context="Mechanic describes this as a 'routine remote diagnostic ping while the customer is "
                "driving'; vehicle is moving at 70 km/h on a highway.",
        expected_decision="deny",
        expected_reason="The stated purpose itself ('while the customer is driving') confirms the "
                         "implausible context rather than concealing it - a competent reasoner should "
                         "flag this explicitly, a field-whitelist rule cannot.",
    ),

    # ---------------- Category B: novel_purpose_drift ----------------
    dict(
        scenario_id=106, scenario_type="novel_purpose_drift",
        sender_type="MECHANIC", sender_did="did:ssi:mechanic:shop1",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user1",
        requested_data=["temperature"], is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(),
        context="Mechanic states the temperature readings will be aggregated across all serviced "
                "vehicles to build and sell a predictive-maintenance analytics product to a fleet "
                "insurer, unrelated to this vehicle's repair.",
        expected_decision="deny",
        expected_reason="Field is allowed and consent was given for THIS vehicle's repair, not for "
                         "resale into a third-party analytics product. This is a purpose-limitation "
                         "violation the rule engine cannot see because it never parses the 'context' "
                         "field's stated purpose - it only checks field membership.",
    ),
    dict(
        scenario_id=107, scenario_type="novel_purpose_drift",
        sender_type="INSURANCE_PROVIDER", sender_did="did:ssi:insurance:company1",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user2",
        requested_data=["trip_history"], is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(),
        context="Insurance provider is compiling trip_history into a marketing dataset for resale "
                "to third parties, unrelated to underwriting or claims.",
        expected_decision="deny",
        expected_reason="Trip history is on the insurer's allow-list for underwriting purposes; "
                         "reselling it for marketing is a distinct, unconsented purpose.",
    ),
    dict(
        scenario_id=108, scenario_type="novel_purpose_drift",
        sender_type="MECHANIC", sender_did="did:ssi:mechanic:shop2",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user1",
        requested_data=["brake_status"], is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(),
        context="Mechanic is using diagnostic access to gather evidence of the owner's driving "
                "habits for an unrelated personal legal dispute with the vehicle owner.",
        expected_decision="deny",
        expected_reason="Same allowed field, same satisfied flags, but the purpose is adversarial "
                         "and entirely outside the repair relationship.",
    ),
    dict(
        scenario_id=109, scenario_type="novel_purpose_drift",
        sender_type="INSURANCE_PROVIDER", sender_did="did:ssi:insurance:company1",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user2",
        requested_data=["speed"], is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(),
        context="Insurance provider wants continuous real-time speed logging fed into a public "
                "'driver leaderboard' consumer app the insurer separately operates.",
        expected_decision="deny",
        expected_reason="Speed is allowed for usage-based insurance risk assessment, not for "
                         "publishing to a public-facing consumer app - a materially different, "
                         "unconsented purpose and exposure risk.",
    ),
    dict(
        scenario_id=110, scenario_type="novel_purpose_drift",
        sender_type="MECHANIC", sender_did="did:ssi:mechanic:shop1",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user1",
        requested_data=["fuel"], is_emergency=False, has_consent=True, policy_allows=True,
        # FIXED: was normal() which defaults to speed=45 (moving) - contradicted the "scheduled
        # service visit" narrative below, which implies the vehicle is stationary at the shop.
        # A real repair session cannot be happening on a vehicle in motion.
        sensor_data=normal(speed=0, rpm=800),
        context="Routine repair follow-up: fuel reading requested to diagnose a previously reported "
                "stalling issue during a scheduled service visit. Vehicle is parked at the shop, "
                "engine idling.",
        expected_decision="approve",
        expected_reason="CONTROL CASE: purpose is squarely within the repair relationship, and the "
                         "vehicle's stationary/idling sensor state is consistent with an active service "
                         "visit. Included so this set is not artificially rigged to make every mechanic "
                         "request look suspicious.",
    ),

    # ---------------- Category C: novel_ambiguous_emergency ----------------
    dict(
        scenario_id=111, scenario_type="novel_ambiguous_emergency",
        sender_type="EMERGENCY_SERVICE", sender_did="did:ssi:emergency:911",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user1",
        requested_data=["location", "sensor_data", "collision_data"],
        is_emergency=True, has_consent=False, policy_allows=False,
        sensor_data=accident(collision=True, airbag="not_deployed", impact_force=3.0),
        context="Low-speed rollover into a roadside ditch. Airbags did not trigger because the "
                "impact vector was lateral/rollover, not frontal. Occupant reports being trapped "
                "and disoriented via emergency call.",
        expected_decision="approve",
        expected_reason="A genuine emergency masked by the rigid 'collision AND airbag-deployed' "
                         "requirement: rollover impacts often do not trigger frontal airbags at all. "
                         "The rule engine's AND-condition treats this identically to a false claim.",
    ),
    dict(
        scenario_id=112, scenario_type="novel_ambiguous_emergency",
        sender_type="EMERGENCY_SERVICE", sender_did="did:ssi:emergency:ambulance",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user2",
        requested_data=["location", "sensor_data"],
        is_emergency=True, has_consent=False, policy_allows=False,
        sensor_data=accident(collision=False, airbag="not_deployed", impact_force=0),
        context="No collision recorded. Driver manually triggered the in-cabin medical-distress "
                "button while parked, reporting a possible cardiac event.",
        expected_decision="approve",
        expected_reason="A medical emergency entirely unrelated to a collision. The rule engine's "
                         "emergency-override rule is hard-wired to collision/airbag sensors and can "
                         "never approve a non-collision medical emergency, regardless of evidence.",
    ),
    dict(
        scenario_id=113, scenario_type="novel_ambiguous_emergency",
        sender_type="EMERGENCY_SERVICE", sender_did="did:ssi:emergency:911",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user1",
        requested_data=["location", "sensor_data", "collision_data"],
        is_emergency=True, has_consent=False, policy_allows=False,
        sensor_data=accident(collision=True, airbag="deployed", impact_force=4.0),
        context="Moderate-speed rear-end collision. Airbags deployed. Occupant reports neck pain "
                "and requests medical data be shared with responders.",
        expected_decision="approve",
        expected_reason="Collision confirmed and airbags deployed, but impact_force (4.0g) falls "
                         "just under the rule engine's fixed 5g cutoff. An arbitrary numeric threshold "
                         "has no principled reason to treat 4.0g as 'not an emergency' when airbags "
                         "have already deployed - this demonstrates the brittleness of hard thresholds.",
    ),
    dict(
        scenario_id=114, scenario_type="novel_ambiguous_emergency",
        sender_type="EMERGENCY_SERVICE", sender_did="did:ssi:emergency:911",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user2",
        requested_data=["location", "sensor_data", "collision_data"],
        is_emergency=True, has_consent=False, policy_allows=False,
        sensor_data=accident(collision=True, airbag="not_deployed", impact_force=6.5),
        context="High-force lateral side-impact collision. Side-curtain airbags deployed via a "
                "subsystem not reflected in the primary airbag_status sensor field. Occupant "
                "unresponsive.",
        expected_decision="approve",
        expected_reason="impact_force (6.5g) clears the threshold, but airbag_status reads "
                         "'not_deployed' because the sensor schema only tracks the frontal-airbag "
                         "subsystem, not side-curtain airbags. This is a sensor-schema gap: the rule "
                         "engine's rigid AND-condition fails whenever the fixed feature set cannot "
                         "represent the real event, whereas a reasoning system can weigh the impact "
                         "force and context text directly.",
    ),
    dict(
        scenario_id=115, scenario_type="novel_ambiguous_emergency",
        sender_type="EMERGENCY_SERVICE", sender_did="did:ssi:emergency:ambulance",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user1",
        requested_data=["location", "sensor_data"],
        is_emergency=True, has_consent=False, policy_allows=False,
        sensor_data=accident(collision=False, airbag="not_deployed", impact_force=0),
        context="Claimed emergency; driver is requesting expedited data sharing to 'get to a "
                "hospital faster' but there is no collision, distress signal, or reported symptom - "
                "driver admits to just being in a hurry.",
        expected_decision="deny",
        expected_reason="CONTROL CASE: this is a genuine false-emergency claim with no corroborating "
                         "evidence of any kind. The rule engine correctly denies this one too - "
                         "included to show the rule engine is not uniformly wrong on emergencies, "
                         "only on ones its rigid feature set cannot represent.",
    ),

    # ---------------- Category D: novel_unrecognized_entity ----------------
    dict(
        scenario_id=116, scenario_type="novel_unrecognized_entity",
        sender_type="THIRD_PARTY_DATA_BROKER", sender_did="did:ssi:broker:adtech1",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user1",
        requested_data=["location", "user_behavior"], is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(),
        context="A third-party data broker, not enrolled in any service relationship with the "
                "vehicle owner, requests continuous location and behavioral data. Consent flag is "
                "True only because it was bundled into a lengthy app-signup EULA the user never read.",
        expected_decision="deny",
        expected_reason="THIRD_PARTY_DATA_BROKER does not exist in the rule engine's hardcoded "
                         "consent matrix at all, so its scope-check rule is silently skipped and the "
                         "decision collapses to raw policy/consent booleans with no scope check "
                         "whatsoever - approving a bulk location+behavior request with no legitimate "
                         "operational relationship to the vehicle.",
    ),
    dict(
        # REVISED (was mislabeled as an "approve" control case): the original sensor_data
        # used normal(brake="failed") which still defaults to speed=45 - i.e. the vehicle
        # was actively cruising at 45 km/h with otherwise normal telemetry, which flatly
        # contradicts the "broke down on the roadside, needs a tow" claim in the context
        # text. That is not a stationary breakdown; it is a healthy, moving vehicle. This is
        # now an insider-attack / false-pretext scenario: an entity (potentially a spoofed or
        # socially-engineered towing credential) requests location under a fabricated
        # breakdown justification while real-time sensor data shows completely normal
        # operation. The rule engine has no scope-check rule for TOWING_SERVICE at all (it is
        # absent from CONSENT_MATRIX), so it falls straight to the policy+consent fallback and
        # approves purely because those two flags are True - it never cross-references the
        # claimed justification against sensor reality. This is exactly the insider-attack
        # detection mechanism described in Section VI-C1 (mechanic-on-highway) applied to an
        # entity type the rule author never enumerated.
        scenario_id=117, scenario_type="novel_unrecognized_entity",
        sender_type="TOWING_SERVICE", sender_did="did:ssi:towing:service1",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user2",
        requested_data=["location"], is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(),
        context="Entity presenting as a towing service claims the vehicle broke down on the "
                "roadside and requests location to arrange pickup. Vehicle sensors show completely "
                "normal operation: brake_status functional, steady 45 km/h cruising speed, normal "
                "engine RPM and acceleration - no fault codes, no stop, no indication of any "
                "breakdown whatsoever.",
        expected_decision="deny",
        expected_reason="Insider attack / false-pretext detection: the stated justification for "
                         "this request (vehicle breakdown) is directly contradicted by real-time "
                         "sensor evidence showing the vehicle operating normally. TOWING_SERVICE is "
                         "absent from the rule engine's hardcoded consent matrix, so its scope-check "
                         "rule is silently skipped and the decision collapses to raw policy/consent "
                         "booleans (both True here) with no cross-check against sensor reality at "
                         "all - approving a location request justified by a fabricated emergency.",
    ),
    dict(
        scenario_id=118, scenario_type="novel_unrecognized_entity",
        sender_type="SMART_CITY_TRAFFIC_AUTHORITY", sender_did="did:ssi:gov:traffic_dept1",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user1",
        requested_data=["real_time_tracking", "location", "user_behavior"],
        is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(),
        context="A municipal traffic authority requests continuous individual-level vehicle tracking "
                "and behavioral data for 'traffic optimization research'. Consent flag defaulted to "
                "True during a city vehicle-registration renewal, buried in fine print, no explicit "
                "opt-in and no warrant.",
        expected_decision="deny",
        expected_reason="Same brittleness pattern: entity type not in the matrix, no scope check "
                         "applied, request for continuous individually-identifiable tracking approved "
                         "purely because a buried default-consent flag happens to read True.",
    ),
    dict(
        scenario_id=119, scenario_type="novel_unrecognized_entity",
        sender_type="VEHICLE_RECALL_AGENCY", sender_did="did:ssi:recall:agency1",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user2",
        requested_data=["diagnostic_codes"], is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(),
        context="Manufacturer-mandated safety-recall check for a known braking defect affecting this "
                "VIN; a narrow, one-time diagnostic-code read.",
        expected_decision="approve",
        expected_reason="CONTROL CASE: unrecognized entity type, but narrow scope and a legitimate, "
                         "safety-relevant relationship (an active manufacturer recall on this VIN).",
    ),
    dict(
        scenario_id=120, scenario_type="novel_unrecognized_entity",
        sender_type="FLEET_MANAGEMENT_COMPANY", sender_did="did:ssi:fleet:company1",
        recipient_type="INDIVIDUAL", recipient_did="did:ssi:individual:user1",
        requested_data=["location", "speed", "trip_history", "user_behavior"],
        is_emergency=False, has_consent=True, policy_allows=True,
        sensor_data=normal(),
        context="A fleet-management company requests full continuous telemetry access, despite the "
                "vehicle being privately owned and never enrolled in any fleet program. has_consent "
                "flag is set True due to a data-sharing default that was never actually reviewed by "
                "the owner.",
        expected_decision="deny",
        expected_reason="Bulk multi-field request from an entity with no enrollment relationship to "
                         "this specific vehicle; approved by the rule engine purely because the "
                         "unrecognized entity type bypasses the scope-check rule entirely.",
    ),
]

for s in SCENARIOS:
    s["timestamp"] = TIMESTAMP


def main():
    dataset = {
        "metadata": {
            "description": "Held-out generalization test set - hand-crafted, NOT used to design "
                            "rule_based_evaluator.py's rules. Tests whether decision logic "
                            "generalizes to request patterns a rule author did not anticipate.",
            "total_scenarios": len(SCENARIOS),
            "generation_timestamp": TIMESTAMP,
            "novelty_categories": sorted(set(s["scenario_type"] for s in SCENARIOS)),
            "category_counts": {
                cat: sum(1 for s in SCENARIOS if s["scenario_type"] == cat)
                for cat in sorted(set(s["scenario_type"] for s in SCENARIOS))
            },
            "control_case_ids": [110, 115, 119],
            "note": "control_case_ids are cases where the correct decision matches what the rule "
                    "engine actually produces, included to avoid rigging this set to make the rule "
                    "engine fail on everything. Scenario 117 was originally a control case but was "
                    "found to have an internally inconsistent sensor_data/context pairing (claimed "
                    "vehicle breakdown contradicted by normal sensor telemetry) and has been revised "
                    "into a genuine insider-attack/false-pretext deny case instead - see the comment "
                    "on scenario 117 above for details.",
        },
        "scenarios": SCENARIOS,
    }
    with open("generalization_test_dataset.json", "w") as f:
        json.dump(dataset, f, indent=2)
    print(f"Saved {len(SCENARIOS)} scenarios to generalization_test_dataset.json")
    for cat, count in dataset["metadata"]["category_counts"].items():
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
