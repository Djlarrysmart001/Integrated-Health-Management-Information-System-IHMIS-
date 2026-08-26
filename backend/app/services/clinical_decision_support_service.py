# app/services/clinical_decision_support_service.py

from itertools import combinations
from app.models.drug_interaction import DrugInteraction


class ClinicalDecisionSupportService:
    """
    Rule-based (knowledge-lookup) drug interaction checking -- the same
    category of AI as Triage Assistant and Inventory Forecast: a
    knowledge base consulted at request time, not a trained model.

    Given the set of drug IDs a Doctor currently has in a prescription,
    checks every unordered pair against the drug_interactions table (see
    DrugInteraction model + seed_drug_interactions.py).

    Unlike Triage or Inventory Forecast, this does NOT create an
    AIRecommendation row. The prescription doesn't exist as a persisted
    entity yet while the Doctor is still adding/removing drugs -- there
    is nothing stable to attach a recommendation to, and the check result
    changes every time a drug is added or removed. Each match found is
    still logged to AuditLog when a consultation_id is available, keeping
    the "every AI suggestion is logged" principle intact without forcing
    a mismatched data model onto a live, in-progress interaction.
    """

    @staticmethod
    def check_interactions(drug_ids: list) -> list:
        """Pure lookup, no writes. Returns a list of matched interaction
        dicts (empty list if fewer than 2 unique drugs or no matches)."""
        unique_ids = sorted({int(d) for d in drug_ids if d})
        if len(unique_ids) < 2:
            return []

        pairs = list(combinations(unique_ids, 2))  # already sorted since unique_ids is sorted

        matches = []
        for id_a, id_b in pairs:
            rec = DrugInteraction.query.filter_by(
                drug_id_a=id_a, drug_id_b=id_b
            ).first()
            if rec:
                matches.append(rec.to_dict())

        return matches

    @staticmethod
    def check_and_log(drug_ids: list, doctor_id: int, consultation_id: int = None) -> dict:
        """Wraps check_interactions() with audit logging for any matches
        found, when a consultation_id is available to attach the log to."""
        from app.services.audit_service import AuditService

        matches = ClinicalDecisionSupportService.check_interactions(drug_ids)

        if matches and consultation_id:
            AuditService.log(
                action="DRUG_INTERACTION_WARNING_SHOWN",
                entity_type="Consultation",
                entity_id=consultation_id,
                user_id=doctor_id,
                new_value={"drug_ids": drug_ids, "interactions": matches},
            )

        return {
            "success": True,
            "message": (
                f"{len(matches)} potential interaction(s) found."
                if matches else "No known interactions found."
            ),
            "data": {"interactions": matches},
        }