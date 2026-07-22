# app/services/medical_certificate_service.py

from datetime import datetime, timezone, date
from app.extensions import db
from app.models.medical_certificate import MedicalCertificate
from app.models.patient import Patient
from app.models.consultation import Consultation


class MedicalCertificateService:

    @staticmethod
    def _generate_certificate_number():
        """
        Format: MC-<year>-<zero-padded sequence for that year>
        e.g. MC-2026-00001
        """
        year = datetime.now(timezone.utc).year
        count_this_year = MedicalCertificate.query.filter(
            db.extract("year", MedicalCertificate.issued_at) == year
        ).count()
        return f"MC-{year}-{str(count_this_year + 1).zfill(5)}"

    @staticmethod
    def issue_certificate(data: dict, issued_by: int):
        """
        Doctor issues a medical certificate.

        Required fields:
            patient_id, reason, valid_from

        Optional fields:
            consultation_id, certificate_type (default 'sick_leave'), valid_to
        """
        patient = Patient.query.get(data.get("patient_id"))
        if not patient:
            return {"success": False, "message": f"Patient with ID {data.get('patient_id')} not found.", "data": None}

        if not (data.get("reason") or "").strip():
            return {"success": False, "message": "'reason' is required.", "data": None}

        if not data.get("valid_from"):
            return {"success": False, "message": "'valid_from' is required.", "data": None}

        try:
            valid_from = datetime.strptime(data["valid_from"], "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "message": "Invalid 'valid_from' format. Use YYYY-MM-DD.", "data": None}

        valid_to = None
        if data.get("valid_to"):
            try:
                valid_to = datetime.strptime(data["valid_to"], "%Y-%m-%d").date()
            except ValueError:
                return {"success": False, "message": "Invalid 'valid_to' format. Use YYYY-MM-DD.", "data": None}
            if valid_to < valid_from:
                return {"success": False, "message": "'valid_to' cannot be before 'valid_from'.", "data": None}

        certificate_type = data.get("certificate_type", "sick_leave")
        if certificate_type not in MedicalCertificate.CERTIFICATE_TYPES:
            return {
                "success": False,
                "message": f"Invalid certificate_type. Valid options: {', '.join(MedicalCertificate.CERTIFICATE_TYPES)}",
                "data": None
            }

        consultation_id = data.get("consultation_id")
        if consultation_id and not Consultation.query.get(consultation_id):
            return {"success": False, "message": f"Consultation with ID {consultation_id} not found.", "data": None}

        certificate = MedicalCertificate(
            certificate_number = MedicalCertificateService._generate_certificate_number(),
            patient_id         = data["patient_id"],
            consultation_id    = consultation_id,
            issued_by          = issued_by,
            certificate_type   = certificate_type,
            reason             = data["reason"].strip(),
            valid_from         = valid_from,
            valid_to           = valid_to,
            status             = "active",
            issued_at          = datetime.now(timezone.utc),
        )
        db.session.add(certificate)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "ISSUE_MEDICAL_CERTIFICATE",
            entity_type = "MedicalCertificate",
            entity_id   = certificate.id,
            user_id     = issued_by,
            new_value   = {"patient_id": data["patient_id"], "certificate_number": certificate.certificate_number}
        )
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"Certificate {certificate.certificate_number} issued for {patient.full_name}.",
            "data": certificate.to_dict()
        }

    @staticmethod
    def get_certificate_by_id(certificate_id: int):
        certificate = MedicalCertificate.query.get(certificate_id)
        if not certificate:
            return {"success": False, "message": f"Certificate with ID {certificate_id} not found.", "data": None}
        return {"success": True, "message": "Certificate retrieved successfully.", "data": certificate.to_dict()}

    @staticmethod
    def get_certificate_by_number(certificate_number: str):
        """Lets anyone with the physical certificate number verify it's genuine and still active."""
        certificate = MedicalCertificate.query.filter_by(certificate_number=certificate_number).first()
        if not certificate:
            return {"success": False, "message": f"No certificate found with number '{certificate_number}'.", "data": None}
        return {"success": True, "message": "Certificate retrieved successfully.", "data": certificate.to_dict()}

    @staticmethod
    def get_patient_certificates(patient_id: int, page=1, per_page=10):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}

        pagination = MedicalCertificate.query.filter_by(patient_id=patient_id).order_by(
            MedicalCertificate.issued_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"Certificate history for {patient.full_name} retrieved.",
            "data": {
                "patient_id":    patient_id,
                "patient_name":  patient.full_name,
                "certificates":  [c.to_dict() for c in pagination.items],
                "total":         pagination.total,
                "pages":         pagination.pages,
                "current_page":  page,
            }
        }

    @staticmethod
    def get_all_certificates(page=1, per_page=20, certificate_type=None, status=None):
        query = MedicalCertificate.query
        if certificate_type:
            query = query.filter(MedicalCertificate.certificate_type == certificate_type)
        if status:
            query = query.filter(MedicalCertificate.status == status)

        query = query.order_by(MedicalCertificate.issued_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": "Certificates retrieved successfully.",
            "data": {
                "certificates": [c.to_dict() for c in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }

    @staticmethod
    def revoke_certificate(certificate_id: int, revoked_by: int, reason: str):
        """
        Voids a wrongly-issued certificate. It stays on record (never
        deleted) but is flagged as revoked, with who revoked it and why —
        so a certificate number can never quietly disappear.
        """
        certificate = MedicalCertificate.query.get(certificate_id)
        if not certificate:
            return {"success": False, "message": f"Certificate with ID {certificate_id} not found.", "data": None}
        if certificate.status == "revoked":
            return {"success": False, "message": "This certificate has already been revoked.", "data": None}
        if not reason or not reason.strip():
            return {"success": False, "message": "A reason is required to revoke a certificate.", "data": None}

        certificate.status        = "revoked"
        certificate.revoked_by    = revoked_by
        certificate.revoked_at    = datetime.now(timezone.utc)
        certificate.revoke_reason = reason.strip()
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "REVOKE_MEDICAL_CERTIFICATE",
            entity_type = "MedicalCertificate",
            entity_id   = certificate_id,
            user_id     = revoked_by,
            old_value   = {"status": "active"},
            new_value   = {"status": "revoked", "reason": reason.strip()}
        )
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"Certificate {certificate.certificate_number} has been revoked.",
            "data": certificate.to_dict()
        }