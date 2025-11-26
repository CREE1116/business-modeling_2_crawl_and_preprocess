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
SIMILARITY_THRESHOLD = 0.2  # 임계값 (0~1, 높을수록 엄격)

# 기술 도메인 정의 (레퍼런스 문장들)
TECH_REFERENCE_TEXTS = [
    # AI/ML 계열 (10개)
    "인공지능 기술 개발 머신러닝",
    "딥러닝 신경망 학습",
    "머신러닝 알고리즘 최적화",
    "자연어처리 NLP 모델",
    "컴퓨터 비전 이미지 인식",
    "강화학습 에이전트 학습",
    "생성형 AI GPT LLM",
    "추천 시스템 협업 필터링",
    "AI 모델 파인튜닝 배포",
    "오토ML 하이퍼파라미터 튜닝",
    
    # 소프트웨어 개발 (10개)
    "소프트웨어 프로그래밍 코딩",
    "프론트엔드 리액트 뷰 개발",
    "백엔드 서버 API 개발",
    "풀스택 개발자 기술스택",
    "객체지향 디자인 패턴",
    "함수형 프로그래밍 람다",
    "마이크로서비스 아키텍처",
    "RESTful API GraphQL 설계",
    "테스트 주도 개발 TDD",
    "코드 리뷰 페어 프로그래밍",
    
    # 데이터 & 분석 (8개)
    "데이터 사이언스 분석 시각화",
    "빅데이터 처리 하둡 스파크",
    "데이터 파이프라인 ETL",
    "데이터베이스 최적화 인덱싱",
    "SQL NoSQL 쿼리 최적화",
    "실시간 스트리밍 카프카",
    "데이터 웨어하우스 레이크",
    "BI 대시보드 태블로",
    
    # 클라우드 & 인프라 (8개)
    "클라우드 컴퓨팅 AWS 애저",
    "쿠버네티스 도커 컨테이너",
    "DevOps CI/CD 파이프라인",
    "인프라 as 코드 테라폼",
    "서버리스 람다 함수",
    "클라우드 네이티브 아키텍처",
    "로드밸런싱 오토스케일링",
    "모니터링 로깅 프로메테우스",
    
    # 보안 & 네트워크 (6개)
    "사이버 보안 해킹 방어",
    "제로트러스트 보안 모델",
    "암호화 인증 OAuth",
    "침투 테스트 취약점 분석",
    "5G 네트워크 통신",
    "VPN 방화벽 네트워크 보안",
    
    # 신기술 & 하드웨어 (8개)
    "블록체인 암호화폐 NFT",
    "메타버스 VR AR XR",
    "양자컴퓨팅 큐비트",
    "반도체 칩 설계 제조",
    "자율주행 센서 퓨전",
    "로봇 자동화 RPA",
    "IoT 센서 엣지 컴퓨팅",
    "드론 기술 제어 시스템"
]


# 제외할 도메인 (노이즈 필터)
EXCLUDE_KEYWORDS = [
    # # 연예/엔터
    # '아이돌', '걸그룹', '보이그룹', '팬덤', '덕질', '오타쿠',
    # '콘서트', '팬미팅', '앨범', '활동', '컴백', '데뷔',
    
    # # 스포츠
    # '야구', '축구', '농구', '배구', '골프', '경기',
    # '선수', '감독', '우승', '경기장', '시즌',
    
    # # 정치/사회
    # '대통령', '국회', '의원', '정당', '선거', '투표',
    
    # # 일상/잡담
    # '먹방', '맛집', '카페', '여행', '패션', '뷰티',
    # '화장품', '옷', '쇼핑', 'MBTI', '별자리',
    
    # # 금융/투자 (기술 제외)
    # '주가', '코인', '비트코인', '투자', '펀드',
    # '대출', '보험', '적금', '예금', '부동산',
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
