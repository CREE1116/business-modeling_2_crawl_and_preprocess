import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from datetime import datetime

# ==========================================
# [설정] 파라미터
# ==========================================
TWITTER_CSV = "/Users/leejongmin/code/비모/data/twitter/twitter_merged_20251212_1623.csv"
MODEL_NAME = 'jhgan/ko-sroberta-multitask'  # 한국어 SBERT
SIMILARITY_THRESHOLD = 0.5  # Max-Similarity 기준이므로 약간 상향 조정

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
    "프롬프트 엔지니어링을 통한 답변 퀄리티 강화",
    "AI 가중치 양자화를 통한 온 디바이스 AI 모델 배포",

    # 2. 로봇 (Robot)
    "휴머노이드 로봇 제어 및 보행 알고리즘", 
    "산업용 로봇 팔 자동화 및 협동 로봇", 
    "자율주행 로봇 SLAM 및 경로 계획",
    "로봇 운영체제 ROS2 및 미들웨어 개발", 
    "드론 비행 제어 및 군집 비행 기술",
    "로봇 센서 퓨전 및 액추에이터 제어",
    "이것이 진짜 완전 자율주행(Full Self-Driving)",

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

    #7. 네트워크
    "TCP/IP 네트워크 프로토콜 분석 및 패킷 트래픽 모니터링",
    "TLS 암호화 통신 및 인증서 기반 보안 모델 구축",
    "방화벽 WAF IDS IPS 기반 인프라 보안 정책 설계",
    "리눅스 서버 최적화 및 시스템 자원 관리",
    "VPN 터널링 및 기업 내부망 구축",
    "제로트러스트 아키텍처 및 접근 제어 정책",
    "취약점 스캐닝 및 보안 패치 자동화",

    #8. 데이터베이스
    "관계형 데이터베이스 스키마 설계 및 조인 최적화",
    "NoSQL 기반 분산 저장소 모델링 및 샤딩 전략",
    "Redis 캐싱 구조 및 세션 클러스터링",
    "Elasticsearch 인덱스 구성 및 검색 최적화",
    "OLAP OLTP 워크로드 기반 쿼리 튜닝",
    "트랜잭션 격리수준 및 락 경합 문제 해결",

    #9. 웹
    "리액트 훅 기반 상태 관리 및 서버 컴포넌트 렌더링",
    "Next.js 서버 액션 및 하이브리드 렌더링 구성",
    "SvelteKit 기반 웹 애플리케이션 라우팅",
    "TypeScript 기반 컴포넌트 아키텍처 설계",
    "웹 성능 최적화 및 번들 사이즈 감소",
    "SPA CSR SSR SSG 렌더링 전략 비교 분석",

    #10. 백엔드
    "NestJS 기반 API 서버 설계 및 모듈화 구조",
    "Spring Boot 마이크로서비스 분산 트랜잭션 처리",
    "Node.js 이벤트루프 및 비동기 처리 모델 분석",
    "Go 언어 기반 고성능 서버 및 고루틴 관리",
    "JWT OAuth2 기반 인증 및 인가 시스템 구축",
    "GRPC 프로토콜 버퍼 기반 서비스 통신",

    #11. 데브옵스
    "도커 이미지 빌드 및 멀티스테이지 최적화",
    "쿠버네티스 헬름 차트 배포 및 롤링 업데이트",
    "GitOps 흐름 ArgoCD를 통한 자동화 배포",
    "CI/CD 파이프라인 구축 및 테스트 자동화",
    "인프라 IaC Terraform 기반 환경 관리",
    "서비스 로그 수집 및 Prometheus 모니터링 구축",

    #12. 임베디드
    "STM32 임베디드 펌웨어 개발 및 RTOS 환경 구성",
    "라즈베리파이 기반 IoT 센서 데이터 수집",
    "CAN 통신 및 차량용 ECU 소프트웨어 구조",
    "저전력 BLE 통신 및 IoT 네트워크 설계",
    "임베디드 리눅스 커널 모듈 빌드 및 드라이버 개발",

    #13. 게임
    "유니티 엔진 기반 3D 게임 로직 구현",
    "언리얼 엔진 블루프린트 및 C++ 게임플레이 코드",
    "WebGL 셰이더 렌더링 및 GLSL 시각효과 개발",
    "VR XR 기반 모션 트래킹 및 공간 매핑",

    #14. 연구용 ai
    "딥러닝 실험 자동화 프레임워크 및 하이퍼파라미터 탐색",
    "트랜스포머 모델 내부 어텐션 헤드 분석",
    "모델 프루닝 및 Knowledge Distillation 압축",
    "Diffusion 모델 기반 이미지 생성 연구",
    "대규모 언어모델 학습 데이터 파이프라인 구축",

    #15. SRE
    "SLI SLO 기반 서비스 안정성 지표 설정",
    "Grafana 대시보드 구성 및 로그 분석",
    "OpenTelemetry 기반 분산 트레이싱 구축",
    "서비스 장애 대응 및 이상 탐지 시스템 구현"
]

# 제외할 도메인 (노이즈 필터)
EXCLUDE_KEYWORDS = [
    # # 연예/엔터 (아이돌, 팬덤 관련 용어 강화)
    '아이돌', '걸그룹', '보이그룹', '팬덤', '덕질', '오타쿠','멀티뷰','나우즈','#NOWZ','고화질테스트',
    '콘서트', '팬미팅', '앨범', '활동', '컴백', '데뷔',' 얼빡샷','존잘','NOWZ','프로미스나인','fromis_9','도경수','HEBI','HEESEUNG','캐스팅','NEXZ','NEXZ(넥스지)','₍ ‌ˆ•𖥦•ˆ ‌ ₎⟆'
    '팬싸', '팬싸인회', '영통', '무나', '양도', '포카', '럭드', '분철', '스밍', '총공','srchafreen','카르티스','한입먹힌정수리클럽','이승현','교차편집',
    '직캠', '굿즈', '응원봉', '티켓팅', '첫방', '막방', '사녹', '공방','포스북','트레저','마비노기','루진우','히어로','AgustD','슈가','멀티 ver','엔하이픈','#우즈',
    
    # 스포츠
    '야구', '축구', '농구', '배구', '골프', '경기',
    '선수', '감독', '우승', '경기장', '시즌', '리그',
    
    # 정치/사회 (단순 정치 언급 제외)
    '대통령', '국회', '의원', '정당', '선거', '투표','민주주의',
    '장관', '청와대', '시위', '집회', 'G20','공산주의','준숰',
    
    # 일상/잡담 (일상 용어 강화)
    '먹방', '맛집', '카페', '여행', '패션', '뷰티','뱀파이어','트릭컬','이세계','chzzk','카제나','jack_art','브러시','개지랄','붕스','코스프레','코스','어머어머','변태들','수탉이',',모바일판타지랑은','선구리곰도리','살생','인외'
    '화장품', '옷', '쇼핑', 'MBTI', '별자리', '타로','알피지',"RPG",'KIMYOHAN','웨이보','초호기바디','witchform','로프꾼','TRPG','주술회전','아츠프로텍터','P3R','DX3rd','개인화면','메탈카드봇','중성화',
    '오늘 점심', '퇴근', '출근', '일상', '셀카', '고양이', '강아지',"브이로그","투어",'트친소','CoC','지휘관','한문철','FC','earcleaning','젬니','LP판','손민수','천생연분','세대테스트',

    # 금융
    '리딩방', '수익률 보장', '최대 수익', '무료 상담', '토토', '홀덤', '바카라', 
    '카지노', '도박', '배팅'
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
