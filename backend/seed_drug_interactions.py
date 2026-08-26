"""
One-off seeding script: creates/updates the drug_interactions knowledge
base used by Clinical Decision Support (Doctor's prescription screen).

Run once from the backend project root, inside your venv, same as
seed_drugs.py. The Flask dev server does NOT need to be running:

    python seed_drug_interactions.py

Safe to re-run: existing pairs (matched by drug names, either order) are
updated in place rather than duplicated.

IMPORTANT — where this data comes from:
This is a small, illustrative set of well-documented drug-drug
interactions, NOT a comprehensive interaction database. Most pairs
involve drugs NOT currently in IHMIS's 10-item catalogue (Warfarin,
Diazepam, etc.) — a Doctor typing one of these names into a prescription
auto-creates a pending Drug entry (existing PharmacyService pattern), so
the check still fires correctly the moment two interacting drugs appear
together, even for drugs the Pharmacy hasn't stocked yet. This was a
deliberate design choice after checking IHMIS's actual 10 stocked drugs
against real interaction data and finding no major interactions among
them alone -- a genuinely good sign for that formulary's safety, not a
gap in this script.

Sources cited per entry in `source`. General pairs not tied to a single
paper are cited as "Standard clinical pharmacology reference" -- meaning
established prescribing knowledge (e.g. BNF-style teaching), not a
specific study, and should be verified against a licensed drug reference
before any real clinical use.
"""

import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from app import create_app
from app.extensions import db
from app.models.pharmacy import Drug
from app.models.drug_interaction import DrugInteraction

INTERACTIONS = [
    {"a": "Warfarin", "b": "Ibuprofen", "severity": "major",
     "description": "Increased bleeding risk -- NSAIDs potentiate warfarin's anticoagulant effect.",
     "recommendation": "Consider paracetamol for analgesia instead of an NSAID; if an NSAID is unavoidable, increase INR monitoring frequency.",
     "source": "Carpenter et al., Am Fam Physician 2019;99(9):558-564"},

    {"a": "Warfarin", "b": "Metronidazole", "severity": "major",
     "description": "Metronidazole raises INR, increasing bleeding risk.",
     "recommendation": "Consider an alternative antibiotic where clinically appropriate; if metronidazole is necessary, monitor INR closely during and after the course.",
     "source": "Carpenter et al., Am Fam Physician 2019;99(9):558-564"},

    {"a": "Doxycycline", "b": "Ferrous Sulfate", "severity": "moderate",
     "description": "Iron chelates with tetracyclines, reducing doxycycline absorption. Separate doses by 2-3 hours.",
     "recommendation": "Separate doxycycline and the iron supplement by at least 2-3 hours to preserve antibiotic absorption; concurrent use is otherwise acceptable.",
     "source": "Standard clinical pharmacology reference"},

    {"a": "Ibuprofen", "b": "Lisinopril", "severity": "moderate",
     "description": "NSAIDs can reduce the antihypertensive effect of ACE inhibitors and raise renal impairment risk.",
     "recommendation": "Consider paracetamol as first-line analgesia in patients on ACE inhibitors; if an NSAID course is required, monitor blood pressure and renal function.",
     "source": "Standard clinical pharmacology reference"},

    {"a": "Ibuprofen", "b": "Prednisolone", "severity": "major",
     "description": "Additive risk of GI ulceration and bleeding when NSAIDs and corticosteroids are combined.",
     "recommendation": "Substitute paracetamol for the NSAID where possible, or add gastroprotection (e.g. a proton-pump inhibitor) if concurrent use is clinically necessary.",
     "source": "Standard clinical pharmacology reference"},

    {"a": "Ibuprofen", "b": "Spironolactone", "severity": "moderate",
     "description": "NSAIDs blunt the natriuretic effect and raise hyperkalemia risk with potassium-sparing diuretics.",
     "recommendation": "Consider paracetamol as an alternative analgesic; if an NSAID is necessary, check serum potassium.",
     "source": "Carpenter et al., Am Fam Physician 2019;99(9):558-564"},

    {"a": "Artemether + Lumefantrine", "b": "Erythromycin", "severity": "major",
     "description": "Additive QT-prolongation risk; both drugs affect cardiac repolarization.",
     "recommendation": "Consider an alternative antibiotic without QT-prolonging effect; if erythromycin is essential, correct electrolyte abnormalities first and monitor for cardiac symptoms.",
     "source": "WHO Guidelines for the Treatment of Malaria -- QT-prolonging drug caution"},

    {"a": "Artemether + Lumefantrine", "b": "Fluconazole", "severity": "moderate",
     "description": "CYP3A4 inhibition by fluconazole may raise artemether/lumefantrine levels and QT risk.",
     "recommendation": "Where possible, use an antifungal with less CYP3A4 inhibition, or monitor closely for QT-related symptoms during antimalarial therapy.",
     "source": "Standard clinical pharmacology reference"},

    {"a": "Diazepam", "b": "Tramadol", "severity": "major",
     "description": "Additive CNS and respiratory depression when benzodiazepines are combined with opioids.",
     "recommendation": "Consider a non-opioid analgesic such as paracetamol; if both are clinically necessary, use the lowest effective doses and monitor respiratory status closely.",
     "source": "Carpenter et al., Am Fam Physician 2019;99(9):558-564"},

    {"a": "Chlorpheniramine", "b": "Diazepam", "severity": "moderate",
     "description": "Additive sedation from combining a sedating antihistamine with a benzodiazepine.",
     "recommendation": "Consider a non-sedating antihistamine alternative, or counsel the patient on increased drowsiness and caution with driving or operating machinery.",
     "source": "Standard clinical pharmacology reference"},

    {"a": "Aspirin", "b": "Ibuprofen", "severity": "minor",
     "description": "Ibuprofen can blunt aspirin's antiplatelet (cardioprotective) effect if taken shortly before it.",
     "recommendation": "If aspirin is prescribed for cardioprotection, advise taking it at least 30 minutes before ibuprofen, or use paracetamol for pain relief instead.",
     "source": "Standard clinical pharmacology reference"},

    {"a": "Amoxicillin", "b": "Ethinylestradiol", "severity": "minor",
     "description": "Theoretical reduction in oral contraceptive efficacy; advise backup contraception during the course.",
     "recommendation": "Advise the patient to use a backup contraceptive method (e.g. condoms) for the duration of the antibiotic course and for 7 days after.",
     "source": "Standard clinical pharmacology reference"},
]

app = create_app()

with app.app_context():

    def get_or_create_drug(name: str) -> Drug:
        drug = Drug.query.filter(Drug.name.ilike(name)).first()
        if drug:
            return drug
        drug = Drug(
            name             = name,
            category         = "Unclassified",
            unit             = "unit",
            is_active        = True,
            is_pending_setup = True,  # no inventory/stock configured yet -- reference-only entry
        )
        db.session.add(drug)
        db.session.flush()  # need drug.id
        print(f"Created reference-only drug (no stock): {drug.name}")
        return drug

    created, updated = 0, 0

    for entry in INTERACTIONS:
        drug_a = get_or_create_drug(entry["a"])
        drug_b = get_or_create_drug(entry["b"])

        if drug_a.id == drug_b.id:
            print(f"Skipping self-pair: {entry['a']}")
            continue

        # Canonical ordering: smaller id first, per DrugInteraction's
        # storage convention (avoids storing the same pair twice reversed).
        id_a, id_b = sorted([drug_a.id, drug_b.id])

        existing = DrugInteraction.query.filter_by(
            drug_id_a=id_a, drug_id_b=id_b
        ).first()

        if existing:
            existing.severity       = entry["severity"]
            existing.description    = entry["description"]
            existing.recommendation = entry.get("recommendation")
            existing.source         = entry["source"]
            updated += 1
            print(f"Updated interaction: {entry['a']} + {entry['b']}")
        else:
            interaction = DrugInteraction(
                drug_id_a      = id_a,
                drug_id_b      = id_b,
                severity       = entry["severity"],
                description    = entry["description"],
                recommendation = entry.get("recommendation"),
                source         = entry["source"],
            )
            db.session.add(interaction)
            created += 1
            print(f"Created interaction: {entry['a']} + {entry['b']}")

    db.session.commit()
    print(f"\nDone -- {created} interaction(s) created, {updated} updated.")