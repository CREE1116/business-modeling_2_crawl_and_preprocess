import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from datetime import datetime

# ==========================================
# [설정] 파라미터
# ==========================================
YOUTUBE_CSV = "/Users/leejongmin/code/비모/data/youtube/youtube_merged_20251124_1919.csv"
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
    
    # 일상/잡담
    '먹방', '맛집', '카페', '여행', '패션', '뷰티',
    '화장품', '옷', '쇼핑', 'MBTI', '별자리',
    
    # 금융/투자 (기술 제외)
    '주가', '코인', '비트코인', '투자', '펀드',
    '대출', '보험', '적금', '예금', '부동산',
]

# ==========================================
# 1. 데이터 로드
# ==========================================
print("\n" + "="*60)
print("📊 [Step 1] 데이터 로드")
print("="*60)

df = pd.read_csv(YOUTUBE_CSV)
print(f"   -> 로드된 행: {len(df)}개 (영상 + 댓글)")

# 고유 영상 제목만 추출 (필터링용)
print("   -> 고유 영상 제목 추출 중...")
unique_titles = df['video_title'].drop_duplicates().tolist()
print(f"   -> 고유 영상: {len(unique_titles)}개\n")

# ==========================================
# 2. SBERT 모델 로드 및 레퍼런스 임베딩
# ==========================================
print("="*60)
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
# 3. 영상 제목 필터링
# ==========================================
print("="*60)
print("🔍 [Step 3] 기술 도메인 필터링 (영상 제목 기준)")
print("="*60)

# 빠른 키워드 필터 (명백한 노이즈 제거)
print("   -> [1단계] 키워드 기반 필터링...")
def contains_exclude_keyword(text):
    if pd.isna(text):
        return True
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in EXCLUDE_KEYWORDS)

initial_count = len(unique_titles)
filtered_titles = [title for title in unique_titles if not contains_exclude_keyword(title)]
print(f"      제거됨: {initial_count - len(filtered_titles)}개")
print(f"      남음: {len(filtered_titles)}개")

# SBERT 유사도 필터
print("\n   -> [2단계] SBERT 유사도 필터링...")
print("      (영상 제목 임베딩 생성 중...)")

# 배치로 나눠서 처리
batch_size = 100
title_similarities = {}

for i in range(0, len(filtered_titles), batch_size):
    batch_titles = filtered_titles[i:i+batch_size]
    batch_embeddings = model.encode(batch_titles, show_progress_bar=False)
    batch_sims = cosine_similarity(batch_embeddings, tech_centroid).flatten()
    
    for title, sim in zip(batch_titles, batch_sims):
        title_similarities[title] = sim
    
    if (i // batch_size + 1) % 5 == 0:
        print(f"      진행: {min(i+batch_size, len(filtered_titles))}/{len(filtered_titles)}")

# 임계값 이상만 남기기
tech_titles = {title for title, sim in title_similarities.items() if sim >= SIMILARITY_THRESHOLD}
print(f"\n      제거됨: {len(filtered_titles) - len(tech_titles)}개")
print(f"      최종: {len(tech_titles)}개 영상 ({len(tech_titles)/initial_count*100:.1f}%)")

# ==========================================
# 4. 원본 데이터와 병합 (모든 댓글 포함)
# ==========================================
print("\n" + "="*60)
print("🔀 [Step 4] 원본 데이터와 병합 (댓글 포함)")
print("="*60)

# 원본 데이터에서 기술 영상에 대한 모든 행(댓글 포함) 필터링
df_final = df[df['video_title'].isin(tech_titles)].copy()

# 유사도 점수 병합
df_final['tech_similarity'] = df_final['video_title'].map(title_similarities)

print(f"   -> 최종 데이터: {len(df_final)}개 행 (영상 + 댓글)")
print(f"   -> 필터링된 영상: {len(tech_titles)}개")
print(f"   -> 평균 댓글수: {len(df_final) / len(tech_titles):.1f}개/영상\n")

# ==========================================
# 5. 통계 분석
# ==========================================
print("="*60)
print("📊 [Step 5] 필터링 통계")
print("="*60)

tech_sims = list(title_similarities.values())
print(f"\n유사도 분포:")
print(f"   - 평균: {np.mean(tech_sims):.3f}")
print(f"   - 중앙값: {np.median(tech_sims):.3f}")
print(f"   - 최소: {np.min(tech_sims):.3f}")
print(f"   - 최대: {np.max(tech_sims):.3f}")

# 상위/하위 예시
sorted_titles = sorted(title_similarities.items(), key=lambda x: x[1], reverse=True)
print(f"\n🔝 기술 도메인 유사도 HIGH (상위 5개):")
for title, sim in sorted_titles[:5]:
    print(f"   [{sim:.3f}] {title[:80]}...")

print(f"\n🔻 기술 도메인 유사도 LOW (하위 5개):")
for title, sim in sorted_titles[-5:]:
    print(f"   [{sim:.3f}] {title[:80]}...")

# ==========================================
# 6. 저장
# ==========================================
print("\n" + "="*60)
print("💾 [Step 6] 결과 저장")
print("="*60)

timestamp = datetime.now().strftime('%Y%m%d_%H%M')
output_filename = f"youtube_tech_filtered_{timestamp}.csv"

# 유사도 점수도 함께 저장
df_final.to_csv(output_filename, index=False, encoding='utf-8-sig')

print(f"   -> 저장 완료: {output_filename}")
print(f"   -> 필터링 전: {initial_count}개 영상")
print(f"   -> 필터링 후: {len(tech_titles)}개 영상")
print(f"   -> 전체 행수: {len(df_final)}개 (댓글 포함)")
print(f"   -> 보존율: {len(tech_titles)/initial_count*100:.1f}%")

print("\n" + "="*60)
print("🎉 기술 도메인 필터링 완료!")
print("="*60)

print(f"\n💡 임계값 조정:")
print(f"   - 현재: {SIMILARITY_THRESHOLD}")
print(f"   - 더 엄격하게: 0.4~0.5 (순수 기술 영상만)")
print(f"   - 더 느슨하게: 0.2~0.3 (기술 주변 포함)")
