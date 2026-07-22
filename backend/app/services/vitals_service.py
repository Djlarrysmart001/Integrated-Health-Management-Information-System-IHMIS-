# app/services/vitals_service.py

from app.extensions import db
from app.models.vital_signs import VitalSigns
from app.models.patient import Patient

REQUIRED_FIELDS = [
    "patient_id", "health_file_id", "weight", "height", "temperature",
    "bp_systolic", "bp_diastolic", "pulse_rate", "chief_complaint", "urgency_level",
]
VALID_URGENCY = ("emergency", "high", "normal", "low")


class VitalsService:

    @staticmethod
    def record_vitals(data: dict, recorded_by: int):
        missing = [f for f in REQUIRED_FIELDS if not data.get(f) and data.get(f) != 0]
        if missing:
            return {"success": False, "message": f"Missing required field(s): {', '.join(missing)}.", "data": None}

        if data["urgency_level"] not in VALID_URGENCY:
            return {"success": False, "message": f"Invalid urgency_level. Must be one of: {', '.join(VALID_URGENCY)}.", "data": None}

        patient = Patient.query.get(data["patient_id"])
        if not patient:
            return {"success": False, "message": f"Patient with ID {data['patient_id']} not found.", "data": None}

        vitals = VitalSigns(
            patient_id               = data["patient_id"],
            health_file_id            = data.get("health_file_id"),
            consultation_id           = data.get("consultation_id"),

            blood_pressure_systolic  = data.get("bp_systolic"),
            blood_pressure_diastolic  = data.get("bp_diastolic"),
            pulse_rate                = data.get("pulse_rate"),
            temperature                = data.get("temperature"),
            weight                     = data.get("weight"),
            height                      = data.get("height"),
            oxygen_saturation           = data.get("spo2"),
            respiratory_rate            = data.get("respiratory_rate"),
            blood_sugar                 = data.get("blood_sugar"),
            pain_score                  = data.get("pain_score"),

            chief_complaint             = (data.get("chief_complaint") or "").strip() or None,
            symptoms                    = (data.get("symptoms") or "").strip() or None,
            duration_of_illness         = (data.get("duration_of_illness") or "").strip() or None,
            general_observations        = (data.get("general_observations") or "").strip() or None,
            urgency_level                = data["urgency_level"],

            nursing_flags                = data.get("nursing_flags") or [],
            nursing_notes                 = (data.get("nursing_notes") or "").strip() or None,

            recorded_by                   = recorded_by,
        )
        vitals.compute_bmi()  # server-side is authoritative — ignores any client-sent bmi

        db.session.add(vitals)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "RECORD_VITALS",
            entity_type = "VitalSigns",
            entity_id   = vitals.id,
            user_id     = recorded_by,
            new_value   = {"patient_id": vitals.patient_id, "health_file_id": vitals.health_file_id,
                            "urgency_level": vitals.urgency_level}
        )
        # ───────────────────────────────────────────────────────

        return {"success": True, "message": "Vitals recorded successfully.", "data": vitals.to_dict()}

    @staticmethod
    def get_vitals(patient_id=None, health_file_id=None, page=1, per_page=20):
        """Returns a plain list (not a paginated envelope) — matches what
        consultation.html / queue.html already expect from
        GET /vitals?health_file_id=<id> (Array.isArray(res.data))."""
        query = VitalSigns.query
        if patient_id:
            query = query.filter(VitalSigns.patient_id == patient_id)
        if health_file_id:
            query = query.filter(VitalSigns.health_file_id == health_file_id)

        query = query.order_by(VitalSigns.recorded_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": "Vitals retrieved successfully.",
            "data": [v.to_dict() for v in pagination.items],
        }

    @staticmethod
    def get_vitals_by_id(vitals_id: int):
        vitals = VitalSigns.query.get(vitals_id)
        if not vitals:
            return {"success": False, "message": f"Vitals record with ID {vitals_id} not found.", "data": None}
        return {"success": True, "message": "Vitals record retrieved successfully.", "data": vitals.to_dict()}

    @staticmethod
    def get_patient_vitals_history(patient_id: int, page=1, per_page=10):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}

        pagination = VitalSigns.query.filter_by(
            patient_id=patient_id
        ).order_by(VitalSigns.recorded_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"Vitals history for {patient.full_name} retrieved.",
            "data": {
                "patient_id":   patient_id,
                "patient_name": patient.full_name,
                "vitals":       [v.to_dict() for v in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }