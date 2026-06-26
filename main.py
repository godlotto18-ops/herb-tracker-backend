import os
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

class RollbackRequest(BaseModel):
    log_id: int
    admin_token: str

@app.get("/api/combinations")
def get_combinations():
    if not engine: raise HTTPException(status_code=500, detail="DB URL Error")
    db = SessionLocal()
    try:
        query = text("SELECT id, herbs, count, is_checked, last_modified_by, result_text FROM combinations ORDER BY count ASC")
        return [dict(row) for row in db.execute(query).mappings().all()]
    finally:
        db.close()

@app.get("/api/logs")
def get_logs():
    db = SessionLocal()
    try:
        # 로그 데이터와 함께 고유 id도 가져옵니다.
        query = text("""
            SELECT l.id as log_id, l.action, l.nickname, l.timestamp, c.herbs 
            FROM change_logs l
            JOIN combinations c ON l.combo_id = c.id
            ORDER BY l.timestamp DESC 
            LIMIT 200
        """)
        return [dict(row) for row in db.execute(query).mappings().all()]
    finally:
        db.close()

@app.post("/api/check")
def update_combination(req: CheckRequest):
    db = SessionLocal()
    try:
        modifier = "관리자" if req.admin_token == "hanwol123" else req.nickname

        # 1. 🌟 현재 상태 가져오기 (스냅샷 저장용)
        current = db.execute(text("SELECT is_checked, result_text, last_modified_by FROM combinations WHERE id = :id"), {"id": req.combo_id}).mappings().first()
        prev_is_checked = current["is_checked"] if current else False
        prev_result_text = current["result_text"] if current else ""
        prev_modifier = current["last_modified_by"] if current else ""

        # 2. 데이터 업데이트
        update_query = text("""
            UPDATE combinations 
            SET is_checked = :is_checked, last_modified_by = :modifier, result_text = :result_text
            WHERE id = :combo_id
        """)
        db.execute(update_query, {
            "is_checked": req.is_checked, "modifier": modifier, 
            "result_text": req.result_text, "combo_id": req.combo_id
        })

        # 3. 🌟 로그와 함께 과거 상태(스냅샷) 저장
        log_query = text("""
            INSERT INTO change_logs (combo_id, action, nickname, prev_is_checked, prev_result_text, prev_modifier) 
            VALUES (:combo_id, :action, :nickname, :prev, :prev_text, :prev_mod)
        """)
        db.execute(log_query, {
            "combo_id": req.combo_id, "action": "체크" if req.is_checked else "체크해제", "nickname": modifier,
            "prev": prev_is_checked, "prev_text": prev_result_text, "prev_mod": prev_modifier
        })

        db.commit()
        return {"success": True, "last_modified_by": modifier}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# 🌟 새로운 엔드포인트: 롤백 기능
@app.post("/api/rollback")
def rollback_change(req: RollbackRequest):
    if req.admin_token != "hanwol123":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    
    db = SessionLocal()
    try:
        # 1. 로그에서 과거 스냅샷 데이터 꺼내오기
        log = db.execute(text("SELECT combo_id, prev_is_checked, prev_result_text, prev_modifier FROM change_logs WHERE id = :log_id"), {"log_id": req.log_id}).mappings().first()
        
        if not log:
            raise HTTPException(status_code=404, detail="로그를 찾을 수 없습니다.")

        # 2. 과거 상태로 덮어쓰기 (롤백)
        db.execute(text("""
            UPDATE combinations 
            SET is_checked = :is_checked, result_text = :result_text, last_modified_by = :modifier
            WHERE id = :combo_id
        """), {
            "is_checked": log["prev_is_checked"],
            "result_text": log["prev_result_text"],
            "modifier": log["prev_modifier"],
            "combo_id": log["combo_id"]
        })
        
        # 3. 롤백을 했다는 기록 남기기
        db.execute(text("INSERT INTO change_logs (combo_id, action, nickname) VALUES (:combo_id, '복구(롤백)', '관리자')"), {"combo_id": log["combo_id"]})
        
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
