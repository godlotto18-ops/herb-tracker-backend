import itertools
from sqlalchemy.orm import Session
from database import SessionLocal, Combination, engine, Base

# 1. 약초 데이터 정의 (S, C, B, A 그룹)
herbs = [
    # S그룹 (4점)
    {"name": '금향과', "group": 'S', "score": 4}, {"name": '빙백설화', "group": 'S', "score": 4},
    {"name": '월계엽', "group": 'S', "score": 4}, {"name": '철목영지', "group": 'S', "score": 4}, {"name": '홍련업화', "group": 'S', "score": 4},
    # C그룹 (3점)
    {"name": '권엽', "group": 'C', "score": 3}, {"name": '금양광초', "group": 'C', "score": 3},
    {"name": '옥향초', "group": 'C', "score": 3}, {"name": '인삼', "group": 'C', "score": 3},
    # B그룹 (2점)
    {"name": '백향초', "group": 'B', "score": 2}, {"name": '자운초', "group": 'B', "score": 2},
    {"name": '적주과', "group": 'B', "score": 2}, {"name": '황초', "group": 'B', "score": 2}, {"name": '흑성과', "group": 'B', "score": 2},
    # A그룹 (1점)
    {"name": '녹태', "group": 'A', "score": 1}, {"name": '민들레', "group": 'A', "score": 1},
    {"name": '생강', "group": 'A', "score": 1}, {"name": '영군버섯', "group": 'A', "score": 1}, {"name": '옥취엽', "group": 'A', "score": 1}
]

def generate_and_insert():
    # 혹시 테이블이 꼬였을 경우를 대비해 초기화 후 다시 생성
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db: Session = SessionLocal()
    combinations_to_add = []

    print("조합 계산 시작...")
    
    # 3개, 4개, 5개 조합 생성
    for count in [3, 4, 5]:
        for combo in itertools.combinations(herbs, count):
            # ID 만들기 (이름순 정렬 후 언더바로 연결)
            names = sorted([h["name"] for h in combo])
            combo_id = "_".join(names)
            
            # 총 점수 계산
            total_score = sum([h["score"] for h in combo])
            
            # DB 모델 객체 생성
            new_combo = Combination(
                id=combo_id,
                count=count,
                score=total_score,
                herbs=combo,  # JSON 형태로 리스트 바로 저장
                is_checked=False
            )
            combinations_to_add.append(new_combo)

    # 16,473개 한 번에 DB에 밀어넣기 (Bulk Insert)
    print(f"총 {len(combinations_to_add)}개의 조합을 DB에 저장합니다. 잠시만 기다려주세요...")
    db.bulk_save_objects(combinations_to_add)
    db.commit()
    db.close()
    print("✨ DB 저장 완료!")

if __name__ == "__main__":
    generate_and_insert()
