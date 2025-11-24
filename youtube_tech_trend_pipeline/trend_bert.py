import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import pandas as pd
import time
import random
import os
import re
from datetime import datetime
import numpy as np

# BERT & Clustering
# [Warning Fix] 병렬 처리 경고 끄기
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.feature_extraction.text import CountVectorizer
from kiwipiepy import Kiwi

# ==========================================
# [설정] 파라미터
# ==========================================
NUM_CLUSTERS = 3           # 기본 군집(토픽) 개수 (AUTO_CLUSTER=False일 때 사용)
KEYWORDS_PER_CLUSTER = 5    # 군집당 키워드 수
MODEL_NAME = 'jhgan/ko-sroberta-multitask' # 한국어 문장 임베딩에 성능 좋은 모델 (SBERT)

# 클러스터 개수 자동 결정 (Silhouette Score 사용)
AUTO_CLUSTER = True        # True면 자동으로 최적 클러스터 개수 탐색
CLUSTER_RANGE = (5, 30)     # 탐색할 클러스터 개수 범위 (최소 3개 이상 권장)

# 불용어 (DC인사이드 노이즈 대응 강화)
STOPWORDS = [
    # 뉴스 관련
    '뉴스', '속보', '단독', '오늘', '어제', '내일', '발표', '공개', 
    '영상', '논란', '이유', '충격', '결국', '진짜', '근황', '예정',
    '관련', '특징', '가장', '대해', '위해', '통해', '때문', '경우',
    '정도', '최근', '지금', '무엇', '어떻게', '다시', '계속', '종합',
    '출시', '공식', '전망', '분석', '시장', '세계', '국내', '한국',
    '주요', '최고', '대비', '시작', '개최', '진행', '참여', '등장',
    '정답', '퀴즈', '문제', '이벤트', '당첨', '참가',
    # DC 노이즈 (욕설/비속어/의미없는 단어)
    '새끼', '이거', '저거', '그거', '뭐임', '개념', '피티', '생각', '사람',
    '진짜', '정말', '매우', '너무', '완전', '대박', '헐', '와', '우와',
    '댓글', '추천', '비추', '신고', '삭제', '차단', '글쓴이', '작성자',
    '형들', '자게', '여기', '저기', '그냥', '이제', '이미', '벌써',
    '해마', '아빠', '정신', '느낌', 'ㅋㅋ', '안녕', 'ㅇㅇ', 'ㄷㄷ','지랄','정병','해주갤','이재명'
]

# Kiwi 초기화
try:
    kiwi = Kiwi()
    # [중요] 사용자 사전 추가 (잘못 분리되는 신조어/고유명사 등록)
    kiwi.add_user_word("제미나이", "NNP") 
    kiwi.add_user_word("챗GPT", "NNP")
    kiwi.add_user_word("바이브코딩", "NNP")
    print("[System] Kiwi 로드 성공. (사용자 사전 적용됨)")
except:
    kiwi = None
    print("[System] Kiwi 로드 실패. (pip install kiwipiepy)")

# ==========================================
# 1. 데이터 수집 (기존 로직 재사용)
# ==========================================
def crawl_dcinside(pages=0):
    """DC인사이드 인기 갤러리에서 개념글 제목 수집"""
    galleries = [
        ('programming', '개발자', 'major'),
        ('chatgpt', 'AI/ChatGPT', 'minor'),
        ('robot', '로봇', 'minor')
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.dcinside.com/'
    }
    
    titles = []
    base_url = "https://gall.dcinside.com"
    
    # 필터링할 패턴 (노이즈 제목)
    noise_patterns = ['ㅋ', 'ㅎ', 'ㄷ', 'ㅇㅇ', '...', '??', '!!']
    
    for g_id, g_name, g_type in galleries:
        for page in range(1, pages + 1):
            try:
                # 개념글(추천순) URL
                if g_type == 'major':
                    url = f"{base_url}/board/lists/?id={g_id}&exception_mode=recommend&page={page}"
                else:
                    url = f"{base_url}/mgallery/board/lists/?id={g_id}&exception_mode=recommend&page={page}"
                
                res = requests.get(url, headers=headers, timeout=10)
                if res.status_code != 200: continue
                
                soup = BeautifulSoup(res.text, 'html.parser')
                rows = soup.select('.ub-content.us-post')
                if not rows:
                    rows = soup.select('tr.ub-content')
                
                for row in rows[:30]:  # 페이지당 최대 30개
                    try:
                        title_tag = row.select_one('.gall_tit a')
                        if title_tag:
                            title = title_tag.text.strip()
                            
                            # 필터링: 너무 짧거나 의미없는 제목 제외
                            if len(title) < 5:  # 5자 미만 제외
                                continue
                            if any(pattern * 2 in title for pattern in noise_patterns):  # 'ㅋㅋ', 'ㅎㅎ' 등 반복 제외
                                continue
                            if title.replace(' ', '').replace('ㅋ', '').replace('ㅎ', '').replace('ㄷ', '').replace('ㅇ', '') == '':  # 자음만 있는 경우
                                continue
                            
                            titles.append(title)
                    except: pass
                
                time.sleep(random.uniform(1.0, 2.0))
            except: pass
    
    return titles

def collect_data():
    print("\n" + "="*60)
    print("📡 [Phase 1] 데이터 수집 (기술 블로그 RSS)")
    print("="*60)
    
    raw_data = []
    
    # 기술 블로그 RSS만 수집 (노이즈 최소화)
    print("   -> 기술 블로그 + 긱뉴스 RSS 수집 중...")
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 뉴스 RSS (긱뉴스만)
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
    
    for name, url in all_rss:
        try:
            res = requests.get(url, headers=headers, timeout=10)
            root = ET.fromstring(res.content)
            count = 0
            
            # Atom 형식 (긱뉴스, 네이버 D2, Hyperconnect 등)
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
                            title = title_elem.text
                            raw_data.append(title)
                            count += 1
                    except: pass
            
            if count > 0:
                print(f"      -> {name}: {count}개")
        except Exception as e:
            # 에러는 조용히 넘김 (일부 블로그는 업데이트가 없을 수 있음)
            pass
    
    unique_data = list(set(raw_data))
    print(f"   -> 총 {len(unique_data)}개 문장 확보.")
    return unique_data

# ==========================================
# 2. BERT 임베딩 및 클러스터링
# ==========================================
def extract_keywords_with_bert(docs):
    print("\n" + "="*60)
    print(f"🧠 [Phase 2] KoBERT(SBERT) 임베딩 & 클러스터링")
    print("="*60)
    
    if not docs: return []

    # 1. 임베딩 (Vectorization)
    print(f"   -> 모델 로드 중 ({MODEL_NAME})...")
    model = SentenceTransformer(MODEL_NAME)
    
    print("   -> 문장 임베딩 생성 중...")
    embeddings = model.encode(docs, show_progress_bar=True)
    
    # 2. 클러스터링 (K-Means)
    # 클러스터 개수 자동 결정 (Grid Search)
    if AUTO_CLUSTER:
        print(f"   -> 최적 클러스터 개수 탐색 중 (범위: {CLUSTER_RANGE[0]}-{CLUSTER_RANGE[1]})...")
        best_score = -1
        best_n_clusters = NUM_CLUSTERS
        scores = {}
        
        for n in range(CLUSTER_RANGE[0], CLUSTER_RANGE[1] + 1):
            kmeans = KMeans(n_clusters=n, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)
            score = silhouette_score(embeddings, labels)
            scores[n] = score
            
            if score > best_score:
                best_score = score
                best_n_clusters = n
        
        print(f"   -> Silhouette Scores: {scores}")
        print(f"   -> ✅ 최적 클러스터 개수: {best_n_clusters} (Score: {best_score:.3f})")
        
        num_clusters = best_n_clusters
    else:
        num_clusters = NUM_CLUSTERS
        print(f"   -> 클러스터링 수행 (Clusters={num_clusters})...")
    
    # 최종 클러스터링
    clustering_model = KMeans(n_clusters=num_clusters, random_state=42)
    clustering_model.fit(embeddings)
    cluster_assignment = clustering_model.labels_
    
    # 3. 클러스터별 키워드 추출 (c-TF-IDF 방식 흉내)
    # 각 클러스터의 문장들을 하나의 긴 텍스트로 합침
    clustered_docs = {i: [] for i in range(num_clusters)}
    for sentence_id, cluster_id in enumerate(cluster_assignment):
        clustered_docs[cluster_id].append(docs[sentence_id])
        
    final_keywords = []  # set에서 list로 변경 (클러스터 정보 포함하기 위해)
    
    print("\n   🔎 [Cluster Analysis Results]")
    
    # 명사 추출 토크나이저
    def tokenizer(text):
        if kiwi:
            tokens = kiwi.tokenize(text)
            nouns = [t.form for t in tokens if t.tag.startswith('N')]
            return [n for n in nouns if len(n) >= 2 and n not in STOPWORDS]
        else:
            return text.split()

    for i in range(num_clusters):
        sentences = clustered_docs[i]
        if not sentences: continue
        
        # 클러스터 내 문장들을 합쳐서 빈도 분석
        combined_text = " ".join(sentences)
        
        # CountVectorizer로 빈도 높은 명사 추출
        try:
            # [Warning Fix] tokenizer 사용 시 token_pattern=None 설정
            cv = CountVectorizer(tokenizer=tokenizer, token_pattern=None, max_features=10)
            cv.fit([combined_text])
            top_words = list(cv.vocabulary_.keys())[:KEYWORDS_PER_CLUSTER]
            
            print(f"\n   📂 Cluster {i+1} (문장 {len(sentences)}개)")
            print(f"      - 대표 문장: {sentences[0][:40]}...")
            print(f"      - 키워드: {top_words}")
            
            # 클러스터 정보와 함께 저장
            for word in top_words:
                final_keywords.append({'keyword': word, 'cluster': i+1})
        except:
            pass

    return final_keywords

# ==========================================
# 메인 실행
# ==========================================
def main():
    # 1. 수집
    docs = collect_data()
    
    # 2. 분석
    keywords = extract_keywords_with_bert(docs)
    
    # 3. 저장
    if keywords:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"trend_keywords_bert_{timestamp}.csv"
        
        # DataFrame으로 저장 (keyword, cluster 컬럼 포함)
        df = pd.DataFrame(keywords)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        print("\n" + "="*60)
        print(f"🎉 BERT 분석 완료!")
        print(f"📁 파일명: {filename}")
        print(f"🔑 추출 키워드: {len(keywords)}개")
        print("="*60)

if __name__ == "__main__":
    main()
