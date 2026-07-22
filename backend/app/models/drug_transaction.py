# app/models/drug_transaction.py

from datetime import datetime, timezone
from app.extensions import db


class DrugTransaction(db.Model):
    """
    Append-only ledger of every stock movement for every drug.
    Complements DrugInventory (which only holds the *current* count)
    by recording *why* the count changed, by whom, and what the
    running balance was immediately after — the pharmacy equivalent
    of the HealthFile audit trail.

    transaction_type:
        received   -> new stock brought in (receive_stock)
        dispensed  -> given to a patient against a prescription
        adjustment -> manual correction (e.g. physical count mismatch)
        disposal   -> written off (expired / damaged / spoiled)
    """
    __tablename__ = "drug_transactions"

    TRANSACTION_TYPES = ("received", "dispensed", "adjustment", "disposal")

    id               = db.Column(db.Integer, primary_key=True)
    drug_id          = db.Column(db.Integer, db.ForeignKey("drugs.id", ondelete="CASCADE"),
                                 nullable=False, index=True)
    batch_id         = db.Column(db.Integer, db.ForeignKey("drug_inventory.id", ondelete="SET NULL"),
                                 nullable=True, index=True)
    transaction_type = db.Column(db.Enum(*TRANSACTION_TYPES), nullable=False, index=True)
    quantity_change  = db.Column(db.Integer, nullable=False)   # signed: +received, -dispensed/-disposal
    balance_after    = db.Column(db.Integer, nullable=False)   # drug.total_stock right after this txn
    reference_type   = db.Column(db.String(50), nullable=True)  # e.g. "PrescriptionItem"
    reference_id     = db.Column(db.Integer, nullable=True)
    reason           = db.Column(db.Text, nullable=True)
    performed_by     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # ── relationships ──────────────────────────────────────────
    drug  = db.relationship("Drug", backref=db.backref(
        "transactions", lazy="dynamic", cascade="all, delete-orphan", order_by="DrugTransaction.created_at.desc()"
    ))
    batch = db.relationship("DrugInventory")
    user  = db.relationship("User", foreign_keys=[performed_by])

    def to_dict(self):
        return {
            "id":               self.id,
            "drug_id":          self.drug_id,
            "drug_name":        self.drug.name if self.drug else None,
            "batch_id":         self.batch_id,
            "transaction_type": self.transaction_type,
            "quantity_change":  self.quantity_change,
            "balance_after":    self.balance_after,
            "reference_type":   self.reference_type,
            "reference_id":     self.reference_id,
            "reason":           self.reason,
            "performed_by":     self.performed_by,
            "performed_by_name": self.user.full_name if self.user else None,
            "created_at":       self.created_at.isoformat(),
        }