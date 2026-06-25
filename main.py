from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import SessionLocal, Combination

app = FastAPI()

# 1. CORS 설정 (내 컴퓨터의 HTML 파일에서 서버로 접근할 수 있게 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. DB 세션 관리 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 3. 클라이언트가 서버로 보낼 '체크 데이터' 패킷 구조체
class CheckRequest(BaseModel):
    combo_id: str
    is_checked: bool


# ==========================================
# 🟢 서버 상태 확인용 API
# ==========================================

@app.get("/")
def read_root():
    return {"message": "약초 조합 서버가 정상적으로 작동 중입니다!"}

@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total_count = db.query(Combination).count()
    return {"message": f"현재 DB에 {total_count}개의 약초 조합이 성공적으로 저장되어 있습니다."}


# ==========================================
# 🚀 프론트엔드 통신용 핵심 API
# ==========================================

# API 1: 전체 조합 데이터 불러오기
@app.get("/api/combinations")
def get_all_combinations(db: Session = Depends(get_db)):
    combinations = db.query(Combination).all()
    return combinations

# API 2: 특정 조합의 체크 상태 업데이트하기
@app.post("/api/check")
def update_check_status(req: CheckRequest, db: Session = Depends(get_db)):
    combo = db.query(Combination).filter(Combination.id == req.combo_id).first()
    
    if combo:
        combo.is_checked = req.is_checked  # 상태 업데이트
        db.commit()                        # DB에 저장
        return {"success": True, "combo_id": req.combo_id, "is_checked": req.is_checked}
    
    return {"success": False, "message": "해당 조합을 찾을 수 없습니다."}
