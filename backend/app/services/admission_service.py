# app/services/admission_service.py

from datetime import datetime, timezone, date
from app.extensions import db
from app.models.admission import Admission
from app.models.patient import Patient
from app.models.consultation import Consultation
from app.services.health_file_service import HealthFileService


class AdmissionService:

    @staticmethod
    def admit_patient(data: dict, admitted_by: int):
        """
        Doctor admits a patient for extended observation/care.

        Required fields:
            patient_id, ward, admission_reason

        Optional fields:
            consultation_id (also used to look up the health_file_id),
            bed_number, expected_discharge_date
        """
        patient = Patient.query.get(data.get("patient_id"))
        if not patient:
            return {"success": False, "message": f"Patient with ID {data.get('patient_id')} not found.", "data": None}

        if not (data.get("ward") or "").strip():
            return {"success": False, "message": "'ward' is required.", "data": None}

        if not (data.get("admission_reason") or "").strip():
            return {"success": False, "message": "'admission_reason' is required.", "data": None}

        existing = Admission.query.filter_by(patient_id=data["patient_id"], status="admitted").first()
        if existing:
            return {
                "success": False,
                "message": f"Patient already has an active admission (ID: {existing.id}, ward: {existing.ward}). Discharge it first.",
                "data": existing.to_dict()
            }

        expected_discharge_date = None
        if data.get("expected_discharge_date"):
            try:
                expected_discharge_date = datetime.strptime(data["expected_discharge_date"], "%Y-%m-%d").date()
            except ValueError:
                return {"success": False, "message": "Invalid 'expected_discharge_date' format. Use YYYY-MM-DD.", "data": None}

        consultation_id = data.get("consultation_id")
        health_file_id  = None
        if consultation_id:
            consultation = Consultation.query.get(consultation_id)
            if not consultation:
                return {"success": False, "message": f"Consultation with ID {consultation_id} not found.", "data": None}
            health_file_id = consultation.health_file_id

        admission = Admission(
            patient_id              = data["patient_id"],
            health_file_id          = health_file_id,
            consultation_id         = consultation_id,
            admitted_by             = admitted_by,
            ward                    = data["ward"].strip(),
            bed_number              = (data.get("bed_number") or "").strip() or None,
            admission_reason        = data["admission_reason"].strip(),
            admission_date          = datetime.now(timezone.utc),
            expected_discharge_date = expected_discharge_date,
            status                  = "admitted",
        )
        db.session.add(admission)
        db.session.commit()

        # ── Close the health file — the visit ends here; the patient ──
        # is now an inpatient rather than continuing the walk-in queue.
        # Non-fatal: if there's no linked health file, admission still stands.
        if health_file_id:
            HealthFileService.close_via_admission(health_file_id, admitted_by)
        # ───────────────────────────────────────────────────────

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "ADMIT_PATIENT",
            entity_type = "Admission",
            entity_id   = admission.id,
            user_id     = admitted_by,
            new_value   = {"patient_id": data["patient_id"], "ward": admission.ward}
        )
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"{patient.full_name} admitted to {admission.ward}.",
            "data": admission.to_dict()
        }

    @staticmethod
    def discharge_patient(admission_id: int, discharged_by: int, discharge_summary: str = None):
        admission = Admission.query.get(admission_id)
        if not admission:
            return {"success": False, "message": f"Admission with ID {admission_id} not found.", "data": None}
        if admission.status != "admitted":
            return {"success": False, "message": f"Cannot discharge — admission status is already '{admission.status}'.", "data": None}

        admission.status                = "discharged"
        admission.actual_discharge_date = datetime.now(timezone.utc)
        admission.discharged_by         = discharged_by
        admission.discharge_summary     = (discharge_summary or "").strip() or None
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "DISCHARGE_PATIENT",
            entity_type = "Admission",
            entity_id   = admission_id,
            user_id     = discharged_by,
            old_value   = {"status": "admitted"},
            new_value   = {"status": "discharged"}
        )
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"{admission.patient.full_name} discharged from {admission.ward}.",
            "data": admission.to_dict()
        }

    @staticmethod
    def get_admission_by_id(admission_id: int):
        admission = Admission.query.get(admission_id)
        if not admission:
            return {"success": False, "message": f"Admission with ID {admission_id} not found.", "data": None}
        return {"success": True, "message": "Admission retrieved successfully.", "data": admission.to_dict()}

    @staticmethod
    def get_patient_admissions(patient_id: int, page=1, per_page=10):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}

        pagination = Admission.query.filter_by(patient_id=patient_id).order_by(
            Admission.admission_date.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"Admission history for {patient.full_name} retrieved.",
            "data": {
                "patient_id":   patient_id,
                "patient_name": patient.full_name,
                "admissions":   [a.to_dict() for a in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }

    @staticmethod
    def get_active_admissions(ward=None):
        """Ward census — everyone currently admitted, right now."""
        query = Admission.query.filter_by(status="admitted")
        if ward:
            query = query.filter(Admission.ward.ilike(f"%{ward}%"))

        admissions = query.order_by(Admission.admission_date.asc()).all()
        return {
            "success": True,
            "message": f"{len(admissions)} patient(s) currently admitted.",
            "data": [a.to_dict() for a in admissions]
        }

    @staticmethod
    def get_all_admissions(page=1, per_page=20, status=None, ward=None):
        query = Admission.query
        if status:
            query = query.filter(Admission.status == status)
        if ward:
            query = query.filter(Admission.ward.ilike(f"%{ward}%"))

        query = query.order_by(Admission.admission_date.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": "Admissions retrieved successfully.",
            "data": {
                "admissions":   [a.to_dict() for a in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }