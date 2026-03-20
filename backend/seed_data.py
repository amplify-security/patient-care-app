#!/usr/bin/env python3
"""Seed script to populate the database with demo data."""

import os
import sys

# Ensure app modules are importable
sys.path.insert(0, os.path.dirname(__file__))

# Set environment variables for seeding if not already set
from cryptography.fernet import Fernet

if not os.environ.get("PHI_ENCRYPTION_KEY"):
    key = Fernet.generate_key().decode()
    os.environ["PHI_ENCRYPTION_KEY"] = key
    print(f"Generated PHI_ENCRYPTION_KEY: {key}")
    print("Save this in your .env file!\n")

if not os.environ.get("JWT_SECRET"):
    import secrets
    secret = secrets.token_urlsafe(48)
    os.environ["JWT_SECRET"] = secret
    print(f"Generated JWT_SECRET: {secret}")
    print("Save this in your .env file!\n")

from datetime import datetime, timezone
import bcrypt
from app.database import init_db, get_db_connection
from app.encryption import encrypt_phi


def seed():
    print("Initializing database...")
    init_db()

    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()

    # Clear existing data
    for table in ["treatment_plans", "treatments", "visits", "patients", "audit_logs", "providers"]:
        conn.execute(f"DELETE FROM {table}")

    # --- Providers ---
    providers = [
        ("admin@patientcare.demo", "AdminPass123!", "Sarah", "Chen", "admin", "Internal Medicine"),
        ("dr.smith@patientcare.demo", "DoctorPass123!", "James", "Smith", "provider", "Cardiology"),
        ("nurse.jones@patientcare.demo", "NursePass123!", "Emily", "Jones", "nurse", None),
    ]

    provider_ids = []
    for email, password, first, last, role, specialty in providers:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cursor = conn.execute(
            """INSERT INTO providers (email, password_hash, first_name, last_name, role, specialty, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (email, password_hash, first, last, role, specialty, now, now),
        )
        provider_ids.append(cursor.lastrowid)

    # --- Patients ---
    patients_data = [
        ("MRN-A1B2C3D4", "John", "Doe", "1985-03-15", "male", "555-0101", "john.doe@email.com", "123 Main St, Springfield", "Jane Doe - 555-0102"),
        ("MRN-E5F6G7H8", "Maria", "Garcia", "1990-07-22", "female", "555-0201", "maria.garcia@email.com", "456 Oak Ave, Springfield", "Carlos Garcia - 555-0202"),
        ("MRN-I9J0K1L2", "Robert", "Johnson", "1978-11-08", "male", "555-0301", "r.johnson@email.com", "789 Pine Rd, Springfield", "Lisa Johnson - 555-0302"),
        ("MRN-M3N4O5P6", "Sarah", "Williams", "1995-01-30", "female", "555-0401", "s.williams@email.com", "321 Elm St, Springfield", "Mike Williams - 555-0402"),
        ("MRN-Q7R8S9T0", "David", "Brown", "1962-09-14", "male", "555-0501", "d.brown@email.com", "654 Maple Dr, Springfield", "Susan Brown - 555-0502"),
    ]

    patient_ids = []
    for mrn, first, last, dob, gender, phone, email, address, emergency in patients_data:
        cursor = conn.execute(
            """INSERT INTO patients (mrn, first_name_enc, last_name_enc, date_of_birth_enc, gender,
               phone_enc, email_enc, address_enc, emergency_contact_enc, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (mrn, encrypt_phi(first), encrypt_phi(last), encrypt_phi(dob), gender,
             encrypt_phi(phone), encrypt_phi(email), encrypt_phi(address), encrypt_phi(emergency), now, now),
        )
        patient_ids.append(cursor.lastrowid)

    # --- Visits ---
    visits_data = [
        (patient_ids[0], provider_ids[1], "2026-03-10T09:00:00", "Chest pain", "Patient reports intermittent chest pain for 2 weeks", "Angina pectoris - stable", "completed"),
        (patient_ids[0], provider_ids[1], "2026-03-25T10:00:00", "Follow-up", None, None, "scheduled"),
        (patient_ids[1], provider_ids[1], "2026-03-12T14:00:00", "Annual physical", "Routine physical exam, all vitals normal", "Healthy - no concerns", "completed"),
        (patient_ids[2], provider_ids[1], "2026-03-08T11:00:00", "Shortness of breath", "SOB on exertion, started 1 month ago", "COPD exacerbation", "completed"),
        (patient_ids[2], provider_ids[1], "2026-03-20T09:30:00", "Follow-up for COPD", "Improvement noted with current medication", "COPD - improving", "completed"),
        (patient_ids[3], provider_ids[1], "2026-03-15T13:00:00", "Migraine", "Severe migraine with aura, 3rd episode this month", "Migraine with aura", "completed"),
        (patient_ids[4], provider_ids[1], "2026-03-18T08:00:00", "Diabetes management", "A1C check and medication review", "Type 2 diabetes - controlled", "completed"),
        (patient_ids[4], provider_ids[1], "2026-04-01T08:00:00", "Diabetes follow-up", None, None, "scheduled"),
    ]

    visit_ids = []
    for pid, prov_id, date, complaint, notes, diagnosis, visit_status in visits_data:
        cursor = conn.execute(
            """INSERT INTO visits (patient_id, provider_id, visit_date, chief_complaint, notes_enc, diagnosis_enc, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, prov_id, date, complaint,
             encrypt_phi(notes) if notes else None,
             encrypt_phi(diagnosis) if diagnosis else None,
             visit_status, now, now),
        )
        visit_ids.append(cursor.lastrowid)

    # --- Treatments ---
    treatments_data = [
        (visit_ids[0], "medication", "Nitroglycerin", "0.4mg", "As needed for chest pain", "Sublingual tablets for acute episodes", "active"),
        (visit_ids[0], "medication", "Aspirin", "81mg", "Once daily", "Low-dose aspirin for cardiovascular protection", "active"),
        (visit_ids[0], "procedure", "ECG", None, None, "12-lead ECG performed, normal sinus rhythm", "completed"),
        (visit_ids[2], "procedure", "Complete Blood Count", None, None, "CBC within normal limits", "completed"),
        (visit_ids[3], "medication", "Albuterol", "90mcg", "Every 4-6 hours as needed", "Rescue inhaler for acute symptoms", "active"),
        (visit_ids[3], "medication", "Tiotropium", "18mcg", "Once daily", "Long-acting bronchodilator for COPD maintenance", "active"),
        (visit_ids[4], "procedure", "Pulmonary Function Test", None, None, "FEV1 improved from 65% to 72% predicted", "completed"),
        (visit_ids[5], "medication", "Sumatriptan", "50mg", "As needed at onset of migraine", "Max 200mg in 24 hours", "active"),
        (visit_ids[5], "medication", "Topiramate", "25mg", "Twice daily", "Preventive therapy, titrate up over 4 weeks", "active"),
        (visit_ids[6], "medication", "Metformin", "1000mg", "Twice daily", "Continue current dose, good A1C control", "active"),
        (visit_ids[6], "medication", "Lisinopril", "10mg", "Once daily", "ACE inhibitor for renal protection", "active"),
        (visit_ids[6], "procedure", "HbA1c Test", None, None, "A1C result: 6.8% - well controlled", "completed"),
    ]

    for vid, ttype, name, dosage, freq, notes, tstatus in treatments_data:
        conn.execute(
            """INSERT INTO treatments (visit_id, treatment_type, name, dosage, frequency, notes_enc, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (vid, ttype, name, dosage, freq,
             encrypt_phi(notes) if notes else None,
             tstatus, now, now),
        )

    # --- Treatment Plans (PHI stored as plaintext — no encrypt_phi) ---
    treatment_plans_data = [
        (patient_ids[0], provider_ids[1], "Cardiac Care Plan", "Comprehensive management of stable angina with medication therapy and lifestyle modifications", "Reduce chest pain frequency to less than once per week; improve exercise tolerance to 30 minutes daily", "Patient is motivated and compliant. Consider cardiac rehab referral if symptoms persist after 3 months.", "active"),
        (patient_ids[2], provider_ids[1], "COPD Management Plan", "Long-term management of COPD with bronchodilator therapy and pulmonary rehabilitation", "Maintain FEV1 above 70% predicted; reduce exacerbation frequency to less than 2 per year", "Patient has history of smoking (quit 2019). Monitor for depression secondary to chronic illness.", "active"),
        (patient_ids[4], provider_ids[1], "Diabetes Type 2 Management", "Integrated diabetes management including glycemic control, cardiovascular risk reduction, and renal protection", "Maintain A1C below 7.0%; blood pressure below 130/80; annual eye and foot exams", "Patient managing well on current regimen. Wife assists with meal planning. Review insulin initiation if A1C rises above 7.5%.", "active"),
        (patient_ids[3], provider_ids[1], "Migraine Prevention Protocol", "Preventive and abortive migraine management with lifestyle trigger identification", "Reduce migraine frequency from 3/month to less than 1/month within 8 weeks", "Patient keeps a headache diary. Oral contraceptive use may be contributing factor — coordinate with OB/GYN.", "active"),
    ]

    for pid, prov_id, name, description, goals, notes, plan_status in treatment_plans_data:
        conn.execute(
            """INSERT INTO treatment_plans (patient_id, provider_id, name, description, goals, notes, status, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (pid, prov_id, name, description, goals, notes, plan_status, now, now),
        )

    conn.commit()
    conn.close()

    print("Database seeded successfully!\n")
    print("=" * 50)
    print("Demo Login Credentials:")
    print("=" * 50)
    print(f"  Admin:    admin@patientcare.demo / AdminPass123!")
    print(f"  Doctor:   dr.smith@patientcare.demo / DoctorPass123!")
    print(f"  Nurse:    nurse.jones@patientcare.demo / NursePass123!")
    print("=" * 50)
    print(f"\nPatients: {len(patients_data)}")
    print(f"Visits: {len(visits_data)}")
    print(f"Treatments: {len(treatments_data)}")


if __name__ == "__main__":
    seed()
