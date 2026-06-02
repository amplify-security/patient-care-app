from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.database import get_db_connection
from app.encryption import encrypt_phi, decrypt_phi
from app.schemas.visit import VisitCreate, VisitUpdate, VisitResponse
from app.auth.rbac import require_permission
from app.middleware.audit import log_audit

router = APIRouter(prefix="/visits", tags=["visits"])


@router.post("/", response_model=VisitResponse, status_code=status.HTTP_201_CREATED)
async def create_visit(
    request: Request,
    visit_data: VisitCreate,
    current_user: dict = Depends(require_permission("visits:create")),
):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        # Verify patient and provider exist
        patient = conn.execute("SELECT id FROM patients WHERE id = ? AND is_active = 1", (visit_data.patient_id,)).fetchone()
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        provider = conn.execute("SELECT id FROM providers WHERE id = ? AND is_active = 1", (visit_data.provider_id,)).fetchone()
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        cursor = conn.execute(
            """INSERT INTO visits (patient_id, provider_id, visit_date, chief_complaint, notes_enc, diagnosis_enc, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                visit_data.patient_id, visit_data.provider_id, visit_data.visit_date,
                visit_data.chief_complaint,
                encrypt_phi(visit_data.notes) if visit_data.notes else None,
                encrypt_phi(visit_data.diagnosis) if visit_data.diagnosis else None,
                visit_data.status or "scheduled", now, now,
            ),
        )
        conn.commit()
        visit_id = cursor.lastrowid

        log_audit(
            user_id=current_user["id"], user_role=current_user["role"],
            action="CREATE", resource_type="visit", resource_id=visit_id,
            details={"patient_id": visit_data.patient_id, "provider_id": visit_data.provider_id},
            ip_address=request.client.host if request.client else None, success=True,
        )

        row = conn.execute("SELECT * FROM visits WHERE id = ?", (visit_id,)).fetchone()
        return _row_to_response(row)
    finally:
        conn.close()


@router.get("/", response_model=list[VisitResponse])
async def list_visits(
    request: Request,
    patient_id: int = None,
    provider_id: int = None,
    status_filter: str = None,
    current_user: dict = Depends(require_permission("visits:read")),
):
    conn = get_db_connection()
    try:
        query = "SELECT * FROM visits WHERE 1=1"
        params = []
        if patient_id:
            query += " AND patient_id = ?"
            params.append(patient_id)
        if provider_id:
            query += " AND provider_id = ?"
            params.append(provider_id)
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)
        query += " ORDER BY visit_date DESC"

        rows = conn.execute(query, params).fetchall()

        log_audit(
            user_id=current_user["id"], user_role=current_user["role"],
            action="READ", resource_type="visit",
            details={"action": "list", "count": len(rows), "filters": {"patient_id": patient_id, "provider_id": provider_id}},
            ip_address=request.client.host if request.client else None, success=True,
        )

        return [_row_to_response(row) for row in rows]
    finally:
        conn.close()


@router.get("/{visit_id}", response_model=VisitResponse)
async def get_visit(
    visit_id: int,
    request: Request,
    current_user: dict = Depends(require_permission("visits:read")),
):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM visits WHERE id = ?", (visit_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")

        log_audit(
            user_id=current_user["id"], user_role=current_user["role"],
            action="READ", resource_type="visit", resource_id=visit_id,
            ip_address=request.client.host if request.client else None, success=True,
        )

        return _row_to_response(row)
    finally:
        conn.close()


@router.put("/{visit_id}", response_model=VisitResponse)
async def update_visit(
    visit_id: int,
    request: Request,
    visit_data: VisitUpdate,
    current_user: dict = Depends(require_permission("visits:update")),
):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM visits WHERE id = ?", (visit_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")

        update_data = visit_data.model_dump(exclude_unset=True)
        if not update_data:
            return _row_to_response(row)

        encrypted_fields = {"notes": "notes_enc", "diagnosis": "diagnosis_enc"}
        updates = {}
        for field, value in update_data.items():
            if field in encrypted_fields:
                updates[encrypted_fields[field]] = encrypt_phi(value) if value else None
            else:
                updates[field] = value
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [visit_id]
        conn.execute(f"UPDATE visits SET {set_clause} WHERE id = ?", values)
        conn.commit()

        row = conn.execute("SELECT * FROM visits WHERE id = ?", (visit_id,)).fetchone()
        return _row_to_response(row)
    finally:
        conn.close()


@router.post("/{visit_id}/cancel", response_model=VisitResponse)
async def cancel_visit(
    request: Request,
    visit_id: int,
    current_user: dict = Depends(require_permission("visits:update")),
):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        # Parameterized — no SQL injection here; the issue is the missing audit entry.
        conn.execute("UPDATE visits SET status = 'cancelled', updated_at = ? WHERE id = ?", (now, visit_id))
        conn.commit()
        row = conn.execute("SELECT * FROM visits WHERE id = ?", (visit_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")
        return _row_to_response(row)
    finally:
        conn.close()


@router.delete("/{visit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_visit(
    visit_id: int,
    request: Request,
    current_user: dict = Depends(require_permission("visits:delete")),
):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM visits WHERE id = ?", (visit_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")

        now = datetime.now(timezone.utc).isoformat()
        conn.execute("UPDATE visits SET status = 'cancelled', updated_at = ? WHERE id = ?", (now, visit_id))
        conn.commit()

        log_audit(
            user_id=current_user["id"], user_role=current_user["role"],
            action="DELETE", resource_type="visit", resource_id=visit_id,
            ip_address=request.client.host if request.client else None, success=True,
        )
    finally:
        conn.close()


def _row_to_response(row) -> VisitResponse:
    return VisitResponse(
        id=row["id"], patient_id=row["patient_id"], provider_id=row["provider_id"],
        visit_date=row["visit_date"], chief_complaint=row["chief_complaint"],
        notes=decrypt_phi(row["notes_enc"]) if row["notes_enc"] else None,
        diagnosis=decrypt_phi(row["diagnosis_enc"]) if row["diagnosis_enc"] else None,
        status=row["status"], created_at=row["created_at"], updated_at=row["updated_at"],
    )
