"""Generate a password salt and hash for manual credential SQL."""

from __future__ import annotations

import getpass
import sys

from app.core.config.settings import settings
from app.core.security.passwords import (
    PASSWORD_ALGORITHM,
    generate_password_salt,
    hash_password,
)


def main() -> int:
    password = getpass.getpass("Password to hash: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords did not match.")
        return 1
    if not password:
        print("Password cannot be empty.")
        return 1
    salt = generate_password_salt()
    password_hash = hash_password(password, salt=salt)
    print("PASSWORD HASH RESULT")
    print(f"algorithm={PASSWORD_ALGORITHM}")
    print(f"iterations={settings.password_hash_iterations}")
    print(f"salt={salt}")
    print(f"hash={password_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
