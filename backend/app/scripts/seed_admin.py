"""ایجاد صریح ادمین اولیه با تایید تعاملی و ثبت حسابرسی (R-117).

استفاده: `uv run --locked python -m app.scripts.seed_admin`
"""

import asyncio
import getpass
import sys
from argparse import ArgumentParser

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.phone import normalize_e164
from app.db.session import SessionFactory
from app.repositories import admin_audit_log as audit_repo
from app.repositories import users as users_repo


async def seed_admin(session: AsyncSession, *, phone: str, name: str | None, email: str | None, with_password: bool) -> None:
    normalized = normalize_e164(phone)
    existing = await users_repo.get_by_phone(session, normalized)
    if existing is not None:
        if existing.role == "admin":
            print(f"admin already exists for {normalized}; skipping.", file=sys.stderr)
            return
        existing.role = "admin"
        actor = None
        after: dict[str, object] = {"role": "admin"}
    else:
        password_hash = None
        if with_password:
            from argon2 import PasswordHasher

            password = getpass.getpass("Password for admin: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                raise SystemExit("passwords do not match")
            password_hash = PasswordHasher().hash(password)
        user = await users_repo.create(session, phone=normalized, role="admin", name=name, email=email, password_hash=password_hash)
        actor = user.id
        after = {"role": "admin", "phone": normalized, "name": name, "email": email}
    await audit_repo.create(
        session,
        actor_user_id=actor,
        action="seed_admin",
        entity_type="user",
        entity_id=str(existing.id if existing is not None else actor),
        reason="initial admin bootstrap via explicit CLI (R-117)",
        after=after,
    )
    await session.commit()
    print(f"admin seeded for {normalized}")


def main() -> int:
    parser = ArgumentParser(description="Seed the first admin user with audit log")
    parser.add_argument("--phone", default=None, help="E.164 phone of the admin (falls back to ADMIN_PHONE)")
    parser.add_argument("--name", default=None, help="Admin display name (falls back to ADMIN_NAME)")
    parser.add_argument("--email", default=None, help="Admin email (falls back to ADMIN_EMAIL)")
    parser.add_argument("--with-password", action="store_true", help="Also set a password (Argon2id)")
    args = parser.parse_args()

    settings = get_settings()
    phone = args.phone or settings.admin_phone
    if not phone:
        print("no admin phone provided; set ADMIN_PHONE or use --phone", file=sys.stderr)
        return 2
    name = args.name or settings.admin_name or None
    email = args.email or settings.admin_email or None
    if not (args.with_password or settings.admin_password_login_enabled):
        print("WARNING: seeding admin without a password (OTP-only login).", file=sys.stderr)
    confirm = input(f"Create admin for {phone}? [y/N] ")
    if confirm.strip().lower() not in {"y", "yes"}:
        print("aborted", file=sys.stderr)
        return 1
    asyncio.run(seed_admin(SessionFactory(), phone=phone, name=name, email=email, with_password=args.with_password or settings.admin_password_login_enabled))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
