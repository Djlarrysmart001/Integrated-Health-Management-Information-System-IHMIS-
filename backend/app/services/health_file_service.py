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
    "admitted":      Roles.NURSE,
}

# Friendlier, action-specific wording than a generic "status changed" message.
ACTION_MESSAGES = {
    "FORWARD_TO_NURSE":    "New patient waiting: {patient_name} needs vitals/triage.",
    "FORWARD_TO_DOCTOR":   "Patient ready for consultation: {patient_name}.",
    "FORWARD_TO_LAB":      "New lab test request for {patient_name}.",
    "RETURN_FROM_LAB":     "Lab result ready for review: {patient_name}.",
    "FORWARD_TO_PHARMACY": "New prescription to dispense for {patient_name}.",
    "ADMIT_PATIENT":       "{patient_name} has been admitted — ongoing monitoring needed.",
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

                # with_doctor and with_nurse are each assigned to a SPECIFIC
                # person, not a whole role -- everyone else on that team
                # broadcasting "patient ready" for a file they were never
                # forwarded is exactly the leak that motivated
                # assigned_doctor_id / assigned_nurse_id in the first place.
                # Every other status (Lab/Pharmacy/admitted) still
                # broadcasts, since those queues are genuinely shared
                # across the whole role.
                if to_status == "with_doctor" and health_file.assigned_doctor_id:
                    NotificationService.create_notification(
                        recipient_id      = health_file.assigned_doctor_id,
                        title             = "Patient Flow Update",
                        message           = message,
                        notification_type = "patient_flow",
                    )
                elif to_status == "with_nurse" and health_file.assigned_nurse_id:
                    NotificationService.create_notification(
                        recipient_id      = health_file.assigned_nurse_id,
                        title             = "Patient Flow Update",
                        message           = message,
                        notification_type = "patient_flow",
                    )
                else:
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
    def forward_to_nurse(health_file_id: int, user_id: int, nurse_id: int = None):
        """
        nurse_id is REQUIRED -- a clinic with more than one nurse on duty
        needs the MHO to pick which specific nurse a file goes to, exactly
        the same reasoning as forward_to_doctor's doctor_id. Unlike the
        Doctor assignment, there's no loop-back stage for Nurse, so this
        is always a first-time assignment -- there's no "already assigned,
        skip the picker" branch to worry about.
        """
        health_file = HealthFile.query.get(health_file_id)
        if not health_file:
            return {"success": False, "message": f"Health file with ID {health_file_id} not found.", "data": None}

        if not nurse_id:
            return {
                "success": False,
                "message": "'nurse_id' is required -- choose an on-duty nurse to forward to.",
                "data": health_file.to_dict()
            }

        nurse = User.query.get(nurse_id)
        if not nurse or not nurse.has_role(Roles.NURSE):
            return {"success": False, "message": f"User {nurse_id} is not a Nurse.", "data": None}
        if not nurse.is_active:
            return {"success": False, "message": f"{nurse.full_name} is not an active account.", "data": None}
        if not nurse.is_on_duty:
            return {"success": False, "message": f"{nurse.full_name} is not currently on duty.", "data": None}

        health_file.assigned_nurse_id = nurse_id
        # Committed together with the status change below in _transition,
        # so a failed transition never leaves an orphaned assignment.

        return HealthFileService._transition(
            health_file_id, ["with_mho"], "with_nurse", user_id, "FORWARD_TO_NURSE"
        )

    # ──────────────────────────────────────────────────────────
    # Nurse -> Doctor
    # Two paths land here: the normal "with_nurse" triage handoff, and
    # the "admitted" loop-back once a Nurse has finished a round of
    # inpatient monitoring and wants the Doctor to review again (see
    # admit_patient below). Same destination, same vitals requirement
    # either way -- a fresh vitals reading should exist before either
    # handoff reaches the Doctor.
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def forward_to_doctor(health_file_id: int, user_id: int, doctor_id: int = None):
        """
        doctor_id is only REQUIRED the first time a file reaches a doctor
        (i.e. when assigned_doctor_id is still unset). On the admitted
        loop-back, the file already has an assigned_doctor_id from the
        original forward -- we deliberately keep that same doctor rather
        than asking the Nurse to pick again, so a patient's admission
        review always goes back to the doctor who admitted them.
        """
        health_file = HealthFile.query.get(health_file_id)
        if not health_file:
            return {"success": False, "message": f"Health file with ID {health_file_id} not found.", "data": None}

        if not health_file.vital_signs:
            return {
                "success": False,
                "message": "Cannot forward to Doctor before recording vital signs.",
                "data": health_file.to_dict()
            }

        if health_file.assigned_doctor_id is None:
            # First-time forward -- a specific on-duty doctor must be chosen.
            if not doctor_id:
                return {
                    "success": False,
                    "message": "'doctor_id' is required -- choose an on-duty doctor to forward to.",
                    "data": health_file.to_dict()
                }

            doctor = User.query.get(doctor_id)
            if not doctor or not doctor.has_role(Roles.DOCTOR):
                return {"success": False, "message": f"User {doctor_id} is not a Doctor.", "data": None}
            if not doctor.is_active:
                return {"success": False, "message": f"Dr. {doctor.full_name} is not an active account.", "data": None}
            if not doctor.is_on_duty:
                return {"success": False, "message": f"Dr. {doctor.full_name} is not currently on duty.", "data": None}

            health_file.assigned_doctor_id = doctor_id
            # Committed together with the status change below in _transition,
            # so a failed transition never leaves an orphaned assignment.

        return HealthFileService._transition(
            health_file_id, ["with_nurse", "admitted"], "with_doctor", user_id, "FORWARD_TO_DOCTOR"
        )

    # ──────────────────────────────────────────────────────────
    # Admin-only escape hatch: reassign a file already sitting
    # with_doctor to a different (or, for orphaned/legacy records, a
    # first-time) doctor. Two real situations this covers:
    #   1. A doctor goes off-duty mid-shift with patients still on
    #      their queue and someone else needs to pick them up.
    #   2. A file somehow ended up with_doctor but assigned_doctor_id
    #      is still null (e.g. a bad request during testing/migration)
    #      and is now stuck -- forward_to_doctor can't touch it because
    #      its status guard only accepts with_nurse/admitted.
    # Deliberately does NOT change status -- the file is already
    # with_doctor and stays there, this only changes WHO it's with.
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def reassign_doctor(health_file_id: int, new_doctor_id: int, admin_user_id: int):
        health_file = HealthFile.query.get(health_file_id)
        if not health_file:
            return {"success": False, "message": f"Health file with ID {health_file_id} not found.", "data": None}

        if health_file.status != "with_doctor":
            return {
                "success": False,
                "message": f"Health file is currently '{health_file.status}' -- reassignment only applies to files 'with_doctor'.",
                "data": health_file.to_dict()
            }

        doctor = User.query.get(new_doctor_id)
        if not doctor or not doctor.has_role(Roles.DOCTOR):
            return {"success": False, "message": f"User {new_doctor_id} is not a Doctor.", "data": None}
        if not doctor.is_active:
            return {"success": False, "message": f"Dr. {doctor.full_name} is not an active account.", "data": None}
        if not doctor.is_on_duty:
            return {"success": False, "message": f"Dr. {doctor.full_name} is not currently on duty.", "data": None}

        old_doctor_id = health_file.assigned_doctor_id
        health_file.assigned_doctor_id = new_doctor_id
        db.session.commit()

        AuditService.log(
            action      = "REASSIGN_DOCTOR",
            entity_type = "HealthFile",
            entity_id   = health_file.id,
            user_id     = admin_user_id,
            old_value   = {"assigned_doctor_id": old_doctor_id},
            new_value   = {"assigned_doctor_id": new_doctor_id}
        )

        try:
            from app.services.notification_service import NotificationService
            patient_name = health_file.patient.full_name if health_file.patient else "A patient"
            NotificationService.create_notification(
                recipient_id      = new_doctor_id,
                title             = "Patient Flow Update",
                message           = f"Patient ready for consultation: {patient_name}.",
                notification_type = "patient_flow",
            )
        except Exception:
            pass

        return {
            "success": True,
            "message": f"Reassigned to Dr. {doctor.full_name}.",
            "data": health_file.to_dict()
        }

    # ──────────────────────────────────────────────────────────
    # Admin-only escape hatch: reassign a file already sitting
    # with_nurse to a different on-duty nurse. Covers a Nurse going
    # off-duty mid-shift with patients still on their queue. Mirrors
    # reassign_doctor exactly -- deliberately does NOT change status,
    # the file is already with_nurse and stays there, this only
    # changes WHO it's with.
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def reassign_nurse(health_file_id: int, new_nurse_id: int, admin_user_id: int):
        health_file = HealthFile.query.get(health_file_id)
        if not health_file:
            return {"success": False, "message": f"Health file with ID {health_file_id} not found.", "data": None}

        if health_file.status != "with_nurse":
            return {
                "success": False,
                "message": f"Health file is currently '{health_file.status}' -- reassignment only applies to files 'with_nurse'.",
                "data": health_file.to_dict()
            }

        nurse = User.query.get(new_nurse_id)
        if not nurse or not nurse.has_role(Roles.NURSE):
            return {"success": False, "message": f"User {new_nurse_id} is not a Nurse.", "data": None}
        if not nurse.is_active:
            return {"success": False, "message": f"{nurse.full_name} is not an active account.", "data": None}
        if not nurse.is_on_duty:
            return {"success": False, "message": f"{nurse.full_name} is not currently on duty.", "data": None}

        old_nurse_id = health_file.assigned_nurse_id
        health_file.assigned_nurse_id = new_nurse_id
        db.session.commit()

        AuditService.log(
            action      = "REASSIGN_NURSE",
            entity_type = "HealthFile",
            entity_id   = health_file.id,
            user_id     = admin_user_id,
            old_value   = {"assigned_nurse_id": old_nurse_id},
            new_value   = {"assigned_nurse_id": new_nurse_id}
        )

        try:
            from app.services.notification_service import NotificationService
            patient_name = health_file.patient.full_name if health_file.patient else "A patient"
            NotificationService.create_notification(
                recipient_id      = new_nurse_id,
                title             = "Patient Flow Update",
                message           = f"New patient waiting: {patient_name} needs vitals/triage.",
                notification_type = "patient_flow",
            )
        except Exception:
            pass

        return {
            "success": True,
            "message": f"Reassigned to {nurse.full_name}.",
            "data": health_file.to_dict()
        }

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
    # Doctor admits patient -> Admitted (inpatient monitoring begins)
    #
    # Unlike close_via_referral (patient leaves the clinic entirely),
    # admission does NOT end the clinic's involvement -- the patient
    # stays, under the Nurse's ongoing care. The file loops back to
    # with_doctor only once the Nurse forwards it again (see
    # forward_to_doctor above); it only reaches "closed" when the
    # Doctor explicitly discharges (see discharge_patient below).
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def admit_patient(health_file_id: int, user_id: int):
        return HealthFileService._transition(
            health_file_id, ["with_doctor"], "admitted", user_id, "ADMIT_PATIENT"
        )

    # ──────────────────────────────────────────────────────────
    # Doctor discharges -> Closed (ends an admission)
    #
    # Deliberately a DIFFERENT action from close_via_referral and
    # close_health_file, even though all three end at "closed" from
    # "with_doctor" -- keeping the audit action name distinct
    # ("DISCHARGE_PATIENT" vs "CLOSE_VIA_REFERRAL" vs "CLOSE_HEALTH_FILE")
    # means the care trail accurately reflects WHY a visit ended, not
    # just that it did. Per the agreed design, discharge only ever
    # happens from "with_doctor" -- i.e. only after the Nurse has
    # forwarded an admitted patient back for a final review. There is
    # deliberately no direct "admitted -> closed" path.
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def discharge_patient(health_file_id: int, user_id: int):
        return HealthFileService._transition(
            health_file_id, ["with_doctor"], "closed", user_id, "DISCHARGE_PATIENT"
        )

    # ──────────────────────────────────────────────────────────
    # Queues — one per role
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_queue(status: str, page=1, per_page=20, doctor_id: int = None, nurse_id: int = None):
        """
        doctor_id, when provided, scopes the with_doctor queue to files
        assigned to that specific doctor (see forward_to_doctor). Left
        as None for every other status, and for Admin viewing with_doctor
        -- Admin needs the unscoped, system-wide view for oversight.

        nurse_id works identically for the with_nurse queue (see
        forward_to_nurse) -- left as None for every other status, and
        for Admin/MHO viewing with_nurse, who need the unscoped,
        system-wide view (Admin for oversight, MHO to pick a nurse to
        forward to in the first place).
        """
        if status not in HealthFile.STATUSES:
            return {"success": False, "message": f"'{status}' is not a valid health file status.", "data": None}

        query = HealthFile.query.filter_by(status=status)
        if doctor_id is not None:
            query = query.filter(HealthFile.assigned_doctor_id == doctor_id)
        if nurse_id is not None:
            query = query.filter(HealthFile.assigned_nurse_id == nurse_id)

        pagination = query.order_by(
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

    # ──────────────────────────────────────────────────────────
    # "How many did I forward today/this week/this month" -- a per-role
    # work-log count, deliberately NOT based on HealthFile.status.
    #
    # Filtering by current status (e.g. status == 'with_doctor') would
    # UNDERCOUNT: if the Doctor has already acted on a file a Nurse forwarded
    # this morning (sent it to Lab, prescribed, closed it), that file is no
    # longer 'with_doctor' even though the Nurse's forward absolutely still
    # happened today. The only durable record of "who forwarded this, and
    # when" is the AuditLog entry _transition() writes on every handoff --
    # so that's what this counts, not the live queue snapshot.
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def count_forwards(action: str, user_id: int = None,
                        date_from=None, date_to=None) -> int:
        from app.models.audit_log import AuditLog

        query = AuditLog.query.filter(
            AuditLog.action == action,
            AuditLog.entity_type == "HealthFile",
        )
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if date_from:
            query = query.filter(AuditLog.created_at >= date_from)
        if date_to:
            query = query.filter(AuditLog.created_at < date_to)

        return query.count()