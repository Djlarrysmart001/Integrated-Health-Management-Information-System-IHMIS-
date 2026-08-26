"""
One-off seeding script: creates/updates the initial drug catalogue with
500 units of stock each.

Run once from the backend project root (same folder as run.py), inside
your venv. The Flask dev server does NOT need to be running -- this
script talks to the database directly, not over HTTP:

    python seed_drugs.py

Safe to re-run: existing drugs (matched by name, case-insensitive) are
updated in place rather than duplicated -- this also properly
categorizes "Artemether + Lumefantrine", which already exists as an
auto-created, pending-setup drug from an earlier doctor-typed
prescription, and clears its is_pending_setup flag. Re-running adds
another 500-unit batch each time, so only run it as many times as you
actually want stock added.
"""

from datetime import date, timedelta
import os

# Load .env explicitly from this script's own folder, before importing
# anything from `app` -- load_dotenv()'s default directory-search
# sometimes resolves differently for `python script.py` vs `flask run`,
# which is what caused the earlier "root@localhost, no password" error:
# without this, the real DATABASE_URL never made it into the process.
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from app import create_app
from app.extensions import db
from app.models.pharmacy import Drug, DrugInventory

DRUGS = [
    {"name": "Paracetamol",                 "category": "Analgesic",     "unit": "tablet"},
    {"name": "Ibuprofen",                   "category": "Analgesic",     "unit": "tablet"},
    {"name": "Amoxicillin",                 "category": "Antibiotic",    "unit": "capsule"},
    {"name": "Metronidazole",               "category": "Antibiotic",    "unit": "tablet"},
    {"name": "Artemether + Lumefantrine",   "category": "Antimalarial",  "unit": "tablet"},
    {"name": "Cetirizine",                  "category": "Antihistamine", "unit": "tablet"},
    {"name": "Omeprazole",                  "category": "Antacid",       "unit": "capsule"},
    {"name": "Oral Rehydration Salts (ORS)","category": "Rehydration",   "unit": "sachet"},
    {"name": "Clotrimazole Cream",          "category": "Antifungal",    "unit": "tube"},
    {"name": "Ceftriaxone",                 "category": "Antibiotic",    "unit": "vial"},
]

STOCK_QTY = 500
EXPIRY    = date.today() + timedelta(days=730)  # 2 years out
MIN_LEVEL = 30

app = create_app()

with app.app_context():
    for entry in DRUGS:
        drug = Drug.query.filter(Drug.name.ilike(entry["name"])).first()

        if drug:
            drug.category        = entry["category"]
            drug.unit             = entry["unit"]
            drug.is_active        = True
            drug.is_pending_setup = False
            print(f"Updated existing drug: {drug.name}")
        else:
            drug = Drug(
                name             = entry["name"],
                category         = entry["category"],
                unit             = entry["unit"],
                is_active        = True,
                is_pending_setup = False,
            )
            db.session.add(drug)
            db.session.flush()  # need drug.id before creating the batch
            print(f"Created new drug: {drug.name}")

        batch = DrugInventory(
            drug_id             = drug.id,
            batch_number        = f"SEED-{drug.id}-{date.today().isoformat()}",
            quantity_in_stock   = STOCK_QTY,
            minimum_stock_level = MIN_LEVEL,
            expiry_date         = EXPIRY,
            supplied_by         = "Initial catalogue seed",
        )
        db.session.add(batch)

    db.session.commit()
    print(f"\nDone — {len(DRUGS)} drug(s) processed, {STOCK_QTY} unit(s) added to each.")