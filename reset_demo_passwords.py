
from app.database import SessionLocal
from app.models import User
from app.security import hash_password

db = SessionLocal()

demo_users = {
    "sneha@ajaia.demo": "sneha123",
    "alex@ajaia.demo": "alex123",
}

try:
    for email, password in demo_users.items():
        user = db.query(User).filter(User.email == email).first()

        if user:
            user.password_hash = hash_password(password)
            print(f"Password reset: {email}")
        else:
            print(f"User not found: {email}")

    db.commit()
    print("Demo password reset completed.")

finally:
    db.close()
