# app/models/vital_signs.py

from datetime import datetime, timezone
from app.extensions import db


class VitalSigns(db.Model):
    """
    Recorded by a Nurse at the start of each visit — vitals AND the nurse's
    triage assessment / nursing notes, stored together to match how the
    frontend (Nurse vitals.html write, Doctor consultation.html read) treats
    this as a single "Nurse's Assessment" record per health file.
    """
    __tablename__ = "vital_signs"

    id                       = db.Column(db.Integer, primary_key=True)
    patient_id               = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"),
                                         nullable=False)
    health_file_id           = db.Column(db.Integer, db.ForeignKey("health_files.id", ondelete="CASCADE"),
                                         nullable=True, index=True)
    consultation_id          = db.Column(db.Integer, db.ForeignKey("consultations.id"), nullable=True)

    # ── Vital signs ──────────────────────────────────────────
    blood_pressure_systolic  = db.Column(db.SmallInteger, nullable=True)   # mmHg
    blood_pressure_diastolic = db.Column(db.SmallInteger, nullable=True)   # mmHg
    pulse_rate               = db.Column(db.SmallInteger, nullable=True)   # bpm
    temperature               = db.Column(db.Numeric(4, 1), nullable=True) # °C
    weight                    = db.Column(db.Numeric(5, 2), nullable=True) # kg
    height                    = db.Column(db.Numeric(5, 2), nullable=True) # cm
    bmi                       = db.Column(db.Numeric(4, 1), nullable=True) # computed server-side
    oxygen_saturation         = db.Column(db.Numeric(4, 1), nullable=True) # %
    respiratory_rate          = db.Column(db.SmallInteger, nullable=True)
    blood_sugar                = db.Column(db.Numeric(4, 1), nullable=True) # mmol/L
    pain_score                = db.Column(db.SmallInteger, nullable=True)  # 0–10

    # ── Triage assessment ────────────────────────────────────
    chief_complaint          = db.Column(db.String(255), nullable=True)
    symptoms                 = db.Column(db.Text, nullable=True)
    duration_of_illness      = db.Column(db.String(120), nullable=True)
    general_observations     = db.Column(db.Text, nullable=True)
    urgency_level            = db.Column(
        db.Enum("emergency", "high", "normal", "low"),
        default="normal", nullable=False,
    )

    # ── Nursing notes ────────────────────────────────────────
    nursing_flags             = db.Column(db.JSON, nullable=True)  # list of short flag strings
    nursing_notes              = db.Column(db.Text, nullable=True)

    recorded_by               = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    recorded_at                = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # NOTE: `patient` and `health_file` accessors already exist via backrefs
    # from Patient.vital_signs and HealthFile.vital_signs respectively (see
    # patient.py / health_file.py) -- not redefined here to avoid a mapper
    # conflict ("property of that name exists on mapper").

    def compute_bmi(self):
        """Auto-calculate BMI if weight and height are provided. Server-side
        is the source of truth — any bmi sent by the client is ignored."""
        if self.weight and self.height and self.height > 0:
            height_m = float(self.height) / 100
            self.bmi = round(float(self.weight) / (height_m ** 2), 1)

    def to_dict(self):
        return {
            "id":                   self.id,
            "patient_id":           self.patient_id,
            "health_file_id":       self.health_file_id,
            "consultation_id":      self.consultation_id,

            # NOTE: key names below intentionally match what
            # consultation.html / queue.html already read
            # (bp_systolic / bp_diastolic / spo2), not the raw column names.
            "bp_systolic":          self.blood_pressure_systolic,
            "bp_diastolic":         self.blood_pressure_diastolic,
            "blood_pressure":       f"{self.blood_pressure_systolic}/{self.blood_pressure_diastolic}"
                                    if self.blood_pressure_systolic else None,
            "pulse_rate":           self.pulse_rate,
            "temperature":          float(self.temperature) if self.temperature is not None else None,
            "weight":               float(self.weight) if self.weight is not None else None,
            "height":               float(self.height) if self.height is not None else None,
            "bmi":                  float(self.bmi) if self.bmi is not None else None,
            "spo2":                 float(self.oxygen_saturation) if self.oxygen_saturation is not None else None,
            "respiratory_rate":     self.respiratory_rate,
            "blood_sugar":          float(self.blood_sugar) if self.blood_sugar is not None else None,
            "pain_score":           self.pain_score,

            "chief_complaint":      self.chief_complaint,
            "symptoms":             self.symptoms,
            "duration_of_illness":  self.duration_of_illness,
            "general_observations": self.general_observations,
            "urgency_level":        self.urgency_level,

            "nursing_flags":        self.nursing_flags or [],
            "nursing_notes":        self.nursing_notes,

            "recorded_by":          self.recorded_by,
            "recorded_at":          self.recorded_at.isoformat() if self.recorded_at else None,
        }