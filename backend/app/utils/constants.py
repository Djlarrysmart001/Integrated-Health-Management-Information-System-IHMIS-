# app/utils/constants.py


class Roles:
    """
    Central definition of all role names in the system.
    Use these constants everywhere instead of typing raw strings.
    This prevents typos like "Doctr" breaking your access control.
    """
    ADMIN                   = "Admin"
    MEDICAL_HEALTH_OFFICER  = "Medical Health Officer"
    NURSE                   = "Nurse"
    DOCTOR                  = "Doctor"
    LAB_TECH                = "Lab Technician"
    PHARMACIST              = "Pharmacist"

    ALL = [ADMIN, MEDICAL_HEALTH_OFFICER, NURSE, DOCTOR, LAB_TECH, PHARMACIST]

    CLINICAL_FLOW = [MEDICAL_HEALTH_OFFICER, NURSE, DOCTOR, LAB_TECH, PHARMACIST]


class TokenType:
    ACCESS  = "access"
    REFRESH = "refresh"