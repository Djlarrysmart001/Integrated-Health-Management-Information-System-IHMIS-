# app/services/health_file_service.py

from datetime import datetime, timezone, time
from app.extensions import db
from app.models.health_file import HealthFile
from app.models.patient import Patient
from app.models.user import User
from app.services.audit_service import AuditService
from app.utils.constants import Roles

# Which role's queue each status feeds -- used to auto-notify the
# right team the moment a health file lands in their queue.
STATUS_TO_ROLE = {
    "with_nurse":    Roles.NURSE,
    "with_doctor":   Roles.DOCTOR,
    "with_lab":      Roles.LAB_TECH,
    "with_pharmacy": Roles.PHARMACIST,
}

# Friendlier, action-specific wording than a generic "status changed" message.
ACTION_MESSAGES = {
    "FORWARD_TO_NURSE":    "New patient waiting: {patient_name} needs vitals/triage.",
    "FORWARD_TO_DOCTOR":   "Patient ready for consultation: {patient_name}.",
    "FORWARD_TO_LAB":      "New lab test request for {patient_name}.",
    "RETURN_FROM_LAB":     "Lab result ready for review: {patient_name}.",
    "FORWARD_TO_PHARMACY": "New prescription to dispense for {patient_name}.",
}


class HealthFileService:
    """
    Owns every stage transition in the walk-in workflow:
        with_mho -> with_nurse -> with_doctor -> (with_lab <-> with_doctor) -> with_pharmacy -> closed

    Every transition is audit-logged with the acting user, so a
    patient's full care trail can always be reconstructed later
    (e.g. for an incident investigation).
    """

    # ──────────────────────────────────────────────────────────
    # Open a new Health File (MHO)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def open_health_file(patient_id: int, opened_by: int):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}
        if not patient.is_active:
            return {"success": False, "message": "Cannot open a health file for an inactive patient.", "data": None}

        existing = HealthFile.query.filter(
            HealthFile.patient_id == patient_id,
            HealthFile.status != "closed"
        ).first()
        if existing:
            return {
                "success": False,
                "message": f"Patient already has an open health file (ID: {existing.id}, status: {existing.status}).",
                "data": existing.to_dict()
            }

        # ── Assign today's queue number ──────────────────────────
        # Counts how many health files have already been opened today
        # (regardless of current status) and takes the next number.
        # This naturally resets each day since it's computed fresh,
        # not stored as a running total anywhere.
        today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
        todays_count = HealthFile.query.filter(HealthFile.opened_at >= today_start).count()
        next_queue_number = todays_count + 1
        # ──────────────────────────────────────────────────────────

        health_file = HealthFile(
            patient_id   = patient_id,
            opened_by    = opened_by,
            status       = "with_mho",
            queue_number = next_queue_number,
            opened_at    = datetime.now(timezone.utc),
        )
        db.session.add(health_file)
        db.session.commit()

        AuditService.log(
            action      = "OPEN_HEALTH_FILE",
            entity_type = "HealthFile",
            entity_id   = health_file.id,
            user_id     = opened_by,
            new_value   = {"patient_id": patient_id, "status": "with_mho", "queue_number": next_queue_number}
        )

        return {"success": True, "message": f"Health file opened for {patient.full_name} (Queue #{next_queue_number}).", "data": health_file.to_dict()}

    # ──────────────────────────────────────────────────────────
    # Generic stage transition (internal helper)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _transition(health_file_id: int, from_statuses: list, to_status: str,
                     user_id: int, action_name: str):
        health_file = HealthFile.query.get(health_file_id)
        if not health_file:
            return {"success": False, "message": f"Health file with ID {health_file_id} not found.", "data": None}

        if health_file.status not in from_statuses:
            return {
                "success": False,
                "message": f"Health file is currently '{health_file.status}' — cannot perform this action from that state.",
                "data": health_file.to_dict()
            }

        old_status = health_file.status
        health_file.status = to_status

        # Stamp called_at the moment MHO forwards to Nurse — this is the
        # end of the "check-in wait" the Average Check-in Time KPI measures.
        if action_name == "FORWARD_TO_NURSE" and not health_file.called_at:
            health_file.called_at = datetime.now(timezone.utc)

        if to_status == "closed":
            health_file.closed_at = datetime.now(timezone.utc)
        db.session.commit()

        AuditService.log(
            action      = action_name,
            entity_type = "HealthFile",
            entity_id   = health_file.id,
            user_id     = user_id,
            old_value   = {"status": old_status},
            new_value   = {"status": to_status}
        )

        # ── Auto-notify whichever role's queue this file just landed in ──
        # Non-fatal: a missing/failed notification should never block the
        # actual clinical workflow transition, which has already committed.
        role_name = STATUS_TO_ROLE.get(to_status)
        if role_name:
            try:
                from app.services.notification_service import NotificationService
                patient_name = health_file.patient.full_name if health_file.patient else "A patient"
                message = ACTION_MESSAGES.get(
                    action_name, "Patient {patient_name} requires your attention."
                ).format(patient_name=patient_name)
                NotificationService.broadcast_to_role(
                    role_name         = role_name,
                    title             = "Patient Flow Update",
                    message           = message,
                    notification_type = "patient_flow",
                )
            except Exception:
                pass
        # ──────────────────────────────────────────────────────────

        return {"success": True, "message": f"Health file moved to '{to_status}'.", "data": health_file.to_dict()}

    # ──────────────────────────────────────────────────────────
    # MHO -> Nurse
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def forward_to_nurse(health_file_id: int, user_id: int):
        return HealthFileService._transition(
            health_file_id, ["with_mho"], "with_nurse", user_id, "FORWARD_TO_NURSE"
        )

    # ──────────────────────────────────────────────────────────
    # Nurse -> Doctor
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def forward_to_doctor(health_file_id: int, user_id: int):
        health_file = HealthFile.query.get(health_file_id)
        if health_file and not health_file.vital_signs:
            return {
                "success": False,
                "message": "Cannot forward to Doctor before recording vital signs.",
                "data": health_file.to_dict()
            }
        return HealthFileService._transition(
            health_file_id, ["with_nurse"], "with_doctor", user_id, "FORWARD_TO_DOCTOR"
        )

    # ──────────────────────────────────────────────────────────
    # Doctor -> Lab
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def forward_to_lab(health_file_id: int, user_id: int):
        return HealthFileService._transition(
            health_file_id, ["with_doctor"], "with_lab", user_id, "FORWARD_TO_LAB"
        )

    # ──────────────────────────────────────────────────────────
    # Lab -> back to Doctor (result ready)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def return_from_lab(health_file_id: int, user_id: int):
        return HealthFileService._transition(
            health_file_id, ["with_lab"], "with_doctor", user_id, "RETURN_FROM_LAB"
        )

    # ──────────────────────────────────────────────────────────
    # Doctor -> Pharmacy
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def forward_to_pharmacy(health_file_id: int, user_id: int):
        return HealthFileService._transition(
            health_file_id, ["with_doctor"], "with_pharmacy", user_id, "FORWARD_TO_PHARMACY"
        )

    # ──────────────────────────────────────────────────────────
    # Pharmacy -> Closed (dispensed)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def close_health_file(health_file_id: int, user_id: int):
        return HealthFileService._transition(
            health_file_id, ["with_pharmacy"], "closed", user_id, "CLOSE_HEALTH_FILE"
        )

    # ──────────────────────────────────────────────────────────
    # MHO manual override — closes a visit from any non-closed state.
    # Covers edge cases like a patient leaving before treatment is
    # complete (e.g. walked out, went to an outside pharmacy).
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def mho_manual_close(health_file_id: int, user_id: int, reason: str = None):
        health_file = HealthFile.query.get(health_file_id)
        if not health_file:
            return {"success": False, "message": f"Health file with ID {health_file_id} not found.", "data": None}
        if health_file.status == "closed":
            return {"success": False, "message": "Health file is already closed.", "data": health_file.to_dict()}

        result = HealthFileService._transition(
            health_file_id, [health_file.status], "closed", user_id, "MHO_MANUAL_CLOSE"
        )

        if result["success"] and reason:
            AuditService.log(
                action      = "MHO_MANUAL_CLOSE_REASON",
                entity_type = "HealthFile",
                entity_id   = health_file_id,
                user_id     = user_id,
                new_value   = {"reason": reason}
            )

        return result

    # ──────────────────────────────────────────────────────────
    # Doctor refers out -> Closed (visit ends here, patient goes elsewhere)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def close_via_referral(health_file_id: int, user_id: int):
        """
        A referral ends this clinic's involvement in the visit — the
        patient is being sent to an external facility instead of
        continuing through Pharmacy. Unlike the normal close (which
        only fires after Pharmacy dispenses), a referral can close the
        file directly from whichever stage the Doctor was at, since
        there's no guarantee a prescription is ever written.
        """
        health_file = HealthFile.query.get(health_file_id)
        if not health_file:
            return {"success": False, "message": f"Health file with ID {health_file_id} not found.", "data": None}
        if health_file.status == "closed":
            return {"success": False, "message": "Health file is already closed.", "data": health_file.to_dict()}
        if health_file.status not in ("with_doctor", "with_lab", "with_pharmacy"):
            return {
                "success": False,
                "message": f"Cannot close via referral from status '{health_file.status}'.",
                "data": health_file.to_dict()
            }
        return HealthFileService._transition(
            health_file_id, [health_file.status], "closed", user_id, "CLOSE_VIA_REFERRAL"
        )

    # ──────────────────────────────────────────────────────────
    # Doctor admits patient -> Closed (visit ends here, patient becomes an inpatient)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def close_via_admission(health_file_id: int, user_id: int):
        """
        Same idea as close_via_referral: admitting a patient ends the
        normal walk-in flow, so the health file closes regardless of
        which stage the Doctor was at.
        """
        health_file = HealthFile.query.get(health_file_id)
        if not health_file:
            return {"success": False, "message": f"Health file with ID {health_file_id} not found.", "data": None}
        if health_file.status == "closed":
            return {"success": False, "message": "Health file is already closed.", "data": health_file.to_dict()}
        if health_file.status not in ("with_doctor", "with_lab", "with_pharmacy"):
            return {
                "success": False,
                "message": f"Cannot close via admission from status '{health_file.status}'.",
                "data": health_file.to_dict()
            }
        return HealthFileService._transition(
            health_file_id, [health_file.status], "closed", user_id, "CLOSE_VIA_ADMISSION"
        )

    # ──────────────────────────────────────────────────────────
    # Queues — one per role
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_queue(status: str, page=1, per_page=20):
        if status not in HealthFile.STATUSES:
            return {"success": False, "message": f"'{status}' is not a valid health file status.", "data": None}

        pagination = HealthFile.query.filter_by(status=status).order_by(
            HealthFile.updated_at.asc()  # oldest-waiting-first, like a real queue
        ).paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"{pagination.total} patient(s) currently '{status}'.",
            "data": {
                "status":       status,
                "queue":        [hf.to_dict() for hf in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }

    # ──────────────────────────────────────────────────────────
    # Single health file / patient history
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_health_file(health_file_id: int):
        health_file = HealthFile.query.get(health_file_id)
        if not health_file:
            return {"success": False, "message": f"Health file with ID {health_file_id} not found.", "data": None}

        data = health_file.to_dict()
        if health_file.vital_signs:
            data["vital_signs"] = health_file.vital_signs.to_dict()
        if health_file.consultation:
            data["consultation"] = health_file.consultation.to_dict()

        return {"success": True, "message": "Health file retrieved successfully.", "data": data}

    @staticmethod
    def get_patient_health_files(patient_id: int, page=1, per_page=10):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}

        pagination = HealthFile.query.filter_by(patient_id=patient_id).order_by(
            HealthFile.opened_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"Health file history for {patient.full_name} retrieved.",
            "data": {
                "patient_id":   patient_id,
                "patient_name": patient.full_name,
                "health_files": [hf.to_dict() for hf in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }

    # ──────────────────────────────────────────────────────────
    # MHO Dashboard stats — today's snapshot
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_mho_dashboard_stats():
        """
        Aggregated counts for the MHO dashboard KPI cards. Kept as a
        single method (rather than one query per card) so the dashboard
        page can hit one endpoint instead of five.
        """
        today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)

        todays_files = HealthFile.query.filter(HealthFile.opened_at >= today_start).all()

        registered_today = Patient.query.filter(Patient.created_at >= today_start).count()
        checked_in_today = len(todays_files)
        waiting_for_nurse = HealthFile.query.filter_by(status="with_nurse").count()
        active_visits = HealthFile.query.filter(HealthFile.status != "closed").count()
        completed_today = sum(1 for f in todays_files if f.status == "closed")

        # New vs returning: a patient is "new" if this is their first-ever
        # health file, "returning" if they've been seen before today.
        new_count = 0
        returning_count = 0
        for f in todays_files:
            prior_visits = HealthFile.query.filter(
                HealthFile.patient_id == f.patient_id,
                HealthFile.id != f.id,
                HealthFile.opened_at < today_start
            ).count()
            if prior_visits == 0:
                new_count += 1
            else:
                returning_count += 1

        # Average check-in time: mean of (called_at - opened_at) for
        # today's files that have actually been forwarded to Nurse.
        wait_times = [
            (f.called_at - f.opened_at).total_seconds()
            for f in todays_files if f.called_at
        ]
        avg_checkin_seconds = int(sum(wait_times) / len(wait_times)) if wait_times else None

        # Long-waiting alert: patients still sitting with MHO (not yet
        # forwarded to Nurse) for more than 30 minutes. Scoped to today's
        # files only, matching the walk-in/same-day nature of the clinic.
        LONG_WAIT_THRESHOLD_SECONDS = 30 * 60
        now = datetime.now(timezone.utc)
        long_waiting_count = sum(
            1 for f in todays_files
            if f.status == "with_mho"
            and (now - f.opened_at).total_seconds() > LONG_WAIT_THRESHOLD_SECONDS
        )

        return {
            "success": True,
            "message": "MHO dashboard stats retrieved successfully.",
            "data": {
                "patients_registered_today": registered_today,
                "checked_in_today":          checked_in_today,
                "waiting_for_nurse":         waiting_for_nurse,
                "active_visits":             active_visits,
                "completed_today":           completed_today,
                "new_patients_today":        new_count,
                "returning_patients_today":  returning_count,
                "avg_checkin_seconds":       avg_checkin_seconds,
                "long_waiting_count":        long_waiting_count,
            }
        }

    # ──────────────────────────────────────────────────────────
    # Accountability trail (Admin / investigation use)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_care_trail(health_file_id: int):
        """
        Returns every staff member who touched this health file and when,
        assembled from the AuditLog. Used to answer "who treated this
        patient, and in what order" during an incident review.
        """
        health_file = HealthFile.query.get(health_file_id)
        if not health_file:
            return {"success": False, "message": f"Health file with ID {health_file_id} not found.", "data": None}

        history = AuditService.get_entity_history("HealthFile", health_file_id)
        logs = history["data"]["logs"] if history["success"] else []

        trail = []
        for log in reversed(logs):  # oldest first
            user = User.query.get(log["user_id"]) if log["user_id"] else None
            trail.append({
                "action":    log["action"],
                "by_user_id": log["user_id"],
                "by_name":   user.full_name if user else "System",
                "at":        log["created_at"],
            })

        return {
            "success": True,
            "message": "Care trail retrieved successfully.",
            "data": {
                "health_file_id": health_file_id,
                "patient_id":     health_file.patient_id,
                "patient_name":   health_file.patient.full_name,
                "current_status": health_file.status,
                "trail":          trail,
            }
        }