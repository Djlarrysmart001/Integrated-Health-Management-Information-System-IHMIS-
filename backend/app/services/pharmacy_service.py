# app/services/pharmacy_service.py

from datetime import datetime, timezone, date
from app.extensions import db
from app.models.pharmacy import Drug, DrugInventory
from app.models.drug_transaction import DrugTransaction
from app.models.prescription import Prescription, PrescriptionItem


class PharmacyService:

    # ──────────────────────────────────────────────────────────
    # Drug Catalogue
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_all_drugs(page=1, per_page=20, search=None,
                      category=None, is_active=None):
        """Returns paginated drug catalogue."""
        query = Drug.query

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Drug.name.ilike(search_term)) |
                (Drug.brand_name.ilike(search_term)) |
                (Drug.category.ilike(search_term))
            )
        if category:
            query = query.filter(Drug.category.ilike(f"%{category}%"))
        if is_active is not None:
            query = query.filter(Drug.is_active == is_active)

        query = query.order_by(Drug.name.asc())
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return {
            "success": True,
            "message": "Drugs retrieved successfully.",
            "data": {
                "drugs":        [d.to_dict() for d in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
                "per_page":     per_page,
                "has_next":     pagination.has_next,
                "has_prev":     pagination.has_prev,
            }
        }

    @staticmethod
    def get_drug_by_id(drug_id: int):
        """Returns a single drug with full inventory details."""
        drug = Drug.query.get(drug_id)
        if not drug:
            return {
                "success": False,
                "message": f"Drug with ID {drug_id} not found.",
                "data": None
            }

        data             = drug.to_dict()
        data["batches"]  = [b.to_dict() for b in drug.inventory_batches]

        return {
            "success": True,
            "message": "Drug retrieved successfully.",
            "data": data
        }

    @staticmethod
    def create_drug(data: dict):
        """
        Adds a new drug to the formulary.

        Required fields:
            name, unit

        Optional fields:
            brand_name, category, description
        """
        if not data.get("name"):
            return {
                "success": False,
                "message": "'name' is required.",
                "data": None
            }

        if not data.get("unit"):
            return {
                "success": False,
                "message": "'unit' is required (e.g. tablet, capsule, vial).",
                "data": None
            }

        # Check drug name uniqueness
        existing = Drug.query.filter(
            Drug.name.ilike(data["name"].strip())
        ).first()
        if existing:
            return {
                "success": False,
                "message": f"Drug '{data['name']}' already exists in the formulary.",
                "data": None
            }

        drug = Drug(
            name        = data["name"].strip(),
            brand_name  = (data.get("brand_name") or "").strip() or None,
            category    = data.get("category", "General").strip(),
            unit        = data["unit"].strip(),
            description = (data.get("description") or "").strip() or None,
            is_active   = True,
        )
        db.session.add(drug)
        db.session.commit()

        return {
            "success": True,
            "message": f"Drug '{drug.name}' added to formulary.",
            "data": drug.to_dict()
        }

    @staticmethod
    def update_drug(drug_id: int, data: dict):
        """Updates drug details."""
        drug = Drug.query.get(drug_id)
        if not drug:
            return {
                "success": False,
                "message": f"Drug with ID {drug_id} not found.",
                "data": None
            }

        if "name" in data:
            drug.name = data["name"].strip()
        if "brand_name" in data:
            drug.brand_name = data["brand_name"].strip() or None
        if "category" in data:
            drug.category = data["category"].strip()
        if "unit" in data:
            drug.unit = data["unit"].strip()
        if "description" in data:
            drug.description = data["description"].strip() or None
        if "is_active" in data:
            drug.is_active = bool(data["is_active"])

        db.session.commit()

        return {
            "success": True,
            "message": f"Drug '{drug.name}' updated successfully.",
            "data": drug.to_dict()
        }

    # ──────────────────────────────────────────────────────────
    # Drug Inventory
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def receive_stock(drug_id: int, data: dict, received_by: int):
        """
        Records receipt of new drug stock (a new batch).

        Required fields:
            quantity_in_stock, expiry_date

        Optional fields:
            batch_number, minimum_stock_level,
            cost_price, selling_price, supplied_by
        """
        drug = Drug.query.get(drug_id)
        if not drug:
            return {
                "success": False,
                "message": f"Drug with ID {drug_id} not found.",
                "data": None
            }

        if not data.get("quantity_in_stock"):
            return {
                "success": False,
                "message": "'quantity_in_stock' is required.",
                "data": None
            }

        if int(data["quantity_in_stock"]) <= 0:
            return {
                "success": False,
                "message": "'quantity_in_stock' must be greater than zero.",
                "data": None
            }

        # Parse expiry date
        expiry_date = None
        if data.get("expiry_date"):
            try:
                expiry_date = datetime.strptime(
                    data["expiry_date"], "%Y-%m-%d"
                ).date()
                if expiry_date <= date.today():
                    return {
                        "success": False,
                        "message": "Cannot receive expired stock.",
                        "data": None
                    }
            except ValueError:
                return {
                    "success": False,
                    "message": "Invalid expiry_date format. Use YYYY-MM-DD.",
                    "data": None
                }

        batch = DrugInventory(
            drug_id             = drug_id,
            batch_number        = (data.get("batch_number") or "").strip() or None,
            quantity_in_stock   = int(data["quantity_in_stock"]),
            minimum_stock_level = int(data.get("minimum_stock_level", 10)),
            cost_price          = data.get("cost_price"),
            selling_price       = data.get("selling_price"),
            expiry_date         = expiry_date,
            supplied_by         = (data.get("supplied_by") or "").strip() or None,
            received_at         = datetime.now(timezone.utc),
            received_by         = received_by,
        )

        db.session.add(batch)
        db.session.commit()

        # ── Ledger entry ──────────────────────────────────────
        transaction = DrugTransaction(
            drug_id          = drug_id,
            batch_id         = batch.id,
            transaction_type = "received",
            quantity_change  = int(data["quantity_in_stock"]),
            balance_after    = drug.total_stock,
            reference_type   = "DrugInventory",
            reference_id     = batch.id,
            reason           = (data.get("reason") or "").strip() or "Stock receipt",
            performed_by     = received_by,
        )
        db.session.add(transaction)
        db.session.commit()
        # ────────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"Stock received: {data['quantity_in_stock']} unit(s) of '{drug.name}'.",
            "data": {
                "drug":  drug.to_dict(),
                "batch": batch.to_dict()
            }
        }

    @staticmethod
    def adjust_stock(drug_id: int, batch_id: int, quantity_delta: int, reason: str, performed_by: int):
        """
        Manually corrects stock — for physical count reconciliation,
        or writing off expired/damaged stock (disposal).

        quantity_delta:
            negative -> removing stock (disposal / correction down)
            positive -> adding stock (correction up, e.g. found miscounted units)

        A reason is mandatory — this bypasses the normal receive/dispense
        flow, so there must always be a stated justification on record.
        """
        drug = Drug.query.get(drug_id)
        if not drug:
            return {"success": False, "message": f"Drug with ID {drug_id} not found.", "data": None}

        batch = DrugInventory.query.get(batch_id)
        if not batch or batch.drug_id != drug_id:
            return {"success": False, "message": f"Batch with ID {batch_id} not found for this drug.", "data": None}

        if not quantity_delta or quantity_delta == 0:
            return {"success": False, "message": "'quantity_delta' must be a non-zero integer.", "data": None}

        if not reason or not reason.strip():
            return {"success": False, "message": "A 'reason' is required for any manual stock adjustment.", "data": None}

        new_batch_quantity = batch.quantity_in_stock + quantity_delta
        if new_batch_quantity < 0:
            return {
                "success": False,
                "message": f"Cannot reduce batch below zero. Current: {batch.quantity_in_stock}, requested change: {quantity_delta}.",
                "data": None
            }

        batch.quantity_in_stock = new_batch_quantity
        db.session.commit()

        transaction_type = "disposal" if quantity_delta < 0 else "adjustment"
        transaction = DrugTransaction(
            drug_id          = drug_id,
            batch_id         = batch_id,
            transaction_type = transaction_type,
            quantity_change  = quantity_delta,
            balance_after    = drug.total_stock,
            reference_type   = "DrugInventory",
            reference_id     = batch_id,
            reason           = reason.strip(),
            performed_by     = performed_by,
        )
        db.session.add(transaction)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "ADJUST_DRUG_STOCK",
            entity_type = "DrugInventory",
            entity_id   = batch_id,
            user_id     = performed_by,
            old_value   = {"quantity_in_stock": new_batch_quantity - quantity_delta},
            new_value   = {"quantity_in_stock": new_batch_quantity, "reason": reason.strip()}
        )
        # ───────────────────────────────────────────────────────

        if quantity_delta < 0:
            PharmacyService._alert_if_low_stock(drug, batch)

        return {
            "success": True,
            "message": f"Stock adjusted by {quantity_delta:+d} unit(s) for '{drug.name}'.",
            "data": {
                "drug":        drug.to_dict(),
                "batch":       batch.to_dict(),
                "transaction": transaction.to_dict(),
            }
        }

    @staticmethod
    def _alert_if_low_stock(drug, batch):
        """
        Broadcasts a low-stock notification to Pharmacists + Admin the
        moment a batch crosses at-or-below its minimum_stock_level.
        Non-fatal: never blocks the stock movement that triggered it.
        """
        if not batch.is_low_stock:
            return
        try:
            from app.services.notification_service import NotificationService
            from app.utils.constants import Roles
            message = (
                f"{drug.name} is low: {batch.quantity_in_stock} unit(s) left "
                f"(threshold {batch.minimum_stock_level}, batch #{batch.id})."
            )
            NotificationService.broadcast_to_role(
                role_name=Roles.PHARMACIST, title="Low Stock Alert",
                message=message, notification_type="low_stock",
            )
            NotificationService.broadcast_to_role(
                role_name=Roles.ADMIN, title="Low Stock Alert",
                message=message, notification_type="low_stock",
            )
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────
    # Drug Transaction Ledger
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_drug_transactions(drug_id=None, transaction_type=None, page=1, per_page=20):
        """
        Returns the full stock-movement ledger — every receipt, dispense,
        adjustment, and disposal, in one place. Used for reconciliation
        and for tracing exactly why a drug's stock changed over time.
        """
        query = DrugTransaction.query

        if drug_id:
            query = query.filter(DrugTransaction.drug_id == drug_id)
        if transaction_type:
            if transaction_type not in DrugTransaction.TRANSACTION_TYPES:
                return {
                    "success": False,
                    "message": f"Invalid transaction_type. Valid options: {', '.join(DrugTransaction.TRANSACTION_TYPES)}",
                    "data": None
                }
            query = query.filter(DrugTransaction.transaction_type == transaction_type)

        query = query.order_by(DrugTransaction.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"{pagination.total} transaction(s) found.",
            "data": {
                "transactions": [t.to_dict() for t in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
                "per_page":     per_page,
            }
        }

    @staticmethod
    def get_inventory(page=1, per_page=20, low_stock_only=False,
                      expired_only=False):
        """
        Returns current inventory status.
        Can filter to show only low stock or expired items.
        """
        query = DrugInventory.query.join(Drug).filter(Drug.is_active == True)

        batches = query.order_by(DrugInventory.expiry_date.asc()).all()

        today = date.today()
        result_list = []

        for batch in batches:
            is_low     = batch.quantity_in_stock <= batch.minimum_stock_level
            is_expired = batch.expiry_date and batch.expiry_date < today

            if low_stock_only and not is_low:
                continue
            if expired_only and not is_expired:
                continue

            item = batch.to_dict()
            item["drug_name"]     = batch.drug.name
            item["drug_category"] = batch.drug.category
            item["unit"]          = batch.drug.unit
            result_list.append(item)

        # Paginate manually
        total    = len(result_list)
        start    = (page - 1) * per_page
        end      = start + per_page
        page_items = result_list[start:end]

        return {
            "success": True,
            "message": f"{total} inventory record(s) found.",
            "data": {
                "inventory":    page_items,
                "total":        total,
                "current_page": page,
                "per_page":     per_page,
            }
        }

    @staticmethod
    def get_low_stock_drugs():
        """
        Returns all drugs where any batch is at or below
        the minimum stock level. Used for alerts.
        """
        low_stock_batches = DrugInventory.query.filter(
            DrugInventory.quantity_in_stock <= DrugInventory.minimum_stock_level
        ).all()
        low_stock    = []
        seen_drug_ids = set()

        for batch in low_stock_batches:
            if batch.drug_id not in seen_drug_ids:
                drug = Drug.query.get(batch.drug_id)
                if drug and drug.is_active:
                    low_stock.append({
                        "drug_id":             drug.id,
                        "drug_name":           drug.name,
                        "category":            drug.category,
                        "unit":                drug.unit,
                        "total_stock":         drug.total_stock,
                        "minimum_stock_level": batch.minimum_stock_level,
                        "batch_number":        batch.batch_number,
                    })
                    seen_drug_ids.add(batch.drug_id)

        return {
            "success": True,
            "message": f"{len(low_stock)} drug(s) are low on stock.",
            "data": low_stock
        }

    @staticmethod
    def get_expiring_soon(days: int = 90):
        """
        Returns drugs expiring within the next N days.
        Default is 90 days.
        """
        from datetime import timedelta
        today      = date.today()
        threshold  = today + timedelta(days=days)

        batches = DrugInventory.query.filter(
            DrugInventory.expiry_date != None,
            DrugInventory.expiry_date <= threshold,
            DrugInventory.expiry_date >= today,
            DrugInventory.quantity_in_stock > 0
        ).order_by(DrugInventory.expiry_date.asc()).all()

        result = []
        for batch in batches:
            drug = Drug.query.get(batch.drug_id)
            if drug:
                days_left = (batch.expiry_date - today).days
                result.append({
                    "drug_id":      drug.id,
                    "drug_name":    drug.name,
                    "batch_number": batch.batch_number,
                    "expiry_date":  batch.expiry_date.isoformat(),
                    "days_to_expiry": days_left,
                    "quantity":     batch.quantity_in_stock,
                    "unit":         drug.unit,
                })

        return {
            "success": True,
            "message": f"{len(result)} batch(es) expiring within {days} days.",
            "data": result
        }

    # ──────────────────────────────────────────────────────────
    # Dispensation History
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_dispensation_history(page=1, per_page=20, drug_id=None):
        """
        Returns history of all dispensed prescription items.
        Used by pharmacists for reporting.
        """
        query = PrescriptionItem.query.filter_by(is_dispensed=True)

        if drug_id:
            query = query.filter(PrescriptionItem.drug_id == drug_id)

        query = query.order_by(PrescriptionItem.dispensed_at.desc())
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        history = []
        for item in pagination.items:
            drug = Drug.query.get(item.drug_id)
            history.append({
                "prescription_item_id": item.id,
                "prescription_id":      item.prescription_id,
                "drug_id":              item.drug_id,
                "drug_name":            drug.name if drug else "Unknown",
                "quantity":             item.quantity,
                "dosage":               item.dosage,
                "dispensed_at":         item.dispensed_at.isoformat() if item.dispensed_at else None,
                "dispensed_by":         item.dispensed_by,
            })

        return {
            "success": True,
            "message": "Dispensation history retrieved.",
            "data": {
                "history":      history,
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
                "per_page":     per_page,
            }
        }

    # ──────────────────────────────────────────────────────────
    # Pharmacy Dashboard Stats
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_pharmacy_stats():
        """Returns summary statistics for the pharmacy dashboard."""
        today = date.today()

        total_drugs       = Drug.query.filter_by(is_active=True).count()
        total_batches     = DrugInventory.query.count()
        low_stock_count   = DrugInventory.query.filter(
            DrugInventory.quantity_in_stock <= DrugInventory.minimum_stock_level
        ).count()
        expired_count     = DrugInventory.query.filter(
            DrugInventory.expiry_date != None,
            DrugInventory.expiry_date < today
        ).count()
        pending_prescriptions = Prescription.query.filter_by(
            status="pending"
        ).count()
        dispensed_today   = PrescriptionItem.query.filter(
            PrescriptionItem.is_dispensed == True,
            db.func.date(PrescriptionItem.dispensed_at) == today
        ).count()

        return {
            "success": True,
            "message": "Pharmacy statistics retrieved.",
            "data": {
                "total_drugs":            total_drugs,
                "total_batches":          total_batches,
                "low_stock_alerts":       low_stock_count,
                "expired_batches":        expired_count,
                "pending_prescriptions":  pending_prescriptions,
                "dispensed_today":        dispensed_today,
            }
        }