# app/services/analytics_service.py

from datetime import datetime, timezone, date, timedelta
from collections import defaultdict
from sqlalchemy import func
from app.extensions import db
from app.models.patient import Patient
from app.models.health_file import HealthFile
from app.models.consultation import Diagnosis
from app.models.audit_log import AuditLog


class AnalyticsService:
    """
    Decision-oriented aggregate statistics -- distinct from ReportService,
    which produces detailed tabular reports for record-keeping. This is
    the "look at this and make a fast decision" dashboard layer, per the
    original brief: "Total patient analytics (statistics, this is to
    enable or make fast decisions)".

    The average-wait-time and visit-outcome metrics are only possible
    because every HealthFile stage transition is already audit-logged --
    a direct payoff of the accountability work done earlier in this
    project for a completely different reason (incident investigation).
    """

    STAGE_LABELS = {
        "OPEN_HEALTH_FILE":     "Waiting at MHO (intake)",
        "FORWARD_TO_NURSE":     "With Nurse (vitals/triage)",
        "FORWARD_TO_DOCTOR":    "With Doctor (consultation)",
        "FORWARD_TO_LAB":       "At Lab (awaiting test)",
        "RETURN_FROM_LAB":      "With Doctor (reviewing result)",
        "FORWARD_TO_PHARMACY":  "At Pharmacy (dispensing)",
    }

    CLOSE_ACTIONS = {
        "CLOSE_HEALTH_FILE":   "dispensed",
        "CLOSE_VIA_REFERRAL":  "referred",
        "CLOSE_VIA_ADMISSION": "admitted",
    }

    # ──────────────────────────────────────────────────────────
    # Helper — Parse Date Range (mirrors ReportService's helper,
    # kept local so this service has no cross-dependency)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _parse_dates(date_from: str = None, date_to: str = None):
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
    # 1. Average Wait Time Per Stage
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_average_wait_times(date_from: str = None, date_to: str = None):
        """
        Average time patients spend at each stage, computed from the
        HealthFile audit trail. Surfaces bottlenecks directly -- e.g.
        "patients wait 35 min with Nurse on average" is a concrete,
        actionable staffing signal.
        """
        start, end = AnalyticsService._parse_dates(date_from, date_to)

        logs = AuditLog.query.filter(
            AuditLog.entity_type == "HealthFile",
            AuditLog.action.in_(list(AnalyticsService.STAGE_LABELS.keys()) + list(AnalyticsService.CLOSE_ACTIONS.keys())),
            func.date(AuditLog.created_at) >= start,
            func.date(AuditLog.created_at) <= end,
        ).order_by(AuditLog.entity_id.asc(), AuditLog.created_at.asc()).all()

        by_file = defaultdict(list)
        for log in logs:
            by_file[log.entity_id].append((log.action, log.created_at))

        stage_durations = defaultdict(list)
        for file_id, events in by_file.items():
            for i in range(len(events) - 1):
                action, ts = events[i]
                _, next_ts = events[i + 1]
                label = AnalyticsService.STAGE_LABELS.get(action)
                if label:
                    stage_durations[label].append((next_ts - ts).total_seconds())

        averages = []
        for stage, durations in stage_durations.items():
            avg_minutes = round(sum(durations) / len(durations) / 60, 1)
            averages.append({"stage": stage, "average_minutes": avg_minutes, "sample_size": len(durations)})

        # Keep a sensible, consistent display order
        order = list(AnalyticsService.STAGE_LABELS.values())
        averages.sort(key=lambda x: order.index(x["stage"]) if x["stage"] in order else 99)

        return {
            "success": True,
            "message": "Average wait times computed successfully.",
            "data": {
                "period": {"from": start.isoformat(), "to": end.isoformat()},
                "stages": averages,
            }
        }

    # ──────────────────────────────────────────────────────────
    # 2. Visit Outcome Breakdown
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_visit_outcomes(date_from: str = None, date_to: str = None):
        """
        What happens to visits, in aggregate: dispensed normally,
        referred out, admitted, or still in progress. Useful for
        spotting trends (e.g. a spike in referrals this month).
        """
        start, end = AnalyticsService._parse_dates(date_from, date_to)

        health_files = HealthFile.query.filter(
            func.date(HealthFile.opened_at) >= start,
            func.date(HealthFile.opened_at) <= end,
        ).all()

        total = len(health_files)
        outcome_counts = {"dispensed": 0, "referred": 0, "admitted": 0, "still_in_progress": 0}

        # Look up the specific close action per closed file from the audit log
        closed_file_ids = [hf.id for hf in health_files if hf.status == "closed"]
        close_logs = {}
        if closed_file_ids:
            logs = AuditLog.query.filter(
                AuditLog.entity_type == "HealthFile",
                AuditLog.entity_id.in_(closed_file_ids),
                AuditLog.action.in_(list(AnalyticsService.CLOSE_ACTIONS.keys())),
            ).all()
            for log in logs:
                close_logs[log.entity_id] = log.action

        for hf in health_files:
            if hf.status != "closed":
                outcome_counts["still_in_progress"] += 1
                continue
            action = close_logs.get(hf.id)
            outcome = AnalyticsService.CLOSE_ACTIONS.get(action, "dispensed")
            outcome_counts[outcome] += 1

        percentages = {
            key: (round(count / total * 100, 1) if total else 0)
            for key, count in outcome_counts.items()
        }

        return {
            "success": True,
            "message": "Visit outcomes computed successfully.",
            "data": {
                "period": {"from": start.isoformat(), "to": end.isoformat()},
                "total_visits": total,
                "counts": outcome_counts,
                "percentages": percentages,
            }
        }

    # ──────────────────────────────────────────────────────────
    # 3. Patient Demographics
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_demographics():
        total_active = Patient.query.filter_by(is_active=True).count()

        by_type = dict(
            db.session.query(Patient.patient_type, func.count(Patient.id))
            .filter_by(is_active=True).group_by(Patient.patient_type).all()
        )
        by_gender = dict(
            db.session.query(Patient.gender, func.count(Patient.id))
            .filter_by(is_active=True).group_by(Patient.gender).all()
        )

        # Age buckets computed in Python (date_of_birth arithmetic isn't
        # portably expressible in a single cross-DB SQL group-by).
        # Deliberately query ONLY the date_of_birth column rather than
        # full Patient objects -- at 50,000 patients, loading every
        # column of every row just to read one date field would be a
        # real memory/latency cost; a single-column tuple query keeps
        # this to a few hundred KB even at full scale.
        age_buckets = {"under_18": 0, "18_25": 0, "26_35": 0, "36_50": 0, "over_50": 0, "unknown": 0}
        today = date.today()
        dobs = db.session.query(Patient.date_of_birth).filter(Patient.is_active == True).all()
        for (dob,) in dobs:
            if not dob:
                age_buckets["unknown"] += 1
                continue
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 18:
                age_buckets["under_18"] += 1
            elif age <= 25:
                age_buckets["18_25"] += 1
            elif age <= 35:
                age_buckets["26_35"] += 1
            elif age <= 50:
                age_buckets["36_50"] += 1
            else:
                age_buckets["over_50"] += 1

        return {
            "success": True,
            "message": "Patient demographics retrieved successfully.",
            "data": {
                "total_active_patients": total_active,
                "by_patient_type": by_type,
                "by_gender": by_gender,
                "by_age_bucket": age_buckets,
            }
        }

    # ──────────────────────────────────────────────────────────
    # 4. Top Diagnoses
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_top_diagnoses(date_from: str = None, date_to: str = None, limit: int = 5):
        start, end = AnalyticsService._parse_dates(date_from, date_to)

        results = db.session.query(
            Diagnosis.description, func.count(Diagnosis.id).label("count")
        ).filter(
            func.date(Diagnosis.created_at) >= start,
            func.date(Diagnosis.created_at) <= end,
        ).group_by(Diagnosis.description).order_by(func.count(Diagnosis.id).desc()).limit(limit).all()

        return {
            "success": True,
            "message": "Top diagnoses retrieved successfully.",
            "data": {
                "period": {"from": start.isoformat(), "to": end.isoformat()},
                "top_diagnoses": [{"diagnosis": desc, "count": count} for desc, count in results],
            }
        }

    # ──────────────────────────────────────────────────────────
    # 5. Visit Trend (for a line/bar chart)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_visit_trend(date_from: str = None, date_to: str = None):
        start, end = AnalyticsService._parse_dates(date_from, date_to)

        results = db.session.query(
            func.date(HealthFile.opened_at).label("day"),
            func.count(HealthFile.id).label("count")
        ).filter(
            func.date(HealthFile.opened_at) >= start,
            func.date(HealthFile.opened_at) <= end,
        ).group_by(func.date(HealthFile.opened_at)).order_by("day").all()

        return {
            "success": True,
            "message": "Visit trend retrieved successfully.",
            "data": {
                "period": {"from": start.isoformat(), "to": end.isoformat()},
                "trend": [{"date": str(day), "visits": count} for day, count in results],
            }
        }

    # ──────────────────────────────────────────────────────────
    # 6. Overview — everything above, bundled for a single dashboard load
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_overview(date_from: str = None, date_to: str = None):
        start, end = AnalyticsService._parse_dates(date_from, date_to)
        date_from_str, date_to_str = start.isoformat(), end.isoformat()

        return {
            "success": True,
            "message": "Analytics overview retrieved successfully.",
            "data": {
                "period":          {"from": date_from_str, "to": date_to_str},
                "demographics":    AnalyticsService.get_demographics()["data"],
                "visit_trend":     AnalyticsService.get_visit_trend(date_from_str, date_to_str)["data"]["trend"],
                "visit_outcomes":  AnalyticsService.get_visit_outcomes(date_from_str, date_to_str)["data"],
                "wait_times":      AnalyticsService.get_average_wait_times(date_from_str, date_to_str)["data"]["stages"],
                "top_diagnoses":   AnalyticsService.get_top_diagnoses(date_from_str, date_to_str)["data"]["top_diagnoses"],
            }
        }