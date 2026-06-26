import os
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DB_URL = os.getenv("DATABASE_URL")
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DB_URL, pool_pre_ping=True) if DB_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CheckRequest(BaseModel):
    combo_id: str
    is_checked: bool
    nickname: str
    admin_token: str = ""
    result_text: str = ""

@app.get("/api/combinations")
def get_combinations():
    if not engine:
        raise HTTPException(status_code=500, detail="DB URL Error")

    db = SessionLocal()
    try:
        query = text("""
            SELECT id, herbs, count, is_checked, last_modified_by, result_text 
            FROM combinations
            ORDER BY count ASC
        """)
        result = db.execute(query).mappings().all()
        return [dict(row) for row in result]
    except Exception as e:
        # 🌟 에러를 억누르지 않고 화면과 로그에 강제로 뱉어냅니다.
        error_msg = traceback.format_exc()
        print("🚨 서버 내부 에러 상세 정보 🚨\n", error_msg, flush=True)
        raise HTTPException(status_code=500, detail=f"실제 에러 원인: {str(e)}")
    finally:
        db.close()

@app.post("/api/check")
def update_combination(req: CheckRequest):
    db = SessionLocal()
    try:
        modifier = "관리자" if req.admin_token == "hanwol123" else req.nickname

        update_query = text("""
            UPDATE combinations 
            SET is_checked = :is_checked, 
                last_modified_by = :modifier,
                result_text = :result_text
            WHERE id = :combo_id
        """)
        
        db.execute(update_query, {
            "is_checked": req.is_checked,
            "modifier": modifier,
            "result_text": req.result_text,
            "combo_id": req.combo_id
        })

        log_query = text("""
            INSERT INTO change_logs (combo_id, action, nickname) 
            VALUES (:combo_id, :action, :nickname)
        """)
        db.execute(log_query, {
            "combo_id": req.combo_id,
            "action": "check" if req.is_checked else "uncheck",
            "nickname": modifier
        })

        db.commit()
        return {"success": True, "last_modified_by": modifier}

    except Exception as e:
        db.rollback()
        error_msg = traceback.format_exc()
        print("🚨 서버 내부 에러 상세 정보 🚨\n", error_msg, flush=True)
        raise HTTPException(status_code=500, detail=f"실제 에러 원인: {str(e)}")
    finally:
        db.close()
