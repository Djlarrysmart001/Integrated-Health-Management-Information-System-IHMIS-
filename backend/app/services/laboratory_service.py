# app/services/laboratory_service.py

from datetime import datetime, timezone
from app.extensions import db
from app.models.laboratory import LabTest, LabRequest, LabResult, lab_request_items
from app.models.consultation import Consultation
from app.models.patient import Patient
from app.services.health_file_service import HealthFileService


class LaboratoryService:

    # ──────────────────────────────────────────────────────────
    # Lab Test Catalogue
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_all_lab_tests(search=None, category=None):
        """Returns the catalogue of all available lab tests."""
        query = LabTest.query.filter_by(is_active=True)

        if search:
            query = query.filter(
                LabTest.name.ilike(f"%{search}%")
            )
        if category:
            query = query.filter(
                LabTest.category.ilike(f"%{category}%")
            )

        tests = query.order_by(LabTest.category.asc(), LabTest.name.asc()).all()

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

        test = LabTest(
            name             = data["name"].strip(),
            category         = data.get("category", "General").strip(),
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

    # ──────────────────────────────────────────────────────────
    # Lab Requests
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_all_requests(page=1, per_page=20, status=None,
                          patient_id=None, priority=None):
        """Returns paginated lab requests."""
        query = LabRequest.query

        if status:
            query = query.filter(LabRequest.status == status)
        if patient_id:
            query = query.filter(LabRequest.patient_id == patient_id)
        if priority:
            query = query.filter(LabRequest.priority == priority)

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
        Returns all pending lab requests.
        This is the lab technician's work queue.
        """
        pagination = LabRequest.query.filter(
            LabRequest.status.in_(["pending", "sample_collected", "in_progress"])
        ).order_by(
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

        data            = lab_request.to_dict()
        data["results"] = [r.to_dict() for r in lab_request.results]

        return {
            "success": True,
            "message": "Lab request retrieved successfully.",
            "data": data
        }

    @staticmethod
    def raise_lab_request(data: dict, requested_by: int):
        """
        Doctor raises a lab request during a consultation.

        Required fields:
            consultation_id
            test_ids: list of lab test IDs

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

        # Validate test IDs
        test_ids = data.get("test_ids", [])
        if not test_ids:
            return {
                "success": False,
                "message": "At least one test ID is required in 'test_ids'.",
                "data": None
            }

        # Validate each test exists
        tests = []
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
            new_value   = {"consultation_id": data["consultation_id"], "tests": len(tests), "priority": priority}
        )
        # ───────────────────────────────────────────────────────

        # ── Move the health file into the Lab queue ─────────────
        # Non-fatal: if this consultation isn't tied to a health file
        # (e.g. legacy data) or the file isn't currently with the
        # Doctor for some reason, the lab request itself still stands.
        if consultation.health_file_id:
            HealthFileService.forward_to_lab(consultation.health_file_id, requested_by)
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"Lab request raised with {len(tests)} test(s). Priority: {priority}.",
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
        One result entry per test in the request.

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

        # Get the test IDs in this request
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

            # Check if result already exists for this test
            existing = LabResult.query.filter_by(
                lab_request_id=request_id,
                lab_test_id=test_id
            ).first()

            if existing:
                # Update existing result
                existing.result_value    = str(result_data["result_value"])
                existing.unit            = result_data.get("unit") or existing.unit
                existing.reference_range = result_data.get("reference_range") or existing.reference_range
                existing.interpretation  = result_data.get("interpretation") or existing.interpretation
                existing.remarks         = result_data.get("remarks") or existing.remarks
                existing.performed_by    = performed_by
                existing.result_date     = now
                recorded.append(existing)
            else:
                # Create new result
                result = LabResult(
                    lab_request_id  = request_id,
                    lab_test_id     = test_id,
                    patient_id      = lab_request.patient_id,
                    result_value    = str(result_data["result_value"]),
                    unit            = result_data.get("unit"),
                    reference_range = result_data.get("reference_range"),
                    interpretation  = result_data.get("interpretation"),
                    remarks         = result_data.get("remarks"),
                    performed_by    = performed_by,
                    result_date     = now,
                    created_at      = now,
                )
                db.session.add(result)
                recorded.append(result)

        # Update request status to completed
        lab_request.status = "completed"
        db.session.commit()

        # ── Send the health file back to the Doctor ─────────────
        consultation = Consultation.query.get(lab_request.consultation_id)
        if consultation and consultation.health_file_id:
            HealthFileService.return_from_lab(consultation.health_file_id, performed_by)
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"{len(recorded)} result(s) recorded. Request marked as completed.",
            "data": {
                "lab_request_id": request_id,
                "results":        [r.to_dict() for r in recorded]
            }
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
                "requests":     [r.to_dict() for r in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }