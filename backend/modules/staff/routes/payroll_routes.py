from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from modules.staff.controllers.payroll_controller import (
    process_payroll,
    get_payroll_history,
)
from modules.staff.schemas.payroll_schemas import PayrollRequest, PayrollResponse

router = APIRouter(prefix="/payrolls", tags=["Payroll"])


@router.post("/", response_model=PayrollResponse)
async def create_payroll(request: PayrollRequest, db: Session = Depends(get_db)):
    try:
        return await process_payroll(request, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{staff_id}/history")
async def get_staff_payroll_history(staff_id: int, db: Session = Depends(get_db)):
    try:
        return await get_payroll_history(staff_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
