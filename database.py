from sqlalchemy import create_engine, Column, String, Integer, Boolean, JSON, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

SQLALCHEMY_DATABASE_URL = "postgresql://herb_tracker_db_user:FAFbi8GVphfhMdJXD7LPH6NvWwK1dasj@dpg-d8ukf4btqb8s73bcoa5g-a.singapore-postgres.render.com/herb_tracker_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 조합 테이블
class Combination(Base):
    __tablename__ = "combinations"

    id = Column(String, primary_key=True, index=True)
    count = Column(Integer)
    score = Column(Integer)
    herbs = Column(JSON)
    is_checked = Column(Boolean, default=False)
    last_modified_by = Column(String, nullable=True) # 🌟 추가됨: 마지막 수정자 닉네임

# 변경 로그 테이블 (복구용)
class ChangeLog(Base):
    __tablename__ = "change_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    combo_id = Column(String, index=True)
    action = Column(String) # CHECK / UNCHECK / ROLLBACK
    nickname = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow) # 🌟 추가됨: 로그 생성 시간

Base.metadata.create_all(bind=engine)
