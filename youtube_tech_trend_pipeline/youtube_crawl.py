import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import random
import os
from datetime import datetime
from itertools import combinations
import re

# ==========================================
# [설정] 파일 입력 및 수집 설정
# ==========================================
# [중요] 1번 스크립트에서 만든 파일명을 여기에 입력하세요
INPUT_KEYWORD_FILE = "gemini_trend_keywords_20251129_1301.csv"  # <-- 파일명 수정 필요

VIDEOS_PER_KEYWORD = 10      # 키워드당 수집할 영상 수
COMMENTS_PER_VIDEO = 100     # 영상당 수집할 댓글 수
MIN_COMMENT_LENGTH = 15     # 15자 미만 댓글 필터링 (품질 관리)

# 키워드 조합 설정
USE_COMBINATION = False     # True면 조합 사용, False면 원본 키워드 그대로 사용
COMBINATION_SIZE = 2        # 키워드 조합 개수 (USE_COMBINATION=True일 때만 사용)
MAX_COMBINATIONS = 50       # 최대 조합 개수 (너무 많으면 시간 오래 걸림)

# ==========================================
# 유틸리티 함수
# ==========================================
def random_sleep(min_t=2.0, max_t=4.0):
    time.sleep(random.uniform(min_t, max_t))

def scroll_down(driver, count=3):
    body = driver.find_element(By.TAG_NAME, "body")
    for _ in range(count):
        body.send_keys(Keys.PAGE_DOWN)
        time.sleep(random.uniform(1.0, 2.0))

def combine_keywords(keywords, combination_size=2, max_combinations=50):
    """
    키워드를 조합하여 더 구체적인 검색어 생성
    예: ['AI', 'Python', 'ML'] -> 'AI Python', 'AI ML', 'Python ML'
    """
    all_combos = list(combinations(keywords, combination_size))
    # 너무 많으면 랜덤 샘플링
    if len(all_combos) > max_combinations:
        all_combos = random.sample(all_combos, max_combinations)
    
    # 조합을 공백으로 연결
    combined_keywords = [' '.join(combo) for combo in all_combos]
    random.shuffle(combined_keywords)
    return combined_keywords

def parse_number_k(text):
    """
    '1.2만회', '500K', '1.5M', '70,454회' 등을 숫자로 변환
    """
    if not text: return 0
    text = text.replace(',', '').replace('회', '').replace('views', '').replace('subscribers', '').replace('구독자', '').replace('명', '').strip()
    try:
        if '만' in text:
            return int(float(text.replace('만', '')) * 10000)
        if '억' in text:
            return int(float(text.replace('억', '')) * 100000000)
        if 'K' in text or '천' in text: # 영문 K or 한글 천
             return int(float(text.replace('K', '').replace('천', '')) * 1000)
        if 'M' in text or '백만' in text:
            return int(float(text.replace('M', '').replace('백만', '')) * 1000000)
        
        # 숫자만 남기기
        nums = re.findall(r'[\d\.]+', text)
        if nums:
            return int(float(nums[0]))
        return 0
    except:
        return 0

# ==========================================
# 유튜브 크롤링 함수들
# ==========================================
def get_video_links(driver, keyword, limit=3):
    print(f"\n[🔍 Search] '{keyword}'")
    try:
        # sp=CAMSAhAB: 조회수 순 정렬 (논쟁 많은 영상 타겟팅)
        search_url = f"https://www.youtube.com/results?search_query={keyword}&sp=CAMSAhAB"
        
        try:
            driver.get(search_url)
        except Exception as e:
            print(f"   [Warning] 검색 페이지 로드 실패 (Timeout 등): {e}")
            return []
            
        random_sleep(3, 5)
        
        links = []
        titles = []
        
        scroll_down(driver, 2)
        videos = driver.find_elements(By.CSS_SELECTOR, 'ytd-video-renderer')
        
        for video in videos:
            if len(links) >= limit: break
            try:
                a_tag = video.find_element(By.ID, "video-title")
                link = a_tag.get_attribute("href")
                title = a_tag.get_attribute("title")
                
                # Shorts 제외, 일반 영상만
                if "/watch?v=" in link:
                    links.append(link)
                    titles.append(title)
            except: continue
        return list(zip(titles, links))
    except: return []

def get_video_description(driver):
    try:
        try:
            driver.find_element(By.CSS_SELECTOR, "#expand").click()
            time.sleep(1)
        except: pass
        return driver.find_element(By.CSS_SELECTOR, "#description-inline-expander").text
    except: return ""

def get_video_metadata(driver):
    """영상 게시일, 좋아요 수, 조회수, 구독자 수 수집"""
    metadata = {
        'video_published_date': None,
        'video_likes': 0,
        'video_views': 0,
        'channel_subscribers': 0
    }
    
    # [Wait] 메타데이터가 로드될 때까지 잠시 대기 (최대 5초)
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#info span, #info-strings yt-formatted-string"))
        )
    except: pass

    # 1. 영상 게시일 & 조회수 (UI Scraping + Retry)
    for attempt in range(3):
        try:
            info_elements = driver.find_elements(By.CSS_SELECTOR, "#info span, yt-formatted-string#info span, #info-text span")
            for span in info_elements:
                text = span.text.strip()
                if not text: continue
                
                if ("조회수" in text or "views" in text) and metadata['video_views'] == 0:
                    metadata['video_views'] = parse_number_k(text)
                elif ("전" in text or "ago" in text or "202" in text) and not metadata['video_published_date']:
                    if "스트리밍" in text: continue 
                    metadata['video_published_date'] = text
            
            if metadata['video_views'] > 0: break
            time.sleep(1.5)
        except: 
            time.sleep(1)
            pass

    # [Fallback] 조회수가 여전히 0이면 소스 코드에서 Regex로 추출 (가장 강력한 방법)
    if metadata['video_views'] == 0:
        try:
            page_source = driver.page_source
            # 패턴 1: "viewCount":"12345"
            match1 = re.search(r'"viewCount":"(\d+)"', page_source)
            if match1:
                metadata['video_views'] = int(match1.group(1))
            else:
                # 패턴 2: "originalViewCount":"12345"
                match2 = re.search(r'"originalViewCount":"(\d+)"', page_source)
                if match2:
                    metadata['video_views'] = int(match2.group(1))
                else:
                    # 패턴 3: "viewCount":{"simpleText":"조회수 1.2만회"}
                    match3 = re.search(r'"viewCount":\{"simpleText":"(.*?)"\}', page_source)
                    if match3:
                        metadata['video_views'] = parse_number_k(match3.group(1))
        except: pass

    # 2. 좋아요 수
    try:
        like_selectors = [
            ".yt-spec-button-shape-next__button-text-content",
            "like-button-view-model button",
            "button[aria-label*='좋아요']",
            "yt-button-shape button[aria-label*='좋아요']",
            "#segmented-like-button button"
        ]
        for selector in like_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    text = elem.text.strip()
                    if text and (text.isdigit() or '천' in text or '만' in text or 'K' in text or 'M' in text):
                         val = parse_number_k(text)
                         if val > 0:
                             metadata['video_likes'] = val
                             break
                    aria_label = elem.get_attribute("aria-label")
                    if aria_label and ('좋아요' in aria_label or 'like' in aria_label.lower()):
                        val = parse_number_k(aria_label)
                        if val > 0:
                            metadata['video_likes'] = val
                            break
                if metadata['video_likes'] > 0: break
            except: continue
    except: pass

    # 3. 조회수 (Views) - Fallback (Specific Renderers)
    if metadata['video_views'] == 0:
        try:
            view_selectors = [
                "ytd-video-view-count-renderer span.view-count",
                "#info-container yt-formatted-string span:nth-child(1)", 
                "ytd-watch-metadata #description-inner #info span"
            ]
            for selector in view_selectors:
                try:
                    view_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    text = view_elem.text
                    if "조회수" in text or "views" in text:
                        metadata['video_views'] = parse_number_k(text)
                        break
                except: continue
        except: pass

    # 4. 구독자 수 (Subscribers)
    try:
        sub_selectors = [
            "#owner-sub-count",
            "yt-formatted-string#owner-sub-count"
        ]
        for selector in sub_selectors:
            try:
                sub_elem = driver.find_element(By.CSS_SELECTOR, selector)
                text = sub_elem.text # "구독자 100만명"
                if text:
                    metadata['channel_subscribers'] = parse_number_k(text)
                    break
            except: continue
    except: pass
    
    return metadata

def get_comments_from_video(driver, title, url, limit=30):
    print(f"   [Mining] {title[:20]}...")
    try:
        driver.get(url)
    except Exception as e:
        print(f"   [Warning] 영상 페이지 로드 실패 (Timeout 등): {e}")
        return []
        
    random_sleep(3, 5) # [Wait] Increased wait time for metadata loading
    collected = []
    
    # 0. 영상 메타데이터 수집 (게시일, 좋아요, 조회수, 구독자)
    video_metadata = get_video_metadata(driver)
    
    # 1. 설명글 수집 (Word2Vec 학습에 매우 중요)
    desc = get_video_description(driver)
    if desc and len(desc) > 50:
        collected.append({
            "video_title": title, 
            "video_url": url, 
            "author": "Uploader(Desc)",
            "comment": desc, 
            "type": "description",
            "video_published_date": video_metadata['video_published_date'],
            "video_likes": video_metadata['video_likes'],
            "video_views": video_metadata['video_views'],
            "channel_subscribers": video_metadata['channel_subscribers'],
            "comment_date": None,  # 설명글은 날짜 없음
            "crawled_at": datetime.now().strftime("%Y-%m-%d")
        })
    
    # 2. 댓글 수집
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "comments")))
    except:
        return collected
    
    driver.execute_script("window.scrollTo(0, 600);")
    random_sleep(3, 5)
    
    last_h = driver.execute_script("return document.documentElement.scrollHeight")
    while len(collected) < limit + 1:
        blocks = driver.find_elements(By.CSS_SELECTOR, 'ytd-comment-thread-renderer')
        for block in blocks:
            if len(collected) >= limit + 1: break
            try:
                text = block.find_element(By.ID, "content-text").text
                # [품질 필터] 너무 짧은 댓글 버림
                if len(text) < MIN_COMMENT_LENGTH: continue
                
                try: vote = block.find_element(By.ID, "vote-count-middle").text
                except: vote = "0"
                try: author = block.find_element(By.ID, "author-text").text.strip()
                except: author = "unknown"
                
                # 댓글 작성일 수집
                comment_date = None
                try:
                    date_elem = block.find_element(By.CSS_SELECTOR, "#published-time-text a")
                    comment_date = date_elem.text.strip()  # "3주 전", "2일 전" 등
                except:
                    pass
                
                collected.append({
                    "video_title": title, 
                    "video_url": url, 
                    "author": author,
                    "comment": text, 
                    "type": "comment",
                    "video_published_date": video_metadata['video_published_date'],
                    "video_likes": video_metadata['video_likes'],
                    "video_views": video_metadata['video_views'],
                    "channel_subscribers": video_metadata['channel_subscribers'],
                    "comment_date": comment_date,
                    "crawled_at": datetime.now().strftime("%Y-%m-%d")
                })
            except: continue
        
        if len(collected) >= limit + 1: break
        driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(random.uniform(1.5, 2.5))
        
        new_h = driver.execute_script("return document.documentElement.scrollHeight")
        if new_h == last_h: break
        last_h = new_h
        
    return collected

# ==========================================
# 메인 실행
# ==========================================
def main():
    # 파일 확인
    if "2025XXXX" in INPUT_KEYWORD_FILE:
        print("[주의] INPUT_KEYWORD_FILE 변수에 1번 스크립트에서 만든 파일명을 입력해주세요!")
        # 폴더 내 가장 최신 csv 파일 자동 찾기 (편의 기능)
        try:
            files = [f for f in os.listdir('.') if f.startswith('trend_keywords_') and f.endswith('.csv')]
            if files:
                latest_file = max(files, key=os.path.getctime)
                print(f"-> 최신 파일 자동 감지됨: {latest_file}")
                target_file = latest_file
            else:
                return
        except: return
    else:
        target_file = INPUT_KEYWORD_FILE

    # 키워드 로드
    try:
        df = pd.read_csv(target_file)
        keywords = df['keyword'].tolist()
        
        # 키워드 조합 여부 결정
        if USE_COMBINATION:
            print(f"\n[🔧 키워드 조합 생성중...]")
            print(f"   - 원본 키워드 개수: {len(keywords)}개")
            print(f"   - 조합 크기: {COMBINATION_SIZE}개씩")
            
            combined_keywords = combine_keywords(
                keywords, 
                combination_size=COMBINATION_SIZE, 
                max_combinations=MAX_COMBINATIONS
            )
            
            print(f"   - 생성된 조합 개수: {len(combined_keywords)}개")
            print(f"   - 예시: {combined_keywords[:3]}")
        else:
            print(f"\n[🔧 키워드 조합 OFF - 원본 키워드 사용]")
            print(f"   - 키워드 개수: {len(keywords)}개")
            print(f"   - 예시: {keywords[:3]}")
            combined_keywords = keywords  # 원본 키워드 그대로 사용
        
    except Exception as e:
        print(f"[Error] 파일 읽기 실패: {e}")
        return

    options = uc.ChromeOptions()
    options.add_argument('--no-first-run')
    options.add_argument("--mute-audio")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = uc.Chrome(options=options)
    driver.set_page_load_timeout(30)  # 30초 이상 로딩되면 Timeout 에러 발생 (무한 대기 방지)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    output_dir = "data/youtube"
    os.makedirs(output_dir, exist_ok=True)
    final_filename = os.path.join(output_dir, f"final_dataset_youtube_{timestamp}.csv")
    total_count = 0

    print("="*60)
    mode_text = "조합 키워드" if USE_COMBINATION else "원본 키워드"
    print(f"🎬 유튜브 마이닝 시작 ({mode_text}: {len(combined_keywords)}개)")
    print("="*60)

    try:
        for idx, kw in enumerate(combined_keywords, 1):
            print(f"\n[{idx}/{len(combined_keywords)}] 키워드: {kw}")
            
            video_list = get_video_links(driver, kw, VIDEOS_PER_KEYWORD)
            
            for title, link in video_list:
                data_list = get_comments_from_video(driver, title, link, COMMENTS_PER_VIDEO)
                
                # 메타데이터: 어떤 키워드로 찾았는지 기록
                for d in data_list:
                    d['search_keyword'] = kw
                
                if data_list:
                    res_df = pd.DataFrame(data_list)
                    header = not os.path.exists(final_filename)
                    res_df.to_csv(final_filename, index=False, mode='a', encoding='utf-8-sig', header=header)
                    total_count += len(data_list)
                
                random_sleep(3, 5) # 영상 간 휴식
            
            time.sleep(5) # 키워드 간 휴식

    finally:
        driver.quit()
        print("\n" + "="*60)
        print(f"🎉 수집 완료! 총 {total_count}개 데이터")
        print(f"📁 결과 파일: {final_filename}")
        print("="*60)

if __name__ == "__main__":
    main()