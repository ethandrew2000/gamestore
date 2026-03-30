import sqlite3
import hashlib
import os
import secrets

SESSION_STORE = {}


class CardDatabase:
    def __init__(self, db_name="cards.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_tables()

    def create_tables(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name      TEXT    NOT NULL,
            last_name       TEXT    NOT NULL,
            email           TEXT    NOT NULL UNIQUE,
            password_hash   TEXT    NOT NULL,
            role            TEXT    NOT NULL DEFAULT 'user'
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

        self.ensure_role_column()
        self.conn.commit()

    def ensure_role_column(self):
        cursor = self.conn.execute("PRAGMA table_info(users)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "role" not in columns:
            self.conn.execute(
                "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
            )
            self.conn.commit()

    def hash_password(self, plain_text):
        salt = os.urandom(32)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            plain_text.encode("utf-8"),
            salt,
            260000
        )
        return salt.hex() + "$" + digest.hex()

    def verify_password(self, plain_text, stored_hash):
        try:
            salt_hex, digest_hex = stored_hash.split("$")
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
            candidate = hashlib.pbkdf2_hmac(
                "sha256",
                plain_text.encode("utf-8"),
                salt,
                260000
            )
            return secrets.compare_digest(candidate, expected)
        except Exception:
            return False

    def email_exists(self, email):
        cursor = self.conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email.lower(),)
        )
        return cursor.fetchone() is not None

    def create_user(self, data):
        if self.email_exists(data["email"]):
            return None

        pw_hash = self.hash_password(data["password"])

        cursor = self.conn.execute(
            """
            INSERT INTO users (first_name, last_name, email, password_hash, role)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                data["first_name"],
                data["last_name"],
                data["email"].lower(),
                pw_hash,
                "user"
            )
        )
        self.conn.commit()
        return self.get_user_public(cursor.lastrowid)

    def authenticate_user(self, email, password):
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.lower(),)
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
            "role": user["role"]
        }

    def get_user_public(self, user_id):
        cursor = self.conn.execute(
            "SELECT id, first_name, last_name, email, role FROM users WHERE id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def set_user_role(self, email, role):
        self.conn.execute(
            "UPDATE users SET role = ? WHERE email = ?",
            (role, email.lower())
        )
        self.conn.commit()

    def create_session(self, user):
        session_id = secrets.token_hex(32)
        SESSION_STORE[session_id] = user
        return session_id

    def get_session(self, session_id):
        return SESSION_STORE.get(session_id)

    def delete_session(self, session_id):
        SESSION_STORE.pop(session_id, None)

    def get_all_cards(self):
        cursor = self.conn.execute("SELECT * FROM cards")
        return [dict(row) for row in cursor.fetchall()]

    def get_card(self, card_id):
        cursor = self.conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
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
                data["rarity"]
            )
        )
        self.conn.commit()
        return self.get_card(cursor.lastrowid)

    def update_card(self, card_id, data):
        self.conn.execute(
            """
            UPDATE cards
            SET name = ?, set_name = ?, condition = ?, price = ?, quantity = ?, rarity = ?
            WHERE id = ?
            """,
            (
                data["name"],
                data["set_name"],
                data["condition"],
                data["price"],
                data["quantity"],
                data["rarity"],
                card_id
            )
        )
        self.conn.commit()
        return self.get_card(card_id)

    def delete_card(self, card_id):
        self.conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        self.conn.commit()