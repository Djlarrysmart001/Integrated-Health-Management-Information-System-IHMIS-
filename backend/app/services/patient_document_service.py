# app/services/patient_document_service.py

import base64
import binascii
from datetime import datetime, timezone
from app.extensions import db
from app.models.patient import Patient
from app.models.patient_document import PatientDocument

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024  # 5MB -- documents can be scanned PDFs, larger than the passport photo
ALLOWED_MIMES = {"image/jpeg", "image/jpg", "image/png", "application/pdf"}


class PatientDocumentService:

    @staticmethod
    def upload_document(patient_id: int, data: dict, uploaded_by: int):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}

        required = ["file_data", "file_name", "doc_type"]
        for field in required:
            if not data.get(field):
                return {"success": False, "message": f"'{field}' is required.", "data": None}

        if data["doc_type"] not in PatientDocument.DOC_TYPES:
            return {
                "success": False,
                "message": f"'{data['doc_type']}' is not a valid document type. Valid: {', '.join(PatientDocument.DOC_TYPES)}",
                "data": None
            }

        file_mime = data.get("file_mime")
        if file_mime not in ALLOWED_MIMES:
            return {"success": False, "message": f"Unsupported file type '{file_mime}'. Use JPEG, PNG, or PDF.", "data": None}

        try:
            raw_bytes = base64.b64decode(data["file_data"], validate=True)
        except (binascii.Error, ValueError):
            return {"success": False, "message": "Invalid base64 file data.", "data": None}

        if len(raw_bytes) > MAX_DOCUMENT_BYTES:
            return {"success": False, "message": "File exceeds the 5MB size limit.", "data": None}

        document = PatientDocument(
            patient_id  = patient_id,
            doc_type    = data["doc_type"],
            file_name   = data["file_name"].strip(),
            file_mime   = file_mime,
            file_data   = raw_bytes,
            notes       = (data.get("notes") or "").strip() or None,
            uploaded_by = uploaded_by,
            uploaded_at = datetime.now(timezone.utc),
        )
        db.session.add(document)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "UPLOAD_PATIENT_DOCUMENT",
            entity_type = "PatientDocument",
            entity_id   = document.id,
            user_id     = uploaded_by,
            new_value   = {"patient_id": patient_id, "doc_type": document.doc_type, "file_name": document.file_name}
        )
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"Document '{document.file_name}' uploaded successfully.",
            "data": document.to_dict()
        }

    @staticmethod
    def get_patient_documents(patient_id: int):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}

        documents = PatientDocument.query.filter_by(patient_id=patient_id).order_by(
            PatientDocument.uploaded_at.desc()
        ).all()

        return {
            "success": True,
            "message": f"{len(documents)} document(s) found.",
            "data": {"documents": [d.to_dict() for d in documents]}
        }

    @staticmethod
    def get_document_file(document_id: int):
        """
        Returns the raw file bytes + mime + filename for serving as a
        download -- not JSON. The route handles the actual response.
        """
        document = PatientDocument.query.get(document_id)
        if not document:
            return {"success": False, "message": f"Document with ID {document_id} not found.", "data": None}

        return {
            "success": True,
            "message": "Document retrieved.",
            "data": {
                "file_data": document.file_data,
                "file_mime": document.file_mime,
                "file_name": document.file_name,
            }
        }

    @staticmethod
    def delete_document(document_id: int, deleted_by: int):
        document = PatientDocument.query.get(document_id)
        if not document:
            return {"success": False, "message": f"Document with ID {document_id} not found.", "data": None}

        file_name = document.file_name
        patient_id = document.patient_id

        db.session.delete(document)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "DELETE_PATIENT_DOCUMENT",
            entity_type = "PatientDocument",
            entity_id   = document_id,
            user_id     = deleted_by,
            old_value   = {"patient_id": patient_id, "file_name": file_name}
        )
        # ───────────────────────────────────────────────────────

        return {"success": True, "message": f"Document '{file_name}' deleted.", "data": None}