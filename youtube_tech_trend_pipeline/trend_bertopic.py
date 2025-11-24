import requests
import xml.etree.ElementTree as ET
import pandas as pd
import os
from datetime import datetime
from kiwipiepy import Kiwi

# BERTopic 관련
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from umap import UMAP
from hdbscan import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer

# ==========================================
# [설정] 파라미터
# ==========================================
MIN_CLUSTER_SIZE = 5        # HDBSCAN 최소 클러스터 크기
MIN_SAMPLES = 3             # HDBSCAN 최소 샘플 수
KEYWORDS_PER_TOPIC = 10     # 토픽당 키워드 개수
MODEL_NAME = 'jhgan/ko-sroberta-multitask'  # 한국어 SBERT

# 불용어
STOPWORDS = [
    # 일반 불용어
    '뉴스', '속보', '단독', '오늘', '어제', '내일', '발표', '공개',
    '영상', '논란', '이유', '충격', '결국', '진짜', '근황', '예정',
    '관련', '특징', '가장', '대해', '위해', '통해', '때문', '경우',
    '정도', '최근', '지금', '무엇', '어떻게', '다시', '계속', '종합',
    '정답', '퀴즈', '문제', '이벤트', '당첨', '참가',
    '이거', '저거', '그거', '뭐임', '개념', '생각', '사람',
    '진짜', '정말', '매우', '너무', '완전', '대박', '헐', '와',
    '댓글', '추천', '비추', '신고', '삭제', '차단',
    
    # 회사명/서비스명 (기술 블로그 출처)
    '뱅크', '뱅크샐러드', '샐러드', '뱅크 샐러드',
    '컬리', '마켓컬리', '헬로우 컬리',
    '데브시스터즈',
    '쿠키런', '킹덤', '쿠키런 킹덤',
    '리디', '리디북스',
    '토스', '비바리퍼블리카',
    '당근', '당근마켓',
    '직방',
    '왓챠', '왓챠플레이',
    '쏘카',
    '요기요',
    '무신사',
    '하이퍼커넥트',
    '네이버', 'd2',
    '라인', 'line',
    '쿠팡',
    'nhn',
    'kurly',
    'toss',
]

# Kiwi 초기화
try:
    kiwi = Kiwi()
    kiwi.add_user_word("제미나이", "NNP")
    kiwi.add_user_word("챗GPT", "NNP")
    kiwi.add_user_word("바이브코딩", "NNP")
    print("[System] Kiwi 로드 성공")
except:
    kiwi = None
    print("[System] Kiwi 로드 실패")

# ==========================================
# 1. 데이터 수집
# ==========================================
def collect_data():
    print("\n" + "="*60)
    print("📡 [Phase 1] 데이터 수집 (기술 블로그 RSS)")
    print("="*60)
    
    raw_data = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 뉴스 RSS
    news_rss = [
        ('긱뉴스', 'https://feeds.feedburner.com/geeknews-feed'),
    ]
    
    # 한국 IT 기업 기술 블로그 RSS
    tech_blog_rss = [
        ('무신사', 'https://medium.com/feed/musinsa-tech'),
        ('네이버 D2', 'https://d2.naver.com/d2.atom'),
        ('마켓컬리', 'https://helloworld.kurly.com/feed.xml'),
        ('우아한형제들', 'https://techblog.woowahan.com/feed'),
        ('카카오엔터', 'https://tech.kakaoenterprise.com/feed'),
        ('데브시스터즈', 'https://tech.devsisters.com/rss.xml'),
        ('라인', 'https://engineering.linecorp.com/ko/feed/index.html'),
        ('쿠팡', 'https://medium.com/feed/coupang-engineering'),
        ('당근마켓', 'https://medium.com/feed/daangn'),
        ('토스', 'https://toss.tech/rss.xml'),
        ('직방', 'https://medium.com/feed/zigbang'),
        ('왓챠', 'https://medium.com/feed/watcha'),
        ('뱅크샐러드', 'https://blog.banksalad.com/rss.xml'),
        ('Hyperconnect', 'https://hyperconnect.github.io/feed.xml'),
        ('요기요', 'https://techblog.yogiyo.co.kr/feed'),
        ('쏘카', 'https://tech.socarcorp.kr/feed'),
        ('리디', 'https://www.ridicorp.com/feed'),
        ('NHN Toast', 'https://meetup.toast.com/rss'),
        ('Velog', 'https://v2.velog.io/rss/'),
        ('개발자스럽다', 'https://blog.gaerae.com/feeds/posts/default?alt=rss'),
        ('44BITS', 'https://www.44bits.io/ko/feed/all'),
    ]
    
    all_rss = news_rss + tech_blog_rss
    
    print("   -> RSS 수집 중...")
    for name, url in all_rss:
        try:
            res = requests.get(url, headers=headers, timeout=10)
            root = ET.fromstring(res.content)
            count = 0
            
            # Atom 형식
            if any(x in url for x in ['geeknews', 'd2.naver', 'hyperconnect']):
                for item in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                    try:
                        title_elem = item.find("{http://www.w3.org/2005/Atom}title")
                        if title_elem is not None and title_elem.text:
                            raw_data.append(title_elem.text)
                            count += 1
                    except: pass
            
            # RSS 2.0 형식
            if count == 0:
                for item in root.findall(".//item"):
                    try:
                        title_elem = item.find("title")
                        if title_elem is not None and title_elem.text:
                            raw_data.append(title_elem.text)
                            count += 1
                    except: pass
            
            if count > 0:
                print(f"      -> {name}: {count}개")
        except:
            pass
    
    unique_data = list(set(raw_data))
    print(f"   -> 총 {len(unique_data)}개 문장 확보.\n")
    return unique_data

# ==========================================
# 2. BERTopic 분석
# ==========================================
def extract_keywords_with_bertopic(documents):
    print("="*60)
    print("🧠 [Phase 2] BERTopic 분석")
    print("="*60)
    
    # 1. SBERT 모델 로드
    print(f"   -> 모델 로드: {MODEL_NAME}")
    embedding_model = SentenceTransformer(MODEL_NAME)
    
    # 2. UMAP 차원 축소 설정
    print("   -> UMAP 차원 축소 설정")
    umap_model = UMAP(
        n_neighbors=15,
        n_components=5,
        min_dist=0.0,
        metric='cosine',
        random_state=42
    )
    
    # 3. HDBSCAN 클러스터링 설정
    print("   -> HDBSCAN 클러스터링 설정")
    hdbscan_model = HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=MIN_SAMPLES,
        metric='euclidean',
        cluster_selection_method='eom',
        prediction_data=True
    )
    
    # 4. CountVectorizer 설정 (한국어)
    if kiwi:
        def korean_tokenizer(text):
            tokens = kiwi.tokenize(text)
            return [
                token.form for token in tokens
                if token.tag in ['NNG', 'NNP', 'SL', 'SH']  # 명사, 외래어, 영어
                and len(token.form) >= 2
                and token.form not in STOPWORDS
            ]
    else:
        korean_tokenizer = None
    
    vectorizer_model = CountVectorizer(
        tokenizer=korean_tokenizer,
        stop_words=STOPWORDS if not kiwi else None,
        min_df=1,
        ngram_range=(1, 2)
    )
    
    # 5. BERTopic 모델 생성
    print("   -> BERTopic 모델 생성 및 학습 중...\n")
    topic_model = BERTopic(
        embedding_model=embedding_model,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer_model,
        top_n_words=KEYWORDS_PER_TOPIC,
        language='korean',
        calculate_probabilities=False,
        verbose=True
    )
    
    # 6. 토픽 추출
    topics, probs = topic_model.fit_transform(documents)
    
    # 7. 결과 출력
    print("\n" + "="*60)
    print("🔎 [BERTopic Results]")
    print("="*60)
    
    topic_info = topic_model.get_topic_info()
    print(f"\n✅ 발견된 토픽 개수: {len(topic_info) - 1}개 (-1 제외)")
    print(f"✅ 노이즈 문서: {topic_info[topic_info['Topic'] == -1]['Count'].values[0]}개\n")
    
    # 각 토픽 출력
    all_keywords = []
    for idx, row in topic_info.iterrows():
        topic_id = row['Topic']
        if topic_id == -1:  # 노이즈 제외
            continue
        
        count = row['Count']
        keywords = topic_model.get_topic(topic_id)
        
        if keywords:
            print(f"📂 Topic {topic_id} ({count}개 문서)")
            keyword_list = [word for word, score in keywords[:KEYWORDS_PER_TOPIC]]
            print(f"   키워드: {keyword_list}\n")
            all_keywords.extend(keyword_list)
    
    return all_keywords, topic_model

# ==========================================
# 3. 메인 실행
# ==========================================
def main():
    # 1. 데이터 수집
    documents = collect_data()
    
    if len(documents) < 10:
        print("❌ 데이터가 너무 적습니다. (최소 10개 필요)")
        return
    
    # 2. BERTopic 분석
    keywords, topic_model = extract_keywords_with_bertopic(documents)
    
    # 3. 구조화된 결과 생성
    topic_info = topic_model.get_topic_info()
    
    # 토픽별로 키워드 정리
    topic_keywords = []
    for idx, row in topic_info.iterrows():
        topic_id = row['Topic']
        if topic_id == -1:  # 노이즈 제외
            continue
        
        count = row['Count']
        topic_words = topic_model.get_topic(topic_id)
        
        if topic_words:
            # 상위 키워드로 토픽 이름 생성
            top_words = [word for word, score in topic_words[:3]]
            topic_name = " | ".join(top_words)
            
            # 모든 키워드 추가
            for word, score in topic_words[:KEYWORDS_PER_TOPIC]:
                topic_keywords.append({
                    'topic_id': topic_id,
                    'topic_name': topic_name,
                    'doc_count': count,
                    'keyword': word,
                    'score': round(score, 4)
                })
    
    # 4. CSV 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    filename = f"bertopic_keywords_{timestamp}.csv"
    
    df = pd.DataFrame(topic_keywords)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    
    # 5. 학습 지표 출력
    print("\n" + "="*60)
    print("📊 [학습 지표]")
    print("="*60)
    print(f"✅ 총 문서 수: {len(documents)}개")
    print(f"✅ 발견된 토픽: {len(topic_info) - 1}개 (노이즈 제외)")
    print(f"✅ 노이즈 문서: {topic_info[topic_info['Topic'] == -1]['Count'].values[0]}개")
    print(f"✅ 노이즈 비율: {topic_info[topic_info['Topic'] == -1]['Count'].values[0] / len(documents) * 100:.1f}%")
    
    # 토픽 크기 분포
    topic_sizes = topic_info[topic_info['Topic'] != -1]['Count'].values
    print(f"\n📈 토픽 크기 분포:")
    print(f"   - 평균: {topic_sizes.mean():.1f}개")
    print(f"   - 최대: {topic_sizes.max()}개")
    print(f"   - 최소: {topic_sizes.min()}개")
    
    print("\n" + "="*60)
    print(f"🎉 BERTopic 분석 완료!")
    print(f"📁 파일: {filename}")
    print(f"🔑 총 키워드: {len(df)}개")
    print(f"📂 토픽별 키워드: {KEYWORDS_PER_TOPIC}개씩")
    print("="*60)
    
    # 샘플 출력 (토픽별로)
    print(f"\n📝 키워드 샘플 (상위 3개 토픽):")
    for topic_id in topic_info['Topic'].values[1:4]:  # 0번째는 -1 (노이즈)
        topic_df = df[df['topic_id'] == topic_id]
        if not topic_df.empty:
            print(f"\n🔖 Topic {topic_id}: {topic_df.iloc[0]['topic_name']}")
            print(f"   문서: {topic_df.iloc[0]['doc_count']}개")
            print(f"   키워드: {', '.join(topic_df['keyword'].head(10).tolist())}")

if __name__ == "__main__":
    main()
