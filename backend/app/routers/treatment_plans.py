from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.database import get_db_connection
from app.schemas.treatment_plan import TreatmentPlanCreate, TreatmentPlanUpdate, TreatmentPlanResponse
from app.auth.rbac import require_permission

router = APIRouter(prefix="/treatment-plans", tags=["treatment-plans"])


@router.post("/", response_model=TreatmentPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_treatment_plan(
    request: Request,
    plan_data: TreatmentPlanCreate,
    current_user: dict = Depends(require_permission("treatments:create")),
):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        patient = conn.execute("SELECT id FROM patients WHERE id = ? AND is_active = 1", (plan_data.patient_id,)).fetchone()
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        cursor = conn.execute(
            """INSERT INTO treatment_plans (patient_id, provider_id, name, description, goals, notes, status, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                plan_data.patient_id, current_user["id"], plan_data.name,
                plan_data.description, plan_data.goals, plan_data.notes,
                plan_data.status or "active", now, now,
            ),
        )
        conn.commit()
        plan_id = cursor.lastrowid

        row = conn.execute("SELECT * FROM treatment_plans WHERE id = ?", (plan_id,)).fetchone()
        return _row_to_response(row)
    finally:
        conn.close()


@router.get("/", response_model=list[TreatmentPlanResponse])
async def list_treatment_plans(
    request: Request,
    patient_id: int = None,
    status_filter: str = None,
    current_user: dict = Depends(require_permission("treatments:read")),
):
    conn = get_db_connection()
    try:
        query = "SELECT * FROM treatment_plans WHERE is_active = 1"
        params = []
        if patient_id:
            query += " AND patient_id = ?"
            params.append(patient_id)
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)
        query += " ORDER BY id DESC"

        rows = conn.execute(query, params).fetchall()
        return [_row_to_response(row) for row in rows]
    finally:
        conn.close()


@router.get("/{plan_id}", response_model=TreatmentPlanResponse)
async def get_treatment_plan(
    plan_id: int,
    request: Request,
    current_user: dict = Depends(require_permission("treatments:read")),
):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM treatment_plans WHERE id = ? AND is_active = 1", (plan_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan not found")

        return _row_to_response(row)
    finally:
        conn.close()


@router.put("/{plan_id}", response_model=TreatmentPlanResponse)
async def update_treatment_plan(
    plan_id: int,
    request: Request,
    plan_data: TreatmentPlanUpdate,
    current_user: dict = Depends(require_permission("treatments:update")),
):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM treatment_plans WHERE id = ? AND is_active = 1", (plan_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan not found")

        update_data = plan_data.model_dump(exclude_unset=True)
        if not update_data:
            return _row_to_response(row)

        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in update_data)
        values = list(update_data.values()) + [plan_id]
        conn.execute(f"UPDATE treatment_plans SET {set_clause} WHERE id = ?", values)
        conn.commit()

        row = conn.execute("SELECT * FROM treatment_plans WHERE id = ?", (plan_id,)).fetchone()
        return _row_to_response(row)
    finally:
        conn.close()


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_treatment_plan(
    plan_id: int,
    request: Request,
    current_user: dict = Depends(require_permission("treatments:delete")),
):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM treatment_plans WHERE id = ? AND is_active = 1", (plan_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment plan not found")

        now = datetime.now(timezone.utc).isoformat()
        conn.execute("UPDATE treatment_plans SET is_active = 0, updated_at = ? WHERE id = ?", (now, plan_id))
        conn.commit()
    finally:
        conn.close()


def _row_to_response(row) -> TreatmentPlanResponse:
    return TreatmentPlanResponse(
        id=row["id"], patient_id=row["patient_id"], provider_id=row["provider_id"],
        name=row["name"], description=row["description"], goals=row["goals"],
        notes=row["notes"], status=row["status"], is_active=row["is_active"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )
