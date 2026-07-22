# app/services/immunization_service.py

from datetime import datetime, timezone, date, timedelta
from app.extensions import db
from app.models.immunization import Immunization
from app.models.patient import Patient


class ImmunizationService:

    @staticmethod
    def record_immunization(data: dict, administered_by: int):
        """
        Nurse or Doctor records a vaccine dose given to a patient.

        Required fields:
            patient_id, vaccine_name, date_administered

        Optional fields:
            dose_number (default 1), batch_number, site,
            next_dose_due, adverse_reaction, notes
        """
        patient = Patient.query.get(data.get("patient_id"))
        if not patient:
            return {"success": False, "message": f"Patient with ID {data.get('patient_id')} not found.", "data": None}

        if not (data.get("vaccine_name") or "").strip():
            return {"success": False, "message": "'vaccine_name' is required.", "data": None}

        if not data.get("date_administered"):
            return {"success": False, "message": "'date_administered' is required.", "data": None}

        try:
            date_administered = datetime.strptime(data["date_administered"], "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "message": "Invalid 'date_administered' format. Use YYYY-MM-DD.", "data": None}

        if date_administered > date.today():
            return {"success": False, "message": "'date_administered' cannot be in the future.", "data": None}

        next_dose_due = None
        if data.get("next_dose_due"):
            try:
                next_dose_due = datetime.strptime(data["next_dose_due"], "%Y-%m-%d").date()
            except ValueError:
                return {"success": False, "message": "Invalid 'next_dose_due' format. Use YYYY-MM-DD.", "data": None}

        dose_number = data.get("dose_number", 1)
        try:
            dose_number = int(dose_number)
            if dose_number < 1:
                raise ValueError
        except (TypeError, ValueError):
            return {"success": False, "message": "'dose_number' must be a positive integer.", "data": None}

        # Warn (but don't block) if this exact dose was already recorded —
        # duplicate entry is more likely a mistake than a real re-dose.
        duplicate = Immunization.query.filter_by(
            patient_id=data["patient_id"],
            vaccine_name=data["vaccine_name"].strip(),
            dose_number=dose_number
        ).first()

        immunization = Immunization(
            patient_id         = data["patient_id"],
            vaccine_name       = data["vaccine_name"].strip(),
            dose_number        = dose_number,
            date_administered  = date_administered,
            administered_by    = administered_by,
            batch_number       = (data.get("batch_number") or "").strip() or None,
            site               = (data.get("site") or "").strip() or None,
            next_dose_due      = next_dose_due,
            adverse_reaction   = (data.get("adverse_reaction") or "").strip() or None,
            notes              = (data.get("notes") or "").strip() or None,
        )
        db.session.add(immunization)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "RECORD_IMMUNIZATION",
            entity_type = "Immunization",
            entity_id   = immunization.id,
            user_id     = administered_by,
            new_value   = {"vaccine_name": immunization.vaccine_name, "dose_number": dose_number}
        )
        # ───────────────────────────────────────────────────────

        message = f"{immunization.vaccine_name} (dose {dose_number}) recorded for {patient.full_name}."
        if duplicate:
            message += f" Note: dose {dose_number} of this vaccine was already on record (ID {duplicate.id}) — please verify this isn't a duplicate entry."

        return {"success": True, "message": message, "data": immunization.to_dict()}

    @staticmethod
    def get_immunization_by_id(immunization_id: int):
        immunization = Immunization.query.get(immunization_id)
        if not immunization:
            return {"success": False, "message": f"Immunization record with ID {immunization_id} not found.", "data": None}
        return {"success": True, "message": "Immunization record retrieved successfully.", "data": immunization.to_dict()}

    @staticmethod
    def get_patient_immunizations(patient_id: int):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}

        records = Immunization.query.filter_by(patient_id=patient_id).order_by(
            Immunization.date_administered.desc()
        ).all()

        return {
            "success": True,
            "message": f"Immunization history for {patient.full_name} retrieved.",
            "data": {
                "patient_id":    patient_id,
                "patient_name":  patient.full_name,
                "immunizations": [i.to_dict() for i in records],
                "total":         len(records),
            }
        }

    @staticmethod
    def get_all_immunizations(page=1, per_page=20, vaccine_name=None):
        query = Immunization.query
        if vaccine_name:
            query = query.filter(Immunization.vaccine_name.ilike(f"%{vaccine_name}%"))

        query = query.order_by(Immunization.date_administered.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": "Immunization records retrieved successfully.",
            "data": {
                "immunizations": [i.to_dict() for i in pagination.items],
                "total":         pagination.total,
                "pages":         pagination.pages,
                "current_page":  page,
            }
        }

    @staticmethod
    def get_due_soon(days: int = 30):
        """
        Returns immunizations with a next_dose_due within the given
        window — used to build a follow-up/reminder list.
        """
        today     = date.today()
        threshold = today + timedelta(days=days)

        records = Immunization.query.filter(
            Immunization.next_dose_due != None,
            Immunization.next_dose_due >= today,
            Immunization.next_dose_due <= threshold,
        ).order_by(Immunization.next_dose_due.asc()).all()

        return {
            "success": True,
            "message": f"{len(records)} dose(s) due within {days} days.",
            "data": [r.to_dict() for r in records]
        }

    @staticmethod
    def update_immunization(immunization_id: int, data: dict):
        """
        Admin-only correction of a record (e.g. fixing a typo in the
        batch number). Does not allow changing patient_id or vaccine_name
        wholesale — that would just be a new record.
        """
        immunization = Immunization.query.get(immunization_id)
        if not immunization:
            return {"success": False, "message": f"Immunization record with ID {immunization_id} not found.", "data": None}

        for field in ["batch_number", "site", "adverse_reaction", "notes"]:
            if field in data:
                setattr(immunization, field, data[field].strip() or None)

        if "next_dose_due" in data:
            if data["next_dose_due"]:
                try:
                    immunization.next_dose_due = datetime.strptime(data["next_dose_due"], "%Y-%m-%d").date()
                except ValueError:
                    return {"success": False, "message": "Invalid 'next_dose_due' format. Use YYYY-MM-DD.", "data": None}
            else:
                immunization.next_dose_due = None

        db.session.commit()
        return {"success": True, "message": "Immunization record updated successfully.", "data": immunization.to_dict()}