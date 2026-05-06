from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class User:
    username: str
    password: str
    role: str
    allowed_part_number: Optional[str] = None
    allowed_tracking_pin: Optional[str] = None
    allowed_part_numbers: Optional[list[str]] = None
    allowed_tracking_pins: Optional[list[str]] = None
    # When CSV lacks `username` but has `customer_name`, isolate rows by these labels.
    csv_customer_names: Optional[list[str]] = None


class AuthService:
    def __init__(
        self,
        user_store_path: Optional[str | Path] = None,
    ) -> None:
        # Resolve against project root so logins work when uvicorn cwd is not the repo root.
        if user_store_path is None:
            self.user_store_path = _PROJECT_ROOT / "data" / "customer_access.json"
        else:
            raw = Path(user_store_path)
            self.user_store_path = raw if raw.is_absolute() else (_PROJECT_ROOT / raw)
        self._users = self._load_users()
        self._tokens: dict[str, User] = {}

    def _load_users(self) -> dict[str, User]:
        if self.user_store_path.exists():
            try:
                data = json.loads(self.user_store_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Could not read user store %s; using defaults: %s",
                    self.user_store_path,
                    exc,
                )
                data = {}
            users: dict[str, User] = {}
            for item in data.get("users", []):
                raw_csv_names = item.get("csv_customer_names") or []
                csv_names = [str(x).strip() for x in raw_csv_names if str(x).strip()]
                user = User(
                    username=item["username"],
                    password=item["password"],
                    role=item["role"],
                    allowed_part_number=item.get("allowed_part_number"),
                    allowed_tracking_pin=item.get("allowed_tracking_pin"),
                    allowed_part_numbers=item.get("allowed_part_numbers"),
                    allowed_tracking_pins=item.get("allowed_tracking_pins"),
                    csv_customer_names=csv_names or None,
                )
                users[user.username] = user
            if users:
                return users

        return {
            "admin": User(username="admin", password="admin123", role="admin"),
            "customer_prt_a": User(
                username="customer_prt_a",
                password="customer123",
                role="customer",
                allowed_part_number="PRT-A",
                allowed_tracking_pin="CON0119",
                allowed_part_numbers=["PRT-A", "PRT-B", "PRT-C"],
                allowed_tracking_pins=["CON0119", "CON0210", "CON0311"],
            ),
        }

    def _save_users(self) -> None:
        self.user_store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "users": [
                {
                    "username": u.username,
                    "password": u.password,
                    "role": u.role,
                    "allowed_part_number": u.allowed_part_number,
                    "allowed_tracking_pin": u.allowed_tracking_pin,
                    "allowed_part_numbers": u.allowed_part_numbers or [],
                    "allowed_tracking_pins": u.allowed_tracking_pins or [],
                    "csv_customer_names": u.csv_customer_names or [],
                }
                for u in self._users.values()
            ]
        }
        self.user_store_path.write_text(json.dumps(payload, indent=2))

    def login(self, username: str, password: str) -> dict:
        # Re-read JSON so edits to customer_access.json apply without restarting uvicorn.
        self._users = self._load_users()
        username = username.strip()
        password = password.strip()
        user = self._users.get(username)
        if user is None or user.password != password:
            raise ValueError("Invalid username or password")

        token = secrets.token_urlsafe(24)
        self._tokens[token] = user
        return {
            "access_token": token,
            "role": user.role,
            "username": user.username,
            "allowed_part_number": user.allowed_part_number,
            "allowed_tracking_pin": user.allowed_tracking_pin,
            "allowed_part_numbers": user.allowed_part_numbers or (
                [user.allowed_part_number] if user.allowed_part_number else []
            ),
            "allowed_tracking_pins": user.allowed_tracking_pins or (
                [user.allowed_tracking_pin] if user.allowed_tracking_pin else []
            ),
        }

    def get_user_by_token(self, token: str) -> User:
        user = self._tokens.get(token)
        if user is None:
            raise ValueError("Invalid or expired auth token")
        return user

    def list_customers(self) -> list[dict]:
        out = []
        for u in self._users.values():
            if u.role != "customer":
                continue
            out.append(
                {
                    "username": u.username,
                    "allowed_part_numbers": u.allowed_part_numbers or [],
                    "allowed_tracking_pins": u.allowed_tracking_pins or [],
                }
            )
        return sorted(out, key=lambda x: x["username"])

    def upsert_customer(
        self,
        username: str,
        password: str,
        allowed_part_numbers: list[str],
        allowed_tracking_pins: list[str],
        csv_customer_names: Optional[list[str]] = None,
    ) -> dict:
        clean_parts = [p.strip() for p in allowed_part_numbers if p and p.strip()]
        clean_pins = [p.strip() for p in allowed_tracking_pins if p and p.strip()]
        if not clean_parts:
            raise ValueError("At least one allowed part number is required")
        if not clean_pins:
            raise ValueError("At least one allowed tracking pin is required")

        existing = self._users.get(username)
        merged_csv: Optional[list[str]] = None
        if csv_customer_names is not None:
            merged_csv = [str(x).strip() for x in csv_customer_names if str(x).strip()] or None
        elif existing and existing.role == "customer":
            merged_csv = existing.csv_customer_names

        self._users[username] = User(
            username=username,
            password=password,
            role="customer",
            allowed_part_numbers=clean_parts,
            allowed_tracking_pins=clean_pins,
            allowed_part_number=clean_parts[0],
            allowed_tracking_pin=clean_pins[0],
            csv_customer_names=merged_csv,
        )
        self._save_users()
        return {
            "username": username,
            "allowed_part_numbers": clean_parts,
            "allowed_tracking_pins": clean_pins,
            "csv_customer_names": merged_csv or [],
        }

    def delete_customer(self, username: str) -> None:
        user = self._users.get(username)
        if user is None or user.role != "customer":
            raise ValueError("Customer not found")
        del self._users[username]
        self._save_users()


auth_service = AuthService()
