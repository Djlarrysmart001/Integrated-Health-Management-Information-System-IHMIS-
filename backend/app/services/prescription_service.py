# app/services/prescription_service.py

from datetime import datetime, timezone
from app.extensions import db
from app.models.prescription import Prescription, PrescriptionItem
from app.models.consultation import Consultation
from app.models.patient import Patient
from app.models.pharmacy import Drug, DrugInventory
from app.models.drug_transaction import DrugTransaction
from app.services.health_file_service import HealthFileService


class PrescriptionService:

    @staticmethod
    def get_all_prescriptions(page=1, per_page=20, patient_id=None,
                               status=None, consultation_id=None):
        query = Prescription.query

        if patient_id:
            query = query.filter(Prescription.patient_id == patient_id)
        if status:
            query = query.filter(Prescription.status == status)
        if consultation_id:
            query = query.filter(Prescription.consultation_id == consultation_id)

        query = query.order_by(Prescription.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": "Prescriptions retrieved successfully.",
            "data": {
                "prescriptions": [p.to_dict() for p in pagination.items],
                "total":         pagination.total,
                "pages":         pagination.pages,
                "current_page":  page,
                "per_page":      per_page,
                "has_next":      pagination.has_next,
                "has_prev":      pagination.has_prev,
            }
        }

    @staticmethod
    def get_prescription_by_id(prescription_id: int):
        prescription = Prescription.query.get(prescription_id)
        if not prescription:
            return {"success": False, "message": f"Prescription with ID {prescription_id} not found.", "data": None}
        return {"success": True, "message": "Prescription retrieved successfully.", "data": prescription.to_dict()}

    @staticmethod
    def get_pending_prescriptions(page=1, per_page=20):
        pagination = Prescription.query.filter(
            Prescription.status.in_(["pending", "partially_dispensed"])
        ).order_by(Prescription.created_at.asc()).paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"{pagination.total} prescription(s) pending dispensing.",
            "data": {
                "prescriptions": [p.to_dict() for p in pagination.items],
                "total":         pagination.total,
                "pages":         pagination.pages,
                "current_page":  page,
            }
        }

    @staticmethod
    def write_prescription(data: dict, prescribed_by: int):
        consultation = Consultation.query.get(data.get("consultation_id"))
        if not consultation:
            return {"success": False, "message": f"Consultation with ID {data.get('consultation_id')} not found.", "data": None}

        if consultation.status == "closed":
            return {"success": False, "message": "Cannot write prescription for a closed consultation.", "data": None}

        items = data.get("items", [])
        if not items:
            return {"success": False, "message": "At least one drug item is required.", "data": None}

        # ── Import here (not at module top) to avoid a circular import
        # with pharmacy_service, which itself imports from prescription
        # models. ──────────────────────────────────────────────────────
        from app.services.pharmacy_service import PharmacyService

        validated_items       = []
        newly_created_drugs   = []  # names of drugs auto-created this call, for the response message

        for i, item in enumerate(items):
            drug = None

            if item.get("drug_id"):
                # Existing catalogue path — unchanged behaviour.
                drug = Drug.query.get(item["drug_id"])
                if not drug:
                    return {"success": False, "message": f"Drug with ID {item['drug_id']} not found.", "data": None}
                if not drug.is_active:
                    return {"success": False, "message": f"Drug '{drug.name}' is not active.", "data": None}

            elif item.get("drug_name"):
                # Doctor typed a name that wasn't picked from the catalogue.
                # Matches an existing drug by name if one exists, otherwise
                # creates it immediately (active, but flagged
                # is_pending_setup) so the prescription can still go
                # through — Pharmacy fills in proper category/unit/stock
                # afterward.
                result = PharmacyService.find_or_create_by_name(item["drug_name"])
                if not result["success"]:
                    return {"success": False, "message": f"Item {i+1}: {result['message']}", "data": None}
                drug = result["data"]
                if result.get("created"):
                    newly_created_drugs.append(drug.name)

            else:
                return {"success": False, "message": f"Item {i+1}: either 'drug_id' or 'drug_name' is required.", "data": None}

            validated_items.append((drug, item))

        prescription = Prescription(
            consultation_id = data["consultation_id"],
            patient_id      = consultation.patient_id,
            prescribed_by   = prescribed_by,
            status          = "pending",
            notes           = (data.get("notes") or "").strip() or None,
        )
        db.session.add(prescription)
        db.session.flush()

        for drug, item in validated_items:
            prescription_item = PrescriptionItem(
                prescription_id = prescription.id,
                drug_id         = drug.id,
                dosage          = (item.get("dosage") or "").strip() or None,
                frequency       = (item.get("frequency") or "").strip() or None,
                duration        = (item.get("duration") or "").strip() or None,
                quantity        = item.get("quantity", 1),
                instructions    = (item.get("instructions") or "").strip() or None,
                is_dispensed    = False,
            )
            db.session.add(prescription_item)

        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "CREATE_PRESCRIPTION",
            entity_type = "Prescription",
            entity_id   = prescription.id,
            user_id     = prescribed_by,
            new_value   = {
                "consultation_id":      data["consultation_id"],
                "items":                len(validated_items),
                "new_drugs_created":    newly_created_drugs,
            }
        )
        # ───────────────────────────────────────────────────────

        # ── Move the health file into the Pharmacy queue ────────
        if consultation.health_file_id:
            HealthFileService.forward_to_pharmacy(consultation.health_file_id, prescribed_by)
        # ───────────────────────────────────────────────────────

        message = f"Prescription written with {len(validated_items)} drug(s)."
        if newly_created_drugs:
            message += f" {len(newly_created_drugs)} new drug(s) added to the catalogue, pending Pharmacy setup: {', '.join(newly_created_drugs)}."

        return {"success": True, "message": message, "data": prescription.to_dict()}

    @staticmethod
    def dispense_prescription(prescription_id: int, dispensed_by: int):
        prescription = Prescription.query.get(prescription_id)
        if not prescription:
            return {"success": False, "message": f"Prescription with ID {prescription_id} not found.", "data": None}
        if prescription.status == "dispensed":
            return {"success": False, "message": "This prescription has already been fully dispensed.", "data": None}
        if prescription.status == "cancelled":
            return {"success": False, "message": "Cannot dispense a cancelled prescription.", "data": None}

        for item in prescription.items:
            if item.is_dispensed:
                continue
            drug = Drug.query.get(item.drug_id)
            if drug.total_stock < item.quantity:
                return {
                    "success": False,
                    "message": f"Insufficient stock for '{drug.name}'. Required: {item.quantity}, Available: {drug.total_stock}",
                    "data": None
                }

        now             = datetime.now(timezone.utc)
        dispensed_count = 0
        touched_batches = {}

        for item in prescription.items:
            if item.is_dispensed:
                continue

            remaining_to_deduct = item.quantity
            batches = DrugInventory.query.filter_by(
                drug_id=item.drug_id
            ).filter(
                DrugInventory.quantity_in_stock > 0
            ).order_by(DrugInventory.received_at.asc()).all()

            for batch in batches:
                if remaining_to_deduct <= 0:
                    break
                deduct = min(batch.quantity_in_stock, remaining_to_deduct)
                batch.quantity_in_stock -= deduct
                remaining_to_deduct     -= deduct

                db.session.flush()
                drug = Drug.query.get(item.drug_id)
                transaction = DrugTransaction(
                    drug_id          = item.drug_id,
                    batch_id         = batch.id,
                    transaction_type = "dispensed",
                    quantity_change  = -deduct,
                    balance_after    = drug.total_stock,
                    reference_type   = "PrescriptionItem",
                    reference_id     = item.id,
                    reason           = f"Dispensed against prescription #{prescription.id}",
                    performed_by     = dispensed_by,
                )
                db.session.add(transaction)

                touched_batches[item.drug_id] = (drug, batch)

            item.is_dispensed = True
            item.dispensed_at = now
            item.dispensed_by = dispensed_by
            dispensed_count  += 1

        prescription.status     = "dispensed"
        prescription.updated_at = now
        db.session.commit()

        from app.services.pharmacy_service import PharmacyService
        for drug, batch in touched_batches.values():
            PharmacyService._alert_if_low_stock(drug, batch)

        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "DISPENSE_PRESCRIPTION",
            entity_type = "Prescription",
            entity_id   = prescription_id,
            user_id     = dispensed_by,
            new_value   = {"status": "dispensed", "items_dispensed": dispensed_count}
        )

        consultation = Consultation.query.get(prescription.consultation_id)
        if consultation and consultation.health_file_id:
            other_pending = Prescription.query.filter(
                Prescription.consultation_id == prescription.consultation_id,
                Prescription.id != prescription.id,
                Prescription.status.in_(["pending", "partially_dispensed"])
            ).count()
            if other_pending == 0:
                HealthFileService.close_health_file(consultation.health_file_id, dispensed_by)

        return {
            "success": True,
            "message": f"Prescription dispensed successfully. {dispensed_count} drug(s) issued.",
            "data": prescription.to_dict()
        }

    @staticmethod
    def cancel_prescription(prescription_id: int, cancelled_by: int = None):
        prescription = Prescription.query.get(prescription_id)
        if not prescription:
            return {"success": False, "message": f"Prescription with ID {prescription_id} not found.", "data": None}
        if prescription.status != "pending":
            return {
                "success": False,
                "message": f"Only pending prescriptions can be cancelled. Current status: {prescription.status}",
                "data": None
            }

        prescription.status = "cancelled"
        db.session.commit()

        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "CANCEL_PRESCRIPTION",
            entity_type = "Prescription",
            entity_id   = prescription_id,
            user_id     = cancelled_by,
            new_value   = {"status": "cancelled"}
        )

        return {"success": True, "message": "Prescription cancelled successfully.", "data": prescription.to_dict()}

    @staticmethod
    def get_patient_prescriptions(patient_id: int, page=1, per_page=10):
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "message": f"Patient with ID {patient_id} not found.", "data": None}

        pagination = Prescription.query.filter_by(
            patient_id=patient_id
        ).order_by(Prescription.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"Prescriptions for {patient.full_name} retrieved.",
            "data": {
                "patient_id":    patient_id,
                "patient_name":  patient.full_name,
                "prescriptions": [p.to_dict() for p in pagination.items],
                "total":         pagination.total,
                "pages":         pagination.pages,
                "current_page":  page,
            }
        }