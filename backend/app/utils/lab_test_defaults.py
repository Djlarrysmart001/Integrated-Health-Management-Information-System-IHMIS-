# app/utils/lab_test_defaults.py
"""
Reference defaults for common school-clinic lab tests.

Used only by LaboratoryService.find_or_create_test_by_name() when a Doctor
types a test name that isn't already in the catalogue. If the typed name
matches a known test here (directly or via an alias), the new LabTest row
is created fully set up — category, normal_range, unit, turnaround_hours —
and is NOT flagged is_pending_setup. Anything that doesn't match still
falls back to the old "Uncategorized / blank / needs setup" behaviour,
since a genuinely novel test can't be safely guessed.

This is Phase 1 knowledge-based reference data (a static lookup table),
not a diagnostic or AI feature — it just prevents avoidable "needs setup"
busywork for tests the clinic runs routinely.
"""

LAB_TEST_DEFAULTS = {
    "full blood count": {
        "category": "Haematology",
        "normal_range": "Hb 11.5-16.5 g/dL; WBC 4.0-11.0 x10^9/L; Plt 150-450 x10^9/L",
        "unit": "g/dL / x10^9/L",
        "turnaround_hours": 4,
    },
    "malaria parasite": {
        "category": "Microbiology / Parasitology",
        "normal_range": "Negative",
        "unit": "Positive/Negative",
        "turnaround_hours": 2,
    },
    "widal test": {
        "category": "Serology",
        "normal_range": "Titre < 1:80",
        "unit": "Titre",
        "turnaround_hours": 24,
    },
    "urinalysis": {
        "category": "Microbiology",
        "normal_range": "No abnormal findings",
        "unit": "Qualitative",
        "turnaround_hours": 2,
    },
    "stool microscopy": {
        "category": "Microbiology",
        "normal_range": "No ova/cysts/parasites seen",
        "unit": "Qualitative",
        "turnaround_hours": 24,
    },
    "hiv screening": {
        "category": "Serology",
        "normal_range": "Non-reactive",
        "unit": "Reactive/Non-reactive",
        "turnaround_hours": 1,
    },
    "hepatitis b surface antigen": {
        "category": "Serology",
        "normal_range": "Non-reactive",
        "unit": "Reactive/Non-reactive",
        "turnaround_hours": 2,
    },
    "pregnancy test": {
        "category": "Serology",
        "normal_range": "Negative",
        "unit": "Positive/Negative",
        "turnaround_hours": 1,
    },
    "blood group and genotype": {
        "category": "Haematology",
        "normal_range": "N/A — result is the type itself",
        "unit": "Group/Genotype",
        "turnaround_hours": 2,
    },
    "random blood sugar": {
        "category": "Chemical Pathology",
        "normal_range": "70-140 mg/dL",
        "unit": "mg/dL",
        "turnaround_hours": 1,
    },
    "fasting blood sugar": {
        "category": "Chemical Pathology",
        "normal_range": "70-100 mg/dL",
        "unit": "mg/dL",
        "turnaround_hours": 1,
    },
    "erythrocyte sedimentation rate": {
        "category": "Haematology",
        "normal_range": "0-20 mm/hr",
        "unit": "mm/hr",
        "turnaround_hours": 4,
    },
    "packed cell volume": {
        "category": "Haematology",
        "normal_range": "36-48%",
        "unit": "%",
        "turnaround_hours": 2,
    },
    "urethral swab culture": {
        "category": "Microbiology",
        "normal_range": "No growth",
        "unit": "Qualitative",
        "turnaround_hours": 48,
    },
}

# Alternate spellings / abbreviations / doctor shorthand -> canonical key
# above. Keep every alias lowercase; matching lowercases the typed name.
LAB_TEST_ALIASES = {
    "fbc": "full blood count",
    "cbc": "full blood count",
    "complete blood count": "full blood count",
    "blood count": "full blood count",
    "blood test": "full blood count",

    "mp": "malaria parasite",
    "mps": "malaria parasite",
    "malaria test": "malaria parasite",
    "malaria parasites": "malaria parasite",

    "widal": "widal test",

    "urine test": "urinalysis",
    "urine microscopy": "urinalysis",
    "u/a": "urinalysis",

    "stool test": "stool microscopy",
    "stool exam": "stool microscopy",
    "stool m/c/s": "stool microscopy",
    "stool mcs": "stool microscopy",

    "hiv test": "hiv screening",
    "hiv": "hiv screening",
    "hiv 1&2": "hiv screening",
    "hiv 1 and 2": "hiv screening",

    "hbsag": "hepatitis b surface antigen",
    "hepatitis b": "hepatitis b surface antigen",
    "hep b": "hepatitis b surface antigen",

    "hcg": "pregnancy test",
    "hcg test": "pregnancy test",
    "urine hcg": "pregnancy test",
    "beta hcg": "pregnancy test",

    "blood group": "blood group and genotype",
    "genotype": "blood group and genotype",
    "blood group & genotype": "blood group and genotype",

    "rbs": "random blood sugar",
    "blood sugar": "random blood sugar",
    "glucose test": "random blood sugar",

    "fbs": "fasting blood sugar",

    "esr": "erythrocyte sedimentation rate",

    "pcv": "packed cell volume",
    "hematocrit": "packed cell volume",
    "haematocrit": "packed cell volume",

    "urethral swab": "urethral swab culture",
    "urethral culture": "urethral swab culture",
}


def get_lab_test_defaults(name: str):
    """
    Case-insensitive lookup: returns a dict with category, normal_range,
    unit, turnaround_hours if the given test name matches a known test
    (directly or via alias), otherwise returns None.
    """
    if not name:
        return None

    key = name.strip().lower()
    key = LAB_TEST_ALIASES.get(key, key)
    return LAB_TEST_DEFAULTS.get(key)