# app/extensions.py
#
# Extensions are created here but NOT initialised with an app.
# They are initialised inside create_app() using .init_app(app).
# This is the correct pattern for large Flask projects.

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_cors import CORS

# Database ORM
db = SQLAlchemy()

# Database migration manager
migrate = Migrate()

# JWT authentication manager
jwt = JWTManager()

# Password hashing
bcrypt = Bcrypt()

# Email sending
mail = Mail()

# Cross-Origin Resource Sharing (allows the frontend to call the API)
cors = CORS()