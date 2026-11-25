package refund.guardrails_test

import data.refund.guardrails

base := {
	"model": {"repo": "AlexWortega/openjev", "checkpoint": "qwen3.5-0.8b-nli-v2s-long"},
	"judgments": {"wants_refund": 0.97, "product_defective": 0.05, "legal_threat": 0.02},
	"facts": {"order_amount_eur": 14.99, "days_since_delivery": 5, "refunds_last_12_months": 0},
	"decision": {"outcome": "AUTO_REFUND", "decided_by": "R5", "policy_version": "v2"},
}

test_small_confident_refund_allowed if {
	guardrails.allow with input as base
}

test_refund_above_cap_denied if {
	inp := json.patch(base, [{"op": "replace", "path": "/facts/order_amount_eur", "value": 44.9}])
	not guardrails.allow with input as inp
	guardrails.result.final_outcome == "HUMAN_REVIEW" with input as inp
}

test_legal_risk_blocks_automation if {
	inp := json.patch(base, [{"op": "replace", "path": "/judgments/legal_threat", "value": 0.4}])
	not guardrails.allow with input as inp
}

test_legal_risk_ok_for_human_outcomes if {
	inp := json.patch(base, [
		{"op": "replace", "path": "/judgments/legal_threat", "value": 0.4},
		{"op": "replace", "path": "/decision/outcome", "value": "FORWARD_AGENT"},
	])
	guardrails.allow with input as inp
}

test_unsure_refund_denied if {
	inp := json.patch(base, [{"op": "replace", "path": "/judgments/wants_refund", "value": 0.8}])
	not guardrails.allow with input as inp
}

test_unsure_not_a_refund_denied if {
	inp := json.patch(base, [
		{"op": "replace", "path": "/judgments/wants_refund", "value": 0.2},
		{"op": "replace", "path": "/decision/outcome", "value": "NOT_A_REFUND"},
	])
	not guardrails.allow with input as inp
}

test_unapproved_model_denied if {
	inp := json.patch(base, [{"op": "replace", "path": "/model/checkpoint", "value": "some-new-checkpoint"}])
	not guardrails.allow with input as inp
}

test_human_outcomes_always_allowed if {
	inp := json.patch(base, [
		{"op": "replace", "path": "/decision/outcome", "value": "HUMAN_REVIEW"},
		{"op": "replace", "path": "/facts/order_amount_eur", "value": 999},
		{"op": "replace", "path": "/model/checkpoint", "value": "unknown"},
	])
	guardrails.allow with input as inp
}
