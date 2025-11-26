import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from datetime import datetime

# ==========================================
# [설정] 파라미터
# ==========================================
TWITTER_CSV = "/Users/leejongmin/code/비모/twitter_merged_20251124_1832.csv"
MODEL_NAME = 'jhgan/ko-sroberta-multitask'  # 한국어 SBERT
SIMILARITY_THRESHOLD = 0.30  # Max-Similarity 기준이므로 약간 상향 조정

# 기술 도메인 정의 (카테고리별 상세화)
# 기술 도메인 정의 (카테고리별 상세화 - 6대 분야)
TECH_REFERENCE_TEXTS = [
    # 1. AI (인공지능)
    "인공지능 딥러닝 모델 학습 및 추론", 
    "자연어처리 NLP 거대언어모델 LLM 파인튜닝", 
    "생성형 AI 프롬프트 엔지니어링 및 RAG 구축",
    "컴퓨터 비전 객체 탐지 및 이미지 세그멘테이션", 
    "강화학습 에이전트 및 자율 의사결정 시스템",
    "트랜스포머 아키텍처 및 어텐션 메커니즘",
    "AI 모델 경량화 및 엣지 디바이스 배포",

    # 2. 로봇 (Robot)
    "휴머노이드 로봇 제어 및 보행 알고리즘", 
    "산업용 로봇 팔 자동화 및 협동 로봇", 
    "자율주행 로봇 SLAM 및 경로 계획",
    "로봇 운영체제 ROS2 및 미들웨어 개발", 
    "드론 비행 제어 및 군집 비행 기술",
    "로봇 센서 퓨전 및 액추에이터 제어",

    # 3. 반도체 (Semiconductor)
    "시스템 반도체 설계 및 파운드리 공정 미세화", 
    "메모리 반도체 HBM 및 DDR5 성능 최적화", 
    "반도체 패키징 기술 및 3D 적층 공정",
    "NPU AI 가속기 및 GPU 아키텍처 설계", 
    "반도체 소자 물성 및 웨이퍼 수율 개선",
    "FPGA 프로그래밍 및 하드웨어 가속",

    # 4. 소프트웨어 (Software)
    "백엔드 마이크로서비스 아키텍처 및 API 게이트웨이", 
    "프론트엔드 리액트 상태 관리 및 성능 최적화", 
    "모바일 앱 플러터 크로스 플랫폼 개발",
    "데브옵스 CI/CD 파이프라인 및 컨테이너 오케스트레이션", 
    "객체지향 디자인 패턴 및 함수형 프로그래밍",
    "알고리즘 최적화 및 자료구조 효율성",
    "시스템 프로그래밍 및 커널 레벨 디버깅",

    # 5. 데이터 (Data)
    "빅데이터 분산 처리 및 데이터 파이프라인 구축", 
    "데이터 웨어하우스 및 데이터 레이크 아키텍처", 
    "SQL 쿼리 튜닝 및 NoSQL 데이터베이스 모델링",
    "데이터 시각화 대시보드 및 BI 분석", 
    "실시간 데이터 스트리밍 처리 및 카프카",
    "데이터 전처리 및 결측치 이상치 탐지",

    # 6. 클라우드 (Cloud)
    "클라우드 네이티브 아키텍처 및 서버리스 컴퓨팅", 
    "AWS Azure GCP 클라우드 인프라 관리", 
    "쿠버네티스 클러스터 운영 및 오토스케일링",
    "하이브리드 클라우드 및 멀티 클라우드 전략", 
    "클라우드 보안 및 IAM 권한 관리",
    "가상화 기술 및 도커 컨테이너 격리"
]

# 제외할 도메인 (노이즈 필터)
EXCLUDE_KEYWORDS = [
    # # 연예/엔터 (아이돌, 팬덤 관련 용어 강화)
    # '아이돌', '걸그룹', '보이그룹', '팬덤', '덕질', '오타쿠',
    # '콘서트', '팬미팅', '앨범', '활동', '컴백', '데뷔',
    # '팬싸', '팬싸인회', '영통', '무나', '양도', '교환', '포카', '럭드', '분철', '스밍', '총공',
    # '직캠', '프리뷰', '굿즈', '응원봉', '티켓팅', '첫방', '막방', '사녹', '공방',
    
    # # 스포츠
    # '야구', '축구', '농구', '배구', '골프', '경기',
    # '선수', '감독', '우승', '경기장', '시즌', '리그',
    
    # # 정치/사회 (단순 정치 언급 제외)
    # '대통령', '국회', '의원', '정당', '선거', '투표',
    # '정부', '장관', '청와대', '시위', '집회',
    
    # # 일상/잡담 (일상 용어 강화)
    # '먹방', '맛집', '카페', '여행', '패션', '뷰티',
    # '화장품', '옷', '쇼핑', 'MBTI', '별자리', '타로',
    # '오늘 점심', '퇴근', '출근', '일상', '셀카', '고양이', '강아지',
    
    # # 금융 (단순 코인 투기 제외, 기술적 블록체인은 허용)
    # '주가', '급등', '떡상', '떡락', '매수', '매도', '익절', '손절',
    # '대출', '보험', '적금', '예금', '부동산', '청약'
]

# ==========================================
# 1. 데이터 로드
# ==========================================
print("\n" + "="*60)
print("📊 [Step 1] 데이터 로드")
print("="*60)

df = pd.read_csv(TWITTER_CSV)
print(f"   -> 로드된 트윗: {len(df)}개")

# ==========================================
# 2. SBERT 모델 로드 및 레퍼런스 임베딩
# ==========================================
print("\n" + "="*60)
print("🧠 [Step 2] SBERT 모델 로드")
print("="*60)

print(f"   -> 모델: {MODEL_NAME}")
model = SentenceTransformer(MODEL_NAME)

print("   -> 기술 도메인 레퍼런스 임베딩 생성 중...")
tech_embeddings = model.encode(TECH_REFERENCE_TEXTS, show_progress_bar=False)
# 주의: 이제 Centroid(평균)를 쓰지 않고, 모든 레퍼런스 임베딩을 그대로 사용합니다.
# tech_embeddings shape: (N_references, Embedding_Dim)

print(f"   -> 기술 도메인 레퍼런스: {len(TECH_REFERENCE_TEXTS)}개 문장 (카테고리별 상세화 완료)\n")

# ==========================================
# 3. 트윗 필터링 (Max-Similarity 방식)
# ==========================================
print("="*60)
print("🔍 [Step 3] 기술 도메인 필터링 (Max-Similarity)")
print("="*60)

# 빠른 키워드 필터 (명백한 노이즈 제거)
print("   -> [1단계] 키워드 기반 필터링...")
def contains_exclude_keyword(text):
    if pd.isna(text):
        return True
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in EXCLUDE_KEYWORDS)

initial_count = len(df)
df = df[~df['text'].apply(contains_exclude_keyword)]
print(f"      제거됨: {initial_count - len(df)}개")
print(f"      남음: {len(df)}개")

# SBERT 유사도 필터
print("\n   -> [2단계] SBERT Max-Similarity 필터링...")
print("      (트윗이 '어떤 하나의 기술 주제'와라도 강하게 연결되면 통과)")

# 배치로 나눠서 처리 (메모리 절약)
batch_size = 100
max_similarities = []

for i in range(0, len(df), batch_size):
    batch_texts = df['text'].iloc[i:i+batch_size].tolist()
    batch_embeddings = model.encode(batch_texts, show_progress_bar=False)
    
    # 코사인 유사도 계산: (Batch_Size, N_References)
    # 각 트윗에 대해 모든 레퍼런스와의 유사도를 구함
    similarity_matrix = cosine_similarity(batch_embeddings, tech_embeddings)
    
    # 각 트윗별로 가장 높은 유사도 점수를 선택 (Max Pooling)
    batch_max_sims = np.max(similarity_matrix, axis=1)
    max_similarities.extend(batch_max_sims)
    
    if (i // batch_size + 1) % 5 == 0:
        print(f"      진행: {min(i+batch_size, len(df))}/{len(df)}")

df['tech_similarity'] = max_similarities

# 임계값 이상만 남기기
before_filter = len(df)
df_filtered = df[df['tech_similarity'] >= SIMILARITY_THRESHOLD].copy()
print(f"\n      제거됨: {before_filter - len(df_filtered)}개")
print(f"      최종: {len(df_filtered)}개 ({len(df_filtered)/initial_count*100:.1f}%)")

# ==========================================
# 4. 통계 분석
# ==========================================
print("\n" + "="*60)
print("📊 [Step 4] 필터링 통계")
print("="*60)

print(f"\n유사도 분포:")
print(f"   - 평균: {df_filtered['tech_similarity'].mean():.3f}")
print(f"   - 중앙값: {df_filtered['tech_similarity'].median():.3f}")
print(f"   - 최소: {df_filtered['tech_similarity'].min():.3f}")
print(f"   - 최대: {df_filtered['tech_similarity'].max():.3f}")

# 상위/하위 예시
print(f"\n🔝 기술 도메인 유사도 HIGH (상위 5개):")
top_5 = df_filtered.nlargest(5, 'tech_similarity')
for idx, row in top_5.iterrows():
    print(f"   [{row['tech_similarity']:.3f}] {row['text'][:80]}...")

print(f"\n🔻 기술 도메인 유사도 LOW (하위 5개):")
bottom_5 = df_filtered.nsmallest(5, 'tech_similarity')
for idx, row in bottom_5.iterrows():
    print(f"   [{row['tech_similarity']:.3f}] {row['text'][:80]}...")

# ==========================================
# 5. 저장
# ==========================================
print("\n" + "="*60)
print("💾 [Step 5] 결과 저장")
print("="*60)

timestamp = datetime.now().strftime('%Y%m%d_%H%M')
output_filename = f"twitter_tech_filtered_{timestamp}.csv"

# 유사도 점수도 함께 저장
df_filtered.to_csv(output_filename, index=False, encoding='utf-8-sig')

print(f"   -> 저장 완료: {output_filename}")
print(f"   -> 필터링 전: {initial_count}개")
print(f"   -> 필터링 후: {len(df_filtered)}개")
print(f"   -> 보존율: {len(df_filtered)/initial_count*100:.1f}%")

print("\n" + "="*60)
print("🎉 기술 도메인 필터링 완료!")
print("="*60)

print(f"\n💡 임계값 조정:")
print(f"   - 현재: {SIMILARITY_THRESHOLD}")
print(f"   - 더 엄격하게: 0.4~0.5 (기술 트윗만)")
print(f"   - 더 느슨하게: 0.2~0.3 (기술 주변 포함)")
