# app/services/staff_attendance_service.py

from datetime import datetime, timezone, date as date_cls
from app.extensions import db
from app.models.staff_attendance import StaffAttendance
from app.models.user import User


class StaffAttendanceService:

    @staticmethod
    def clock_in(user_id: int, recorded_by: int = None):
        """
        Clocks a staff member in for today. recorded_by is None for
        self-clock-in, or the Nurse/Admin's user_id if recording on
        someone else's behalf.
        """
        user = User.query.get(user_id)
        if not user:
            return {"success": False, "message": f"User with ID {user_id} not found.", "data": None}

        today  = date_cls.today()
        record = StaffAttendance.query.filter_by(user_id=user_id, date=today).first()

        if record and record.clock_in:
            return {
                "success": False,
                "message": f"{user.full_name} already clocked in today at {record.clock_in.strftime('%H:%M')}.",
                "data": record.to_dict()
            }

        if record:
            # Record exists (e.g. was pre-marked) but no clock_in yet
            record.clock_in    = datetime.now(timezone.utc)
            record.status      = "present"
            record.recorded_by = recorded_by
        else:
            record = StaffAttendance(
                user_id     = user_id,
                date        = today,
                clock_in    = datetime.now(timezone.utc),
                status      = "present",
                recorded_by = recorded_by,
            )
            db.session.add(record)

        db.session.commit()
        return {"success": True, "message": f"{user.full_name} clocked in.", "data": record.to_dict()}

    @staticmethod
    def clock_out(user_id: int, recorded_by: int = None):
        user = User.query.get(user_id)
        if not user:
            return {"success": False, "message": f"User with ID {user_id} not found.", "data": None}

        today  = date_cls.today()
        record = StaffAttendance.query.filter_by(user_id=user_id, date=today).first()

        if not record or not record.clock_in:
            return {"success": False, "message": f"{user.full_name} has not clocked in today.", "data": None}
        if record.clock_out:
            return {
                "success": False,
                "message": f"{user.full_name} already clocked out today at {record.clock_out.strftime('%H:%M')}.",
                "data": record.to_dict()
            }

        record.clock_out = datetime.now(timezone.utc)
        if recorded_by:
            record.recorded_by = recorded_by
        db.session.commit()

        return {
            "success": True,
            "message": f"{user.full_name} clocked out. Hours worked: {record.hours_worked}.",
            "data": record.to_dict()
        }

    @staticmethod
    def mark_status(user_id: int, target_date: str, status: str, recorded_by: int, notes: str = None):
        """
        Nurse/Admin marks a staff member absent, on leave, or half-day —
        for days with no clock-in/out at all. A mandatory action taken
        by someone else on the staff member's behalf, so recorded_by
        is always required here (unlike clock_in/out).
        """
        user = User.query.get(user_id)
        if not user:
            return {"success": False, "message": f"User with ID {user_id} not found.", "data": None}

        if status not in StaffAttendance.STATUSES:
            return {
                "success": False,
                "message": f"Invalid status. Valid options: {', '.join(StaffAttendance.STATUSES)}",
                "data": None
            }

        try:
            parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "message": "Invalid date format. Use YYYY-MM-DD.", "data": None}

        record = StaffAttendance.query.filter_by(user_id=user_id, date=parsed_date).first()
        if record:
            record.status      = status
            record.recorded_by = recorded_by
            record.notes       = (notes or "").strip() or record.notes
        else:
            record = StaffAttendance(
                user_id     = user_id,
                date        = parsed_date,
                status      = status,
                recorded_by = recorded_by,
                notes       = (notes or "").strip() or None,
            )
            db.session.add(record)

        db.session.commit()
        return {
            "success": True,
            "message": f"{user.full_name} marked '{status}' for {parsed_date.isoformat()}.",
            "data": record.to_dict()
        }

    @staticmethod
    def get_staff_attendance(user_id: int, date_from: str = None, date_to: str = None, page=1, per_page=30):
        user = User.query.get(user_id)
        if not user:
            return {"success": False, "message": f"User with ID {user_id} not found.", "data": None}

        query = StaffAttendance.query.filter_by(user_id=user_id)

        if date_from:
            try:
                query = query.filter(StaffAttendance.date >= datetime.strptime(date_from, "%Y-%m-%d").date())
            except ValueError:
                return {"success": False, "message": "Invalid 'date_from' format. Use YYYY-MM-DD.", "data": None}
        if date_to:
            try:
                query = query.filter(StaffAttendance.date <= datetime.strptime(date_to, "%Y-%m-%d").date())
            except ValueError:
                return {"success": False, "message": "Invalid 'date_to' format. Use YYYY-MM-DD.", "data": None}

        query = query.order_by(StaffAttendance.date.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"Attendance history for {user.full_name} retrieved.",
            "data": {
                "user_id":      user_id,
                "user_name":    user.full_name,
                "records":      [r.to_dict() for r in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }

    @staticmethod
    def get_daily_roster(target_date: str = None):
        """
        Everyone's attendance for a single day — who's in, who's out,
        who's absent. Defaults to today.
        """
        if target_date:
            try:
                parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                return {"success": False, "message": "Invalid date format. Use YYYY-MM-DD.", "data": None}
        else:
            parsed_date = date_cls.today()

        records = StaffAttendance.query.filter_by(date=parsed_date).order_by(
            StaffAttendance.clock_in.asc()
        ).all()

        return {
            "success": True,
            "message": f"{len(records)} attendance record(s) for {parsed_date.isoformat()}.",
            "data": {
                "date":    parsed_date.isoformat(),
                "records": [r.to_dict() for r in records],
            }
        }

    @staticmethod
    def get_all_attendance(page=1, per_page=30, status=None, date_from=None, date_to=None):
        query = StaffAttendance.query

        if status:
            query = query.filter(StaffAttendance.status == status)
        if date_from:
            try:
                query = query.filter(StaffAttendance.date >= datetime.strptime(date_from, "%Y-%m-%d").date())
            except ValueError:
                return {"success": False, "message": "Invalid 'date_from' format. Use YYYY-MM-DD.", "data": None}
        if date_to:
            try:
                query = query.filter(StaffAttendance.date <= datetime.strptime(date_to, "%Y-%m-%d").date())
            except ValueError:
                return {"success": False, "message": "Invalid 'date_to' format. Use YYYY-MM-DD.", "data": None}

        query = query.order_by(StaffAttendance.date.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": "Attendance records retrieved successfully.",
            "data": {
                "records":      [r.to_dict() for r in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }

    @staticmethod
    def update_attendance(attendance_id: int, data: dict):
        """Admin-only correction of a record (fix a clock-in typo, etc.)."""
        record = StaffAttendance.query.get(attendance_id)
        if not record:
            return {"success": False, "message": f"Attendance record with ID {attendance_id} not found.", "data": None}

        if "status" in data:
            if data["status"] not in StaffAttendance.STATUSES:
                return {
                    "success": False,
                    "message": f"Invalid status. Valid options: {', '.join(StaffAttendance.STATUSES)}",
                    "data": None
                }
            record.status = data["status"]

        for field in ["clock_in", "clock_out"]:
            if field in data:
                if data[field]:
                    try:
                        setattr(record, field, datetime.fromisoformat(data[field]))
                    except ValueError:
                        return {"success": False, "message": f"Invalid '{field}' format. Use ISO datetime.", "data": None}
                else:
                    setattr(record, field, None)

        if "notes" in data:
            record.notes = (data["notes"] or "").strip() or None

        db.session.commit()
        return {"success": True, "message": "Attendance record updated successfully.", "data": record.to_dict()}