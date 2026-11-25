"""Deterministic refund policy - the "decision" half of demo 2.

This module deliberately imports no AI code. It receives:
  * judgments: probabilities from OpenJev for atomic questions, and
  * facts:     hard data from the order system (amount, dates, history),
and applies ordered business rules with explicit thresholds. The first rule
that matches decides; every rule is still evaluated so the trace shows why
the others did not fire. The same contract (judgments + facts in, decision +
trace out) could be served by a policy engine such as OPA.
"""

from dataclasses import asdict, dataclass

# Atomic judgments: one independent yes/no question per hypothesis.
# The model is never told about amounts, deadlines or what happens next.
JUDGMENTS = {
    "wants_refund": "The customer wants their money back.",
    "product_defective": "The product the customer received is broken or defective.",
    "legal_threat": "The customer says they will involve a lawyer or go to court.",
}

# Explicit thresholds instead of argmax.
CONFIDENT_YES = 0.90   # P(entailment) at or above this counts as "yes"
CONFIDENT_NO = 0.10    # P(entailment) below this counts as "no"; in between = unsure
LEGAL_THRESHOLD = 0.80
AUTO_REFUND_MAX_EUR = 25.00
RETURN_WINDOW_DAYS = 30
WARRANTY_DAYS = 730
MAX_REFUNDS_PER_YEAR = 3

OUTCOMES = {
    "ESCALATE_LEGAL": "Doorsturen naar juridische dienst",
    "NOT_A_REFUND": "Geen terugbetalingsvraag: gewone supportflow",
    "HUMAN_REVIEW": "Menselijke review: oordeel te onzeker",
    "FORWARD_AGENT": "Doorsturen naar medewerker",
    "AUTO_REFUND": "Automatisch terugbetalen",
}


@dataclass
class Facts:
    order_amount_eur: float
    days_since_delivery: int
    refunds_last_12_months: int


@dataclass
class RuleResult:
    rule: str
    description: str
    matched: bool
    reason: str
    outcome: str | None = None


def _eur(x: float) -> str:
    return f"€{x:.2f}".replace(".", ",")


def evaluate(judgments: dict[str, float], facts: Facts) -> dict:
    """Apply the policy. `judgments` maps judgment id -> P(entailment)."""
    wants = judgments["wants_refund"]
    defective = judgments["product_defective"]
    legal = judgments["legal_threat"]
    window = WARRANTY_DAYS if defective >= CONFIDENT_YES else RETURN_WINDOW_DAYS
    window_why = "garantie (defect)" if window == WARRANTY_DAYS else "retourtermijn"

    rules = [
        RuleResult(
            "R1", f"legal_threat ≥ {LEGAL_THRESHOLD:.0%} → juridische dienst",
            legal >= LEGAL_THRESHOLD,
            f"legal_threat = {legal:.1%}", "ESCALATE_LEGAL"),
        RuleResult(
            "R2", f"wants_refund < {CONFIDENT_NO:.0%} → geen terugbetalingsvraag",
            wants < CONFIDENT_NO,
            f"wants_refund = {wants:.1%}", "NOT_A_REFUND"),
        RuleResult(
            "R3", f"{CONFIDENT_NO:.0%} ≤ wants_refund < {CONFIDENT_YES:.0%} → menselijke review",
            CONFIDENT_NO <= wants < CONFIDENT_YES,
            f"wants_refund = {wants:.1%}", "HUMAN_REVIEW"),
        RuleResult(
            "R4", f"buiten termijn ({RETURN_WINDOW_DAYS} d, of {WARRANTY_DAYS} d als "
                  f"product_defective ≥ {CONFIDENT_YES:.0%}) of ≥ {MAX_REFUNDS_PER_YEAR} "
                  "terugbetalingen in 12 maanden → medewerker",
            facts.days_since_delivery > window
            or facts.refunds_last_12_months >= MAX_REFUNDS_PER_YEAR,
            f"{facts.days_since_delivery} d sinds levering, termijn {window} d "
            f"({window_why}); {facts.refunds_last_12_months} eerdere terugbetalingen",
            "FORWARD_AGENT"),
        RuleResult(
            "R5", f"bedrag ≤ {_eur(AUTO_REFUND_MAX_EUR)} → automatisch terugbetalen",
            facts.order_amount_eur <= AUTO_REFUND_MAX_EUR,
            f"bedrag = {_eur(facts.order_amount_eur)}", "AUTO_REFUND"),
        RuleResult(
            "R6", "anders → medewerker", True,
            f"bedrag {_eur(facts.order_amount_eur)} > {_eur(AUTO_REFUND_MAX_EUR)}",
            "FORWARD_AGENT"),
    ]
    decided = next(r for r in rules if r.matched)
    return {
        "outcome": decided.outcome,
        "outcome_label": OUTCOMES[decided.outcome],
        "decided_by": decided.rule,
        "trace": [asdict(r) for r in rules],
    }


def describe() -> dict:
    """Policy parameters, published alongside the results for transparency."""
    return {
        "judgments": JUDGMENTS,
        "thresholds": {
            "confident_yes": CONFIDENT_YES,
            "confident_no": CONFIDENT_NO,
            "legal_threshold": LEGAL_THRESHOLD,
            "auto_refund_max_eur": AUTO_REFUND_MAX_EUR,
            "return_window_days": RETURN_WINDOW_DAYS,
            "warranty_days": WARRANTY_DAYS,
            "max_refunds_per_year": MAX_REFUNDS_PER_YEAR,
        },
        "outcomes": OUTCOMES,
    }
