from sqlalchemy import create_engine, Column, String, Integer, Boolean, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

# 🌟 수정됨: 방금 알려주신 Render의 External Database URL
SQLALCHEMY_DATABASE_URL = "postgresql://herb_tracker_db_user:FAFbi8GVphfhMdJXD7LPH6NvWwK1dasj@dpg-d8ukf4btqb8s73bcoa5g-a.singapore-postgres.render.com/herb_tracker_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Combination(Base):
    __tablename__ = "combinations"

    id = Column(String, primary_key=True, index=True)
    count = Column(Integer)
    score = Column(Integer)
    herbs = Column(JSON)
    is_checked = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)
