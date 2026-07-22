# app/services/dashboard_service.py

from datetime import datetime, timezone, date, timedelta
from sqlalchemy import func
from app.extensions import db
from app.models.patient import Patient
from app.models.vital_signs import VitalSigns
from app.models.consultation import Consultation, Diagnosis
from app.models.prescription import Prescription, PrescriptionItem
from app.models.laboratory import LabRequest, LabResult
from app.models.pharmacy import Drug, DrugInventory
from app.models.notification import Notification
from app.models.user import User
from app.models.audit_log import AuditLog


class DashboardService:

    # ──────────────────────────────────────────────────────────
    # Admin Dashboard
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_admin_dashboard():
        """
        Full institutional overview for the Admin.
        Shows everything: patients, staff, visits, pharmacy, lab.
        """
        today      = date.today()
        this_month_start = today.replace(day=1)

        # ── Patient stats ──────────────────────────────────────
        total_patients     = Patient.query.count()
        patients_this_month = Patient.query.filter(
            func.date(Patient.created_at) >= this_month_start
        ).count()
        active_patients    = Patient.query.filter_by(is_active=True).count()

        # ── Staff stats ────────────────────────────────────────
        total_staff        = User.query.filter_by(is_active=True).count()

        # ── Today's activity ───────────────────────────────────
        todays_registrations = Patient.query.filter(
            func.date(Patient.created_at) == today
        ).count()

        todays_consultations = Consultation.query.filter(
            func.date(Consultation.visit_date) == today
        ).count()

        open_consultations = Consultation.query.filter_by(status="open").count()

        # ── Prescription stats ─────────────────────────────────
        pending_prescriptions = Prescription.query.filter_by(
            status="pending"
        ).count()

        dispensed_today = PrescriptionItem.query.filter(
            PrescriptionItem.is_dispensed == True,
            func.date(PrescriptionItem.dispensed_at) == today
        ).count()

        # ── Lab stats ──────────────────────────────────────────
        pending_lab_requests = LabRequest.query.filter(
            LabRequest.status.in_(["pending", "sample_collected", "in_progress"])
        ).count()

        # ── Pharmacy alerts ────────────────────────────────────
        low_stock_count = DrugInventory.query.filter(
            DrugInventory.quantity_in_stock <= DrugInventory.minimum_stock_level
        ).count()
        expired_count = DrugInventory.query.filter(
            DrugInventory.expiry_date != None,
            DrugInventory.expiry_date < today
        ).count()

        # ── This month's visit trend ───────────────────────────
        monthly_visits = db.session.query(
            func.date(Consultation.visit_date).label("day"),
            func.count(Consultation.id).label("count")
        ).filter(
            func.date(Consultation.visit_date) >= this_month_start
        ).group_by(
            func.date(Consultation.visit_date)
        ).order_by("day").all()

        # ── Recent audit activity ──────────────────────────────
        recent_logs = AuditLog.query.order_by(
            AuditLog.created_at.desc()
        ).limit(5).all()

        return {
            "success": True,
            "message": "Admin dashboard loaded successfully.",
            "data": {
                "role":    "Admin",
                "date":    today.isoformat(),
                "patients": {
                    "total":       total_patients,
                    "active":      active_patients,
                    "new_this_month": patients_this_month,
                },
                "staff": {
                    "total_active": total_staff,
                },
                "today": {
                    "new_registrations": todays_registrations,
                    "consultations":  todays_consultations,
                    "open_consultations": open_consultations,
                    "dispensed_items": dispensed_today,
                },
                "pharmacy_alerts": {
                    "pending_prescriptions": pending_prescriptions,
                    "low_stock_drugs":       low_stock_count,
                    "expired_batches":       expired_count,
                },
                "laboratory": {
                    "pending_requests": pending_lab_requests,
                },
                "monthly_visit_trend": [
                    {"date": str(day), "visits": count}
                    for day, count in monthly_visits
                ],
                "recent_activity": [
                    log.to_dict() for log in recent_logs
                ],
            }
        }

    # ──────────────────────────────────────────────────────────
    # Doctor Dashboard
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_doctor_dashboard(doctor_id: int):
        """
        Doctor-specific dashboard.
        Shows their open consultations, monthly stats, and pending labs.
        """
        today = date.today()
        this_month_start = today.replace(day=1)

        # ── Active consultations ───────────────────────────────
        open_consultations = Consultation.query.filter_by(
            doctor_id=doctor_id, status="open"
        ).all()

        # ── This month's stats ─────────────────────────────────
        consultations_this_month = Consultation.query.filter(
            Consultation.doctor_id == doctor_id,
            func.date(Consultation.visit_date) >= this_month_start
        ).count()

        prescriptions_this_month = Prescription.query.filter(
            Prescription.prescribed_by == doctor_id,
            func.date(Prescription.created_at) >= this_month_start
        ).count()

        lab_requests_this_month = LabRequest.query.filter(
            LabRequest.requested_by == doctor_id,
            func.date(LabRequest.created_at) >= this_month_start
        ).count()

        # ── Pending lab results for this doctor's patients ─────
        pending_lab_results = LabRequest.query.join(
            Consultation,
            LabRequest.consultation_id == Consultation.id
        ).filter(
            Consultation.doctor_id == doctor_id,
            LabRequest.status.in_(["pending", "in_progress", "sample_collected"])
        ).count()

        # ── Top diagnoses this month ───────────────────────────
        top_diagnoses = db.session.query(
            Diagnosis.description,
            func.count(Diagnosis.id).label("count")
        ).join(
            Consultation, Consultation.id == Diagnosis.consultation_id
        ).filter(
            Consultation.doctor_id == doctor_id,
            func.date(Consultation.visit_date) >= this_month_start
        ).group_by(
            Diagnosis.description
        ).order_by(
            func.count(Diagnosis.id).desc()
        ).limit(5).all()

        # ── Unread notifications ───────────────────────────────
        unread_notifications = Notification.query.filter_by(
            recipient_id=doctor_id, is_read=False
        ).count()

        return {
            "success": True,
            "message": "Doctor dashboard loaded successfully.",
            "data": {
                "role":  "Doctor",
                "date":  today.isoformat(),
                "open_consultations": {
                    "total": len(open_consultations),
                    "list":  [c.to_dict() for c in open_consultations]
                },
                "this_month": {
                    "consultations":   consultations_this_month,
                    "prescriptions":   prescriptions_this_month,
                    "lab_requests":    lab_requests_this_month,
                },
                "pending_lab_results":   pending_lab_results,
                "unread_notifications":  unread_notifications,
                "top_diagnoses_this_month": [
                    {"diagnosis": desc, "count": count}
                    for desc, count in top_diagnoses
                ],
            }
        }

    # ──────────────────────────────────────────────────────────
    # Medical Health Officer Dashboard
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_mho_dashboard():
        """
        Medical Health Officer dashboard.
        First point of contact — focuses on patient registration
        and health file intake (front-desk duties formerly split
        between a receptionist and the nurse).
        """
        today = date.today()

        # ── Patients registered today ──────────────────────────
        registered_today = Patient.query.filter(
            func.date(Patient.created_at) == today
        ).count()

        total_patients = Patient.query.filter_by(is_active=True).count()

        # ── Recently registered (for quick "forward to nurse") ──
        recent_patients = Patient.query.filter(
            func.date(Patient.created_at) == today
        ).order_by(Patient.created_at.desc()).limit(10).all()

        return {
            "success": True,
            "message": "Medical Health Officer dashboard loaded successfully.",
            "data": {
                "role": "Medical Health Officer",
                "date": today.isoformat(),
                "patients": {
                    "total_active":     total_patients,
                    "registered_today": registered_today,
                },
                "recent_registrations": [p.to_dict() for p in recent_patients],
            }
        }

    # ──────────────────────────────────────────────────────────
    # Nurse Dashboard
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_nurse_dashboard():
        """
        Nurse dashboard.
        Focuses on vitals/triage — patients forwarded by the MHO,
        then handed off to the Doctor once triaged.
        """
        today = date.today()

        # ── Open consultations (patients currently in the flow) ─
        open_consultations = Consultation.query.filter_by(
            status="open"
        ).count()

        # ── Vitals recorded today ───────────────────────────────
        vitals_today = VitalSigns.query.filter(
            func.date(VitalSigns.recorded_at) == today
        ).count()

        total_patients = Patient.query.filter_by(is_active=True).count()

        return {
            "success": True,
            "message": "Nurse dashboard loaded successfully.",
            "data": {
                "role": "Nurse",
                "date": today.isoformat(),
                "patients": {
                    "total_active": total_patients,
                },
                "vitals_recorded_today": vitals_today,
                "open_consultations": open_consultations,
            }
        }

    # ──────────────────────────────────────────────────────────
    # Pharmacist Dashboard
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_pharmacist_dashboard():
        """
        Pharmacist dashboard.
        Focuses on prescription queue, stock levels, and alerts.
        """
        today = date.today()

        # ── Prescription queue ─────────────────────────────────
        pending_prescriptions = Prescription.query.filter(
            Prescription.status.in_(["pending", "partially_dispensed"])
        ).order_by(Prescription.created_at.asc()).limit(10).all()

        pending_count = Prescription.query.filter(
            Prescription.status.in_(["pending", "partially_dispensed"])
        ).count()

        # ── Today's dispensing ─────────────────────────────────
        dispensed_today = PrescriptionItem.query.filter(
            PrescriptionItem.is_dispensed == True,
            func.date(PrescriptionItem.dispensed_at) == today
        ).count()

        # ── Stock alerts ───────────────────────────────────────
        all_batches   = DrugInventory.query.all()
        low_stock     = [b for b in all_batches if b.is_low_stock]
        expired       = [
            b for b in all_batches
            if b.expiry_date and b.expiry_date < today
        ]

        # ── Expiring soon (next 30 days) ───────────────────────
        threshold = today + timedelta(days=30)
        expiring_soon = [
            b for b in all_batches
            if b.expiry_date and today <= b.expiry_date <= threshold
        ]

        # ── Total drugs ────────────────────────────────────────
        total_drugs = Drug.query.filter_by(is_active=True).count()

        return {
            "success": True,
            "message": "Pharmacist dashboard loaded successfully.",
            "data": {
                "role": "Pharmacist",
                "date": today.isoformat(),
                "prescription_queue": {
                    "total_pending":  pending_count,
                    "next_10":        [p.to_dict() for p in pending_prescriptions]
                },
                "dispensing_today": dispensed_today,
                "inventory_alerts": {
                    "total_drugs":        total_drugs,
                    "low_stock_count":    len(low_stock),
                    "expired_count":      len(expired),
                    "expiring_soon_count": len(expiring_soon),
                    "low_stock_drugs": [
                        {
                            "drug_name":     Drug.query.get(b.drug_id).name,
                            "stock":         b.quantity_in_stock,
                            "minimum_level": b.minimum_stock_level,
                        }
                        for b in low_stock[:5]
                    ],
                    "expiring_soon_drugs": [
                        {
                            "drug_name":   Drug.query.get(b.drug_id).name,
                            "expiry_date": b.expiry_date.isoformat(),
                            "quantity":    b.quantity_in_stock,
                        }
                        for b in expiring_soon[:5]
                    ],
                },
            }
        }

    # ──────────────────────────────────────────────────────────
    # Lab Technician Dashboard
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_lab_dashboard():
        """
        Lab Technician dashboard.
        Focuses on pending requests, results to enter, and stats.
        """
        today = date.today()
        this_month_start = today.replace(day=1)

        # ── Pending requests queue ─────────────────────────────
        pending_requests = LabRequest.query.filter(
            LabRequest.status.in_(["pending", "sample_collected", "in_progress"])
        ).order_by(
            LabRequest.created_at.asc()
        ).limit(10).all()

        pending_count = LabRequest.query.filter(
            LabRequest.status.in_(["pending", "sample_collected", "in_progress"])
        ).count()

        urgent_count = LabRequest.query.filter(
            LabRequest.status.in_(["pending", "sample_collected"]),
            LabRequest.priority.in_(["urgent", "stat"])
        ).count()

        # ── Completed today ────────────────────────────────────
        completed_today = LabRequest.query.filter(
            LabRequest.status == "completed",
            func.date(LabRequest.updated_at) == today
        ).count()

        # ── This month stats ───────────────────────────────────
        total_this_month = LabRequest.query.filter(
            func.date(LabRequest.created_at) >= this_month_start
        ).count()

        completed_this_month = LabRequest.query.filter(
            LabRequest.status == "completed",
            func.date(LabRequest.created_at) >= this_month_start
        ).count()

        completion_rate = round(
            (completed_this_month / total_this_month * 100), 1
        ) if total_this_month else 0

        return {
            "success": True,
            "message": "Lab dashboard loaded successfully.",
            "data": {
                "role": "Lab Technician",
                "date": today.isoformat(),
                "pending_queue": {
                    "total":        pending_count,
                    "urgent":       urgent_count,
                    "next_10":      [r.to_dict() for r in pending_requests]
                },
                "today": {
                    "completed": completed_today,
                },
                "this_month": {
                    "total_requests":    total_this_month,
                    "completed":         completed_this_month,
                    "completion_rate":   f"{completion_rate}%",
                },
            }
        }