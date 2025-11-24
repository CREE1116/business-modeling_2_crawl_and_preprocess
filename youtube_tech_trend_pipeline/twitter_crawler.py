import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
CSV_FILE_PATH = "gemini_trend_keywords_20251124_1623.csv" 
COOKIE_FILE = "twitter_cookies.pkl"

TWEETS_PER_QUERY_GROUP = 300  # 쿼리 세트 당 수집 목표
SEARCH_MODE = "live"          # live: 최신순 (양 확보용), top: 인기순
LANG_FILTER = "lang:ko"       

# [1] 리트윗 컷오프 설정 (1차 필터링)
# 트윗이 검색될 때 최소 이 숫자 이상의 리트윗이 있어야만 나옵니다.
# 0이면 모든 글, 5~10 정도면 적당한 퀄리티, 50 이상이면 네임드 글만 나옴.
MIN_RETWEETS = 10

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
    anime_otaku + idol_celeb + sports + 
    loan_finance + gambling + adult_content +
    shopping_spam + scam_phishing + crypto_scam +
    political_hate
)

# 중복 제거
ALL_NOISE_KEYWORDS = list(set(all_spam_keywords))

# [입구 컷] 쿼리에 직접 넣을 제외어 (독립 검색이므로 강하게 설정 가능)
QUERY_EXCLUDE_KEYWORDS = [
    # 아이돌/팬덤 (최우선)
    "아이돌", "포카", "양도", "나눔", "rt", "알티", "직캠", "팬싸", 
    "콘서트", "굿즈", "앨범", "컴백", "최애", "덕질",
    
    # 스포츠
    "야구", "축구", "KBO", "경기", "선수",
    
    # 금융/도박
    "토토", "대출", "급전", "배팅", "카지노",
    
    # 성인/쇼핑
    "19금", "쿠팡", "알리", "할인", "쿠폰"
]

# ==========================================
# 1. 유틸리티
# ==========================================
def random_sleep(min_t=2.0, max_t=4.0):
    time.sleep(random.uniform(min_t, max_t))

def human_like_scroll(driver):
    scroll_amount = random.randint(700, 1000)
    driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
    time.sleep(random.uniform(2.0, 3.5))

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
def expand_keyword(text):
    """
    키워드 내부 OR 조합 생성 (첫 단어만, 큰따옴표로 감싸기)
    "DevOps 문화" → ("DevOps 문화" OR "DevOps")
    "DDD 아키텍처" → ("DDD 아키텍처" OR "DDD")  # 사람 이름 방지
    """
    text = str(text).strip()
    
    # 1. 원본 전체
    expanded = [f'"{text}"']
    
    # 2. 첫 번째 단어만 추가 (큰따옴표로 감싸서 정확한 매칭)
    tokens = text.split()
    if len(tokens) > 1 and len(tokens[0]) >= 2:
        expanded.append(f'"{tokens[0]}"')
            
    return expanded

def generate_queries(csv_path, max_query_length=600):
    """
    각 키워드를 독립 쿼리로 생성하되, 키워드 내부에서 OR 조합 사용
    """
    print("\n" + "="*60)
    print("📂 [Step 1] 키워드 로드 및 쿼리 생성")
    print("="*60)
    
    if not os.path.exists(csv_path): return []

    try:
        df = pd.read_csv(csv_path)
        col = [c for c in df.columns if 'keyword' in c.lower()][0]
        raw_keywords = df[col].dropna().unique().tolist()
        random.shuffle(raw_keywords)
        
        query_groups = []
        
        # 각 키워드를 독립 쿼리로 생성
        for keyword in raw_keywords:
            # 키워드 내부 OR 조합
            expanded = expand_keyword(keyword)
            or_clause = " OR ".join(expanded)
            
            # 날짜 범위 계산
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=SEARCH_DAYS)
            
            # 쿼리 조립 (날짜 필터 포함)
            parts = [
                f"({or_clause})", 
                LANG_FILTER, 
                "-filter:retweets", 
                f"min_retweets:{MIN_RETWEETS}",
                f"since:{start_date.strftime('%Y-%m-%d')}",
                f"until:{end_date.strftime('%Y-%m-%d')}"
            ]
            
            # 노이즈 키워드 추가
            for noise in QUERY_EXCLUDE_KEYWORDS:
                parts.append(f"-{noise}")
            
            full_query_string = " ".join(parts)
            
            # 길이 체크
            if len(full_query_string) > max_query_length:
                print(f"   [Skip] 쿼리 너무 길음: {keyword[:30]}...")
                continue
                
            query_groups.append((full_query_string, [keyword]))
            
        print(f"   -> 총 {len(query_groups)}개 독립 쿼리 생성 (각 키워드 내 OR 조합 포함)")
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

def parse_tweet(article):
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

        return {
            'text': text,
            'created_at': dt,
            'reply': metrics['reply'],
            'retweet': metrics['retweet'],
            'like': metrics['like'],
            'view': metrics['view']
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
            print("   -> ❌ 검색 결과 없음.")
            return []
            
        collected = []
        seen_texts = set()
        last_height = driver.execute_script("return document.body.scrollHeight")
        stuck = 0
        
        while len(collected) < limit:
            articles = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
            found_new = False
            
            for art in articles:
                if len(collected) >= limit: break
                
                data = parse_tweet(art)
                # 파이썬 내부 필터링 + 리트윗 수 더블 체크 (선택사항)
                if data and is_clean_content(data['text']):
                    # 검색 결과가 정확하다면 여기서 min_retweets가 적용된 글만 보여야 함
                    sig = data['text'][:50]
                    if sig not in seen_texts:
                        seen_texts.add(sig)
                        data['search_keyword'] = detect_keyword_in_text(data['text'], group_keywords)
                        data['search_query'] = query_string 
                        collected.append(data)
                        found_new = True
            
            if len(collected) >= limit: break
            
            human_like_scroll(driver)
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                stuck += 1
                if stuck > 4: 
                    print("   -> ⚠️ 스크롤 끝 도달")
                    break
            else:
                stuck = 0
                last_height = new_height
                
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
        filename = f"twitter_retweet_filtered_{timestamp}.csv"
        total = 0
        
        print("="*60)
        print(f"🚀 트위터 수집 시작 (Min Retweets: {MIN_RETWEETS}, 3글자 미만 분할 금지)")
        print("="*60)
        
        columns = ['text', 'reply', 'retweet', 'like', 'view', 'created_at', 'search_keyword', 'search_query']
        
        for idx, (q_str, k_list) in enumerate(query_groups, 1):
            print(f"\n[Group {idx}/{len(query_groups)}] 시작")
            
            data = perform_search_and_collect(driver, q_str, k_list, TWEETS_PER_QUERY_GROUP)
            
            if data:
                df = pd.DataFrame(data)
                for col in columns:
                    if col not in df.columns:
                        df[col] = 0 if col in ['reply','retweet','like','view'] else ""
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