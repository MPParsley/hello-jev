# Guardrails for AI-assisted refund decisions - the "control" layer of demo 3.
#
# The business policy (scripts/refund_policy.py) proposes a decision. This
# policy, owned by risk/compliance, checks it before it is carried out.
# It does not repeat the business logic; it states limits that must hold
# whatever the business rules say. Any deny turns the decision into a
# human review.
#
# Input:
#   {
#     "model":     {"repo": "...", "checkpoint": "..."},
#     "judgments": {"wants_refund": 0.97, "legal_threat": 0.01, ...},
#     "facts":     {"order_amount_eur": 14.99, ...},
#     "decision":  {"outcome": "AUTO_REFUND", "decided_by": "R5", "policy_version": "v2"}
#   }
package refund.guardrails

# Hard cap on money paid out without a human.
max_auto_refund_eur := 25.00

# Above this legal-threat score no decision may be taken without a human,
# even far below the business policy's escalation threshold.
max_legal_for_automation := 0.30

# Minimum model confidence for automated outcomes (EU AI Act spirit: human
# oversight where the AI component is unsure).
min_confidence := 0.90

# Only model versions that were evaluated and approved may drive automation.
approved_models := {
	"AlexWortega/openjev@qwen3.5-0.8b-nli-v2s-long",
	"AlexWortega/openjev@qwen3.5-2b-nli-v5",
}

# Outcomes that take effect without a person looking at the ticket.
automatic_outcomes := {"AUTO_REFUND", "NOT_A_REFUND"}

automatic if input.decision.outcome in automatic_outcomes

model_id := sprintf("%s@%s", [input.model.repo, input.model.checkpoint])

deny contains msg if {
	input.decision.outcome == "AUTO_REFUND"
	input.facts.order_amount_eur > max_auto_refund_eur
	msg := sprintf(
		"G1 automatische terugbetaling van €%.2f boven het plafond van €%.2f",
		[input.facts.order_amount_eur, max_auto_refund_eur],
	)
}

deny contains msg if {
	automatic
	input.judgments.legal_threat > max_legal_for_automation
	msg := sprintf(
		"G2 legal_threat %v%% > %v%%: geen automatische beslissing bij mogelijk juridisch risico",
		[round(input.judgments.legal_threat * 100), round(max_legal_for_automation * 100)],
	)
}

deny contains msg if {
	input.decision.outcome == "AUTO_REFUND"
	input.judgments.wants_refund < min_confidence
	msg := sprintf(
		"G3 wants_refund %v%% < %v%%: te onzeker om automatisch te betalen",
		[round(input.judgments.wants_refund * 100), round(min_confidence * 100)],
	)
}

deny contains msg if {
	input.decision.outcome == "NOT_A_REFUND"
	input.judgments.wants_refund > 1 - min_confidence
	msg := sprintf(
		"G3 wants_refund %v%% > %v%%: te onzeker om als gewone vraag af te handelen",
		[round(input.judgments.wants_refund * 100), round((1 - min_confidence) * 100)],
	)
}

deny contains msg if {
	automatic
	not model_id in approved_models
	msg := sprintf("G4 model %s is niet goedgekeurd voor automatische beslissingen", [model_id])
}

default allow := false

allow if count(deny) == 0

final_outcome := input.decision.outcome if allow

final_outcome := "HUMAN_REVIEW" if not allow

result := {
	"allow": allow,
	"deny": sort([m | some m in deny]),
	"final_outcome": final_outcome,
}
