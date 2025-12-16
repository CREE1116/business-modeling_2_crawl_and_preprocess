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
# 입력 파일 패턴 (data/twitter 폴더 내의 파일 검색)
INPUT_FILE_PATTERN = "/Users/leejongmin/code/비모/twitter_tech_filtered_20251212_1627.csv" # 기본 패턴 변경
COOKIE_FILE = "twitter_cookies.pkl"

# [Anti-Ban 설정]
MIN_SLEEP = 4.0        # 최소 대기 시간 (초)
MAX_SLEEP = 8.0        # 최대 대기 시간 (초)
LONG_SLEEP_EVERY = 20  # N명마다 길게 휴식
LONG_SLEEP_DURATION = (30, 60) # 긴 휴식 시간 범위 (초)

# ==========================================
# 유틸리티
# ==========================================
def random_sleep(min_t=MIN_SLEEP, max_t=MAX_SLEEP):
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
    if not text: return 0
    text = str(text).replace(',', '').strip()
    try:
        if 'K' in text: return int(float(text.replace('K', '')) * 1000)
        if 'M' in text: return int(float(text.replace('M', '')) * 1000000)
        if '만' in text: return int(float(text.replace('만', '')) * 10000)
        nums = re.findall(r'[\d\.]+', text)
        if nums: return int(float(nums[0]))
        return 0
    except: return 0

def get_latest_input_file():
    # 1. data/twitter 폴더 검색
    files = glob.glob(INPUT_FILE_PATTERN)
    
    # 2. 없으면 루트 폴더 검색 (하위 호환성)
    if not files:
        files = glob.glob("data/twitter/twitter_tech_filtered_*.csv")
        
    if not files: return None
    return max(files, key=os.path.getctime)

# ==========================================
# 크롤링 로직
# ==========================================
def get_follower_count(driver, username):
    url = f"https://x.com/{username}"
    print(f"   [Visiting] {url}")
    
    # [Retry Logic] 로딩 실패 시 최대 2회 재시도 (Backoff 적용)
    for attempt in range(2):
        try:
            driver.get(url)
            
            # 프로필 로딩 대기 (최대 10초로 증가)
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="UserName"]'))
                )
            except:
                # 로딩 실패 시 잠시 대기 후 재시도
                print(f"      -> ⚠️ 로딩 지연 (시도 {attempt+1}/2)")
                time.sleep(5 * (attempt + 1))
                continue

            random_sleep(1.5, 2.5)
            
            # 팔로워 수 추출
            try:
                # 1. /verified_followers
                selector = f'a[href="/{username}/verified_followers"] span'
                elem = driver.find_element(By.CSS_SELECTOR, selector)
                return parse_number_k(elem.text)
            except:
                try:
                    # 2. /followers
                    selector = f'a[href="/{username}/followers"] span'
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    return parse_number_k(elem.text)
                except:
                    # 3. 페이지 소스에서 Regex로 찾기 (Fallback)
                    try:
                        src = driver.page_source
                        # "followers_count": 1234
                        match = re.search(r'"followers_count":\s*(\d+)', src)
                        if match: return int(match.group(1))
                    except: pass
                    
                    print("      -> ⚠️ 팔로워 수 요소를 찾을 수 없음")
                    return 0
            
            # 성공 시 루프 탈출
            break
            
        except Exception as e:
            print(f"      -> [Error] {e}")
            time.sleep(3)
            
    return -1 # 결국 실패함

# ==========================================
# 메인
# ==========================================
def main():
    input_file = get_latest_input_file()
    if not input_file:
        print(f"[Error] 입력 파일을 찾을 수 없습니다. 패턴: {INPUT_FILE_PATTERN}")
        return
    
    print(f"📂 입력 파일: {input_file}")
    
    try:
        df = pd.read_csv(input_file)
        if 'author_id' not in df.columns:
            print("[Error] 'author_id' 컬럼이 없습니다.")
            return
            
        # follower_count 컬럼이 없으면 초기화
        if 'follower_count' not in df.columns:
            df['follower_count'] = -1
            print("   -> 'follower_count' 컬럼 추가됨")
            
        # author_id 정리
        df['author_id_clean'] = df['author_id'].astype(str).apply(lambda x: x.replace('@', '').strip())
        
        # 수집 대상: follower_count가 없거나 -1인 유저
        # 이미 수집된 유저는 건너뜀
        users_to_crawl = df[df['follower_count'] == -1]['author_id_clean'].unique().tolist()
        users_to_crawl = [u for u in users_to_crawl if u]
        
        print(f"   -> 총 {len(df['author_id_clean'].unique())}명의 유저 중 {len(users_to_crawl)}명 수집 예정")
        
        if not users_to_crawl:
            print("   -> 모든 유저의 팔로워 정보가 이미 있습니다.")
            return

    except Exception as e:
        print(f"[Error] 파일 읽기 실패: {e}")
        return

# ==========================================
# 드라이버 설정
# ==========================================
def init_driver():
    print("🔧 드라이버 초기화 중...")
    options = uc.ChromeOptions()
    options.add_argument('--no-first-run')
    options.add_argument('--blink-settings=imagesEnabled=false')
    
    try:
        driver = uc.Chrome(options=options)
        driver.get("https://x.com")
        
        if load_cookies(driver, COOKIE_FILE):
            driver.refresh()
            print("🍪 쿠키 로드 완료")
            random_sleep(3, 5)
        else:
            print("⚠️ 쿠키 파일이 없습니다. 로그인 상태가 아닐 수 있습니다.")
            random_sleep(2, 3)
            
        return driver
    except Exception as e:
        print(f"[Error] 드라이버 초기화 실패: {e}")
        return None

# ==========================================
# 메인
# ==========================================
def main():
    input_file = get_latest_input_file()
    if not input_file:
        print(f"[Error] 입력 파일을 찾을 수 없습니다. 패턴: {INPUT_FILE_PATTERN}")
        return
    
    print(f"📂 입력 파일: {input_file}")
    
    try:
        df = pd.read_csv(input_file)
        if 'author_id' not in df.columns:
            print("[Error] 'author_id' 컬럼이 없습니다.")
            return
            
        # follower_count 컬럼이 없으면 초기화
        if 'follower_count' not in df.columns:
            df['follower_count'] = -1
            print("   -> 'follower_count' 컬럼 추가됨")
            
        # author_id 정리
        df['author_id_clean'] = df['author_id'].astype(str).apply(lambda x: x.replace('@', '').strip())
        
        # 수집 대상: follower_count가 없거나 -1인 유저
        users_to_crawl = df[df['follower_count'] == -1]['author_id_clean'].unique().tolist()
        users_to_crawl = [u for u in users_to_crawl if u]
        
        print(f"   -> 총 {len(df['author_id_clean'].unique())}명의 유저 중 {len(users_to_crawl)}명 수집 예정")
        
        if not users_to_crawl:
            print("   -> 모든 유저의 팔로워 정보가 이미 있습니다.")
            return

    except Exception as e:
        print(f"[Error] 파일 읽기 실패: {e}")
        return

    driver = init_driver()
    if not driver: return

    try:
        print("="*60)
        print(f"🚀 유저 팔로워 수집 시작 ({len(users_to_crawl)}명)")
        print(f"   - 기본 대기: {MIN_SLEEP}~{MAX_SLEEP}초")
        print(f"   - 긴 휴식: {LONG_SLEEP_EVERY}명마다 {LONG_SLEEP_DURATION}초")
        print("="*60)
        
        consecutive_failures = 0
        MAX_CONSECUTIVE_FAILURES = 3
        
        for idx, user in enumerate(users_to_crawl, 1):
            print(f"[{idx}/{len(users_to_crawl)}] @{user}")
            
            try:
                followers = get_follower_count(driver, user)
                
                if followers != -1:
                    df.loc[df['author_id_clean'] == user, 'follower_count'] = followers
                    consecutive_failures = 0 # 성공 시 초기화
                else:
                    consecutive_failures += 1
                    print(f"   -> ⚠️ 실패 (연속 {consecutive_failures}회)")

            except Exception as e:
                print(f"   -> [Critical Error] 크롤링 중 예외 발생: {e}")
                consecutive_failures += 1
            
            # 연속 실패가 많으면 드라이버 재시작
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"   🚨 연속 {consecutive_failures}회 실패 또는 오류. 드라이버 재시작...")
                try:
                    driver.quit()
                except: pass
                
                time.sleep(10) # 잠시 대기
                driver = init_driver()
                if not driver:
                    print("   -> [Fatal] 드라이버 재시작 실패. 종료합니다.")
                    break
                consecutive_failures = 0
                continue

            # 중간 저장
            if idx % 10 == 0:
                save_df = df.drop(columns=['author_id_clean'])
                save_df.to_csv(input_file, index=False, encoding='utf-8-sig')
                print(f"   -> 💾 중간 저장 완료 (진행률: {idx}/{len(users_to_crawl)})")
            
            # [Anti-Ban] 긴 휴식
            if idx % LONG_SLEEP_EVERY == 0:
                sleep_time = random.uniform(*LONG_SLEEP_DURATION)
                print(f"   💤 {LONG_SLEEP_EVERY}명 수집 완료. {int(sleep_time)}초 휴식...")
                time.sleep(sleep_time)
            else:
                random_sleep()
            
        # 최종 저장
        save_df = df.drop(columns=['author_id_clean'])
        save_df.to_csv(input_file, index=False, encoding='utf-8-sig')
        print(f"\n🎉 완료! 파일 업데이트됨.\n📁 {input_file}")
        
    except KeyboardInterrupt:
        print("\n🛑 사용자에 의해 중단됨. 현재까지의 진행 상황을 저장합니다.")
        save_df = df.drop(columns=['author_id_clean'])
        save_df.to_csv(input_file, index=False, encoding='utf-8-sig')
        print("   -> 💾 저장 완료")
        
    except Exception as e:
        print(f"\n[Fatal Error] 알 수 없는 오류 발생: {e}")
        save_df = df.drop(columns=['author_id_clean'])
        save_df.to_csv(input_file, index=False, encoding='utf-8-sig')
        print("   -> 💾 비상 저장 완료")
        
    finally:
        if driver:
            try: driver.quit()
            except: pass

if __name__ == "__main__":
    main()
