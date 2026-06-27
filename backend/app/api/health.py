from app.db.database import get_db
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/db")
def db_health(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT current_database();")).scalar()
    return {
        "status": "ok",
        "database": result,
    }
