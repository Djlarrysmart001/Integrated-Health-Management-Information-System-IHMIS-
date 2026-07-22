# app/services/consultation_service.py

from datetime import datetime, timezone
from app.extensions import db
from app.models.consultation import Consultation, Diagnosis
from app.models.patient import Patient
from app.models.user import User
from app.models.health_file import HealthFile


class ConsultationService:

    @staticmethod
    def get_all_consultations(page=1, per_page=20, doctor_id=None,
                               patient_id=None, status=None):
        query = Consultation.query
        if doctor_id:
            query = query.filter(Consultation.doctor_id == doctor_id)
        if patient_id:
            query = query.filter(Consultation.patient_id == patient_id)
        if status:
            query = query.filter(Consultation.status == status)

        query = query.order_by(Consultation.visit_date.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": "Consultations retrieved successfully.",
            "data": {
                "consultations": [c.to_dict() for c in pagination.items],
                "total":         pagination.total,
                "pages":         pagination.pages,
                "current_page":  page,
                "per_page":      per_page,
                "has_next":      pagination.has_next,
                "has_prev":      pagination.has_prev,
            }
        }

    @staticmethod
    def get_consultation_by_id(consultation_id: int):
        consultation = Consultation.query.get(consultation_id)
        if not consultation:
            return {"success": False, "message": f"Consultation with ID {consultation_id} not found.", "data": None}

        data                      = consultation.to_dict()
        data["diagnoses"]         = [d.to_dict() for d in consultation.diagnoses]
        data["prescriptions_count"] = consultation.prescriptions.count()
        data["lab_requests_count"]  = consultation.lab_requests.count()

        return {"success": True, "message": "Consultation retrieved successfully.", "data": data}

    @staticmethod
    def open_consultation(data: dict, doctor_id: int):
        patient = Patient.query.get(data.get("patient_id"))
        if not patient:
            return {"success": False, "message": f"Patient with ID {data.get('patient_id')} not found.", "data": None}
        if not patient.is_active:
            return {"success": False, "message": "Cannot open consultation for an inactive patient.", "data": None}

        existing = Consultation.query.filter_by(patient_id=data["patient_id"], status="open").first()
        if existing:
            return {
                "success": False,
                "message": f"Patient already has an open consultation (ID: {existing.id}). Close it first.",
                "data": None
            }

        # ── Optional: link to a HealthFile from the walk-in workflow ──
        # If provided, it must belong to this patient and currently be
        # waiting on the Doctor (i.e. the Nurse has already forwarded it).
        health_file_id = data.get("health_file_id")
        if health_file_id:
            health_file = HealthFile.query.get(health_file_id)
            if not health_file:
                return {"success": False, "message": f"Health file with ID {health_file_id} not found.", "data": None}
            if health_file.patient_id != data["patient_id"]:
                return {"success": False, "message": "This health file does not belong to the specified patient.", "data": None}
            if health_file.status != "with_doctor":
                return {
                    "success": False,
                    "message": f"Health file is currently '{health_file.status}' — it must be forwarded to the Doctor before a consultation can be opened.",
                    "data": None
                }
        # ───────────────────────────────────────────────────────

        consultation = Consultation(
            patient_id                    = data["patient_id"],
            health_file_id                = health_file_id,
            doctor_id                     = doctor_id,
            visit_date                    = datetime.now(timezone.utc),
            chief_complaint               = (data.get("chief_complaint") or "").strip() or None,
            history_of_presenting_illness = (data.get("history_of_presenting_illness") or "").strip() or None,
            physical_examination          = (data.get("physical_examination") or "").strip() or None,
            clinical_notes                = (data.get("clinical_notes") or "").strip() or None,
            status                        = "open",
        )
        db.session.add(consultation)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "OPEN_CONSULTATION",
            entity_type = "Consultation",
            entity_id   = consultation.id,
            user_id     = doctor_id,
            new_value   = {"patient_id": data["patient_id"], "status": "open"}
        )
        # ───────────────────────────────────────────────────────

        return {"success": True, "message": f"Consultation opened for {patient.full_name}.", "data": consultation.to_dict()}

    @staticmethod
    def update_consultation(consultation_id: int, data: dict):
        consultation = Consultation.query.get(consultation_id)
        if not consultation:
            return {"success": False, "message": f"Consultation with ID {consultation_id} not found.", "data": None}
        if consultation.status == "closed":
            return {"success": False, "message": "Cannot update a closed consultation.", "data": None}

        for field in ["chief_complaint", "history_of_presenting_illness", "physical_examination", "clinical_notes"]:
            if field in data:
                setattr(consultation, field, data[field])

        db.session.commit()
        return {"success": True, "message": "Consultation updated successfully.", "data": consultation.to_dict()}

    @staticmethod
    def close_consultation(consultation_id: int):
        consultation = Consultation.query.get(consultation_id)
        if not consultation:
            return {"success": False, "message": f"Consultation with ID {consultation_id} not found.", "data": None}
        if consultation.status == "closed":
            return {"success": False, "message": "Consultation is already closed.", "data": None}

        consultation.status    = "closed"
        consultation.closed_at = datetime.now(timezone.utc)

        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "CLOSE_CONSULTATION",
            entity_type = "Consultation",
            entity_id   = consultation_id,
            new_value   = {"status": "closed"}
        )
        # ───────────────────────────────────────────────────────

        return {"success": True, "message": "Consultation closed successfully.", "data": consultation.to_dict()}

    @staticmethod
    def add_diagnosis(consultation_id: int, data: dict, created_by: int):
        consultation = Consultation.query.get(consultation_id)
        if not consultation:
            return {"success": False, "message": f"Consultation with ID {consultation_id} not found.", "data": None}
        if consultation.status == "closed":
            return {"success": False, "message": "Cannot add diagnosis to a closed consultation.", "data": None}
        if not data.get("description"):
            return {"success": False, "message": "'description' is required for a diagnosis.", "data": None}

        diagnosis_type = data.get("diagnosis_type", "primary")
        if diagnosis_type not in ["primary", "secondary"]:
            return {"success": False, "message": "diagnosis_type must be 'primary' or 'secondary'.", "data": None}

        diagnosis = Diagnosis(
            consultation_id = consultation_id,
            icd10_code      = (data.get("icd10_code") or "").strip() or None,
            description     = data["description"].strip(),
            diagnosis_type  = diagnosis_type,
            created_by      = created_by,
        )
        db.session.add(diagnosis)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "ADD_DIAGNOSIS",
            entity_type = "Diagnosis",
            entity_id   = diagnosis.id,
            user_id     = created_by,
            new_value   = {"description": data["description"], "type": diagnosis_type}
        )
        # ───────────────────────────────────────────────────────

        return {"success": True, "message": "Diagnosis added successfully.", "data": diagnosis.to_dict()}

    @staticmethod
    def get_diagnoses(consultation_id: int):
        consultation = Consultation.query.get(consultation_id)
        if not consultation:
            return {"success": False, "message": f"Consultation with ID {consultation_id} not found.", "data": None}

        diagnoses = Diagnosis.query.filter_by(
            consultation_id=consultation_id
        ).order_by(Diagnosis.created_at.asc()).all()

        return {
            "success": True,
            "message": f"{len(diagnoses)} diagnosis(es) found.",
            "data": {"consultation_id": consultation_id, "diagnoses": [d.to_dict() for d in diagnoses]}
        }

    @staticmethod
    def delete_diagnosis(diagnosis_id: int):
        diagnosis = Diagnosis.query.get(diagnosis_id)
        if not diagnosis:
            return {"success": False, "message": f"Diagnosis with ID {diagnosis_id} not found.", "data": None}

        consultation = Consultation.query.get(diagnosis.consultation_id)
        if consultation and consultation.status == "closed":
            return {"success": False, "message": "Cannot delete diagnosis from a closed consultation.", "data": None}

        db.session.delete(diagnosis)
        db.session.commit()
        return {"success": True, "message": "Diagnosis removed successfully.", "data": None}

    @staticmethod
    def get_patient_consultations(patient_id: int, page=1, per_page=10):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}

        pagination = Consultation.query.filter_by(
            patient_id=patient_id
        ).order_by(Consultation.visit_date.desc()).paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"Consultation history for {patient.full_name} retrieved.",
            "data": {
                "patient_id":    patient_id,
                "patient_name":  patient.full_name,
                "consultations": [c.to_dict() for c in pagination.items],
                "total":         pagination.total,
                "pages":         pagination.pages,
                "current_page":  page,
            }
        }