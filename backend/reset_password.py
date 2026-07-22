# reset_password.py

from dotenv import load_dotenv
load_dotenv()  # Must be FIRST before any app imports

from app import create_app
from app.extensions import db, bcrypt
from app.models.user import User

app = create_app()

with app.app_context():
    print("=== ALL USERS ===")
    all_users = User.query.all()
    for u in all_users:
        print(f"ID:{u.id} | username:'{u.username}' | email:'{u.email}' | active:{u.is_active}")

    user = User.query.filter_by(username='admin').first()
    if user:
        new_hash = bcrypt.generate_password_hash('Admin@1234').decode('utf-8')
        user.password_hash = new_hash
        db.session.commit()
        check = bcrypt.check_password_hash(user.password_hash, 'Admin@1234')
        print(f"\n=== RESULT ===")
        print(f"User: {user.username}")
        print(f"Password check: {check}")
        if check:
            print("SUCCESS - Login will work now")
    else:
        print("No admin user found!")