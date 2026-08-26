# app/models/pharmacy.py

from datetime import datetime, timezone
from app.extensions import db


class Drug(db.Model):
    """
    The drug formulary — catalogue of all drugs available at the health center.
    """
    __tablename__ = "drugs"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(150), nullable=False, index=True)  # Generic name
    brand_name  = db.Column(db.String(150), nullable=True)
    category    = db.Column(db.String(80), nullable=True)   # e.g. Antibiotic, Analgesic
    unit        = db.Column(db.String(30), nullable=True)   # e.g. tablet, vial, sachet
    description = db.Column(db.Text, nullable=True)
    is_active   = db.Column(db.Boolean, default=True)

    # Set True only when a Doctor prescribes a drug name that wasn't in the
    # catalogue — the drug is created immediately (active) so the
    # prescription can still go through, but this flag tells Pharmacy the
    # entry still needs a real category/unit/stock before it's a properly
    # set-up catalogue item. Cleared by Pharmacy/Admin via update_drug.
    is_pending_setup = db.Column(db.Boolean, default=False, nullable=False)

    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # ── relationships ──────────────────────────────────────────
    inventory_batches  = db.relationship("DrugInventory", backref="drug",
                                         lazy="dynamic", cascade="all, delete-orphan")
    prescription_items = db.relationship("PrescriptionItem", backref="drug", lazy="dynamic")

    @property
    def total_stock(self):
        """Sum all non-expired batches for current stock level."""
        from datetime import date
        today = date.today()
        return sum(
            b.quantity_in_stock
            for b in self.inventory_batches
            if b.expiry_date is None or b.expiry_date >= today
        )

    def to_dict(self):
        return {
            "id":                self.id,
            "name":              self.name,
            "brand_name":        self.brand_name,
            "category":          self.category,
            "unit":              self.unit,
            "description":       self.description,
            "is_active":         self.is_active,
            "is_pending_setup":  self.is_pending_setup,
            "total_stock":       self.total_stock,
        }


class DrugInventory(db.Model):
    """
    Tracks stock per drug batch. Each time drugs are received,
    a new inventory record is created with its own expiry date and batch number.
    """
    __tablename__ = "drug_inventory"

    id                  = db.Column(db.Integer, primary_key=True)
    drug_id             = db.Column(db.Integer, db.ForeignKey("drugs.id", ondelete="CASCADE"),
                                    nullable=False, index=True)
    batch_number        = db.Column(db.String(60), nullable=True)
    quantity_in_stock   = db.Column(db.Integer, default=0, nullable=False)
    minimum_stock_level = db.Column(db.Integer, default=10, nullable=False)  # Alert threshold
    cost_price          = db.Column(db.Numeric(10, 2), nullable=True)
    selling_price       = db.Column(db.Numeric(10, 2), nullable=True)
    expiry_date         = db.Column(db.Date, nullable=True)
    supplied_by         = db.Column(db.String(120), nullable=True)
    received_at         = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    received_by         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    @property
    def is_low_stock(self):
        return self.quantity_in_stock <= self.minimum_stock_level

    @property
    def is_expired(self):
        from datetime import date
        return self.expiry_date is not None and self.expiry_date < date.today()

    def to_dict(self):
        return {
            "id":                  self.id,
            "drug_id":             self.drug_id,
            "batch_number":        self.batch_number,
            "quantity_in_stock":   self.quantity_in_stock,
            "minimum_stock_level": self.minimum_stock_level,
            "is_low_stock":        self.is_low_stock,
            "is_expired":          self.is_expired,
            "expiry_date":         self.expiry_date.isoformat() if self.expiry_date else None,
            "supplied_by":         self.supplied_by,
            "received_at":         self.received_at.isoformat(),
        }