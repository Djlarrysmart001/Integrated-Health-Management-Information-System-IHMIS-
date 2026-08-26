# app/services/report_service.py

from datetime import datetime, timezone, date, timedelta
from sqlalchemy import func, extract
from app.extensions import db
from app.models.patient import Patient, StudentProfile, StaffProfile
from app.models.consultation import Consultation, Diagnosis
from app.models.prescription import Prescription, PrescriptionItem
from app.models.laboratory import LabRequest, LabResult
from app.models.pharmacy import Drug, DrugInventory
from app.models.user import User
from app.services.pharmacy_service import PharmacyService


class ReportService:

    # ──────────────────────────────────────────────────────────
    # Helper — Parse Date Range
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _parse_dates(date_from: str = None, date_to: str = None):
        """
        Parses date strings into date objects.
        Defaults to the current month if not provided.
        """
        today = date.today()

        if date_from:
            try:
                start = datetime.strptime(date_from, "%Y-%m-%d").date()
            except ValueError:
                start = today.replace(day=1)
        else:
            start = today.replace(day=1)

        if date_to:
            try:
                end = datetime.strptime(date_to, "%Y-%m-%d").date()
            except ValueError:
                end = today
        else:
            end = today

        return start, end

    # ──────────────────────────────────────────────────────────
    # 1. Patient Registration Report
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def patient_registration_report(date_from=None, date_to=None):
        """
        Summary of patient registrations within a date range.
        Breaks down by patient type, gender, and blood group.
        """
        start, end = ReportService._parse_dates(date_from, date_to)

        # Total registrations
        base_query = Patient.query.filter(
            func.date(Patient.created_at) >= start,
            func.date(Patient.created_at) <= end
        )

        total        = base_query.count()
        total_students = base_query.filter_by(patient_type="student").count()
        total_staff    = base_query.filter_by(patient_type="staff").count()
        total_male     = base_query.filter_by(gender="male").count()
        total_female   = base_query.filter_by(gender="female").count()

        # Blood group distribution
        blood_groups = db.session.query(
            Patient.blood_group,
            func.count(Patient.id).label("count")
        ).filter(
            func.date(Patient.created_at) >= start,
            func.date(Patient.created_at) <= end
        ).group_by(Patient.blood_group).all()

        # Daily registrations trend
        daily = db.session.query(
            func.date(Patient.created_at).label("day"),
            func.count(Patient.id).label("count")
        ).filter(
            func.date(Patient.created_at) >= start,
            func.date(Patient.created_at) <= end
        ).group_by(func.date(Patient.created_at)).order_by("day").all()

        return {
            "success": True,
            "message": "Patient registration report generated.",
            "data": {
                "report_type":   "patient_registration",
                "period":        {"from": start.isoformat(), "to": end.isoformat()},
                "summary": {
                    "total_registered": total,
                    "students":         total_students,
                    "staff":            total_staff,
                    "male":             total_male,
                    "female":           total_female,
                },
                "blood_group_distribution": [
                    {"blood_group": bg, "count": c}
                    for bg, c in blood_groups
                ],
                "daily_trend": [
                    {"date": str(day), "count": count}
                    for day, count in daily
                ],
            }
        }

    # ──────────────────────────────────────────────────────────
    # 2. Patient Visits Report
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def patient_visits_report(date_from=None, date_to=None):
        """
        Summary of consultations (patient visits) within a date range.
        Shows visit trends and doctor activity.
        """
        start, end = ReportService._parse_dates(date_from, date_to)

        base_query = Consultation.query.filter(
            func.date(Consultation.visit_date) >= start,
            func.date(Consultation.visit_date) <= end
        )

        total_visits  = base_query.count()
        open_visits   = base_query.filter_by(status="open").count()
        closed_visits = base_query.filter_by(status="closed").count()

        # Visits per doctor
        doctor_stats = db.session.query(
            User.first_name,
            User.last_name,
            func.count(Consultation.id).label("visit_count")
        ).join(
            Consultation, Consultation.doctor_id == User.id
        ).filter(
            func.date(Consultation.visit_date) >= start,
            func.date(Consultation.visit_date) <= end
        ).group_by(User.id).order_by(
            func.count(Consultation.id).desc()
        ).all()

        # Daily visits trend
        daily = db.session.query(
            func.date(Consultation.visit_date).label("day"),
            func.count(Consultation.id).label("count")
        ).filter(
            func.date(Consultation.visit_date) >= start,
            func.date(Consultation.visit_date) <= end
        ).group_by(
            func.date(Consultation.visit_date)
        ).order_by("day").all()

        return {
            "success": True,
            "message": "Patient visits report generated.",
            "data": {
                "report_type": "patient_visits",
                "period":      {"from": start.isoformat(), "to": end.isoformat()},
                "summary": {
                    "total_visits":  total_visits,
                    "open_visits":   open_visits,
                    "closed_visits": closed_visits,
                },
                "doctor_activity": [
                    {
                        "doctor": f"{fn} {ln}",
                        "visits": vc
                    }
                    for fn, ln, vc in doctor_stats
                ],
                "daily_trend": [
                    {"date": str(day), "count": count}
                    for day, count in daily
                ],
            }
        }

    # ──────────────────────────────────────────────────────────
    # 3. Disease Burden Report
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def disease_burden_report(date_from=None, date_to=None, top_n=10):
        """
        Shows the most common diagnoses within a date range.
        Useful for identifying disease trends in the institution.
        """
        start, end = ReportService._parse_dates(date_from, date_to)

        # Top diagnoses by frequency
        top_diagnoses = db.session.query(
            Diagnosis.description,
            Diagnosis.icd10_code,
            func.count(Diagnosis.id).label("count")
        ).join(
            Consultation, Consultation.id == Diagnosis.consultation_id
        ).filter(
            func.date(Consultation.visit_date) >= start,
            func.date(Consultation.visit_date) <= end
        ).group_by(
            Diagnosis.description,
            Diagnosis.icd10_code
        ).order_by(
            func.count(Diagnosis.id).desc()
        ).limit(top_n).all()

        total_diagnoses = db.session.query(
            func.count(Diagnosis.id)
        ).join(
            Consultation, Consultation.id == Diagnosis.consultation_id
        ).filter(
            func.date(Consultation.visit_date) >= start,
            func.date(Consultation.visit_date) <= end
        ).scalar()

        return {
            "success": True,
            "message": "Disease burden report generated.",
            "data": {
                "report_type":     "disease_burden",
                "period":          {"from": start.isoformat(), "to": end.isoformat()},
                "total_diagnoses": total_diagnoses,
                "top_diagnoses": [
                    {
                        "rank":        idx + 1,
                        "description": desc,
                        "icd10_code":  code,
                        "count":       count,
                        "percentage":  round((count / total_diagnoses * 100), 1)
                        if total_diagnoses else 0
                    }
                    for idx, (desc, code, count) in enumerate(top_diagnoses)
                ],
            }
        }

    # ──────────────────────────────────────────────────────────
    # 4. Drug Consumption Report
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def drug_consumption_report(date_from=None, date_to=None):
        """
        Shows how many units of each drug were dispensed
        within the date range.
        """
        start, end = ReportService._parse_dates(date_from, date_to)

        consumption = db.session.query(
            Drug.name,
            Drug.category,
            Drug.unit,
            func.sum(PrescriptionItem.quantity).label("total_dispensed"),
            func.count(PrescriptionItem.id).label("dispensation_count")
        ).join(
            PrescriptionItem, PrescriptionItem.drug_id == Drug.id
        ).filter(
            PrescriptionItem.is_dispensed == True,
            func.date(PrescriptionItem.dispensed_at) >= start,
            func.date(PrescriptionItem.dispensed_at) <= end
        ).group_by(
            Drug.id
        ).order_by(
            func.sum(PrescriptionItem.quantity).desc()
        ).all()

        total_units = sum(row[3] for row in consumption if row[3])

        return {
            "success": True,
            "message": "Drug consumption report generated.",
            "data": {
                "report_type": "drug_consumption",
                "period":      {"from": start.isoformat(), "to": end.isoformat()},
                "total_units_dispensed": total_units,
                "drugs": [
                    {
                        "drug_name":           name,
                        "category":            category,
                        "unit":                unit,
                        "total_dispensed":     int(dispensed) if dispensed else 0,
                        "dispensation_count":  count,
                    }
                    for name, category, unit, dispensed, count in consumption
                ],
            }
        }

    # ──────────────────────────────────────────────────────────
    # 5. Laboratory Turnaround Report
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def lab_turnaround_report(date_from=None, date_to=None):
        """
        Shows lab request volume and completion statistics.
        """
        start, end = ReportService._parse_dates(date_from, date_to)

        base_query = LabRequest.query.filter(
            func.date(LabRequest.created_at) >= start,
            func.date(LabRequest.created_at) <= end
        )

        total     = base_query.count()
        completed = base_query.filter_by(status="completed").count()
        pending   = base_query.filter_by(status="pending").count()
        cancelled = base_query.filter_by(status="cancelled").count()
        urgent    = base_query.filter_by(priority="urgent").count()
        stat      = base_query.filter_by(priority="stat").count()

        completion_rate = round(
            (completed / total * 100), 1
        ) if total else 0

        return {
            "success": True,
            "message": "Lab turnaround report generated.",
            "data": {
                "report_type": "lab_turnaround",
                "period":      {"from": start.isoformat(), "to": end.isoformat()},
                "summary": {
                    "total_requests":   total,
                    "completed":        completed,
                    "pending":          pending,
                    "cancelled":        cancelled,
                    "urgent_requests":  urgent,
                    "stat_requests":    stat,
                    "completion_rate":  f"{completion_rate}%",
                },
            }
        }

    # ──────────────────────────────────────────────────────────
    # 6. Inventory Status Report
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def inventory_status_report():
        """
        Current snapshot of pharmacy inventory.
        Shows stock levels, low stock alerts, and expiring drugs.
        """
        today         = date.today()
        threshold_90  = today + timedelta(days=90)

        all_drugs  = Drug.query.filter_by(is_active=True).all()
        expiring   = []
        out_of_stock = []

        # Low stock, judged the SAME way everywhere in the system: against
        # the drug's total (aggregate) stock, not any single batch in
        # isolation. See PharmacyService._drugs_with_low_stock for why.
        low_stock = [
            {
                "drug_id":             entry["drug"].id,
                "drug_name":           entry["drug"].name,
                "quantity_in_stock":   entry["total_stock"],
                "minimum_stock_level": entry["min_level"],
            }
            for entry in PharmacyService._drugs_with_low_stock()
        ]

        for drug in all_drugs:
            total_stock = drug.total_stock
            if total_stock == 0:
                out_of_stock.append({
                    "drug_id":   drug.id,
                    "drug_name": drug.name,
                    "category":  drug.category,
                })

            for batch in drug.inventory_batches:
                if batch.expiry_date and batch.expiry_date <= threshold_90:
                    expiring.append({
                        "drug_id":      drug.id,
                        "drug_name":    drug.name,
                        "batch_number": batch.batch_number,
                        "expiry_date":  batch.expiry_date.isoformat(),
                        "days_left":    (batch.expiry_date - today).days,
                        "quantity":     batch.quantity_in_stock,
                    })

        return {
            "success": True,
            "message": "Inventory status report generated.",
            "data": {
                "report_type":        "inventory_status",
                "generated_at":       datetime.now(timezone.utc).isoformat(),
                "total_drugs":        len(all_drugs),
                "out_of_stock_count": len(out_of_stock),
                "low_stock_count":    len(low_stock),
                "expiring_soon_count": len(expiring),
                "out_of_stock":       out_of_stock,
                "low_stock_drugs":    low_stock,
                "expiring_soon":      expiring,
            }
        }

    # ──────────────────────────────────────────────────────────
    # 7. Summary Dashboard Report
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def summary_report(date_from=None, date_to=None):
        """
        A high-level executive summary combining all key metrics.
        Used for the admin dashboard and management reports.
        """
        start, end = ReportService._parse_dates(date_from, date_to)

        total_patients      = Patient.query.count()
        new_patients        = Patient.query.filter(
            func.date(Patient.created_at) >= start,
            func.date(Patient.created_at) <= end
        ).count()

        total_consultations = Consultation.query.filter(
            func.date(Consultation.visit_date) >= start,
            func.date(Consultation.visit_date) <= end
        ).count()

        total_prescriptions = Prescription.query.filter(
            func.date(Prescription.created_at) >= start,
            func.date(Prescription.created_at) <= end
        ).count()

        total_lab_requests  = LabRequest.query.filter(
            func.date(LabRequest.created_at) >= start,
            func.date(LabRequest.created_at) <= end
        ).count()

        total_staff         = User.query.filter_by(is_active=True).count()
        total_drugs         = Drug.query.filter_by(is_active=True).count()

        return {
            "success": True,
            "message": "Summary report generated.",
            "data": {
                "report_type": "summary",
                "period":      {"from": start.isoformat(), "to": end.isoformat()},
                "metrics": {
                    "total_registered_patients": total_patients,
                    "new_patients_this_period":  new_patients,
                    "total_consultations":        total_consultations,
                    "total_prescriptions":        total_prescriptions,
                    "total_lab_requests":         total_lab_requests,
                    "active_staff_accounts":      total_staff,
                    "drugs_in_formulary":         total_drugs,
                }
            }
        }