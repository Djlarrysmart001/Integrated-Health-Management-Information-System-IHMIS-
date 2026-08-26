# app/api/__init__.py

from flask import Flask


def register_blueprints(flask_app: Flask) -> None:

    from app.api.v1.auth.routes import auth_bp
    from app.api.v1.users.routes import users_bp
    from app.api.v1.patients.routes import patients_bp
    from app.api.v1.health_files.routes import health_files_bp
    from app.api.v1.consultations.routes import consultations_bp
    from app.api.v1.medical_certificates.routes import medical_certificates_bp
    from app.api.v1.immunizations.routes import immunizations_bp
    from app.api.v1.admissions.routes import admissions_bp
    from app.api.v1.staff_attendance.routes import staff_attendance_bp
    from app.api.v1.roles.routes import roles_bp
    from app.api.v1.analytics.routes import analytics_bp
    from app.api.v1.medical_records.routes import medical_records_bp
    from app.api.v1.laboratory.routes import laboratory_bp
    from app.api.v1.pharmacy.routes import pharmacy_bp
    from app.api.v1.prescriptions.routes import prescriptions_bp
    from app.api.v1.referrals.routes import referrals_bp
    from app.api.v1.notifications.routes import notifications_bp
    from app.api.v1.reports.routes import reports_bp
    from app.api.v1.audit_logs.routes import audit_logs_bp
    from app.api.v1.dashboard.routes import dashboard_bp
    from app.api.v1.settings.routes import settings_bp
    from app.api.v1.mho.routes import mho_bp
    from app.api.v1.documents.routes import documents_bp
    from app.api.v1.vitals.routes import vitals_bp
    from app.api.v1.ai.routes import ai_bp

    url_prefix = "/api/v1"

    flask_app.register_blueprint(auth_bp,            url_prefix=f"{url_prefix}/auth")
    flask_app.register_blueprint(users_bp,           url_prefix=f"{url_prefix}/users")
    flask_app.register_blueprint(patients_bp,        url_prefix=f"{url_prefix}/patients")
    flask_app.register_blueprint(health_files_bp,    url_prefix=f"{url_prefix}/health-files")
    flask_app.register_blueprint(consultations_bp,   url_prefix=f"{url_prefix}/consultations")
    flask_app.register_blueprint(medical_certificates_bp, url_prefix=f"{url_prefix}/medical-certificates")
    flask_app.register_blueprint(immunizations_bp, url_prefix=f"{url_prefix}/immunizations")
    flask_app.register_blueprint(admissions_bp, url_prefix=f"{url_prefix}/admissions")
    flask_app.register_blueprint(staff_attendance_bp, url_prefix=f"{url_prefix}/staff-attendance")
    flask_app.register_blueprint(roles_bp, url_prefix=f"{url_prefix}/roles")
    flask_app.register_blueprint(analytics_bp, url_prefix=f"{url_prefix}/analytics")
    flask_app.register_blueprint(medical_records_bp, url_prefix=f"{url_prefix}/medical-records")
    flask_app.register_blueprint(laboratory_bp,      url_prefix=f"{url_prefix}/laboratory")
    flask_app.register_blueprint(pharmacy_bp,        url_prefix=f"{url_prefix}/pharmacy")
    flask_app.register_blueprint(prescriptions_bp,   url_prefix=f"{url_prefix}/prescriptions")
    flask_app.register_blueprint(referrals_bp,       url_prefix=f"{url_prefix}/referrals")
    flask_app.register_blueprint(notifications_bp,   url_prefix=f"{url_prefix}/notifications")
    flask_app.register_blueprint(reports_bp,         url_prefix=f"{url_prefix}/reports")
    flask_app.register_blueprint(audit_logs_bp,      url_prefix=f"{url_prefix}/audit-logs")
    flask_app.register_blueprint(dashboard_bp,       url_prefix=f"{url_prefix}/dashboard")
    flask_app.register_blueprint(settings_bp,        url_prefix=f"{url_prefix}/settings")
    flask_app.register_blueprint(mho_bp,             url_prefix=f"{url_prefix}/mho")
    flask_app.register_blueprint(documents_bp,       url_prefix=f"{url_prefix}/documents")
    flask_app.register_blueprint(vitals_bp,          url_prefix=f"{url_prefix}/vitals")
    flask_app.register_blueprint(ai_bp,              url_prefix=f"{url_prefix}/ai")