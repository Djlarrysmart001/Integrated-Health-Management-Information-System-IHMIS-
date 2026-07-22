# app/services/medical_record_service.py

from datetime import datetime, timezone
from app.extensions import db
from app.models.medical_record import MedicalRecord
from app.models.vital_signs import VitalSigns
from app.models.patient import Patient


class MedicalRecordService:

    # ──────────────────────────────────────────────────────────
    # Get Medical Record
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_medical_record(patient_id: int):
        """
        Returns the medical record for a patient.
        Every patient has exactly one medical record created
        automatically when they are registered.
        """
        patient = Patient.query.get(patient_id)
        if not patient:
            return {
                "success": False,
                "message": f"Patient with ID {patient_id} not found.",
                "data": None
            }

        record = MedicalRecord.query.filter_by(patient_id=patient_id).first()
        if not record:
            return {
                "success": False,
                "message": "Medical record not found for this patient.",
                "data": None
            }

        return {
            "success": True,
            "message": "Medical record retrieved successfully.",
            "data": {
                "patient":        patient.to_dict(),
                "medical_record": record.to_dict()
            }
        }

    # ──────────────────────────────────────────────────────────
    # Update Medical Record
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def update_medical_record(patient_id: int, data: dict, updated_by: int):
        """
        Updates a patient's medical record.
        All fields are optional — only provided fields are updated.
        """
        record = MedicalRecord.query.filter_by(patient_id=patient_id).first()
        if not record:
            return {
                "success": False,
                "message": "Medical record not found for this patient.",
                "data": None
            }

        # Update only the fields that were provided
        updatable_fields = [
            "known_allergies",
            "chronic_conditions",
            "current_medications",
            "surgical_history",
            "family_history",
            "immunization_history",
            "notes"
        ]

        for field in updatable_fields:
            if field in data:
                setattr(record, field, data[field])

        record.updated_by = updated_by
        db.session.commit()

        return {
            "success": True,
            "message": "Medical record updated successfully.",
            "data": record.to_dict()
        }

    # ──────────────────────────────────────────────────────────
    # Record Vital Signs
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def record_vital_signs(patient_id: int, data: dict, recorded_by: int):
        """
        Records a new set of vital signs for a patient.
        Called by nurses at the start of every visit.

        Optional fields:
            blood_pressure_systolic, blood_pressure_diastolic,
            pulse_rate, temperature, weight, height,
            oxygen_saturation, respiratory_rate, consultation_id
        """
        patient = Patient.query.get(patient_id)
        if not patient:
            return {
                "success": False,
                "message": f"Patient with ID {patient_id} not found.",
                "data": None
            }

        vitals = VitalSigns(
            patient_id               = patient_id,
            consultation_id          = data.get("consultation_id"),
            blood_pressure_systolic  = data.get("blood_pressure_systolic"),
            blood_pressure_diastolic = data.get("blood_pressure_diastolic"),
            pulse_rate               = data.get("pulse_rate"),
            temperature              = data.get("temperature"),
            weight                   = data.get("weight"),
            height                   = data.get("height"),
            oxygen_saturation        = data.get("oxygen_saturation"),
            respiratory_rate         = data.get("respiratory_rate"),
            recorded_by              = recorded_by,
            recorded_at              = datetime.now(timezone.utc),
        )

        # Auto-calculate BMI if weight and height provided
        vitals.compute_bmi()

        db.session.add(vitals)
        db.session.commit()

        return {
            "success": True,
            "message": "Vital signs recorded successfully.",
            "data": vitals.to_dict()
        }

    # ──────────────────────────────────────────────────────────
    # Get Vital Signs History
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_vital_signs(patient_id: int, page=1, per_page=10):
        """
        Returns the vital signs history for a patient,
        ordered from most recent to oldest.
        """
        patient = Patient.query.get(patient_id)
        if not patient:
            return {
                "success": False,
                "message": f"Patient with ID {patient_id} not found.",
                "data": None
            }

        pagination = VitalSigns.query.filter_by(
            patient_id=patient_id
        ).order_by(
            VitalSigns.recorded_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": "Vital signs retrieved successfully.",
            "data": {
                "patient_id":   patient_id,
                "patient_name": patient.full_name,
                "vitals":       [v.to_dict() for v in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }

    # ──────────────────────────────────────────────────────────
    # Get Latest Vital Signs
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_latest_vitals(patient_id: int):
        """Returns only the most recent vital signs for a patient."""
        patient = Patient.query.get(patient_id)
        if not patient:
            return {
                "success": False,
                "message": f"Patient with ID {patient_id} not found.",
                "data": None
            }

        latest = VitalSigns.query.filter_by(
            patient_id=patient_id
        ).order_by(VitalSigns.recorded_at.desc()).first()

        if not latest:
            return {
                "success": True,
                "message": "No vital signs recorded yet for this patient.",
                "data": None
            }

        return {
            "success": True,
            "message": "Latest vital signs retrieved.",
            "data": latest.to_dict()
        }

    # ──────────────────────────────────────────────────────────
    # Get Full Patient Summary
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_patient_summary(patient_id: int):
        """
        Returns a complete patient summary including:
        - Patient details
        - Medical record
        - Latest vital signs
        Used by doctors at the start of a consultation.
        """
        patient = Patient.query.get(patient_id)
        if not patient:
            return {
                "success": False,
                "message": f"Patient with ID {patient_id} not found.",
                "data": None
            }

        record = MedicalRecord.query.filter_by(patient_id=patient_id).first()
        latest_vitals = VitalSigns.query.filter_by(
            patient_id=patient_id
        ).order_by(VitalSigns.recorded_at.desc()).first()

        # Build profile
        profile = None
        if patient.patient_type == "student" and patient.student_profile:
            profile = patient.student_profile.to_dict()
        elif patient.patient_type == "staff" and patient.staff_profile:
            profile = patient.staff_profile.to_dict()

        return {
            "success": True,
            "message": "Patient summary retrieved successfully.",
            "data": {
                "patient":        patient.to_dict(),
                "profile":        profile,
                "medical_record": record.to_dict() if record else None,
                "latest_vitals":  latest_vitals.to_dict() if latest_vitals else None,
            }
        }