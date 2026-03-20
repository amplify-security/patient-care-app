import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "patient_care.db")


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'provider', 'nurse')),
            specialty TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mrn TEXT UNIQUE NOT NULL,
            first_name_enc BLOB NOT NULL,
            last_name_enc BLOB NOT NULL,
            date_of_birth_enc BLOB NOT NULL,
            gender TEXT,
            phone_enc BLOB,
            email_enc BLOB,
            address_enc BLOB,
            emergency_contact_enc BLOB,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            provider_id INTEGER NOT NULL,
            visit_date TEXT NOT NULL,
            chief_complaint TEXT,
            notes_enc BLOB,
            diagnosis_enc BLOB,
            status TEXT DEFAULT 'scheduled' CHECK(status IN ('scheduled', 'in_progress', 'completed', 'cancelled')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (provider_id) REFERENCES providers(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS treatments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visit_id INTEGER NOT NULL,
            treatment_type TEXT NOT NULL CHECK(treatment_type IN ('medication', 'procedure')),
            name TEXT NOT NULL,
            dosage TEXT,
            frequency TEXT,
            notes_enc BLOB,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'discontinued')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (visit_id) REFERENCES visits(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS treatment_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            provider_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            goals TEXT,
            notes TEXT,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'discontinued')),
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (provider_id) REFERENCES providers(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_id INTEGER,
            user_role TEXT,
            action TEXT NOT NULL CHECK(action IN ('CREATE', 'READ', 'UPDATE', 'DELETE')),
            resource_type TEXT NOT NULL,
            resource_id INTEGER,
            details TEXT,
            ip_address TEXT,
            success BOOLEAN NOT NULL,
            FOREIGN KEY (user_id) REFERENCES providers(id)
        )
    """)

    conn.commit()
    conn.close()
