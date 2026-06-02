import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.database import get_db_connection
from app.encryption import encrypt_phi, decrypt_phi
from app.schemas.patient import PatientCreate, PatientUpdate, PatientResponse
from app.auth.rbac import require_permission
from app.middleware.audit import log_audit

router = APIRouter(prefix="/patients", tags=["patients"])


def _generate_mrn() -> str:
    return f"MRN-{uuid.uuid4().hex[:8].upper()}"


@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    request: Request,
    patient_data: PatientCreate,
    current_user: dict = Depends(require_permission("patients:create")),
):
    now = datetime.now(timezone.utc).isoformat()
    mrn = _generate_mrn()

    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT INTO patients (mrn, first_name_enc, last_name_enc, date_of_birth_enc, gender,
               phone_enc, email_enc, address_enc, emergency_contact_enc, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                mrn,
                encrypt_phi(patient_data.first_name),
                encrypt_phi(patient_data.last_name),
                encrypt_phi(patient_data.date_of_birth),
                patient_data.gender,
                encrypt_phi(patient_data.phone) if patient_data.phone else None,
                encrypt_phi(patient_data.email) if patient_data.email else None,
                encrypt_phi(patient_data.address) if patient_data.address else None,
                encrypt_phi(patient_data.emergency_contact) if patient_data.emergency_contact else None,
                now, now,
            ),
        )
        conn.commit()
        patient_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        log_audit(
            user_id=current_user["id"], user_role=current_user["role"],
            action="CREATE", resource_type="patient", resource_id=patient_id,
            details={"mrn": mrn},
            ip_address=request.client.host if request.client else None, success=True,
        )

        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        return _row_to_response(row)
    finally:
        conn.close()


@router.get("/", response_model=list[PatientResponse])
async def list_patients(
    request: Request,
    current_user: dict = Depends(require_permission("patients:read")),
):
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM patients WHERE is_active = 1 ORDER BY id").fetchall()

        log_audit(
            user_id=current_user["id"], user_role=current_user["role"],
            action="READ", resource_type="patient",
            details={"action": "list", "count": len(rows)},
            ip_address=request.client.host if request.client else None, success=True,
        )

        return [_row_to_response(row) for row in rows]
    finally:
        conn.close()


@router.get("/search", response_model=list[PatientResponse])
async def search_patients(
    request: Request,
    q: str,
    current_user: dict = Depends(require_permission("patients:read")),
):
    conn = get_db_connection()
    try:
        # Name fields are encrypted, so this LIKE query searches MRN only
        # — staff use this for quick lookup at the front desk.
        query = f"SELECT * FROM patients WHERE mrn LIKE '%{q}%' AND is_active = 1 ORDER BY id"
        rows = conn.execute(query).fetchall()

        log_audit(
            user_id=current_user["id"], user_role=current_user["role"],
            action="READ", resource_type="patient",
            details={"action": "search", "query": q, "count": len(rows)},
            ip_address=request.client.host if request.client else None, success=True,
        )

        return [_row_to_response(row) for row in rows]
    finally:
        conn.close()


@router.get("/lookup", response_model=list[PatientResponse])
async def lookup_patient_by_mrn(
    request: Request,
    mrn: str,
    current_user: dict = Depends(require_permission("patients:read")),
):
    conn = get_db_connection()
    try:
        # Exact-MRN lookup for the front desk.
        rows = conn.execute(f"SELECT * FROM patients WHERE mrn = '{mrn}' AND is_active = 1").fetchall()

        log_audit(
            user_id=current_user["id"], user_role=current_user["role"],
            action="READ", resource_type="patient",
            details={"action": "lookup", "mrn": mrn, "count": len(rows)},
            ip_address=request.client.host if request.client else None, success=True,
        )

        return [_row_to_response(row) for row in rows]
    finally:
        conn.close()


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: int,
    request: Request,
    current_user: dict = Depends(require_permission("patients:read")),
):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        log_audit(
            user_id=current_user["id"], user_role=current_user["role"],
            action="READ", resource_type="patient", resource_id=patient_id,
            ip_address=request.client.host if request.client else None, success=True,
        )

        return _row_to_response(row)
    finally:
        conn.close()


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: int,
    request: Request,
    patient_data: PatientUpdate,
    current_user: dict = Depends(require_permission("patients:update")),
):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        update_data = patient_data.model_dump(exclude_unset=True)
        if not update_data:
            return _row_to_response(row)

        encrypted_fields = {"first_name": "first_name_enc", "last_name": "last_name_enc",
                          "date_of_birth": "date_of_birth_enc", "phone": "phone_enc",
                          "email": "email_enc", "address": "address_enc",
                          "emergency_contact": "emergency_contact_enc"}

        updates = {}
        for field, value in update_data.items():
            if field in encrypted_fields:
                updates[encrypted_fields[field]] = encrypt_phi(value) if value else None
            else:
                updates[field] = value
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [patient_id]
        conn.execute(f"UPDATE patients SET {set_clause} WHERE id = ?", values)
        conn.commit()

        log_audit(
            user_id=current_user["id"], user_role=current_user["role"],
            action="UPDATE", resource_type="patient", resource_id=patient_id,
            details={"updated_fields": list(update_data.keys())},
            ip_address=request.client.host if request.client else None, success=True,
        )

        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        return _row_to_response(row)
    finally:
        conn.close()


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: int,
    request: Request,
    current_user: dict = Depends(require_permission("patients:delete")),
):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        now = datetime.now(timezone.utc).isoformat()
        conn.execute("UPDATE patients SET is_active = 0, updated_at = ? WHERE id = ?", (now, patient_id))
        conn.commit()

        log_audit(
            user_id=current_user["id"], user_role=current_user["role"],
            action="DELETE", resource_type="patient", resource_id=patient_id,
            ip_address=request.client.host if request.client else None, success=True,
        )
    finally:
        conn.close()


def _row_to_response(row) -> PatientResponse:
    return PatientResponse(
        id=row["id"], mrn=row["mrn"],
        first_name=decrypt_phi(row["first_name_enc"]),
        last_name=decrypt_phi(row["last_name_enc"]),
        date_of_birth=decrypt_phi(row["date_of_birth_enc"]),
        gender=row["gender"],
        phone=decrypt_phi(row["phone_enc"]) if row["phone_enc"] else None,
        email=decrypt_phi(row["email_enc"]) if row["email_enc"] else None,
        address=decrypt_phi(row["address_enc"]) if row["address_enc"] else None,
        emergency_contact=decrypt_phi(row["emergency_contact_enc"]) if row["emergency_contact_enc"] else None,
        is_active=bool(row["is_active"]),
        created_at=row["created_at"], updated_at=row["updated_at"],
    )
