from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import database

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 클라이언트 요청 데이터 구조 정의
class CheckRequest(BaseModel):
    combo_id: str
    is_checked: bool
    nickname: str               # 🌟 유저 닉네임 필수화
    admin_token: Optional[str] = None # 🌟 관리자 인증 토큰 (옵션)

@app.get("/api/combinations")
def get_combinations(db: Session = Depends(get_db)):
    # 데이터 조회 시 수정자 정보도 함께 내려갑니다.
    combos = db.query(database.Combination).all()
    return combos

@app.post("/api/check")
def update_check_status(req: CheckRequest, db: Session = Depends(get_db)):
    ADMIN_TOKEN = "hanwol123" # 🌟 나만 사용할 관리자 비밀번호
    is_admin = (req.admin_token == ADMIN_TOKEN)

    combo = db.query(database.Combination).filter(database.Combination.id == req.combo_id).first()
    if not combo:
        raise HTTPException(status_code=404, detail="조합을 찾을 수 없습니다.")

    # 🛑 [권한 검사] 체크를 해제(False) 하려고 할 때
    if not req.is_checked:
        # 관리자도 아니고, 마지막으로 체크한 사람의 닉네임과 현재 요청한 사람의 닉네임이 다르면 거부
        if not is_admin and combo.last_modified_by != req.nickname:
            return {
                "success": False, 
                "message": f"이 항목은 '{combo.last_modified_by}'님이 체크했습니다. 본인이 체크한 항목만 해제할 수 있습니다."
            }

    # 갱신 처리
    combo.is_checked = req.is_checked
    # 체크될 때만 닉네임을 남기고, 완전히 해제되면 수정한 사람 이름을 비웁니다.
    combo.last_modified_by = req.nickname if req.is_checked else None
    
    # 📝 [로그 기록] 어떤 유저가 어떤 행동을 했는지 영구 저장
    action_type = "CHECK" if req.is_checked else "UNCHECK"
    log_entry = database.ChangeLog(
        combo_id=req.combo_id,
        action=action_type,
        nickname=req.nickname
    )
    db.add(log_entry)
    db.commit()

    return {
        "success": True, 
        "combo_id": req.combo_id, 
        "is_checked": req.is_checked, 
        "last_modified_by": combo.last_modified_by
    }

# 🛠️ [로그 기반 롤백 엔드포인트] 관리자가 문제 발생 시 최근 기록을 취소하는 기능
@app.post("/api/rollback/latest")
def rollback_latest_action(admin_token: str, db: Session = Depends(get_db)):
    if admin_token != "hanwol123":
        raise HTTPException(status_code=403, detail="관리자 권한이 없습니다.")
    
    # 가장 최근의 정상 액션 로그 가져오기 (이미 복구된 건 제외)
    latest_log = db.query(database.ChangeLog).filter(~database.ChangeLog.action.like("ROLLBACK%")).order_by(database.ChangeLog.timestamp.desc()).first()
    if not latest_log:
        return {"success": False, "message": "되돌릴 로그 기록이 없습니다."}
    
    combo = db.query(database.Combination).filter(database.Combination.id == latest_log.combo_id).first()
    if combo:
        # 정반대 상태로 복구
        if latest_log.action == "CHECK":
            combo.is_checked = False
            combo.last_modified_by = None
        else:
            combo.is_checked = True
            combo.last_modified_by = latest_log.nickname
            
        # 롤백 완료 로그 남기기
        rollback_log = database.ChangeLog(
            combo_id=latest_log.combo_id,
            action=f"ROLLBACK_{latest_log.id}",
            nickname="ADMIN_SYSTEM"
        )
        db.add(rollback_log)
        db.commit()
        return {"success": True, "message": f"[{latest_log.nickname}]님의 최근 행동({latest_log.action})을 되돌렸습니다. 대상 ID: {latest_log.combo_id}"}
    
    return {"success": False, "message": "조합을 찾을 수 없습니다."}
