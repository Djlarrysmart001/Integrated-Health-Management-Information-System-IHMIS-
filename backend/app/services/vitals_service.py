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
    def get_vitals(patient_id=None, health_file_id=None, recorded_by=None,
                    date_from=None, date_to=None, search=None, page=1, per_page=20):
        """
        Two response shapes, chosen automatically:

        - LOOKUP mode (patient_id or health_file_id given): returns a plain
          list under "data" -- matches what consultation.html / queue.html
          already expect from GET /vitals?health_file_id=<id>.

        - SUMMARY mode (neither given -- e.g. a nurse's "patients seen"
          history): returns {"items": [...], "total": N, "pages": P,
          "current_page": page} under "data". Each item is enriched with
          patient_name / patient_number (VitalSigns itself only stores
          patient_id) and health_file_status (the file's CURRENT stage --
          e.g. a vitals record taken this morning may now show "closed" if
          the visit has already finished; this reflects where the patient
          is right now, not a frozen snapshot of the moment vitals were
          recorded).

        RBAC scoping (who is allowed to land in summary mode with which
        recorded_by) is enforced by the route, not here -- this method
        trusts whatever filters it's given.
        """
        query = VitalSigns.query
        if patient_id:
            query = query.filter(VitalSigns.patient_id == patient_id)
        if health_file_id:
            query = query.filter(VitalSigns.health_file_id == health_file_id)
        if recorded_by:
            query = query.filter(VitalSigns.recorded_by == recorded_by)
        if date_from:
            query = query.filter(VitalSigns.recorded_at >= date_from)
        if date_to:
            query = query.filter(VitalSigns.recorded_at < date_to)
        if search:
            query = query.join(Patient, VitalSigns.patient_id == Patient.id).filter(
                db.or_(
                    Patient.first_name.ilike(f"%{search}%"),
                    Patient.last_name.ilike(f"%{search}%"),
                    Patient.patient_number.ilike(f"%{search}%"),
                )
            )

        query = query.order_by(VitalSigns.recorded_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        summary_mode = not patient_id and not health_file_id
        if summary_mode:
            items = []
            for v in pagination.items:
                d = v.to_dict()
                d["patient_name"]   = v.patient.full_name if v.patient else None
                d["patient_number"] = v.patient.patient_number if v.patient else None
                d["health_file_status"] = v.health_file.status if v.health_file else None
                items.append(d)
        else:
            items = [v.to_dict() for v in pagination.items]

        data = {
            "items": items,
            "total": pagination.total,
            "pages": pagination.pages,
            "current_page": page,
        } if summary_mode else items

        return {
            "success": True,
            "message": "Vitals retrieved successfully.",
            "data": data,
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