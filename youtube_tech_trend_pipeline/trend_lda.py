import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import numpy as np
import warnings

# 경고 무시 (LDA 실행 시 발생하는 DeprecationWarning 등)
warnings.filterwarnings("ignore")

# ==========================================
# [설정] LDA 분석 및 품질 관리 파라미터
# ==========================================
NUM_TOPICS = 10              # 추출할 토픽(주제) 개수
WORDS_PER_TOPIC = 5         # 각 토픽당 추출할 대표 키워드 수
MIN_KEYWORD_LENGTH = 2      # 2글자 미만 단어 제외 (의미 없는 조사 등 필터링)

# [중요] 불용어(Stopwords) 리스트
# 뉴스 헤드라인에서 흔히 나오지만 분석 가치는 없는 단어들을 제거합니다.
STOPWORDS = [
    '뉴스', '속보', '단독', '오늘', '어제', '내일', '발표', '공개', 
    '영상', '논란', '이유', '충격', '결국', '진짜', '근황', '예정',
    '관련', '특징', '가장', '대해', '위해', '통해', '때문', '경우',
    '정도', '최근', '지금', '무엇', '어떻게', '다시', '계속', '종합',
    '출시', '공식', '전망', '분석', '시장', '세계', '국내', '한국',
    '주요', '최고', '대비', '시작', '개최', '진행', '참여', '등장'
]

# Kiwi (Python 전용 한국어 형태소 분석기) 로드
# Java 의존성 없이 빠르고 정확함
USE_KIWI = False
try:
    from kiwipiepy import Kiwi
    kiwi = Kiwi()
    USE_KIWI = True
    print("[System] Kiwi 로드 성공. 고품질 명사 추출 모드로 동작합니다.")
except ImportError:
    print("[System] kiwipiepy가 설치되지 않았습니다.")
    print("         -> 단순 정규표현식 모드로 동작합니다.")
    print("         -> pip install kiwipiepy 권장.")
except Exception as e:
    print(f"[System] Kiwi 초기화 오류: {e}")
    print("         -> 단순 정규표현식 모드로 동작합니다.")

# ==========================================
# 1. 4대 소스 원천 데이터 수집 함수
# ==========================================
def collect_raw_trend_data():
    print("\n" + "="*60)
    print("📡 [Phase 1] 4대 소스 원천 데이터 수집 시작")
    print("="*60)
    
    raw_data = []
    
    # Selenium 드라이버 초기화 (Google Trends도 Selenium으로 수집하기 위함)
    options = uc.ChromeOptions()
    options.add_argument('--headless') # 화면 없이 실행
    options.add_argument('--no-first-run')
    
    driver = None
    try:
        driver = uc.Chrome(options=options)
        
        # [1] Google Trends (Daily - HTML Scraping)
        # RSS가 404/차단되는 경우가 많아 Selenium으로 HTML 페이지 직접 크롤링
        print("   -> [1/4] Google Trends (Daily) 수집 중... (Selenium)")
        try:
            url = "https://trends.google.co.kr/trends/trendingsearches/daily?geo=KR&hl=ko"
            driver.get(url)
            time.sleep(5) # 로딩 대기
            
            # [수정] google_trend.py와 동일한 selector 사용
            # feed-item이 아니라 tr[role='row'] 구조임
            rows = driver.find_elements(By.CSS_SELECTOR, "tr[role='row']")
            
            for row in rows:
                try:
                    # 키워드 추출 (mZ3RIc 클래스 또는 테이블 구조)
                    try:
                        keyword_elem = row.find_element(By.CLASS_NAME, "mZ3RIc")
                        keyword = keyword_elem.text.strip()
                    except:
                        # Fallback
                        keyword_elem = row.find_element(By.CSS_SELECTOR, "td:nth-child(2) > div")
                        keyword = keyword_elem.text.strip()
                        
                    if keyword:
                        raw_data.append(keyword)
                except:
                    continue
                    
            print(f"      - {len(rows)}개 키워드 확보")
            
        except Exception as e:
            print(f"      [Error] Google Trends 수집 실패: {e}")

        # [2] Google News RSS (Technology, Science, Business)
        # 데이터 소스 확장 (사용자 요청)
        print("   -> [2/4] Google News (Tech/Biz/Sci) 수집 중...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }
        
        # 여러 섹션 수집
        sections = {
            'TECHNOLOGY': 'https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ko&gl=KR&ceid=KR:ko',
            'BUSINESS': 'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko',
            'SCIENCE': 'https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=ko&gl=KR&ceid=KR:ko'
        }
        
        for sec_name, url in sections.items():
            try:
                response = requests.get(url, headers=headers, timeout=10)
                root = ET.fromstring(response.content)
                count = 0
                for item in root.findall(".//item"):
                    title = item.find("title").text.split(" - ")[0]
                    raw_data.append(title)
                    count += 1
                print(f"      - {sec_name}: {count}개")
            except Exception as e:
                print(f"      [Error] {sec_name} 수집 실패: {e}")

        # [3] & [4] Naver News (IT/Science & Ranking)
        print("   -> [3/4, 4/4] Naver News (IT/Science & Ranking) 수집 중...")
        try:
            # Naver IT 일반 뉴스
            driver.get("https://news.naver.com/section/105")
            time.sleep(3)
            headlines = driver.find_elements(By.CSS_SELECTOR, "a strong, .sa_text_strong, .sh_text_headline")
            for h in headlines:
                text = h.text.strip()
                if len(text) > 4: raw_data.append(text)
                
            # Naver Ranking (IT/Science)
            driver.get("https://news.naver.com/main/ranking/popularDay.naver")
            time.sleep(2)
            rankings = driver.find_elements(By.CSS_SELECTOR, ".list_content a")
            for r in rankings:
                text = r.text.strip()
                if len(text) > 4: raw_data.append(text)
                
        except Exception as e:
            print(f"      [Error] Naver 수집 중 오류: {e}")
            
    except Exception as e:
        print(f"   [Critical Error] 브라우저 초기화 실패: {e}")
    finally:
        if driver: driver.quit()
        
    # 중복 제거
    raw_data = list(set(raw_data))
    print(f"   -> [완료] 총 {len(raw_data)}개의 원천 헤드라인 확보.")
    return raw_data

# ==========================================
# 2. 토크나이저 (명사 추출 + 불용어 처리)
# ==========================================
def tokenizer(text):
    if USE_KIWI:
        # 형태소 분석으로 명사(NNG, NNP, NR, NP)만 추출
        # Kiwi는 (token, tag, start, len) 튜플을 반환하거나 Token 객체 반환
        tokens = kiwi.tokenize(text)
        nouns = [t.form for t in tokens if t.tag.startswith('N')] # 명사 계열 태그 (NNG, NNP 등)
        
        # 2글자 이상이고 불용어가 아닌 것만 필터링
        return [n for n in nouns if len(n) >= MIN_KEYWORD_LENGTH and n not in STOPWORDS]
    else:
        # Fallback: 정규표현식 (한글/영어/숫자 2글자 이상)
        tokens = re.findall(r'[가-힣a-zA-Z0-9]{2,}', text)
        return [t for t in tokens if t not in STOPWORDS]

# ==========================================
# 3. LDA 분석 및 품질 평가 (Grid Search + Coherence)
# ==========================================
from sklearn.model_selection import GridSearchCV
from sklearn.feature_extraction.text import TfidfVectorizer
import gensim
from gensim.corpora import Dictionary
from gensim.models import CoherenceModel

def calculate_coherence_score(sklearn_lda_model, dtm, vectorizer, tokenized_docs):
    """
    Sklearn LDA 모델의 Coherence Score(c_v)를 Gensim을 이용해 계산
    """
    try:
        # 1. 토픽별 상위 단어 추출
        feature_names = vectorizer.get_feature_names_out()
        topics = []
        for topic_idx, topic in enumerate(sklearn_lda_model.components_):
            top_indices = topic.argsort()[:-WORDS_PER_TOPIC - 1:-1]
            top_words = [feature_names[i] for i in top_indices]
            topics.append(top_words)
            
        # 2. Gensim Dictionary 생성
        dictionary = Dictionary(tokenized_docs)
        
        # 3. Coherence Model 생성 (c_v)
        cm = CoherenceModel(topics=topics, texts=tokenized_docs, dictionary=dictionary, coherence='c_v')
        return cm.get_coherence()
    except Exception as e:
        print(f"   [Warning] Coherence 계산 실패: {e}")
        return 0.0

def extract_keywords_with_lda(docs):
    print("\n" + "="*60)
    print("🧠 [Phase 2] TF-IDF 필터링 & LDA 분석 (Grid Search + Coherence)")
    print("="*60)
    
    if not docs: return []

    # 0. 전처리 (토큰화)
    tokenized_docs = [tokenizer(doc) for doc in docs]
    # 빈 문서 제거
    tokenized_docs = [doc for doc in tokenized_docs if doc]
    # 다시 문자열로 결합 (Sklearn 입력용)
    preprocessed_docs = [" ".join(doc) for doc in tokenized_docs]

    # 1. TF-IDF 벡터화 (중요도 낮은 단어 필터링 효과)
    try:
        # min_df=2: 최소 2번 이상 등장
        # max_df=0.8: 80% 이상 문서에 등장하면 제외 (불용어 성격)
        vectorizer = TfidfVectorizer(tokenizer=lambda x: x.split(), preprocessor=lambda x: x, max_df=0.8, min_df=2)
        dtm = vectorizer.fit_transform(preprocessed_docs)
        
        vocab_size = len(vectorizer.get_feature_names_out())
        print(f"   -> 추출된 고유 명사 개수: {vocab_size}개")
        
        if vocab_size < 10:
            print("   [Error] 데이터가 너무 적어 분석 불가.")
            return docs[:5]

        # 2. Grid Search로 최적의 토픽 수 찾기
        print("   -> 최적의 토픽 수 탐색 중 (Grid Search)...")
        
        search_params = {'n_components': [3, 4, 5, 6, 7, 8]}
        
        lda = LatentDirichletAllocation(random_state=42, learning_method='online', learning_offset=50.)
        
        model = GridSearchCV(lda, param_grid=search_params, cv=3, verbose=1)
        model.fit(dtm)
        
        best_lda_model = model.best_estimator_
        best_n_topics = model.best_params_['n_components']
        
        # 3. Coherence Score 계산
        coherence_score = calculate_coherence_score(best_lda_model, dtm, vectorizer, tokenized_docs)
        
        print(f"\n   🏆 [Best Model Found]")
        print(f"      - Best Topic Count: {best_n_topics}")
        print(f"      - Best Log Likelihood: {model.best_score_:.2f}")
        print(f"      - Perplexity: {best_lda_model.perplexity(dtm):.2f}")
        print(f"      - Coherence Score (c_v): {coherence_score:.4f} (0.5 이상이면 좋음)")

        # 4. 키워드 추출
        feature_names = vectorizer.get_feature_names_out()
        extracted_keywords = set()
        
        print(f"\n   🔎 [Topic Keywords Extraction (Topics={best_n_topics})]")
        for idx, topic in enumerate(best_lda_model.components_):
            top_indices = topic.argsort()[:-WORDS_PER_TOPIC - 1:-1]
            top_words = [feature_names[i] for i in top_indices]
            
            print(f"      Topic {idx+1}: {top_words}")
            extracted_keywords.update(top_words)
            
        return list(extracted_keywords)

    except ValueError as e:
        print(f"   [Error] LDA 분석 실패: {e}")
        return docs[:20] 

# ==========================================
# 메인 실행
# ==========================================
if __name__ == "__main__":
    # 1. 수집
    raw_headlines = collect_raw_trend_data()
    
    # 2. 분석
    final_keywords = extract_keywords_with_lda(raw_headlines)
    
    # 3. 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    filename = f"trend_keywords_{timestamp}.csv"
    
    df = pd.DataFrame(final_keywords, columns=["keyword"])
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    
    print("\n" + "="*60)
    print(f"🎉 고품질 키워드 추출 완료!")
    print(f"📁 파일명: {filename}")
    print(f"🔑 최종 키워드: {len(final_keywords)}개")
    print("="*60)