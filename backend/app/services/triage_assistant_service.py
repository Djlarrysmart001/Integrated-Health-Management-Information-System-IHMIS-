# app/services/triage_assistant_service.py

from datetime import datetime, timezone
from app.extensions import db
from app.models.vital_signs import VitalSigns
from app.models.ai_recommendation import AIRecommendation
from app.utils.constants import Roles


class TriageAssistantService:
    """
    Rule-based (not machine-learned) triage scoring.

    NOTE (important for the report): this is ADAPTED FROM NEWS2 principles,
    it is NOT a validated clinical scoring instrument and must not be
    described as full NEWS2. VitalSigns does not capture consciousness
    level (AVPU) or supplemental-oxygen-use, both required parameters of
    real NEWS2 — those two parameters are simply omitted here rather than
    guessed at. Five of the seven NEWS2 parameters are scored (respiratory
    rate, SpO2, systolic BP, pulse rate, temperature), plus one addition
    beyond NEWS2: a pain_score >= 7 flag, since pain_score is already
    captured on this form and is clinically relevant to a Nurse's triage
    decision even though it isn't part of NEWS2 itself.

    Manually triggered per VitalSigns record (Nurse clicks "Score Vitals"
    after recording) — not automatic on every submission, so the Nurse
    stays in control of when the AI is consulted.

    Like the Inventory Forecast, this NEVER writes to VitalSigns or
    Consultation directly. It only creates/updates an AIRecommendation for
    the Nurse (and, read-only, the Doctor) to see.
    """

    # ──────────────────────────────────────────────────────────
    # Per-parameter scoring bands (0-3 each), adapted from NEWS2
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _score_respiratory_rate(rr):
        if rr is None: return None
        if rr <= 8:  return 3
        if rr <= 11: return 1
        if rr <= 20: return 0
        if rr <= 24: return 2
        return 3

    @staticmethod
    def _score_spo2(spo2):
        if spo2 is None: return None
        if spo2 <= 91: return 3
        if spo2 <= 93: return 2
        if spo2 <= 95: return 1
        return 0

    @staticmethod
    def _score_systolic_bp(sbp):
        if sbp is None: return None
        if sbp <= 90:  return 3
        if sbp <= 100: return 2
        if sbp <= 110: return 1
        if sbp <= 219: return 0
        return 3

    @staticmethod
    def _score_pulse_rate(pr):
        if pr is None: return None
        if pr <= 40:  return 3
        if pr <= 50:  return 1
        if pr <= 90:  return 0
        if pr <= 110: return 1
        if pr <= 130: return 2
        return 3

    @staticmethod
    def _score_temperature(temp):
        if temp is None: return None
        temp = float(temp)
        if temp <= 35.0: return 3
        if temp <= 36.0: return 1
        if temp <= 38.0: return 0
        if temp <= 39.0: return 1
        return 2

    # ──────────────────────────────────────────────────────────
    # Score a single VitalSigns record (pure calculation, no writes)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _compute_score(vitals: VitalSigns) -> dict:
        params = {
            "respiratory_rate": (vitals.respiratory_rate,
                                  TriageAssistantService._score_respiratory_rate(vitals.respiratory_rate)),
            "spo2":             (float(vitals.oxygen_saturation) if vitals.oxygen_saturation is not None else None,
                                  TriageAssistantService._score_spo2(
                                      float(vitals.oxygen_saturation) if vitals.oxygen_saturation is not None else None)),
            "systolic_bp":      (vitals.blood_pressure_systolic,
                                  TriageAssistantService._score_systolic_bp(vitals.blood_pressure_systolic)),
            "pulse_rate":       (vitals.pulse_rate,
                                  TriageAssistantService._score_pulse_rate(vitals.pulse_rate)),
            "temperature":      (float(vitals.temperature) if vitals.temperature is not None else None,
                                  TriageAssistantService._score_temperature(vitals.temperature)),
        }

        scored_params = {k: v for k, (raw, v) in params.items() if v is not None}
        skipped_params = [k for k, (raw, v) in params.items() if v is None]

        total_score = sum(scored_params.values())
        any_single_param_critical = any(v == 3 for v in scored_params.values())

        severe_pain = vitals.pain_score is not None and vitals.pain_score >= 7

        # NEWS2-style escalation rule: a single parameter scoring 3 forces
        # at least "Watch", regardless of the total.
        if total_score >= 7:
            band = "Urgent"
        elif total_score >= 5 or any_single_param_critical:
            band = "Watch"
        else:
            band = "Normal"

        reasons = []
        param_labels = {
            "respiratory_rate": "Respiratory rate",
            "spo2":             "Oxygen saturation",
            "systolic_bp":      "Systolic BP",
            "pulse_rate":       "Pulse rate",
            "temperature":      "Temperature",
        }
        for key, points in scored_params.items():
            if points >= 2:
                raw_value = params[key][0]
                reasons.append(f"{param_labels[key]} abnormal ({raw_value}), scored {points}/3")
        if severe_pain:
            reasons.append(f"Severe pain reported (pain_score={vitals.pain_score}/10)")
        if skipped_params:
            reasons.append(
                "Not scored (missing): " + ", ".join(param_labels[k] for k in skipped_params)
            )

        return {
            "vitals_id":      vitals.id,
            "patient_id":     vitals.patient_id,
            "total_score":    total_score,
            "band":           band,
            "severe_pain":    severe_pain,
            "params_scored":  scored_params,
            "params_skipped": skipped_params,
            "reasons":        reasons,
            "nurse_urgency_level": vitals.urgency_level,  # for comparison only, never overwritten
        }

    # ──────────────────────────────────────────────────────────
    # Run the score for one vitals record (writes a recommendation)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def run_triage_score(vitals_id: int, triggered_by: int) -> dict:
        from app.services.audit_service import AuditService

        vitals = VitalSigns.query.get(vitals_id)
        if not vitals:
            return {"success": False, "message": f"Vitals record {vitals_id} not found.", "data": None}

        score = TriageAssistantService._compute_score(vitals)

        existing_pending = AIRecommendation.query.filter_by(
            recommendation_type="TRIAGE_SCORE",
            source_entity_type="VitalSigns",
            source_entity_id=vitals.id,
            status="pending",
        ).first()

        if existing_pending:
            existing_pending.payload = score
            existing_pending.generated_at = datetime.now(timezone.utc)
            db.session.commit()
            rec = existing_pending
        else:
            rec = AIRecommendation(
                recommendation_type="TRIAGE_SCORE",
                source_entity_type="VitalSigns",
                source_entity_id=vitals.id,
                target_role=Roles.NURSE,
                payload=score,
                status="pending",
            )
            db.session.add(rec)
            db.session.commit()

        AuditService.log(
            action="GENERATE_AI_RECOMMENDATION",
            entity_type="AIRecommendation",
            entity_id=rec.id,
            user_id=triggered_by,
            new_value=score,
        )

        return {"success": True, "message": f"Triage score computed: {score['band']}.", "data": rec.to_dict()}

    # ──────────────────────────────────────────────────────────
    # Read the latest recommendation for a vitals record
    # (used by both Nurse vitals page and Doctor consultation view)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_score_for_vitals(vitals_id: int) -> dict:
        rec = AIRecommendation.query.filter_by(
            recommendation_type="TRIAGE_SCORE",
            source_entity_type="VitalSigns",
            source_entity_id=vitals_id,
        ).order_by(AIRecommendation.generated_at.desc()).first()

        if not rec:
            return {"success": True, "message": "No triage score computed yet.", "data": None}

        return {"success": True, "message": "Triage score retrieved.", "data": rec.to_dict()}