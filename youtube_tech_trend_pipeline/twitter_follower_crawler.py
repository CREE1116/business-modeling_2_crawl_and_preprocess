import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import random
import pickle
import os
import re
from datetime import datetime
import glob

# ==========================================
# [설정]
# ==========================================
# 입력 파일 패턴 (가장 최신 파일을 자동으로 찾음)
INPUT_FILE_PATTERN = "twitter_retweet_filtered_*.csv"
COOKIE_FILE = "twitter_cookies.pkl"
OUTPUT_FILE_PREFIX = "twitter_user_metrics"

# ==========================================
# 유틸리티
# ==========================================
def random_sleep(min_t=1.5, max_t=3.0):
    time.sleep(random.uniform(min_t, max_t))

def load_cookies(driver, filename):
    if not os.path.exists(filename): return False
    try:
        with open(filename, "rb") as file:
            cookies = pickle.load(file)
            for cookie in cookies: driver.add_cookie(cookie)
        return True
    except: return False

def parse_number_k(text):
    """
    '1.2만', '500K', '1.5M', '1,234' 등을 숫자로 변환
    """
    if not text: return 0
    text = str(text).replace(',', '').strip()
    try:
        if 'K' in text: return int(float(text.replace('K', '')) * 1000)
        if 'M' in text: return int(float(text.replace('M', '')) * 1000000)
        if '만' in text: return int(float(text.replace('만', '')) * 10000)
        
        nums = re.findall(r'[\d\.]+', text)
        if nums:
            return int(float(nums[0]))
        return 0
    except:
        return 0

def get_latest_input_file():
    files = glob.glob(INPUT_FILE_PATTERN)
    if not files: return None
    return max(files, key=os.path.getctime)

# ==========================================
# 크롤링 로직
# ==========================================
def get_follower_count(driver, username):
    url = f"https://x.com/{username}"
    print(f"   [Visiting] {url}")
    try:
        driver.get(url)
        
        # 프로필 로딩 대기 (최대 5초)
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="UserName"]'))
            )
        except:
            print("      -> ❌ 프로필 로딩 실패 (존재하지 않거나 비공개)")
            return -1

        random_sleep(1.0, 2.0)
        
        # 팔로워 수 추출
        # 보통 href="/username/verified_followers" 또는 "/username/followers" 링크 안에 있음
        try:
            # 1. /verified_followers (최신 트위터)
            selector = f'a[href="/{username}/verified_followers"] span'
            elem = driver.find_element(By.CSS_SELECTOR, selector)
            count_text = elem.text
            return parse_number_k(count_text)
        except:
            try:
                # 2. /followers (구버전 또는 일반)
                selector = f'a[href="/{username}/followers"] span'
                elem = driver.find_element(By.CSS_SELECTOR, selector)
                count_text = elem.text
                return parse_number_k(count_text)
            except:
                print("      -> ⚠️ 팔로워 수 요소를 찾을 수 없음")
                return 0
                
    except Exception as e:
        print(f"      -> [Error] {e}")
        return -1

# ==========================================
# 메인
# ==========================================
def main():
    # 1. 입력 파일 찾기
    input_file = get_latest_input_file()
    if not input_file:
        print(f"[Error] 입력 파일을 찾을 수 없습니다. 패턴: {INPUT_FILE_PATTERN}")
        return
    
    print(f"📂 입력 파일: {input_file}")
    
    # 2. 유저 ID 추출 (중복 제거)
    try:
        df = pd.read_csv(input_file)
        if 'author_id' not in df.columns:
            print("[Error] 'author_id' 컬럼이 없습니다.")
            return
            
        # @username -> username 변환 및 빈값 제거
        users = df['author_id'].dropna().unique().tolist()
        users = [u.replace('@', '').strip() for u in users if u.strip()]
        
        print(f"   -> 총 {len(users)}명의 고유 유저 발견")
        
    except Exception as e:
        print(f"[Error] 파일 읽기 실패: {e}")
        return

    # 3. 크롤러 설정
    options = uc.ChromeOptions()
    options.add_argument('--no-first-run')
    options.add_argument('--blink-settings=imagesEnabled=false') # 이미지 로딩 차단 (속도 향상)
    
    driver = uc.Chrome(options=options)
    
    try:
        # 4. 로그인 (쿠키 로드)
        driver.get("https://x.com")
        if load_cookies(driver, COOKIE_FILE):
            driver.refresh()
            print("🍪 쿠키 로드 완료")
            random_sleep(3, 5)
        else:
            print("⚠️ 쿠키 파일이 없습니다. 로그인 상태가 아닐 수 있습니다.")
            random_sleep(2, 3)

        # 5. 수집 시작
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        output_filename = f"{OUTPUT_FILE_PREFIX}_{timestamp}.csv"
        
        results = []
        
        print("="*60)
        print(f"🚀 유저 팔로워 수집 시작 ({len(users)}명)")
        print("="*60)
        
        for idx, user in enumerate(users, 1):
            print(f"[{idx}/{len(users)}] @{user}")
            
            followers = get_follower_count(driver, user)
            
            results.append({
                'author_id': f"@{user}",
                'follower_count': followers,
                'crawled_at': datetime.now().strftime('%Y-%m-%d')
            })
            
            # 중간 저장 (10명마다)
            if idx % 10 == 0:
                pd.DataFrame(results).to_csv(output_filename, index=False, encoding='utf-8-sig')
                print(f"   -> 💾 중간 저장 완료 ({len(results)}명)")
            
            random_sleep(1.5, 3.0) # 밴 방지용 딜레이
            
        # 최종 저장
        pd.DataFrame(results).to_csv(output_filename, index=False, encoding='utf-8-sig')
        print(f"\n🎉 완료! 총 {len(results)}명 저장됨.\n📁 {output_filename}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
