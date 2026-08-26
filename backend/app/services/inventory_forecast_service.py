# app/services/inventory_forecast_service.py

from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from app.extensions import db
from app.models.pharmacy import Drug
from app.models.drug_transaction import DrugTransaction
from app.models.ai_recommendation import AIRecommendation
from app.utils.constants import Roles


class InventoryForecastService:
    """
    Rule-based (not machine-learned) drug reorder forecasting.

    Algorithm, confirmed with the project supervisor's expected scope:
      1. For each active drug, sum quantity dispensed over the last
         LOOKBACK_DAYS from the DrugTransaction ledger.
      2. avg_daily_use = total dispensed / LOOKBACK_DAYS.
      3. projected_days_remaining = current total_stock / avg_daily_use.
      4. If projected_days_remaining <= REORDER_THRESHOLD_DAYS, an
         AIRecommendation is created (or refreshed) for Pharmacist review.
      5. If a drug's outstanding pending recommendation is no longer
         warranted (e.g. stock was replenished since the last run), that
         recommendation is auto-dismissed by the system.

    This NEVER writes to Drug/DrugInventory directly — it only ever
    creates/updates rows in ai_recommendations. A Pharmacist accepting a
    recommendation just records that acknowledgement; placing an actual
    supplier order remains a separate, human action.
    """

    LOOKBACK_DAYS          = 7
    REORDER_THRESHOLD_DAYS = 7

    # ──────────────────────────────────────────────────────────
    # Forecast a single drug (pure calculation, no writes)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _compute_forecast_for_drug(drug: Drug) -> dict:
        since = datetime.now(timezone.utc) - timedelta(
            days=InventoryForecastService.LOOKBACK_DAYS
        )

        # quantity_change is stored negative for "dispensed" transactions
        # (see DrugTransaction docstring), so this sum comes back <= 0.
        #
        # NOTE: MySQL's SUM() over an Integer column returns a DECIMAL,
        # which pymysql decodes as decimal.Decimal in Python. That type
        # cannot be serialized by the JSON column's default encoder, so
        # every numeric value derived from this query must be cast to a
        # plain float immediately -- before it ever lands in `payload`.
        dispensed_sum = db.session.query(
            func.sum(DrugTransaction.quantity_change)
        ).filter(
            DrugTransaction.drug_id == drug.id,
            DrugTransaction.transaction_type == "dispensed",
            DrugTransaction.created_at >= since,
        ).scalar() or 0

        total_dispensed = abs(float(dispensed_sum))
        avg_daily_use = round(
            total_dispensed / InventoryForecastService.LOOKBACK_DAYS, 2
        )
        current_stock = drug.total_stock

        if avg_daily_use > 0:
            projected_days_remaining = round(current_stock / avg_daily_use, 1)
        else:
            # No dispensing activity in the lookback window — nothing to
            # project from, so we deliberately do NOT recommend a reorder
            # based on silence. Reordering off a lack of data would be
            # noise, not signal.
            projected_days_remaining = None

        reorder_recommended = (
            projected_days_remaining is not None
            and projected_days_remaining <= InventoryForecastService.REORDER_THRESHOLD_DAYS
        )

        return {
            "drug_id":                  drug.id,
            "drug_name":                drug.name,
            "current_stock":            current_stock,
            "avg_daily_use":            avg_daily_use,
            "lookback_days":            InventoryForecastService.LOOKBACK_DAYS,
            "projected_days_remaining": projected_days_remaining,
            "reorder_threshold_days":   InventoryForecastService.REORDER_THRESHOLD_DAYS,
            "reorder_recommended":      reorder_recommended,
        }

    # ──────────────────────────────────────────────────────────
    # Run the forecast across the whole catalogue (writes recommendations)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def run_forecast(triggered_by: int) -> dict:
        """Runs the forecast for every active drug. Triggered on-demand
        by a Pharmacist or Admin (no scheduler in this phase)."""
        from app.services.audit_service import AuditService

        active_drugs = Drug.query.filter_by(is_active=True).all()
        generated = []
        auto_dismissed = []

        for drug in active_drugs:
            forecast = InventoryForecastService._compute_forecast_for_drug(drug)

            existing_pending = AIRecommendation.query.filter_by(
                recommendation_type="INVENTORY_FORECAST",
                source_entity_type="Drug",
                source_entity_id=drug.id,
                status="pending",
            ).first()

            if forecast["reorder_recommended"]:
                if existing_pending:
                    existing_pending.payload = forecast
                    existing_pending.generated_at = datetime.now(timezone.utc)
                    db.session.commit()
                    rec = existing_pending
                else:
                    rec = AIRecommendation(
                        recommendation_type="INVENTORY_FORECAST",
                        source_entity_type="Drug",
                        source_entity_id=drug.id,
                        target_role=Roles.PHARMACIST,
                        payload=forecast,
                        status="pending",
                    )
                    db.session.add(rec)
                    db.session.commit()

                generated.append(rec.to_dict())

                AuditService.log(
                    action="GENERATE_AI_RECOMMENDATION",
                    entity_type="AIRecommendation",
                    entity_id=rec.id,
                    user_id=triggered_by,
                    new_value=forecast,
                )

            elif existing_pending:
                # Stock position improved since the last run (e.g. new
                # stock was received) — the old recommendation no longer
                # applies, so the system resolves it automatically.
                existing_pending.status = "dismissed"
                existing_pending.reviewed_at = datetime.now(timezone.utc)
                # NOTE: reviewed_by is deliberately left None here — this
                # is a system auto-dismissal, not a human decision. The
                # frontend can use "reviewed_by is None" to show these
                # differently from Pharmacist-dismissed ones.
                db.session.commit()
                auto_dismissed.append(existing_pending.to_dict())

                AuditService.log(
                    action="AUTO_DISMISS_AI_RECOMMENDATION",
                    entity_type="AIRecommendation",
                    entity_id=existing_pending.id,
                    user_id=None,
                    old_value={"status": "pending"},
                    new_value={
                        "status": "dismissed",
                        "reason": "Stock position no longer warrants reorder.",
                    },
                )

        return {
            "success": True,
            "message": (
                f"Forecast run complete: {len(generated)} recommendation(s) "
                f"active, {len(auto_dismissed)} auto-resolved."
            ),
            "data": {
                "generated":      generated,
                "auto_dismissed": auto_dismissed,
                "drugs_checked":  len(active_drugs),
            },
        }

    # ──────────────────────────────────────────────────────────
    # Read pending recommendations (for Pharmacist's dashboard)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_active_recommendations(page=1, per_page=20):
        query = AIRecommendation.query.filter_by(
            recommendation_type="INVENTORY_FORECAST", status="pending"
        ).order_by(AIRecommendation.generated_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": "Inventory forecast recommendations retrieved.",
            "data": {
                "recommendations": [r.to_dict() for r in pagination.items],
                "total":           pagination.total,
                "pages":           pagination.pages,
                "current_page":    page,
                "per_page":        per_page,
            },
        }

    # ──────────────────────────────────────────────────────────
    # Accept / dismiss a recommendation (human decision)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def review_recommendation(recommendation_id: int, decision: str, reviewed_by: int):
        """
        decision must be "accepted" or "dismissed". Accepting only records
        that Pharmacy acknowledged the recommendation — it does NOT place
        a supplier order or touch DrugInventory. That stays a deliberate
        separate action so the AI layer never writes to real records.
        """
        from app.services.audit_service import AuditService

        if decision not in ("accepted", "dismissed"):
            return {
                "success": False,
                "message": "decision must be 'accepted' or 'dismissed'.",
                "data": None,
            }

        rec = AIRecommendation.query.get(recommendation_id)
        if not rec:
            return {
                "success": False,
                "message": f"Recommendation {recommendation_id} not found.",
                "data": None,
            }
        if rec.status != "pending":
            return {
                "success": False,
                "message": f"Recommendation already {rec.status}.",
                "data": None,
            }

        rec.status = decision
        rec.reviewed_by = reviewed_by
        rec.reviewed_at = datetime.now(timezone.utc)
        db.session.commit()

        AuditService.log(
            action=f"{decision.upper()}_AI_RECOMMENDATION",
            entity_type="AIRecommendation",
            entity_id=rec.id,
            user_id=reviewed_by,
            new_value={"status": decision},
        )

        return {
            "success": True,
            "message": f"Recommendation {decision}.",
            "data": rec.to_dict(),
        }