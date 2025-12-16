import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import pandas as pd
import time
import random
import pickle
import os
import urllib.parse
import re
from datetime import datetime

# ==========================================
# [설정] 수집 옵션 (여기를 수정하세요)
# ==========================================
CSV_FILE_PATH = "gemini_trend_keywords_20251211_2350.csv" 
COOKIE_FILE = "twitter_cookies.pkl"

TWEETS_PER_QUERY_GROUP = 200  # 쿼리 세트 당 수집 목표
SEARCH_MODE = "live"          # live: 최신순 (양 확보용), top: 인기순
LANG_FILTER = "lang:ko"       

# [1] 리트윗 컷오프 설정 (1차 필터링)
# 트윗이 검색될 때 최소 이 숫자 이상의 리트윗이 있어야만 나옵니다.
# 0이면 모든 글, 5~10 정도면 적당한 퀄리티, 50 이상이면 네임드 글만 나옴.
MIN_RETWEETS = 1

# [2] 날짜 범위 설정
# 최근 며칠 동안의 트윗만 검색 (예: 7 = 최근 7일, 30 = 최근 1개월)
SEARCH_DAYS = 365  
# [내부 검문] 파이썬으로 걸러낼 전체 노이즈 리스트
# 1. 애니메이션/오타쿠 관련
anime_otaku = [
    '애니', '애니메이션', '오타쿠', '코스프레', '코스어', '만화',
    '라이트노벨', '라노벨', '성우', '덕질', '덕후', '굿즈',
    '피규어', '아크릴', '스탠드', '러버스트랩', '일러스트', '동인',
    '코믹마켓', '코미케', '2D', '왁타버스', '버츄얼', '버튜버',
    '홀로라이브', '니지산지', '아이돌마스터', '러브라이브', '원신',
    '붕괴', '명일방주', '블루아카', '블아', '우마무스메'
]

# 2. 아이돌/연예인 관련
idol_celeb = [
    '아이돌', '걸그룹', '보이그룹', '컴백', '음방', '뮤직뱅크', '음중',
    '팬덤', '팬싸', '팬미팅', '콘서트', '직캠', '무대', '쇼케이스',
    '데뷔', '솔로', '유닛', '센터', '비주얼', '메보', '리보',
    '포카', '앨범', '초동', '1위', '차트', '스밍', '멜론', '지니',
    'BTS', '블랙핑크', '뉴진스', '아이브', '에스파', '르세라핌',
    '엔시티', '세븐틴', '투모로우바이투게더', '있지', '스테이씨',
    '펜', '덕질', '최애', '본진', '입덕', '탈덕'
]

# 3. 스포츠(야구/축구 등) 관련
sports = [
    '야구', '프로야구', 'KBO', 'MLB', '롯데', '두산', 'LG', '삼성', 
    '한화', 'SSG', 'KT', 'NC', '키움', 'KIA',
    '타자', '투수', '홈런', '안타', '선발', '불펜', '마무리',
    '감독', '코치', '선수', '트레이드', 'FA', '계약', '연봉',
    '경기', '이닝', '득점', '실점', '승리', '패배', '무승부',
    '축구', 'EPL', '프리미어리그', '라리가', '분데스리가', '세리에',
    '손흥민', '이강인', '김민재', '황희찬', '토트넘', '맨유', '맨시티',
    '승부조작', '스포츠토토', '베팅'
]

# 4. 대출/금융사기 관련
loan_finance = [
    '대출', '소액대출', '무직자대출', '신용대출', '담보대출', '급전',
    '개인돈', '사채', '무방문', '무서류', '당일대출', '즉시대출',
    '저금리', '고액대출', '한도조회', '신용회복', '채무통합',
    '연체자', '신불자', '파산', '회생', '면책',
    '햇살론', '새희망홀씨', '직장인대출', '프리랜서대출',
    '비대면', '모바일대출', 'P2P', '핀테크', '저축은행',
    '대부업', '중개', '상담', '문의', 'DM', '카톡', '텔레그램'
]

# 5. 도박/불법베팅 관련
gambling = [
    '토토', '스포츠토토', '배팅', '베팅', '카지노', '바카라', '슬롯',
    '먹튀', '사설토토', '사설', '안전놀이터', '메이저사이트',
    '라이브카지노', '온라인카지노', '해외배팅', '해외사이트',
    '보증업체', '꽁머니', '환전', '충전', '입금', '출금',
    '픽스터', '스포츠분석', '승부예측', '해외축구', 'EPL베팅',
    '에볼루션', '프라그마틱', '마이크로게이밍', '텔레그램', 'VIP'
]

# 6. 성인/불건전 관련
adult_content = [
    '떡방', '떡', '19', '성인', '야동', '야사', '에로',
    '조건', '원조', '만남', '섹파', '폰팅', '채팅', '화상',
    '오프', '직거래', '후불제', '선불제', '페이', '후기',
    '텔레방', '텔방', '오픈방', 'n번방', '몸캠', '영통',
    '술집', '유흥', '룸살롱', '노래방', '안마', '마사지'
]

# 7. 쇼핑몰/마케팅 스팸
shopping_spam = [
    '최저가', '무료배송', '할인', '쿠폰', '적립', '이벤트',
    '당첨', '경품', '추첨', '무료나눔', '선착순',
    '구매링크', '쇼핑몰', '스마트스토어', '오픈마켓',
    '쿠팡', '알리', '타오바오', '직구', '구매대행',
    '팔로우', '좋아요', '리트윗', 'RT', '멘션',
    '홍보', '광고', '마케팅', '제휴', '협찬'
]

# 8. 사기/피싱 관련
scam_phishing = [
    '당첨금', '환급', '세금환급', '미수령', '조회',
    '무료지급', '보상금', '포인트', '마일리지', '적립금',
    '본인인증', '실명인증', '계좌인증', '카드등록',
    '클릭', '링크', '접속', '바로가기', 'URL',
    '긴급', '즉시', '빠른', '신속', '당일',
    '정부지원', '정부혜택', '국가지원', '코로나지원금'
]

# 9. 가상화폐 사기
crypto_scam = [
    '코인', '비트코인', '이더리움', '리플', '알트코인',
    '상장', '에어드랍', '에어드롭', '프리세일', 'ICO', 'IDO',
    '펌핑', '폭등', '급등', '대박', '수익인증',
    '시그널', '선물거래', '레버리지', '마진거래',
    '단톡방', '오픈채팅', '텔레그램방', '디스코드',
    'NFT', '메타버스', 'P2E', '게임파이'
]

# 10. 정치/혐오 관련 (선택적)
political_hate = [
    '좌파', '우파', '종북', '빨갱이', '수꼴', '매국노',
    '페미', '한남', '된장녀', '김치녀', '맘충', '틀딱',
    '급식충', '노무현', '박근혜', '문재인', '윤석열',
    '민주당', '국민의힘', '정의당', '국짐', '더불어',
    '일베', '메갈', '워마드', '디시', '펨코'
]

# 전체 필터링 단어 통합
all_spam_keywords = (
    # anime_otaku + idol_celeb + sports + 
    # loan_finance + gambling + adult_content +
    # shopping_spam + scam_phishing + crypto_scam +
    # political_hate
)

# 중복 제거
ALL_NOISE_KEYWORDS = list(set(all_spam_keywords))

# [입구 컷] 쿼리에 직접 넣을 제외어 (독립 검색이므로 강하게 설정 가능)
QUERY_EXCLUDE_KEYWORDS = [

]

# ==========================================
# 1. 유틸리티
# ==========================================
def random_sleep(min_t=2.0, max_t=4.0):
    time.sleep(random.uniform(min_t, max_t))

# ==========================================
# [수정] 스크롤 로직 개선 (요요 스크롤 적용)
# ==========================================
def smart_scroll(driver, last_height, stuck_count):
    """
    단순 스크롤이 아니라, 바닥을 찍고 살짝 올렸다가 다시 내리는 
    '요요 동작'을 통해 트위터의 데이터 로딩을 강제로 트리거함
    """
    try:
        # 1. 현재 높이에서 화면 절반 정도 내림 (자연스럽게)
        driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
        time.sleep(random.uniform(1.0, 1.5))

        # 2. 바닥까지 확 내림
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(2.0, 3.0))

        # 3. [핵심] 만약 높이 변화가 없어서 'stuck' 상태라면? -> 충격 요법
        if stuck_count > 0:
            # 3-1. 위로 살짝 올림 (로딩 트리거)
            driver.execute_script("window.scrollBy(0, -500);")
            time.sleep(random.uniform(1.0, 1.5))
            
            # 3-2. 다시 바닥으로 내림
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2.0, 3.0))
            
        return True
    except Exception as e:
        print(f"   [Scroll Error] {e}")
        return False

def load_cookies(driver, filename):
    if not os.path.exists(filename): return False
    try:
        with open(filename, "rb") as file:
            cookies = pickle.load(file)
            for cookie in cookies: driver.add_cookie(cookie)
        return True
    except: return False

def save_cookies(driver, filename):
    with open(filename, "wb") as file: pickle.dump(driver.get_cookies(), file)

def wait_for_login(driver):
    print("\n[USER ACTION] 로그인 필요! (3분 대기)")
    start = time.time()
    while time.time() - start < 180:
        if "home" in driver.current_url or "explore" in driver.current_url:
            save_cookies(driver, COOKIE_FILE)
            print("[SUCCESS] 로그인 감지 완료.")
            return True
        time.sleep(1)
    return False

# ==========================================
# 2. 키워드 확장 및 쿼리 생성 (수정됨)
# ==========================================
def clean_keyword(text):
    """특수문자 제거 및 정제"""
    return re.sub(r'[^\w\s]', '', str(text)).strip()

def build_smart_query(keyword):
    """
    키워드 길이에 따라 검색 전략을 다르게 가져감
    """
    keyword = clean_keyword(keyword)
    tokens = keyword.split()
    
    # Case 1: 1단어짜리 (예: "Python", "서버")
    # -> 기존처럼 확장하거나 그대로 둠
    if len(tokens) == 1:
        return f'"{keyword}"'  # 1단어는 정확도를 위해 따옴표 추천
        
    # Case 2: 2단어 이상 (예: "생성형 AI 모델", "리액트 상태 관리")
    # -> 따옴표를 쓰면 결과가 0이 나오므로, 따옴표 없이 AND 조건으로 묶음
    # -> 트위터에서 (A B) 라고 쓰면 (A AND B)로 동작함
    else:
        # 전략: "정확한 구문" OR (단어 AND 단어)
        # 예: "생성형 AI" OR (생성형 AI)
        loose_match = f"{' '.join(tokens)}" # 따옴표 없는 버전
        
        # 두 가지 경우를 다 찾되, loose_match가 더 많은 결과를 가져옴
        return f"{loose_match}"

def generate_queries(csv_path, max_query_length=500):
    print("\n" + "="*60)
    print("📂 [Step 1] 지능형 쿼리 생성 (Long-tail 키워드 구출 작전)")
    print("="*60)
    
    if not os.path.exists(csv_path): return []

    try:
        df = pd.read_csv(csv_path)
        # 컬럼명 찾기 (keyword가 포함된 컬럼)
        col = [c for c in df.columns if 'keyword' in c.lower()][0]
        raw_keywords = df[col].dropna().unique().tolist()
        random.shuffle(raw_keywords)
        
        query_groups = []
        
        for keyword in raw_keywords:
            # [핵심] 스마트 쿼리 빌더 사용
            core_query = build_smart_query(keyword)
            
            # 날짜 범위 계산
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=SEARCH_DAYS)
            
            # 쿼리 조립
            parts = [
                core_query,  # ("생성형 AI" OR (생성형 AI)) 형태
                # LANG_FILTER, 
                # "-filter:retweets", 
                # f"min_retweets:{MIN_RETWEETS}",
                # 제외어는 가장 핵심적인 것 5개만 (쿼리 길이 절약)
                # "-양도 -나눔 -포카 -토토 -대출", 
                # f"since:{start_date.strftime('%Y-%m-%d')}",
                # f"until:{end_date.strftime('%Y-%m-%d')}"
            ]
        
            full_query_string = " ".join(parts)
            
            # 길이 체크
            if len(full_query_string) > max_query_length:
                print(f"   [Skip] 쿼리 너무 길음: {keyword[:30]}...")
                continue
                
            query_groups.append((full_query_string, [keyword]))
            
        print(f"   -> 총 {len(query_groups)}개 스마트 쿼리 생성")
        return query_groups
        
    except Exception as e:
        print(f"Error: {e}")
        return []
# ==========================================
# 3. 데이터 파싱
# ==========================================
def parse_number(text):
    if not text: return 0
    text = text.replace(',', '')
    try:
        if 'K' in text: return int(float(text.replace('K', '')) * 1000)
        if 'M' in text: return int(float(text.replace('M', '')) * 1000000)
        nums = re.findall(r'\d+', text)
        return int(nums[0]) if nums else 0
    except: return 0

def parse_tweet(driver, article):
    try:
        text_elem = article.find_element(By.CSS_SELECTOR, 'div[data-testid="tweetText"]')
        text = text_elem.text
        if not text: return None
        
        try: dt = article.find_element(By.TAG_NAME, "time").get_attribute("datetime")
        except: dt = datetime.now().isoformat()
        
        metrics = {'reply': 0, 'retweet': 0, 'like': 0, 'view': 0}
        
        for m_key, testid in [('reply', 'reply'), ('retweet', 'retweet'), ('like', 'like')]:
            try:
                btn = article.find_element(By.CSS_SELECTOR, f'button[data-testid="{testid}"]')
                metrics[m_key] = parse_number(btn.get_attribute("aria-label"))
            except: 
                if m_key == 'like':
                    try:
                        btn = article.find_element(By.CSS_SELECTOR, 'button[data-testid="unlike"]')
                        metrics['like'] = parse_number(btn.get_attribute("aria-label"))
                    except: pass

        try:
            link = article.find_element(By.CSS_SELECTOR, 'a[href*="/analytics"]')
            metrics['view'] = parse_number(link.get_attribute("aria-label"))
        except: pass

        # [수정] 팔로워 수 대신 작성자 ID(핸들) 수집
        author_id = "unknown"
        try:
            user_link = article.find_element(By.CSS_SELECTOR, 'div[data-testid="User-Name"] a')
            href = user_link.get_attribute("href")
            if href:
                # https://twitter.com/username -> @username
                author_id = "@" + href.split('/')[-1]
        except: pass

        return {
            'text': text,
            'created_at': dt,
            'reply': metrics['reply'],
            'retweet': metrics['retweet'],
            'like': metrics['like'],
            'view': metrics['view'],
            'author_id': author_id  # [변경] follower_count -> author_id
        }
    except: return None

# ==========================================
# 4. 필터링 및 수집
# ==========================================
def is_clean_content(text):
    text = str(text).lower()
    for noise in ALL_NOISE_KEYWORDS:
        if noise in text: return False
    return True

def detect_keyword_in_text(text, keyword_list):
    text_lower = text.lower()
    for k in keyword_list:
        if k.lower() in text_lower:
            return k
    return keyword_list[0] 

def perform_search_and_collect(driver, query_string, group_keywords, limit):
    try:
        # [수정] 현재 실행 중인 쿼리 출력 (디버깅용)
        print(f"\n   [🔍 Current Query] {query_string[:100]}... (Total len: {len(query_string)})")
        
        encoded = urllib.parse.quote(query_string)
        driver.get(f"https://twitter.com/search?q={encoded}&src=typed_query&f={SEARCH_MODE}")
        
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
            )
        except: 
            # [추가] 리미트 감지
            page_source = driver.page_source
            if "요청 한도를 초과했습니다" in page_source or "Rate limit exceeded" in page_source:
                print("\n" + "="*60)
                print("🚨 [CRITICAL] 트위터 요청 한도 초과 (Rate Limit Exceeded)")
                print("   -> 15분간 대기 후 재시도합니다... (커피 한 잔 하고 오세요 ☕️)")
                print("="*60)
                time.sleep(900) # 15분 대기
                return [] # 이번 쿼리는 건너뛰거나, 재시도 로직을 상위에 구현해야 함 (일단은 스킵)
            
            print("   -> ❌ 검색 결과 없음.")
            # print(f"   -> [Debug] Current URL: {driver.current_url}")
            # driver.save_screenshot("debug_search_fail.png")
            return []
            
        collected = []
        seen_texts = set()
        last_height = driver.execute_script("return document.body.scrollHeight")
        stuck = 0
        consecutive_retries = 0  # [추가] 연속 재시도 횟수 제한
        
        while len(collected) < limit:
            articles = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
            found_new = False
            
            # [Debug] 필터링 통계
            scanned_count = 0
            filtered_noise = 0
            filtered_seen = 0
            
            for art in articles:
                if len(collected) >= limit: break
                
                # [수정] driver 전달
                data = parse_tweet(driver, art)
                scanned_count += 1
                
                if not data: continue
                
                # 1. 노이즈 필터링 체크
                if not is_clean_content(data['text']):
                    filtered_noise += 1
                    # print(f"      [Noise Filtered] {data['text'][:30]}...") # 너무 시끄러우면 주석 처리
                    continue
                    
                # 2. 중복 체크
                sig = data['text'][:50]
                if sig in seen_texts:
                    filtered_seen += 1
                    continue
                    
                seen_texts.add(sig)
                data['search_keyword'] = detect_keyword_in_text(data['text'], group_keywords)
                data['search_query'] = query_string 
                collected.append(data)
                found_new = True
            
            # [Debug] 이번 스크롤 결과 출력
            if scanned_count > 0:
                print(f"      -> 스캔: {scanned_count}개 | 수집: {found_new} | 노이즈: {filtered_noise} | 중복: {filtered_seen}")
            
            if len(collected) >= limit: break
            
            # ... (데이터 수집 코드 바로 뒤) ...

            # 1. 스마트 스크롤 실행 (stuck 상태 전달)
            smart_scroll(driver, last_height, stuck)
            
            # 2. 높이 체크
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            # 3. 멈춤 판별 로직 강화
            if new_height == last_height:
                stuck += 1
                print(f"      [Stuck {stuck}/7] 로딩 대기 중...")
                
                # [수정] 막히면 즉시 '다시 시도' 버튼 찾기 시도 (단, 연속 3회까지만)
                # [수정] 막히면 즉시 '다시 시도' 버튼 찾기 시도
                if consecutive_retries < 3:
                    try:
                        retry_selectors = [
                            "//span[text()='다시 시도']",
                            "//span[contains(text(), 'Retry')]",
                            "//div[@role='button']//span[contains(text(), '다시 시도')]",
                            "//span[contains(text(), '다시 시도하세요')]" # [추가] 정확한 문구
                        ]
                        
                        clicked_retry = False
                        for sel in retry_selectors:
                            try:
                                retry_btn = driver.find_element(By.XPATH, sel)
                                driver.execute_script("arguments[0].click();", retry_btn)
                                print(f"      -> 🔄 '다시 시도' 버튼 클릭 성공 ({sel})")
                                stuck = 0 # 성공 시 리셋
                                consecutive_retries += 1 # 재시도 횟수 증가
                                clicked_retry = True
                                time.sleep(random.uniform(3.0, 5.0)) # [수정] 대기 시간 약간 증가
                                break
                            except: continue
                        
                        if clicked_retry:
                            continue # 재시도 했으면 스크롤 체크 건너뛰고 다시 스캔
                    except: pass
                
                # [추가] 3회 이상 연속 재시도 실패 시 -> 페이지 새로고침 (Soft Refresh)
                elif consecutive_retries >= 3:
                    print("      -> ⚠️ 연속 재시도 실패. 페이지 새로고침 시도...")
                    driver.refresh()
                    time.sleep(random.uniform(5.0, 8.0))
                    stuck = 0
                    consecutive_retries = 0
                    continue
                
                else:
                    print("      -> ⚠️ 재시도 한도 초과 (무한 루프 방지)")
                
                # 7번 이상 막히면 포기 (다음 키워드로)
                if stuck > 7: 
                    print("   -> ⚠️ 스크롤 끝 도달 (더 이상 데이터 없음)")
                    break
            else:
                stuck = 0
                consecutive_retries = 0 # 높이가 변했으면 재시도 카운트 초기화
                last_height = new_height
                
            # ... (진행률 표시 코드) ...
                
            if len(collected) % 50 == 0 and found_new:
                print(f"      [{len(collected)}/{limit}] 수집 중...")
                
        return collected
    except Exception as e: 
        print(f"   [Error] {e}")
        return []

# ==========================================
# 5. 메인
# ==========================================
def main():
    query_groups = generate_queries(CSV_FILE_PATH)
    if not query_groups: return
    
    options = uc.ChromeOptions()
    options.add_argument('--no-first-run')
    options.add_argument('--blink-settings=imagesEnabled=false')
    
    driver = uc.Chrome(options=options)
    
    try:
        driver.get("https://twitter.com")
        load_cookies(driver, COOKIE_FILE)
        driver.refresh()
        random_sleep(3, 5)
        
        if "login" in driver.current_url:
            if not wait_for_login(driver): return
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        output_dir = "data/twitter"
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"twitter_retweet_filtered_{timestamp}.csv")
        total = 0
        
        print("="*60)
        print(f"🚀 트위터 수집 시작 (Min Retweets: {MIN_RETWEETS}, 3글자 미만 분할 금지)")
        print("="*60)
        
        # [수정] follower_count -> author_id
        columns = ['text', 'reply', 'retweet', 'like', 'view', 'author_id', 'created_at', 'search_keyword', 'search_query']
        
        for idx, (q_str, k_list) in enumerate(query_groups, 1):
            print(f"\n[Group {idx}/{len(query_groups)}] 시작")
            
            data = perform_search_and_collect(driver, q_str, k_list, TWEETS_PER_QUERY_GROUP)
            
            if data:
                df = pd.DataFrame(data)
                for col in columns:
                    if col not in df.columns:
                        df[col] = 0 if col in ['reply','retweet','like','view'] else ("" if col == 'author_id' else "")
                df = df[columns]
                
                header = not os.path.exists(filename)
                df.to_csv(filename, index=False, mode='a', encoding='utf-8-sig', header=header)
                total += len(data)
                print(f"   -> ✅ {len(data)}개 저장 (누적: {total})")
            
            if idx < len(query_groups):
                random_sleep(10, 15)
                
        print(f"\n🎉 완료! 총 {total}개 저장됨.\n📁 {filename}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()