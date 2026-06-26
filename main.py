import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 1. 데이터베이스 연결 설정 (Render 환경 변수 사용)
DB_URL = os.getenv("DATABASE_URL")
# Render의 postgres:// 주소를 SQLAlchemy가 인식할 수 있는 postgresql:// 로 자동 변환
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

# DB 엔진 및 세션 생성
engine = create_engine(DB_URL, pool_pre_ping=True) if DB_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()

# 2. CORS 설정 (프론트엔드 연동)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 데이터 검증 모델 (🌟 result_text 추가됨)
class CheckRequest(BaseModel):
    combo_id: str
    is_checked: bool
    nickname: str
    admin_token: str = ""
    result_text: str = ""  # 프론트엔드에서 넘어오는 텍스트 결과값

# 4. API: 전체 약초 조합 데이터 불러오기
@app.get("/api/combinations")
def get_combinations():
    if not engine:
        raise HTTPException(status_code=500, detail="DB URL이 설정되지 않았습니다.")
        
    db = SessionLocal()
    try:
        # 🌟 DB에서 가져올 때 result_text 컬럼도 함께 불러옵니다.
        query = text("""
            SELECT id, herbs, count, is_checked, last_modified_by, result_text 
            FROM combinations
            ORDER BY count ASC
        """)
        result = db.execute(query).mappings().all()
        
        # 결과를 딕셔너리 리스트로 변환하여 프론트엔드로 전달
        return [dict(row) for row in result]
    except Exception as e:
        print(f"Error fetching data: {e}")
        raise HTTPException(status_code=500, detail="데이터를 불러오는 중 오류가 발생했습니다.")
    finally:
        db.close()

# 5. API: 체크 상태 및 결과 텍스트 업데이트
@app.post("/api/check")
def update_combination(req: CheckRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="DB URL이 설정되지 않았습니다.")

    db = SessionLocal()
    try:
        # 관리자 비밀번호 확인 (맞으면 '관리자', 아니면 유저 '닉네임'으로 저장)
        modifier = "관리자" if req.admin_token == "hanwol123" else req.nickname

        # 🌟 combinations 테이블 업데이트 (result_text 포함)
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

        # 누가 어떤 액션을 했는지 change_logs 테이블에 기록 남기기
        log_query = text("""
            INSERT INTO change_logs (combo_id, action, nickname) 
            VALUES (:combo_id, :action, :nickname)
        """)
        db.execute(log_query, {
            "combo_id": req.combo_id,
            "action": "check" if req.is_checked else "uncheck",
            "nickname": modifier
        })

        # 최종 저장(Commit)
        db.commit()

        # 프론트엔드에 성공 신호와 수정자 이름 반환
        return {"success": True, "last_modified_by": modifier}

    except Exception as e:
        db.rollback() # 에러가 나면 DB를 이전 상태로 되돌림
        print(f"Error updating data: {e}")
        raise HTTPException(status_code=500, detail="데이터 업데이트 중 오류가 발생했습니다.")
    finally:
        db.close()
