# app/models/patient.py

from datetime import datetime, timezone
from app.extensions import db


class Patient(db.Model):
    __tablename__ = "patients"

    id                      = db.Column(db.Integer, primary_key=True)
    patient_number          = db.Column(db.String(30), unique=True, nullable=False, index=True)
    patient_type            = db.Column(db.Enum("student", "staff", "other"), nullable=False)
    first_name              = db.Column(db.String(80), nullable=False, index=True)
    last_name               = db.Column(db.String(80), nullable=False, index=True)
    date_of_birth           = db.Column(db.Date, nullable=True)
    gender                  = db.Column(db.Enum("male", "female", "other"), nullable=True)
    blood_group             = db.Column(db.Enum("A+","A-","B+","B-","AB+","AB-","O+","O-","unknown"), default="unknown")
    genotype                = db.Column(db.String(10), nullable=True)
    phone                   = db.Column(db.String(20), nullable=True, index=True)
    email                   = db.Column(db.String(120), nullable=True, index=True)
    emergency_contact_name         = db.Column(db.String(120), nullable=True)
    emergency_contact_phone        = db.Column(db.String(20), nullable=True)
    # New — present on the paper Medical Registration Form, missing from
    # the original model. Both nullable so existing rows/records aren't
    # broken by this migration.
    emergency_contact_relationship = db.Column(db.String(60), nullable=True)
    emergency_contact_address      = db.Column(db.Text, nullable=True)

    address                 = db.Column(db.Text, nullable=True)

    # Legacy field, kept for backwards compatibility with anything already
    # referencing photo_url. Not used for new uploads — see photo_data below.
    photo_url               = db.Column(db.String(255), nullable=True)

    # Passport photo stored directly in MySQL as a BLOB (Aiven-hosted),
    # per the decision to avoid standing up separate object storage.
    # photo_mime keeps the original content type (e.g. "image/jpeg") so
    # it can be served back correctly.
    photo_data               = db.Column(db.LargeBinary(length=(2**24)-1), nullable=True)  # MEDIUMBLOB range
    photo_mime                = db.Column(db.String(50), nullable=True)

    is_active               = db.Column(db.Boolean, default=True)
    registered_by           = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at              = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at              = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    student_profile = db.relationship("StudentProfile", backref="patient", uselist=False, cascade="all, delete-orphan")
    staff_profile   = db.relationship("StaffProfile", backref="patient", uselist=False, cascade="all, delete-orphan")
    medical_record  = db.relationship("MedicalRecord", backref="patient", uselist=False, cascade="all, delete-orphan")
    vital_signs     = db.relationship("VitalSigns", backref="patient", lazy="dynamic", cascade="all, delete-orphan")
    health_files    = db.relationship("HealthFile", backref="patient", lazy="dynamic", cascade="all, delete-orphan")
    consultations   = db.relationship("Consultation", backref="patient", lazy="dynamic", cascade="all, delete-orphan")
    documents       = db.relationship("PatientDocument", backref="patient", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = datetime.now(timezone.utc).date()
        dob   = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @property
    def has_photo(self):
        return self.photo_data is not None

    def __repr__(self):
        return f"<Patient {self.patient_number}>"

    def to_dict(self, include_photo=False):
        data = {
            "id":                              self.id,
            "patient_number":                  self.patient_number,
            "patient_type":                    self.patient_type,
            "first_name":                      self.first_name,
            "last_name":                       self.last_name,
            "full_name":                       self.full_name,
            "age":                             self.age,
            "date_of_birth":                   self.date_of_birth.isoformat() if self.date_of_birth else None,
            "gender":                          self.gender,
            "blood_group":                     self.blood_group,
            "genotype":                        self.genotype,
            "phone":                           self.phone,
            "email":                           self.email,
            "emergency_contact_name":          self.emergency_contact_name,
            "emergency_contact_phone":         self.emergency_contact_phone,
            "emergency_contact_relationship":  self.emergency_contact_relationship,
            "emergency_contact_address":       self.emergency_contact_address,
            "address":                         self.address,
            "has_photo":                       self.has_photo,
            "is_active":                       self.is_active,
            "created_at":                      self.created_at.isoformat(),
        }
        # Photo bytes are deliberately excluded by default -- list/search
        # endpoints should never ship BLOBs in a paginated response. The
        # dedicated GET /patients/<id>/photo route serves the raw bytes.
        return data


class StudentProfile(db.Model):
    __tablename__ = "student_profiles"

    id                = db.Column(db.Integer, primary_key=True)
    patient_id        = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"), unique=True, nullable=False)
    matric_number     = db.Column(db.String(30), unique=True, nullable=False, index=True)
    department        = db.Column(db.String(120), nullable=True)
    faculty           = db.Column(db.String(120), nullable=True)
    level             = db.Column(db.String(10), nullable=True)
    year_of_admission = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        return {
            "matric_number":     self.matric_number,
            "department":        self.department,
            "faculty":           self.faculty,
            "level":             self.level,
            "year_of_admission": self.year_of_admission,
        }


class StaffProfile(db.Model):
    __tablename__ = "staff_profiles"

    id              = db.Column(db.Integer, primary_key=True)
    patient_id      = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"), unique=True, nullable=False)
    staff_id_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    department      = db.Column(db.String(120), nullable=True)
    designation     = db.Column(db.String(120), nullable=True)

    def to_dict(self):
        return {
            "staff_id_number": self.staff_id_number,
            "department":      self.department,
            "designation":     self.designation,
        }