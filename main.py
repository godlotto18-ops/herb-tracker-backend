import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DB_URL = os.getenv("DATABASE_URL")
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "hanwol123")

engine = create_engine(DB_URL, pool_pre_ping=True) if DB_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

if engine:
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE change_logs ADD COLUMN IF NOT EXISTS prev_is_checked BOOLEAN;"))
            conn.execute(text("ALTER TABLE change_logs ADD COLUMN IF NOT EXISTS prev_result_text TEXT;"))
            conn.execute(text("ALTER TABLE change_logs ADD COLUMN IF NOT EXISTS prev_modifier VARCHAR(255);"))
            conn.execute(text("ALTER TABLE combinations ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 0;"))
        print("DB 자동 패치 완료!")
    except Exception as e:
        print("DB 패치 오류:", e)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def read_root():
    return {"status": "ok"}

class CheckRequest(BaseModel):
    combo_id: str
    is_checked: bool
    nickname: str
    admin_token: str = ""
    result_text: str = ""
    version: int

class RollbackRequest(BaseModel):
    log_id: int
    admin_token: str
    combo_id: str
    version: int

@app.get("/api/combinations")
def get_combinations():
    db = SessionLocal()
    try:
        query = text("SELECT id, herbs, count, is_checked, last_modified_by, result_text, version FROM combinations ORDER BY count ASC")
        return [dict(row) for row in db.execute(query).mappings().all()]
    finally:
        db.close()

@app.get("/api/logs")
def get_logs():
    db = SessionLocal()
    try:
        # herbs, 변경 전/후 result_text, is_checked 모두 포함
        query = text("""
            SELECT
                cl.id as log_id,
                cl.action,
                cl.nickname,
                cl.timestamp,
                cl.combo_id,
                cl.prev_is_checked,
                cl.prev_result_text,
                cl.prev_modifier,
                c.herbs,
                c.result_text as current_result_text,
                c.is_checked as current_is_checked
            FROM change_logs cl
            LEFT JOIN combinations c ON cl.combo_id = c.id
            ORDER BY cl.timestamp DESC
            LIMIT 200
        """)
        return [dict(row) for row in db.execute(query).mappings().all()]
    except Exception as e:
        return {"error_details": str(e)}
    finally:
        db.close()

@app.post("/api/check")
def update_combination(req: CheckRequest):
    db = SessionLocal()
    try:
        modifier = "관리자" if req.admin_token == ADMIN_TOKEN else req.nickname
        current = db.execute(
            text("SELECT is_checked, result_text, last_modified_by, version FROM combinations WHERE id = :id"),
            {"id": req.combo_id}
        ).mappings().first()

        if not current:
            raise HTTPException(status_code=404, detail="조합 없음")
        if current["version"] != req.version:
            raise HTTPException(status_code=409, detail="데이터 변경됨. 페이지를 새로고침 후 다시 시도해주세요.")

        db.execute(
            text("""
                UPDATE combinations
                SET is_checked = :is_checked, last_modified_by = :modifier, result_text = :result_text, version = version + 1
                WHERE id = :combo_id
            """),
            {"is_checked": req.is_checked, "modifier": modifier, "result_text": req.result_text, "combo_id": req.combo_id}
        )
        db.execute(
            text("""
                INSERT INTO change_logs (combo_id, action, nickname, prev_is_checked, prev_result_text, prev_modifier, timestamp)
                VALUES (:combo_id, :action, :nickname, :prev, :prev_text, :prev_mod, NOW() AT TIME ZONE 'Asia/Seoul')
            """),
            {
                "combo_id": req.combo_id,
                "action": "체크" if req.is_checked else "체크해제",
                "nickname": modifier,
                "prev": current["is_checked"],
                "prev_text": current["result_text"],
                "prev_mod": current["last_modified_by"]
            }
        )
        db.commit()
        return {"success": True}
    finally:
        db.close()

@app.post("/api/rollback")
def rollback_change(req: RollbackRequest):
    if req.admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="권한 없음")
    db = SessionLocal()
    try:
        log = db.execute(
            text("SELECT id, combo_id, prev_is_checked, prev_result_text, prev_modifier, timestamp FROM change_logs WHERE id = :log_id"),
            {"log_id": req.log_id}
        ).mappings().first()

        if not log:
            raise HTTPException(status_code=404, detail="로그 없음")

        current = db.execute(
            text("SELECT version FROM combinations WHERE id = :id"),
            {"id": req.combo_id}
        ).mappings().first()

        if not current:
            raise HTTPException(status_code=404, detail="조합 없음")
        if current["version"] != req.version:
            raise HTTPException(status_code=409, detail="데이터 변경됨. 페이지를 새로고침 후 다시 시도해주세요.")

        db.execute(
            text("""
                UPDATE combinations
                SET is_checked = :is_checked, result_text = :result_text, last_modified_by = :modifier, version = version + 1
                WHERE id = :combo_id
            """),
            {
                "is_checked": log["prev_is_checked"],
                "result_text": log["prev_result_text"],
                "modifier": log["prev_modifier"],
                "combo_id": log["combo_id"]
            }
        )

        # 해당 로그 시점 이후의 로그 삭제 (같은 combo_id 한정)
        db.execute(
            text("""
                DELETE FROM change_logs
                WHERE combo_id = :combo_id
                AND timestamp >= :log_timestamp
            """),
            {"combo_id": log["combo_id"], "log_timestamp": log["timestamp"]}
        )

        db.commit()
        return {"success": True}
    finally:
        db.close()
