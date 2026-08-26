# app/services/laboratory_service.py

from datetime import datetime, timezone
from app.extensions import db
from app.models.laboratory import LabTest, LabTestCategory, LabRequest, LabResult, lab_request_items
from app.models.consultation import Consultation
from app.models.patient import Patient
from app.services.health_file_service import HealthFileService

VALID_INTERPRETATIONS = ["normal", "low", "high", "critical"]


class LaboratoryService:

    # ──────────────────────────────────────────────────────────
    # Categories
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _find_or_create_category(name: str):
        """
        Case-insensitive find-or-create, shared by every path that assigns
        a test to a category (single add, bulk add, edit, and the
        auto-create-on-request fallback) so "Haematology" and "haematology"
        never end up as two different rows.
        """
        clean = (name or "Uncategorized").strip() or "Uncategorized"
        category = LabTestCategory.query.filter(LabTestCategory.name.ilike(clean)).first()
        if not category:
            category = LabTestCategory(name=clean)
            db.session.add(category)
            db.session.flush()  # assigns category.id without committing yet
        return category

    @staticmethod
    def get_all_categories():
        """Returns every category with how many active tests sit under it —
        this is what the Doctor's Category dropdown will be populated from."""
        categories = LabTestCategory.query.order_by(LabTestCategory.name.asc()).all()
        return {
            "success": True,
            "message": f"{len(categories)} categor{'y' if len(categories)==1 else 'ies'} found.",
            "data": [c.to_dict(include_test_count=True) for c in categories]
        }

    # ──────────────────────────────────────────────────────────
    # Lab Test Catalogue
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_all_lab_tests(search=None, category=None, category_id=None, pending_setup_only=False):
        """Returns the catalogue of all available lab tests."""
        query = LabTest.query.filter_by(is_active=True).outerjoin(
            LabTestCategory, LabTest.category_id == LabTestCategory.id
        )

        if search:
            query = query.filter(
                LabTest.name.ilike(f"%{search}%")
            )
        if category_id:
            query = query.filter(LabTest.category_id == category_id)
        elif category:
            query = query.filter(
                LabTestCategory.name.ilike(f"%{category}%")
            )
        if pending_setup_only:
            query = query.filter(LabTest.is_pending_setup.is_(True))

        tests = query.order_by(LabTestCategory.name.asc(), LabTest.name.asc()).all()

        return {
            "success": True,
            "message": f"{len(tests)} lab test(s) found.",
            "data": [t.to_dict() for t in tests]
        }

    @staticmethod
    def create_lab_test(data: dict):
        """Admin adds a new test to the catalogue."""
        if not data.get("name"):
            return {
                "success": False,
                "message": "'name' is required.",
                "data": None
            }

        existing = LabTest.query.filter_by(name=data["name"]).first()
        if existing:
            return {
                "success": False,
                "message": f"Lab test '{data['name']}' already exists.",
                "data": None
            }

        category = LaboratoryService._find_or_create_category(data.get("category") or "General")

        test = LabTest(
            name             = data["name"].strip(),
            category_id      = category.id,
            normal_range     = (data.get("normal_range") or "").strip() or None,
            unit             = (data.get("unit") or "").strip() or None,
            turnaround_hours = data.get("turnaround_hours", 24),
            is_active        = True,
        )
        db.session.add(test)
        db.session.commit()

        return {
            "success": True,
            "message": f"Lab test '{test.name}' added to catalogue.",
            "data": test.to_dict()
        }

    @staticmethod
    def bulk_create_lab_tests(category: str, names: list, defaults: dict = None):
        """
        Adds many tests to the catalogue under one category in a single call,
        e.g. category="Haematology", names=["Full Blood Count (FBC)", "Haemoglobin (Hb)", ...].
        Existing tests (case-insensitive match on name, across the whole
        catalogue — not just this category, since a test can only belong to
        one category) are skipped rather than duplicated or errored on, so
        this is safe to re-run if a list is pasted in twice or overlaps
        with what's already there.
        """
        if not category or not category.strip():
            return {"success": False, "message": "'category' is required.", "data": None}
        if not names:
            return {"success": False, "message": "At least one test name is required.", "data": None}

        defaults = defaults or {}
        category_row = LaboratoryService._find_or_create_category(category)
        created, skipped = [], []

        for raw_name in names:
            name = (raw_name or "").strip()
            if not name:
                continue
            existing = LabTest.query.filter(LabTest.name.ilike(name)).first()
            if existing:
                skipped.append(name)
                continue
            test = LabTest(
                name             = name,
                category_id      = category_row.id,
                normal_range     = defaults.get("normal_range"),
                unit             = defaults.get("unit"),
                turnaround_hours = defaults.get("turnaround_hours", 24),
                is_active        = True,
            )
            db.session.add(test)
            created.append(test)

        db.session.commit()

        message = f"{len(created)} test(s) added under '{category_row.name}'."
        if skipped:
            message += f" {len(skipped)} already existed elsewhere in the catalogue and were skipped: {', '.join(skipped)}."

        return {
            "success": True,
            "message": message,
            "data": {
                "created": [t.to_dict() for t in created],
                "skipped": skipped,
            }
        }

    @staticmethod
    def update_lab_test(test_id: int, data: dict):
        """
        Admin (or Lab, if you choose to grant it) fills in the missing
        details on a test that was auto-created via find_or_create_test_by_name
        (is_pending_setup=True), or edits an existing catalogue entry.
        Clears is_pending_setup once normal_range and unit are both set.
        """
        test = LabTest.query.get(test_id)
        if not test:
            return {"success": False, "message": f"Lab test with ID {test_id} not found.", "data": None}

        if "name" in data and data["name"]:
            test.name = data["name"].strip()
        if "category" in data and data["category"]:
            test.category_id = LaboratoryService._find_or_create_category(data["category"]).id
        if "normal_range" in data:
            test.normal_range = (data.get("normal_range") or "").strip() or None
        if "unit" in data:
            test.unit = (data.get("unit") or "").strip() or None
        if "turnaround_hours" in data and data["turnaround_hours"]:
            test.turnaround_hours = data["turnaround_hours"]

        if test.is_pending_setup and test.normal_range and test.unit:
            test.is_pending_setup = False

        db.session.commit()
        return {
            "success": True,
            "message": f"Lab test '{test.name}' updated.",
            "data": test.to_dict()
        }

    @staticmethod
    def find_or_create_test_by_name(name: str):
        """
        Used only when a Doctor requests a test by typed name instead of
        picking a test_id from the catalogue (test not found there).
        Mirrors PharmacyService.find_or_create_by_name exactly.

        - If a test with this name (case-insensitive) already exists,
          it's reused as-is — no duplicate is created.
        - Otherwise, a brand-new LabTest row is created immediately as
          is_active=True (so the request can go through right away) but
          flagged is_pending_setup=True, so Lab's dashboard can surface it
          as "needs setup" — category, normal_range, unit, and
          turnaround_hours still need to be filled in manually.

        Returns the raw LabTest ORM object (not to_dict()) in "data",
        since the caller (raise_lab_request) needs it directly to attach
        to the LabRequest.
        """
        if not name or not name.strip():
            return {"success": False, "message": "Test name is required.", "data": None, "created": False}

        clean_name = name.strip()
        existing = LabTest.query.filter(LabTest.name.ilike(clean_name)).first()
        if existing:
            return {
                "success": True,
                "message": f"Matched existing test '{existing.name}'.",
                "data": existing,
                "created": False,
            }

        uncategorized = LaboratoryService._find_or_create_category("Uncategorized")

        test = LabTest(
            name             = clean_name,
            category_id      = uncategorized.id,
            normal_range     = None,
            unit             = None,
            turnaround_hours = 24,
            is_active        = True,
            is_pending_setup = True,
        )
        db.session.add(test)
        db.session.commit()

        return {
            "success": True,
            "message": f"New test '{test.name}' created — pending Lab setup.",
            "data": test,
            "created": True,
        }

    # ──────────────────────────────────────────────────────────
    # Lab Requests
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_all_requests(page=1, per_page=20, status=None,
                          patient_id=None, priority=None, search=None):
        """Returns paginated lab requests."""
        query = LabRequest.query

        if status:
            query = query.filter(LabRequest.status == status)
        if patient_id:
            query = query.filter(LabRequest.patient_id == patient_id)
        if priority:
            query = query.filter(LabRequest.priority == priority)

        if search:
            like = f"%{search.strip()}%"
            query = query.join(Patient, LabRequest.patient_id == Patient.id).filter(
                db.or_(
                    Patient.full_name.ilike(like),
                    LabRequest.tests.any(LabTest.name.ilike(like)),
                )
            )

        query = query.order_by(LabRequest.created_at.desc())
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return {
            "success": True,
            "message": "Lab requests retrieved successfully.",
            "data": {
                "requests":     [r.to_dict() for r in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
                "per_page":     per_page,
                "has_next":     pagination.has_next,
                "has_prev":     pagination.has_prev,
            }
        }

    @staticmethod
    def get_pending_requests(page=1, per_page=20):
        """
        Returns all pending lab requests, ordered so the lab tech sees the
        most clinically urgent work first (STAT > urgent > routine), and
        oldest-first within the same priority tier.
        This is the lab technician's work queue.
        """
        priority_order = db.case(
            (LabRequest.priority == "stat", 0),
            (LabRequest.priority == "urgent", 1),
            else_=2,
        )

        pagination = LabRequest.query.filter(
            LabRequest.status.in_(["pending", "sample_collected", "in_progress"])
        ).order_by(
            priority_order.asc(),
            LabRequest.created_at.asc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"{pagination.total} pending lab request(s).",
            "data": {
                "requests":     [r.to_dict() for r in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }

    @staticmethod
    def get_request_by_id(request_id: int):
        """Returns a single lab request with all results."""
        lab_request = LabRequest.query.get(request_id)
        if not lab_request:
            return {
                "success": False,
                "message": f"Lab request with ID {request_id} not found.",
                "data": None
            }

        return {
            "success": True,
            "message": "Lab request retrieved successfully.",
            "data": lab_request.to_dict(include_results=True)
        }

    @staticmethod
    def raise_lab_request(data: dict, requested_by: int):
        """
        Doctor raises a lab request during a consultation.

        Required fields (at least one of):
            test_ids: list of existing catalogue lab test IDs
            test_names: list of typed test names not in the catalogue —
                each one is matched to an existing test by name, or
                created as a new pending-setup test so the request can
                still go through (mirrors write_prescription's drug_name
                fallback exactly).

        Required fields:
            consultation_id

        Optional fields:
            priority (routine/urgent/stat)
            notes
        """

        # Validate consultation
        consultation = Consultation.query.get(data.get("consultation_id"))
        if not consultation:
            return {
                "success": False,
                "message": f"Consultation with ID {data.get('consultation_id')} not found.",
                "data": None
            }

        if consultation.status == "closed":
            return {
                "success": False,
                "message": "Cannot raise lab request for a closed consultation.",
                "data": None
            }

        test_ids   = data.get("test_ids") or []
        test_names = data.get("test_names") or []

        if not test_ids and not test_names:
            return {
                "success": False,
                "message": "At least one test is required, via 'test_ids' or 'test_names'.",
                "data": None
            }

        tests                = []
        newly_created_tests   = []  # names of tests auto-created this call, for the response message

        for test_id in test_ids:
            test = LabTest.query.get(test_id)
            if not test:
                return {
                    "success": False,
                    "message": f"Lab test with ID {test_id} not found.",
                    "data": None
                }
            if not test.is_active:
                return {
                    "success": False,
                    "message": f"Lab test '{test.name}' is not currently active.",
                    "data": None
                }
            tests.append(test)

        for name in test_names:
            result = LaboratoryService.find_or_create_test_by_name(name)
            if not result["success"]:
                return {"success": False, "message": result["message"], "data": None}
            tests.append(result["data"])
            if result.get("created"):
                newly_created_tests.append(result["data"].name)

        # Validate priority
        priority = data.get("priority", "routine")
        if priority not in ["routine", "urgent", "stat"]:
            return {
                "success": False,
                "message": "priority must be 'routine', 'urgent', or 'stat'.",
                "data": None
            }

        # Create lab request
        lab_request = LabRequest(
            consultation_id = data["consultation_id"],
            patient_id      = consultation.patient_id,
            requested_by    = requested_by,
            priority        = priority,
            status          = "pending",
            notes           = (data.get("notes") or "").strip() or None,
        )

        # Add tests to request
        for test in tests:
            lab_request.tests.append(test)

        db.session.add(lab_request)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "RAISE_LAB_REQUEST",
            entity_type = "LabRequest",
            entity_id   = lab_request.id,
            user_id     = requested_by,
            new_value   = {
                "consultation_id":    data["consultation_id"],
                "tests":              len(tests),
                "priority":           priority,
                "new_tests_created":  newly_created_tests,
            }
        )
        # ───────────────────────────────────────────────────────

        # ── Move the health file into the Lab queue ─────────────
        if consultation.health_file_id:
            HealthFileService.forward_to_lab(consultation.health_file_id, requested_by)
        # ───────────────────────────────────────────────────────

        message = f"Lab request raised with {len(tests)} test(s). Priority: {priority}."
        if newly_created_tests:
            message += f" {len(newly_created_tests)} new test(s) added to the catalogue, pending Lab setup: {', '.join(newly_created_tests)}."

        return {
            "success": True,
            "message": message,
            "data": lab_request.to_dict()
        }

    @staticmethod
    def update_request_status(request_id: int, new_status: str):
        """
        Updates the status of a lab request.

        Valid transitions:
            pending → sample_collected
            sample_collected → in_progress
            in_progress → completed
            any → cancelled
        """
        lab_request = LabRequest.query.get(request_id)
        if not lab_request:
            return {
                "success": False,
                "message": f"Lab request with ID {request_id} not found.",
                "data": None
            }

        valid_statuses = [
            "pending", "sample_collected",
            "in_progress", "completed", "cancelled"
        ]

        if new_status not in valid_statuses:
            return {
                "success": False,
                "message": f"Invalid status. Valid options: {', '.join(valid_statuses)}",
                "data": None
            }

        allowed_transitions = {
            "pending":          ["sample_collected", "cancelled"],
            "sample_collected": ["in_progress", "cancelled"],
            "in_progress":      ["completed", "cancelled"],
            "completed":        [],
            "cancelled":        [],
        }

        if new_status not in allowed_transitions[lab_request.status]:
            return {
                "success": False,
                "message": f"Cannot change status from '{lab_request.status}' to '{new_status}'.",
                "data": None
            }

        lab_request.status = new_status
        db.session.commit()

        return {
            "success": True,
            "message": f"Lab request status updated to '{new_status}'.",
            "data": lab_request.to_dict()
        }

    # ──────────────────────────────────────────────────────────
    # Lab Results
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def record_results(request_id: int, results: list, performed_by: int):
        """
        Lab technician records results for a lab request.
        One result entry per test in the request — a request can carry
        several tests (e.g. Full Blood Count + Malaria Test), so the
        caller must send one array entry per lab_test_id on the request.
        Partial submissions are allowed: the request only moves to
        'completed' once every test on it has a recorded result.

        Each result requires:
            lab_test_id, result_value

        Optional per result:
            unit, reference_range, interpretation, remarks
        """
        lab_request = LabRequest.query.get(request_id)
        if not lab_request:
            return {
                "success": False,
                "message": f"Lab request with ID {request_id} not found.",
                "data": None
            }

        if lab_request.status == "cancelled":
            return {
                "success": False,
                "message": "Cannot record results for a cancelled request.",
                "data": None
            }

        if not results:
            return {
                "success": False,
                "message": "At least one result is required.",
                "data": None
            }

        request_test_ids = [t.id for t in lab_request.tests]

        recorded = []
        now      = datetime.now(timezone.utc)

        for result_data in results:
            test_id = result_data.get("lab_test_id")

            if not test_id:
                return {
                    "success": False,
                    "message": "'lab_test_id' is required for each result.",
                    "data": None
                }

            if test_id not in request_test_ids:
                return {
                    "success": False,
                    "message": f"Test ID {test_id} is not part of this lab request.",
                    "data": None
                }

            if not result_data.get("result_value"):
                return {
                    "success": False,
                    "message": f"'result_value' is required for test ID {test_id}.",
                    "data": None
                }

            interpretation = result_data.get("interpretation") or None
            if interpretation and interpretation not in VALID_INTERPRETATIONS:
                return {
                    "success": False,
                    "message": f"'interpretation' must be one of: {', '.join(VALID_INTERPRETATIONS)}.",
                    "data": None
                }

            existing = LabResult.query.filter_by(
                lab_request_id=request_id,
                lab_test_id=test_id
            ).first()

            if existing:
                existing.result_value    = str(result_data["result_value"])
                existing.unit            = result_data.get("unit") or existing.unit
                existing.reference_range = result_data.get("reference_range") or existing.reference_range
                existing.interpretation  = interpretation or existing.interpretation
                existing.remarks         = result_data.get("remarks") or existing.remarks
                existing.performed_by    = performed_by
                existing.result_date     = now
                recorded.append(existing)
            else:
                result = LabResult(
                    lab_request_id  = request_id,
                    lab_test_id     = test_id,
                    patient_id      = lab_request.patient_id,
                    result_value    = str(result_data["result_value"]),
                    unit            = result_data.get("unit"),
                    reference_range = result_data.get("reference_range"),
                    interpretation  = interpretation,
                    remarks         = result_data.get("remarks"),
                    performed_by    = performed_by,
                    result_date     = now,
                    created_at      = now,
                )
                db.session.add(result)
                recorded.append(result)

        db.session.flush()

        # Only mark the request completed once every test on it has a
        # result — a lab request can bundle several tests, and previously
        # this flipped to 'completed' after any single POST even if other
        # tests on the same request were still outstanding.
        results_count = LabResult.query.filter_by(lab_request_id=request_id).count()
        if results_count >= len(request_test_ids):
            lab_request.status = "completed"

        db.session.commit()

        if lab_request.status == "completed":
            consultation = Consultation.query.get(lab_request.consultation_id)
            if consultation and consultation.health_file_id:
                HealthFileService.return_from_lab(consultation.health_file_id, performed_by)

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "RECORD_LAB_RESULTS",
            entity_type = "LabRequest",
            entity_id   = lab_request.id,
            user_id     = performed_by,
            new_value   = {
                "results_submitted": len(recorded),
                "request_status":    lab_request.status,
            }
        )
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"{len(recorded)} result(s) recorded. Request status: {lab_request.status}.",
            "data": {
                "lab_request_id": request_id,
                "status":         lab_request.status,
                "results":        [r.to_dict() for r in recorded]
            }
        }

    @staticmethod
    def send_results_to_doctor(request_id: int, sent_by: int):
        """
        Explicit hand-off: Lab confirms results are final and notifies the
        requesting Doctor. The health file itself is already moved back to
        the Doctor's queue automatically once every test on the request has
        a result (see record_results -> HealthFileService.return_from_lab);
        this adds the notification + a visible "sent" record that was
        previously missing, so Lab has a clear, explicit action to take and
        Doctor gets an actual alert rather than having to notice the file
        moved.
        """
        lab_request = LabRequest.query.get(request_id)
        if not lab_request:
            return {"success": False, "message": f"Lab request with ID {request_id} not found.", "data": None}

        if lab_request.status != "completed":
            return {
                "success": False,
                "message": "All tests on this request must have results recorded before it can be sent to the doctor.",
                "data": None,
            }

        if lab_request.sent_to_doctor:
            return {
                "success": False,
                "message": "Results for this request were already sent to the doctor.",
                "data": lab_request.to_dict(),
            }

        now = datetime.now(timezone.utc)
        lab_request.sent_to_doctor    = True
        lab_request.sent_to_doctor_at = now
        lab_request.sent_to_doctor_by = sent_by
        db.session.commit()

        # ── Notify the requesting doctor ─────────────────────────
        try:
            from app.services.notification_service import NotificationService
            test_names = ", ".join(t.name for t in lab_request.tests)
            NotificationService.create_notification(
                recipient_id      = lab_request.requested_by,
                title             = "Lab results ready",
                message           = f"Results for {test_names} are ready for review.",
                notification_type = "lab_result",
                reference_id      = lab_request.id,
                reference_type    = "lab_request",
            )
        except Exception:
            # Non-critical — the send action itself (sent_to_doctor flag,
            # already committed above) must not be undone just because the
            # notification failed (e.g. recipient account deleted).
            pass
        # ───────────────────────────────────────────────────────

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "SEND_LAB_RESULTS_TO_DOCTOR",
            entity_type = "LabRequest",
            entity_id   = lab_request.id,
            user_id     = sent_by,
            new_value   = {"sent_to_doctor_at": now.isoformat()},
        )
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": "Results sent to the requesting doctor.",
            "data": lab_request.to_dict()
        }

    @staticmethod
    def get_patient_lab_history(patient_id: int, page=1, per_page=10):
        """Returns all lab requests for a patient."""
        patient = Patient.query.get(patient_id)
        if not patient:
            return {
                "success": False,
                "message": f"Patient with ID {patient_id} not found.",
                "data": None
            }

        pagination = LabRequest.query.filter_by(
            patient_id=patient_id
        ).order_by(
            LabRequest.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"Lab history for {patient.full_name} retrieved.",
            "data": {
                "patient_id":   patient_id,
                "patient_name": patient.full_name,
                "requests":     [r.to_dict(include_results=True) for r in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }