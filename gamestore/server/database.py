import sqlite3
import hashlib
import os
import secrets

# ──────────────────────────────────────────────
#  In-memory session store  { session_id: { user_id, first_name, last_name, email } }
# ──────────────────────────────────────────────
SESSION_STORE = {}


class CardDatabase:
    def __init__(self, db_name="cards.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_tables()

    # ──────────────────────────────────────────
    #  Schema
    # ──────────────────────────────────────────

    def create_tables(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name      TEXT    NOT NULL,
            last_name       TEXT    NOT NULL,
            email           TEXT    NOT NULL UNIQUE,
            password_hash   TEXT    NOT NULL
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT,
            set_name  TEXT,
            condition TEXT,
            price     REAL,
            quantity  INTEGER,
            rarity    TEXT
        )
        """)
        self.conn.commit()

    # ──────────────────────────────────────────
    #  Password helpers  (PBKDF2-HMAC-SHA256)
    # ──────────────────────────────────────────

    def hash_password(self, plain_text: str) -> str:
        """
        Returns a self-contained string:  <hex-salt>$<hex-digest>
        Algorithm : PBKDF2-HMAC-SHA256, 260 000 iterations, 32-byte salt
        """
        salt = os.urandom(32)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            plain_text.encode("utf-8"),
            salt,
            iterations=260_000,
        )
        return salt.hex() + "$" + digest.hex()

    def verify_password(self, plain_text: str, stored_hash: str) -> bool:
        try:
            salt_hex, digest_hex = stored_hash.split("$")
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
            candidate = hashlib.pbkdf2_hmac(
                "sha256",
                plain_text.encode("utf-8"),
                salt,
                iterations=260_000,
            )
            return secrets.compare_digest(candidate, expected)
        except Exception:
            return False

    # ──────────────────────────────────────────
    #  User operations
    # ──────────────────────────────────────────

    def email_exists(self, email: str) -> bool:
        cursor = self.conn.execute(
            "SELECT id FROM users WHERE email = ?", (email.lower(),)
        )
        return cursor.fetchone() is not None

    def create_user(self, data: dict):
        """Returns new user dict (without password hash) or raises on duplicate email."""
        if self.email_exists(data["email"]):
            return None  # caller checks for None → 409

        pw_hash = self.hash_password(data["password"])
        cursor = self.conn.execute(
            """
            INSERT INTO users (first_name, last_name, email, password_hash)
            VALUES (?, ?, ?, ?)
            """,
            (
                data["first_name"],
                data["last_name"],
                data["email"].lower(),
                pw_hash,
            ),
        )
        self.conn.commit()
        return self.get_user_public(cursor.lastrowid)

    def authenticate_user(self, email: str, password: str):
        """Returns public user dict on success, None on failure."""
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower(),)
        )
        row = cursor.fetchone()
        if not row:
            return None
        user = dict(row)
        if not self.verify_password(password, user["password_hash"]):
            return None
        return {
            "id": user["id"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "email": user["email"],
        }

    def get_user_public(self, user_id: int):
        cursor = self.conn.execute(
            "SELECT id, first_name, last_name, email FROM users WHERE id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # ──────────────────────────────────────────
    #  Session helpers
    # ──────────────────────────────────────────

    def create_session(self, user: dict) -> str:
        session_id = secrets.token_hex(32)
        SESSION_STORE[session_id] = user
        return session_id

    def get_session(self, session_id: str):
        return SESSION_STORE.get(session_id)

    def delete_session(self, session_id: str):
        SESSION_STORE.pop(session_id, None)

    # ──────────────────────────────────────────
    #  Card operations
    # ──────────────────────────────────────────

    def get_all_cards(self):
        cursor = self.conn.execute("SELECT * FROM cards")
        return [dict(row) for row in cursor.fetchall()]

    def get_card(self, card_id):
        cursor = self.conn.execute("SELECT * FROM cards WHERE id=?", (card_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_card(self, data):
        cursor = self.conn.execute(
            """
            INSERT INTO cards (name, set_name, condition, price, quantity, rarity)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data["set_name"],
                data["condition"],
                data["price"],
                data["quantity"],
                data["rarity"],
            ),
        )
        self.conn.commit()
        return self.get_card(cursor.lastrowid)

    def update_card(self, card_id, data):
        self.conn.execute(
            """
            UPDATE cards
            SET name=?, set_name=?, condition=?, price=?, quantity=?, rarity=?
            WHERE id=?
            """,
            (
                data["name"],
                data["set_name"],
                data["condition"],
                data["price"],
                data["quantity"],
                data["rarity"],
                card_id,
            ),
        )
        self.conn.commit()
        return self.get_card(card_id)

    def delete_card(self, card_id):
        self.conn.execute("DELETE FROM cards WHERE id=?", (card_id,))
        self.conn.commit()