import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from datetime import datetime

# ==========================================
# [설정] 파라미터
# ==========================================
TWITTER_CSV = "/Users/leejongmin/code/비모/data/twitter/twitter_clean_data_20251124_1341.csv"
MODEL_NAME = 'jhgan/ko-sroberta-multitask'  # 한국어 SBERT
SIMILARITY_THRESHOLD = 0.3  # 임계값 (0~1, 높을수록 엄격)

# 기술 도메인 정의 (레퍼런스 문장들)
TECH_REFERENCE_TEXTS = [
    "인공지능 기술 개발",
    "소프트웨어 프로그래밍",
    "데이터 사이언스 분석",
    "클라우드 컴퓨팅 서비스",
    "머신러닝 알고리즘",
    "프론트엔드 백엔드 개발",
    "데이터베이스 최적화",
    "사이버 보안 취약점",
    "모바일 앱 개발",
    "블록체인 기술",
    "IoT 센서 네트워크",
    "API 통합 구현",
    "DevOps CI/CD",
    "웹 서비스 아키텍처",
    "반도체 칩 설계",
    "자율주행 기술",
    "로봇 자동화",
    "5G 네트워크",
    "빅데이터 처리",
    "오픈소스 라이브러리"
]

# 제외할 도메인 (노이즈 필터)
EXCLUDE_KEYWORDS = [
    # 연예/엔터
    '아이돌', '걸그룹', '보이그룹', '팬덤', '덕질', '오타쿠',
    '콘서트', '팬미팅', '앨범', '활동', '컴백', '데뷔',
    
    # 스포츠
    '야구', '축구', '농구', '배구', '골프', '경기',
    '선수', '감독', '우승', '경기장', '시즌',
    
    # 정치/사회
    '대통령', '국회', '의원', '정당', '선거', '투표',
    '정부', '장관', '청와대',
    
    # 일상/잡담
    '먹방', '맛집', '카페', '여행', '패션', '뷰티',
    '화장품', '옷', '쇼핑', 'MBTI', '별자리',
    
    # 금융 (기술 제외)
    '주가', '코인', '비트코인', '투자', '펀드',
    '대출', '보험', '적금', '예금',
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
# 평균 임베딩 계산 (기술 도메인의 중심점)
tech_centroid = np.mean(tech_embeddings, axis=0).reshape(1, -1)

print(f"   -> 기술 도메인 레퍼런스: {len(TECH_REFERENCE_TEXTS)}개 문장\n")

# ==========================================
# 3. 트윗 필터링
# ==========================================
print("="*60)
print("🔍 [Step 3] 기술 도메인 필터링")
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
print("\n   -> [2단계] SBERT 유사도 필터링...")
print("      (트윗 임베딩 생성 중...)")

# 배치로 나눠서 처리 (메모리 절약)
batch_size = 100
similarities = []

for i in range(0, len(df), batch_size):
    batch_texts = df['text'].iloc[i:i+batch_size].tolist()
    batch_embeddings = model.encode(batch_texts, show_progress_bar=False)
    batch_similarities = cosine_similarity(batch_embeddings, tech_centroid).flatten()
    similarities.extend(batch_similarities)
    
    if (i // batch_size + 1) % 5 == 0:
        print(f"      진행: {min(i+batch_size, len(df))}/{len(df)}")

df['tech_similarity'] = similarities

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
