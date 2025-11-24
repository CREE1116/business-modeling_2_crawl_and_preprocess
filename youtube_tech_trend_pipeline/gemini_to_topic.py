import google.generativeai as genai
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

# ==========================================
# [설정] API 키 및 파라미터
# ==========================================
# 구글 AI Studio(https://aistudio.google.com/)에서 발급받은 키를 입력하세요
GEMINI_API_KEY = "" 

# 수집할 페이지 수 (DC인사이드)
DC_PAGES = 2

# Gemini 모델 설정
genai.configure(api_key=GEMINI_API_KEY)
# 최신 트렌드 분석엔 속도가 빠른 Flash 모델이 적합합니다.
model = genai.GenerativeModel('gemini-2.5-flash')

# ==========================================
# 1. 데이터 수집 모듈
# ==========================================
def crawl_dcinside(pages=3):
    """DC인사이드 주요 갤러리 개념글 수집"""
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
    
    # 노이즈 필터링 패턴
    noise_patterns = ['ㅋ', 'ㅎ', 'ㄷ', 'ㅇㅇ', '...', '??', '!!']
    
    print(f"   -> DC인사이드 {len(galleries)}개 갤러리 순회 중...")
    
    for g_id, g_name, g_type in galleries:
        for page in range(1, pages + 1):
            try:
                if g_type == 'major':
                    url = f"{base_url}/board/lists/?id={g_id}&exception_mode=recommend&page={page}"
                else:
                    url = f"{base_url}/mgallery/board/lists/?id={g_id}&exception_mode=recommend&page={page}"
                
                res = requests.get(url, headers=headers, timeout=5)
                if res.status_code != 200: continue
                
                soup = BeautifulSoup(res.text, 'html.parser')
                rows = soup.select('.ub-content.us-post')
                if not rows: rows = soup.select('tr.ub-content')
                
                for row in rows:
                    try:
                        title_tag = row.select_one('.gall_tit a')
                        if title_tag:
                            title = title_tag.text.strip()
                            # 간단한 전처리
                            if len(title) < 2: continue
                            if any(p * 3 in title for p in noise_patterns): continue # ㅋㅋㅋ 반복 등
                            titles.append(f"[{g_name}] {title}") # 갤러리 이름 포함해서 문맥 제공
                    except: pass
                
                time.sleep(random.uniform(0.5, 1.0)) # 차단 방지
            except Exception as e:
                print(f"      [Error] {g_name}: {e}")
                
    return list(set(titles))

def collect_data():
    """RSS 기반 데이터 수집 (Selenium 불필요)"""
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
                            raw_data.append(f"[{name}] {title_elem.text}")
                            count += 1
                    except: pass
            
            # RSS 2.0 형식
            if count == 0:
                for item in root.findall(".//item"):
                    try:
                        title_elem = item.find("title")
                        if title_elem is not None and title_elem.text:
                            raw_data.append(f"[{name}] {title_elem.text}")
                            count += 1
                    except: pass
            
            if count > 0:
                print(f"      -> {name}: {count}개")
        except:
            pass
    
    print(f"   -> 총 {len(raw_data)}개 텍스트 확보.\n")
    return raw_data

# ==========================================
# 2. Gemini 분석 모듈 (BERT 대체)
# ==========================================
def extract_keywords_with_gemini(docs):
    print("\n" + "="*60)
    print(f"🧠 [Phase 2] Gemini 1.5 Flash 트렌드 분석")
    print("="*60)
    
    if not docs: return []
    
    # 너무 많은 데이터를 한 번에 보내면 토큰 제한에 걸릴 수 있으므로 샘플링하거나 배치를 나눔
    # 여기서는 최신 데이터 위주로 최대 500개만 추려서 보냄 (Flash 모델은 100만 토큰까지 가능하긴 함)
    docs_sample = docs[:2000] 
    
    doc_text = "\n".join(docs_sample)
    
    # 프롬프트 엔지니어링 (핵심) - reason 컬럼 제거하여 파싱 에러 방지
    prompt = f"""
    아래 텍스트는 현재 한국의 기술 뉴스 헤드라인과 기술블로그 게시글의 제목들입니다.

    [데이터 시작]
    {doc_text}
    [데이터 끝]

    [목표]
    이 텍스트들을 분석하여, AI/IT 기술 트렌드와 관련된 키워드 30개 이상을 추출해주세요.

    [매우 중요]
    - 키워드는 반드시 [데이터 시작]과 [데이터 끝] 사이 텍스트에 실제로 등장한 단어·표현만 사용하세요.
    - 뉴스/커뮤니티에 등장하지 않은 기술명, 회사명, 모델명, 약어를 새로 만들지 마세요.
    - 영어 고유명사와 모델명(ChatGPT, GPT-5.1, Gemini 등)은 원문에 나온 철자를 그대로 사용하세요.

    [제외할 카테고리]
    - 주식, 투자, 코인, 암호화폐, 금리, 환율 등 금융/투자 관련 키워드는 완전히 제외하세요.
    - 특정 기업의 주가나 재무 관련 내용도 제외하세요.

    [집중할 카테고리]
    - AI/머신러닝 기술 (ChatGPT, Gemini, LLM, 딥러닝 등)
    - 로봇/자동화 기술 (휴머노이드 로봇, 산업용 로봇 등)
    - 반도체/하드웨어 기술 (AI 칩, GPU, HBM 등의 '기술' 자체)
    - 소프트웨어/플랫폼 (앱, 서비스, 프레임워크 등)
    - 신기술/미래기술 (양자컴퓨팅, AR/VR, 메타버스 등)
    - 데이터/클라우드 기술

    [조건]
    1. 추상적인 단어(상승, 전망, 폭락, 특징주, 마감, 코스피)는 절대 제외하세요.
    2. 단어 자체가 주는 의미가 여러 가지일 경우 맥락을 포함하는 '주체 + 사건/재료' 형태의 복합 키워드로 만드세요.
    - 나쁜 예: 삼성전자, 엔비디아, 로봇, 금리
    - 좋은 예: 삼성전자 HBM, 엔비디아 AI칩, 휴머노이드 로봇, GPT 검열 논란
    3. 복합 키워드도 원문에 등장한 단어만 조합해서 만드세요.
    - 예: "삼성전자 HBM"이 원문에 있으면 그대로 사용 가능, "삼성전자 HBM 기술"처럼 '기술' 한 단어만 추가하는 것은 허용
    4. 복합키워드라도 지나치게 복잡해지거나 길어지는것을 경계하세요
    5. 커뮤니티 은어(돔황챠, 떡상 등)는 그 원인이 되는 표준어 이슈로 번역하세요.
    6. 기술 자체에 초점을 맞추세요.
    - "엔비디아 주가" → 제외
    - "엔비디아 AI칩 성능" → 포함
    - "삼성전자 실적" → 제외
    - "삼성전자 HBM 기술" → 포함
    7. 반드시 30개 이상 채워주세요. 많을수록 좋습니다.
    8. 줄임말이나 은어가 있을 경우, 원문에 등장한 공식 명칭(회사/서비스/모델 이름)으로 변환해 키워드를 만드세요.

    [출력 형식]
    반드시 아래 CSV 형식으로만 출력하세요. (헤더 포함, keyword 안에는 쉼표를 넣지 마세요)
    category는 AI, 로봇, 반도체, 소프트웨어, 데이터, 클라우드만 사용하세요.

    keyword,category
    ChatGPT 성능 향상,AI
    휴머노이드 로봇 기술,로봇
    HBM 메모리 기술,반도체
    """
    
    print("   -> Gemini에게 분석 요청 중... (약 5~10초 소요)")
    try:
        response = model.generate_content(prompt)
        result_text = response.text
        
        # 마크다운 코드 블록 제거 (```csv ... ```)
        result_text = re.sub(r'```csv', '', result_text)
        result_text = re.sub(r'```', '', result_text)
        
        # 불필요한 텍스트 제거 (}}, 공백 등)
        result_text = re.sub(r'\}\}.*$', '', result_text, flags=re.MULTILINE)
        result_text = result_text.strip()
        
        # 빈 줄 제거
        lines = [line.strip() for line in result_text.split('\n') if line.strip()]
        result_text = '\n'.join(lines)
        
        print("   -> 분석 완료!")
        print(f"   -> 추출된 키워드 미리보기:")
        print("   " + "\n   ".join(lines[:5]))
        
        return result_text
        
    except Exception as e:
        print(f"   [Error] Gemini API 호출 실패: {e}")
        return None

# ==========================================
# 메인 실행
# ==========================================
def main():
    # 1. 데이터 수집
    docs = collect_data()
    
    # 2. Gemini 분석
    csv_string = extract_keywords_with_gemini(docs)
    
    # 3. 결과 저장
    if csv_string:
        try:
            # 문자열을 StringIO로 변환하여 PD로 읽기
            from io import StringIO
            df = pd.read_csv(StringIO(csv_string))
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            filename = f"gemini_trend_keywords_{timestamp}.csv"
            
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            
            print("\n" + "="*60)
            print(f"🎉 분석 성공! 파일 저장됨: {filename}")
            print("="*60)
            print(df)
            
        except Exception as e:
            print(f"파싱 에러: {e}")
            print("원본 응답:", csv_string)
    else:
        print("분석된 데이터가 없습니다.")

if __name__ == "__main__":
    main()