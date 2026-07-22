# app/models/__init__.py
# Import every model here so Flask-Migrate can detect all tables.

from app.models.user import User, Role, user_roles
from app.models.patient import Patient, StudentProfile, StaffProfile
from app.models.patient_document import PatientDocument
from app.models.medical_record import MedicalRecord
from app.models.health_file import HealthFile
from app.models.vital_signs import VitalSigns
from app.models.consultation import Consultation, Diagnosis
from app.models.medical_certificate import MedicalCertificate
from app.models.immunization import Immunization
from app.models.prescription import Prescription, PrescriptionItem
from app.models.pharmacy import Drug, DrugInventory
from app.models.drug_transaction import DrugTransaction
from app.models.laboratory import LabTest, LabRequest, LabResult, lab_request_items
from app.models.referral import Referral
from app.models.admission import Admission
from app.models.staff_attendance import StaffAttendance
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.system_settings import SystemSettings