import os
import sys
from pathlib import Path
import uuid

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Default to local SQLite database if not explicitly set
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///wms_dev.db"

from app.db.base import Base
from app.db.session import engine, SessionLocal
import app.models  # Register all models on metadata
from app.models.enums import UserType
from app.models.user_account import UserAccount
from app.core.security import hash_password


def seed():
    print("Ensuring database tables exist...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1. Admin User
        admin = db.query(UserAccount).filter(UserAccount.email == "admin@company.com").first()
        if not admin:
            admin = UserAccount(
                account_id=uuid.uuid4(),
                email="admin@company.com",
                password_hash=hash_password("Admin@123"),
                user_type=UserType.ADMIN,
                is_active=True,
                is_mfa_enabled=False,
            )
            db.add(admin)
            print("Created Admin user: admin@company.com / Admin@123")
        else:
            # Reset MFA so testing can start fresh
            admin.is_mfa_enabled = False
            admin.mfa_secret = None
            admin.password_hash = hash_password("Admin@123")
            print("Reset Admin user to clean state: admin@company.com / Admin@123 (MFA disabled)")

        # 2. Employee User (for RBAC testing)
        emp = db.query(UserAccount).filter(UserAccount.email == "employee@company.com").first()
        if not emp:
            emp = UserAccount(
                account_id=uuid.uuid4(),
                email="employee@company.com",
                password_hash=hash_password("Password@123"),
                user_type=UserType.EMPLOYEE,
                is_active=True,
                is_mfa_enabled=False,
            )
            db.add(emp)
            print("Created Employee user: employee@company.com / Password@123")
        else:
            emp.password_hash = hash_password("Password@123")
            print("Updated Employee password to: Password@123")

        db.commit()
        print("\nDatabase successfully seeded and ready for Postman testing!")
    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

