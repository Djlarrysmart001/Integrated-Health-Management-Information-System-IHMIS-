# app/services/patient_service.py

from datetime import datetime, timezone
from app.extensions import db
from app.models.patient import Patient, StudentProfile, StaffProfile
from app.models.medical_record import MedicalRecord
from app.models.consultation import Consultation


class PatientService:

    @staticmethod
    def get_doctor_patients(doctor_id: int, page=1, per_page=20, search=None):
        """
        This is what actually feeds a Doctor's "My Patients" page --
        distinct patients this doctor has personally consulted
        (Consultation.doctor_id), NOT the full clinic-wide patient
        directory get_all_patients returns. Mirrors the same
        Consultation.doctor_id scoping the Doctor dashboard already
        uses for its stat cards.
        """
        query = (
            Patient.query
            .join(Consultation, Consultation.patient_id == Patient.id)
            .filter(Consultation.doctor_id == doctor_id)
        )

        if search:
            prefix_term = f"{search}%"
            contains_term = f"%{search}%"
            query = query.filter(
                (Patient.first_name.ilike(prefix_term)) |
                (Patient.last_name.ilike(prefix_term)) |
                (Patient.patient_number.ilike(prefix_term)) |
                (Patient.phone.ilike(contains_term))
            )

        query = query.distinct().order_by(Patient.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"{pagination.total} patient(s) you've consulted.",
            "data": {
                "patients":     [p.to_dict() for p in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
                "per_page":     per_page,
                "has_next":     pagination.has_next,
                "has_prev":     pagination.has_prev,
            }
        }

    @staticmethod
    def generate_patient_number() -> str:
        year  = datetime.now(timezone.utc).year
        count = Patient.query.filter(
            db.extract("year", Patient.created_at) == year
        ).count()
        return f"PAT-{year}-{str(count + 1).zfill(5)}"

    @staticmethod
    def get_all_patients(page=1, per_page=20, search=None,
                         patient_type=None, is_active=None):
        query = Patient.query

        if search:
            # Prefix match ('term%') on the newly-indexed name/number
            # columns so MySQL can actually use a B-tree index seek
            # instead of a full table scan -- this is the difference
            # between an instant lookup and a multi-second scan once
            # the patients table reaches tens of thousands of rows.
            # A leading wildcard ('%term%') can never use an index
            # regardless of how many indexes exist, so we deliberately
            # don't offer "contains" matching on these three columns.
            # Phone is kept as a "contains" search since people often
            # search by remembering only the last few digits -- it's a
            # far less frequent lookup path than name/number search,
            # so the occasional full scan there is an acceptable trade.
            prefix_term = f"{search}%"
            contains_term = f"%{search}%"
            query = query.filter(
                (Patient.first_name.ilike(prefix_term)) |
                (Patient.last_name.ilike(prefix_term)) |
                (Patient.patient_number.ilike(prefix_term)) |
                (Patient.phone.ilike(contains_term)) |
                (Patient.email.ilike(prefix_term))
            )
        if patient_type:
            query = query.filter(Patient.patient_type == patient_type)
        if is_active is not None:
            query = query.filter(Patient.is_active == is_active)

        query = query.order_by(Patient.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": "Patients retrieved successfully.",
            "data": {
                "patients":     [p.to_dict() for p in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
                "per_page":     per_page,
                "has_next":     pagination.has_next,
                "has_prev":     pagination.has_prev,
            }
        }

    @staticmethod
    def get_patient_by_id(patient_id: int):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {
                "success": False,
                "message": f"Patient with ID {patient_id} not found.",
                "data": None
            }
        data = patient.to_dict()
        if patient.patient_type == "student" and patient.student_profile:
            data["profile"] = patient.student_profile.to_dict()
        elif patient.patient_type == "staff" and patient.staff_profile:
            data["profile"] = patient.staff_profile.to_dict()
        return {"success": True, "message": "Patient retrieved successfully.", "data": data}

    @staticmethod
    def search_by_id_number(id_number: str):
        student = StudentProfile.query.filter_by(
            matric_number=id_number.strip().upper()
        ).first()
        if student:
            return PatientService.get_patient_by_id(student.patient_id)

        staff = StaffProfile.query.filter_by(
            staff_id_number=id_number.strip().upper()
        ).first()
        if staff:
            return PatientService.get_patient_by_id(staff.patient_id)

        return {
            "success": False,
            "message": f"No patient found with ID number '{id_number}'.",
            "data": None
        }

    # ──────────────────────────────────────────────────────────
    # Soft duplicate check — Name + Date of Birth match
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def check_potential_duplicate(first_name: str, last_name: str, date_of_birth: str):
        """
        Non-blocking duplicate check used by the MHO registration form.
        Matches on first_name + last_name + date_of_birth (case-insensitive
        on names). Returns any matches found so the frontend can show a
        warning banner -- this never blocks registration, since two real
        people can share a name and birthdate.
        """
        if not (first_name and last_name and date_of_birth):
            return {"success": True, "message": "Insufficient data to check.", "data": {"matches": []}}

        try:
            dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "message": "Invalid date_of_birth format. Use YYYY-MM-DD.", "data": None}

        matches = Patient.query.filter(
            Patient.first_name.ilike(first_name.strip()),
            Patient.last_name.ilike(last_name.strip()),
            Patient.date_of_birth == dob
        ).all()

        return {
            "success": True,
            "message": f"{len(matches)} potential duplicate(s) found." if matches else "No duplicates found.",
            "data": {
                "matches": [
                    {
                        "id":             p.id,
                        "patient_number": p.patient_number,
                        "full_name":      p.full_name,
                        "patient_type":   p.patient_type,
                        "is_active":      p.is_active,
                    } for p in matches
                ]
            }
        }

    @staticmethod
    def register_student(data: dict, registered_by: int):
        required = ["first_name", "last_name", "matric_number", "gender", "department"]
        for field in required:
            if not data.get(field):
                return {"success": False, "message": f"'{field}' is required.", "data": None}

        matric = data["matric_number"].strip().upper()
        if StudentProfile.query.filter_by(matric_number=matric).first():
            return {
                "success": False,
                "message": f"A patient with matric number '{matric}' already exists.",
                "data": None
            }

        dob = None
        if data.get("date_of_birth"):
            try:
                dob = datetime.strptime(data["date_of_birth"], "%Y-%m-%d").date()
            except ValueError:
                return {"success": False, "message": "Invalid date_of_birth format. Use YYYY-MM-DD.", "data": None}

        patient = Patient(
            patient_number                  = PatientService.generate_patient_number(),
            patient_type                    = "student",
            first_name                      = data["first_name"].strip(),
            last_name                       = data["last_name"].strip(),
            date_of_birth                   = dob,
            gender                          = data.get("gender"),
            blood_group                     = data.get("blood_group", "unknown"),
            genotype                        = data.get("genotype"),
            phone                           = data.get("phone"),
            email                           = data.get("email"),
            emergency_contact_name          = data.get("emergency_contact_name"),
            emergency_contact_phone         = data.get("emergency_contact_phone"),
            emergency_contact_relationship  = data.get("emergency_contact_relationship"),
            emergency_contact_address       = data.get("emergency_contact_address"),
            address                         = data.get("address"),
            registered_by                   = registered_by,
        )
        db.session.add(patient)
        db.session.flush()

        profile = StudentProfile(
            patient_id        = patient.id,
            matric_number     = matric,
            department        = (data.get("department") or "").strip(),
            faculty           = (data.get("faculty") or "").strip(),
            level             = (data.get("level") or "").strip(),
            year_of_admission = data.get("year_of_admission"),
        )
        db.session.add(profile)

        record = MedicalRecord(patient_id=patient.id, created_by=registered_by)
        db.session.add(record)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "CREATE_PATIENT",
            entity_type = "Patient",
            entity_id   = patient.id,
            user_id     = registered_by,
            new_value   = {
                "patient_number": patient.patient_number,
                "name":           patient.full_name,
                "type":           "student"
            }
        )
        # ───────────────────────────────────────────────────────

        result = patient.to_dict()
        result["profile"] = profile.to_dict()

        return {
            "success": True,
            "message": f"Student '{patient.full_name}' registered successfully with number {patient.patient_number}.",
            "data": result
        }

    @staticmethod
    def register_other(data: dict, registered_by: int):
        """
        Registers a walk-in patient who is neither a student nor staff
        (e.g. a visitor, contractor, or community member). No
        StudentProfile/StaffProfile row is created -- department,
        matric number, and staff ID simply don't apply to this group.
        """
        required = ["first_name", "last_name", "gender"]
        for field in required:
            if not data.get(field):
                return {"success": False, "message": f"'{field}' is required.", "data": None}

        dob = None
        if data.get("date_of_birth"):
            try:
                dob = datetime.strptime(data["date_of_birth"], "%Y-%m-%d").date()
            except ValueError:
                return {"success": False, "message": "Invalid date_of_birth format. Use YYYY-MM-DD.", "data": None}

        patient = Patient(
            patient_number                  = PatientService.generate_patient_number(),
            patient_type                    = "other",
            first_name                      = data["first_name"].strip(),
            last_name                       = data["last_name"].strip(),
            date_of_birth                   = dob,
            gender                          = data.get("gender"),
            blood_group                     = data.get("blood_group", "unknown"),
            genotype                        = data.get("genotype"),
            phone                           = data.get("phone"),
            email                           = data.get("email"),
            emergency_contact_name          = data.get("emergency_contact_name"),
            emergency_contact_phone         = data.get("emergency_contact_phone"),
            emergency_contact_relationship  = data.get("emergency_contact_relationship"),
            emergency_contact_address       = data.get("emergency_contact_address"),
            address                         = data.get("address"),
            registered_by                   = registered_by,
        )
        db.session.add(patient)
        db.session.flush()

        record = MedicalRecord(patient_id=patient.id, created_by=registered_by)
        db.session.add(record)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "CREATE_PATIENT",
            entity_type = "Patient",
            entity_id   = patient.id,
            user_id     = registered_by,
            new_value   = {
                "patient_number": patient.patient_number,
                "name":           patient.full_name,
                "type":           "other"
            }
        )
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"Patient '{patient.full_name}' registered successfully with number {patient.patient_number}.",
            "data": patient.to_dict()
        }

    @staticmethod
    def register_staff(data: dict, registered_by: int):
        required = ["first_name", "last_name", "staff_id_number", "gender", "department"]
        for field in required:
            if not data.get(field):
                return {"success": False, "message": f"'{field}' is required.", "data": None}

        staff_id = data["staff_id_number"].strip().upper()
        if StaffProfile.query.filter_by(staff_id_number=staff_id).first():
            return {
                "success": False,
                "message": f"A patient with staff ID '{staff_id}' already exists.",
                "data": None
            }

        dob = None
        if data.get("date_of_birth"):
            try:
                dob = datetime.strptime(data["date_of_birth"], "%Y-%m-%d").date()
            except ValueError:
                return {"success": False, "message": "Invalid date_of_birth format. Use YYYY-MM-DD.", "data": None}

        patient = Patient(
            patient_number                  = PatientService.generate_patient_number(),
            patient_type                    = "staff",
            first_name                      = data["first_name"].strip(),
            last_name                       = data["last_name"].strip(),
            date_of_birth                   = dob,
            gender                          = data.get("gender"),
            blood_group                     = data.get("blood_group", "unknown"),
            genotype                        = data.get("genotype"),
            phone                           = data.get("phone"),
            email                           = data.get("email"),
            emergency_contact_name          = data.get("emergency_contact_name"),
            emergency_contact_phone         = data.get("emergency_contact_phone"),
            emergency_contact_relationship  = data.get("emergency_contact_relationship"),
            emergency_contact_address       = data.get("emergency_contact_address"),
            address                         = data.get("address"),
            registered_by                   = registered_by,
        )
        db.session.add(patient)
        db.session.flush()

        profile = StaffProfile(
            patient_id      = patient.id,
            staff_id_number = staff_id,
            department      = (data.get("department") or "").strip(),
            designation     = (data.get("designation") or "").strip(),
        )
        db.session.add(profile)

        record = MedicalRecord(patient_id=patient.id, created_by=registered_by)
        db.session.add(record)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "CREATE_PATIENT",
            entity_type = "Patient",
            entity_id   = patient.id,
            user_id     = registered_by,
            new_value   = {
                "patient_number": patient.patient_number,
                "name":           patient.full_name,
                "type":           "staff"
            }
        )
        # ───────────────────────────────────────────────────────

        result = patient.to_dict()
        result["profile"] = profile.to_dict()

        return {
            "success": True,
            "message": f"Staff '{patient.full_name}' registered successfully with number {patient.patient_number}.",
            "data": result
        }

    @staticmethod
    def register_other(data: dict, registered_by: int):
        """
        Registers a walk-in patient who is neither a student nor staff
        (e.g. a visitor, contractor, or family member). No StudentProfile
        or StaffProfile is created -- patient_type='other' has no linked
        profile table, so identification is whatever is captured in the
        base Patient fields (name, phone, address) alone.
        """
        required = ["first_name", "last_name", "gender"]
        for field in required:
            if not data.get(field):
                return {"success": False, "message": f"'{field}' is required.", "data": None}

        dob = None
        if data.get("date_of_birth"):
            try:
                dob = datetime.strptime(data["date_of_birth"], "%Y-%m-%d").date()
            except ValueError:
                return {"success": False, "message": "Invalid date_of_birth format. Use YYYY-MM-DD.", "data": None}

        patient = Patient(
            patient_number                  = PatientService.generate_patient_number(),
            patient_type                    = "other",
            first_name                      = data["first_name"].strip(),
            last_name                       = data["last_name"].strip(),
            date_of_birth                   = dob,
            gender                          = data.get("gender"),
            blood_group                     = data.get("blood_group", "unknown"),
            genotype                        = data.get("genotype"),
            phone                           = data.get("phone"),
            email                           = data.get("email"),
            emergency_contact_name          = data.get("emergency_contact_name"),
            emergency_contact_phone         = data.get("emergency_contact_phone"),
            emergency_contact_relationship  = data.get("emergency_contact_relationship"),
            emergency_contact_address       = data.get("emergency_contact_address"),
            address                         = data.get("address"),
            registered_by                   = registered_by,
        )
        db.session.add(patient)
        db.session.flush()

        record = MedicalRecord(patient_id=patient.id, created_by=registered_by)
        db.session.add(record)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "CREATE_PATIENT",
            entity_type = "Patient",
            entity_id   = patient.id,
            user_id     = registered_by,
            new_value   = {
                "patient_number": patient.patient_number,
                "name":           patient.full_name,
                "type":           "other"
            }
        )
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"'{patient.full_name}' registered successfully with number {patient.patient_number}.",
            "data": patient.to_dict()
        }

    @staticmethod
    def update_patient(patient_id: int, data: dict):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}

        updatable = ["first_name", "last_name", "phone", "email",
                     "blood_group", "genotype", "address",
                     "emergency_contact_name", "emergency_contact_phone",
                     "emergency_contact_relationship", "emergency_contact_address"]

        for field in updatable:
            if field in data:
                setattr(patient, field, data[field])

        if data.get("date_of_birth"):
            try:
                patient.date_of_birth = datetime.strptime(data["date_of_birth"], "%Y-%m-%d").date()
            except ValueError:
                return {"success": False, "message": "Invalid date_of_birth format. Use YYYY-MM-DD.", "data": None}

        if patient.patient_type == "student" and patient.student_profile:
            for field in ["department", "faculty", "level", "year_of_admission"]:
                if field in data:
                    setattr(patient.student_profile, field, data[field])

        if patient.patient_type == "staff" and patient.staff_profile:
            for field in ["department", "designation"]:
                if field in data:
                    setattr(patient.staff_profile, field, data[field])

        db.session.commit()

        result = patient.to_dict()
        if patient.patient_type == "student" and patient.student_profile:
            result["profile"] = patient.student_profile.to_dict()
        elif patient.patient_type == "staff" and patient.staff_profile:
            result["profile"] = patient.staff_profile.to_dict()

        return {"success": True, "message": "Patient updated successfully.", "data": result}

    @staticmethod
    def deactivate_patient(patient_id: int):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}
        patient.is_active = False
        db.session.commit()
        return {"success": True, "message": f"Patient '{patient.full_name}' has been deactivated.", "data": patient.to_dict()}

    @staticmethod
    def get_statistics():
        total          = Patient.query.count()
        total_students = Patient.query.filter_by(patient_type="student").count()
        total_staff    = Patient.query.filter_by(patient_type="staff").count()
        total_active   = Patient.query.filter_by(is_active=True).count()

        return {
            "success": True,
            "message": "Patient statistics retrieved.",
            "data": {
                "total_patients": total,
                "total_students": total_students,
                "total_staff":    total_staff,
                "total_active":   total_active,
                "total_inactive": total - total_active,
            }
        }

    # ──────────────────────────────────────────────────────────
    # Passport photo — stored as BLOB directly on Patient
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def upload_photo(patient_id: int, photo_data_b64: str, photo_mime: str):
        """
        Accepts a base64-encoded image string (no data-URL prefix --
        that's stripped client-side before sending) and stores the raw
        bytes on Patient.photo_data. Overwrites any existing photo.
        """
        import base64
        import binascii

        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}

        if not photo_data_b64:
            return {"success": False, "message": "'photo_data' is required.", "data": None}

        allowed_mimes = {"image/jpeg", "image/jpg", "image/png"}
        if photo_mime not in allowed_mimes:
            return {"success": False, "message": f"Unsupported photo type '{photo_mime}'. Use JPEG or PNG.", "data": None}

        try:
            raw_bytes = base64.b64decode(photo_data_b64, validate=True)
        except (binascii.Error, ValueError):
            return {"success": False, "message": "Invalid base64 image data.", "data": None}

        # 2MB cap, matching the frontend's own pre-upload check -- this
        # is the server-side backstop in case that check is bypassed.
        MAX_PHOTO_BYTES = 2 * 1024 * 1024
        if len(raw_bytes) > MAX_PHOTO_BYTES:
            return {"success": False, "message": "Photo exceeds the 2MB size limit.", "data": None}

        patient.photo_data = raw_bytes
        patient.photo_mime = photo_mime
        db.session.commit()

        return {
            "success": True,
            "message": "Photo uploaded successfully.",
            "data": {"patient_id": patient.id, "has_photo": True}
        }

    @staticmethod
    def get_photo(patient_id: int):
        """
        Returns the raw photo bytes + mime type for serving directly as
        an image response, not as JSON -- the route handles that part.
        """
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}
        if not patient.photo_data:
            return {"success": False, "message": "This patient has no photo on file.", "data": None}

        return {
            "success": True,
            "message": "Photo retrieved.",
            "data": {"photo_data": patient.photo_data, "photo_mime": patient.photo_mime or "image/jpeg"}
        }