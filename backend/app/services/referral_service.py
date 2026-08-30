# app/services/referral_service.py

from datetime import datetime, timezone
from app.extensions import db
from app.models.referral import Referral
from app.models.consultation import Consultation
from app.models.patient import Patient
from app.services.health_file_service import HealthFileService


class ReferralService:

    @staticmethod
    def issue_referral(data: dict, referred_by: int):
        """
        Doctor refers a patient to an external facility (specialist
        care, imaging, treatment beyond what the clinic can offer).

        Required fields:
            consultation_id, referred_to_facility

        Optional fields:
            reason, urgency (routine/urgent/emergency, default routine), notes
        """
        consultation = Consultation.query.get(data.get("consultation_id"))
        if not consultation:
            return {"success": False, "message": f"Consultation with ID {data.get('consultation_id')} not found.", "data": None}

        if not (data.get("referred_to_facility") or "").strip():
            return {"success": False, "message": "'referred_to_facility' is required.", "data": None}

        urgency = data.get("urgency", "routine")
        if urgency not in ["routine", "urgent", "emergency"]:
            return {"success": False, "message": "urgency must be 'routine', 'urgent', or 'emergency'.", "data": None}

        referral = Referral(
            consultation_id      = data["consultation_id"],
            patient_id           = consultation.patient_id,
            referred_by          = referred_by,
            referred_to_facility = data["referred_to_facility"].strip(),
            reason               = (data.get("reason") or "").strip() or None,
            urgency              = urgency,
            status               = "issued",
            notes                = (data.get("notes") or "").strip() or None,
        )
        db.session.add(referral)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "ISSUE_REFERRAL",
            entity_type = "Referral",
            entity_id   = referral.id,
            user_id     = referred_by,
            new_value   = {
                "patient_id": consultation.patient_id,
                "referred_to_facility": referral.referred_to_facility,
                "urgency": urgency,
            }
        )
        # ───────────────────────────────────────────────────────

        # ── Close the health file — the visit ends here; the patient ──
        # is going to an external facility instead of Pharmacy.
        # Non-fatal: if this consultation isn't tied to a health file
        # (legacy data), the referral itself still stands.
        if consultation.health_file_id:
            HealthFileService.close_via_referral(consultation.health_file_id, referred_by)
        # ───────────────────────────────────────────────────────

        patient = Patient.query.get(consultation.patient_id)
        return {
            "success": True,
            "message": f"{patient.full_name if patient else 'Patient'} referred to {referral.referred_to_facility}.",
            "data": referral.to_dict()
        }

    @staticmethod
    def get_referral_by_id(referral_id: int):
        referral = Referral.query.get(referral_id)
        if not referral:
            return {"success": False, "message": f"Referral with ID {referral_id} not found.", "data": None}
        return {"success": True, "message": "Referral retrieved successfully.", "data": referral.to_dict()}

    @staticmethod
    def get_patient_referrals(patient_id: int, page=1, per_page=10):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}

        pagination = Referral.query.filter_by(patient_id=patient_id).order_by(
            Referral.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"Referral history for {patient.full_name} retrieved.",
            "data": {
                "patient_id":   patient_id,
                "patient_name": patient.full_name,
                "referrals":    [r.to_dict() for r in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }

    @staticmethod
    def get_all_referrals(page=1, per_page=20, status=None, urgency=None, doctor_id=None):
        query = Referral.query
        if status:
            query = query.filter(Referral.status == status)
        if urgency:
            query = query.filter(Referral.urgency == urgency)
        if doctor_id is not None:
            query = query.filter(Referral.referred_by == doctor_id)

        query = query.order_by(Referral.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": "Referrals retrieved successfully.",
            "data": {
                "referrals":    [r.to_dict() for r in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }

    @staticmethod
    def update_referral_status(referral_id: int, new_status: str, notes: str = None, updated_by: int = None):
        """
        Updates a referral's lifecycle status based on follow-up with
        the external facility (e.g. confirmation the patient was seen).

        Valid transitions:
            issued -> accepted -> completed
            issued/accepted -> cancelled
        """
        referral = Referral.query.get(referral_id)
        if not referral:
            return {"success": False, "message": f"Referral with ID {referral_id} not found.", "data": None}

        valid_statuses = ["issued", "accepted", "completed", "cancelled"]
        if new_status not in valid_statuses:
            return {"success": False, "message": f"Invalid status. Valid options: {', '.join(valid_statuses)}", "data": None}

        allowed_transitions = {
            "issued":    ["accepted", "cancelled"],
            "accepted":  ["completed", "cancelled"],
            "completed": [],
            "cancelled": [],
        }
        if new_status not in allowed_transitions[referral.status]:
            return {
                "success": False,
                "message": f"Cannot change status from '{referral.status}' to '{new_status}'.",
                "data": None
            }

        old_status      = referral.status
        referral.status = new_status
        if notes:
            referral.notes = ((referral.notes + "\n") if referral.notes else "") + notes.strip()
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "UPDATE_REFERRAL_STATUS",
            entity_type = "Referral",
            entity_id   = referral_id,
            user_id     = updated_by,
            old_value   = {"status": old_status},
            new_value   = {"status": new_status}
        )
        # ───────────────────────────────────────────────────────

        return {"success": True, "message": f"Referral status updated to '{new_status}'.", "data": referral.to_dict()}