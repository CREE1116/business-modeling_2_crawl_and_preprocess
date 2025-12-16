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
import json
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# ==========================================
# [설정] API 키 및 파라미터
# ==========================================
# .env 파일에서 API 키 읽기
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("⚠️ GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요!") 

# 수집할 페이지 수 (DC인사이드)
DC_PAGES = 2

# Gemini 모델 설정
genai.configure(api_key=GEMINI_API_KEY)
# 최신 트렌드 분석엔 속도가 빠른 Flash 모델이 적합합니다.
model = genai.GenerativeModel('gemini-1.5-pro')

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
# 역할
당신은 IT 기술 트렌드 빅데이터를 분석하는 **'키워드 추출 엔진'**입니다.
아래 [데이터]를 정밀 분석하여, 기술 트렌드 분석에 유효한 핵심 키워드를 **최대한 많이(50개 이상 목표)** 추출하세요.

[데이터 시작]
{doc_text}
[데이터 끝]

# 핵심 목표
1. **Quantity (양):** 텍스트에 등장한 유의미한 기술 키워드를 빠짐없이 긁어모으세요.
2. **Distinct (다양성):** 똑같은 의미의 단어를 반복하지 말고, **서로 다른 세부 기술**이나 **구체적인 주제**를 찾아내세요.

# 추출 규칙 (Algorithm)
1. **[복합 명사구 우선]**: 단순한 단어(예: 'AI', '로봇')는 너무 포괄적입니다. 본문의 맥락을 살려 **'주체 + 세부기술/특징'** 형태로 추출하세요.
   - (Bad): 삼성전자, HBM, 로봇, 생성형 AI
   - (Good): 삼성전자 HBM4, 휴머노이드 로봇 제어, 생성형 AI 환각 문제, 온디바이스 AI 칩

2. **[복합 명사구와 단순 명사]**: 복합명사구를 사용했다면, 그 이후에는 해당 복합명사 안에서의 조합으로 문맥적 의미 없이도 명확힌 기술 키워드를 다음 키워드에 적어두어야합니다.
   예시: keyword
         AI 생성 이미지 인페인팅 평가,
         AI 생성,
         이미지 생성,
         인페인팅,
         AI 평가,

2. **[의미적 중복 제거 (Semantic De-duplication)]**: 표기법만 다르고 뜻이 같은 단어는 하나만 남기세요.
   - '챗GPT'와 'ChatGPT'가 둘 다 있다면 -> 영문인 **'ChatGPT'**만 추출
   - '인공지능'과 'AI'가 둘 다 있다면 -> 더 짧고 명확한 **'AI'**만 추출
   - 단, **'AI 학습'**과 **'AI 추론'**은 서로 다른 기술 단계이므로 **둘 다 추출**해야 합니다. (이 차이를 구분하는 것이 핵심입니다)

3. **[금융/잡담 필터링]**: 아래 내용은 발견 즉시 삭제하세요.
   - 주가, 급등/급락, 목표가, 실적, 배당, 코인 시세, 투자 전망
   - "충격", "대박", "결국", "공개" 같은 수식어

4. **[엔티티 정규화]**:
   - 영어 고유명사(모델명, 라이브러리명)는 원문 철자를 유지하세요.

# 출력 가이드
- 카테고리를 나누지 말고, 모든 키워드를 하나의 리스트로 통합하세요.
- 출력은 반드시 CSV 포맷(헤더 포함)으로 하세요.

keyword
ChatGPT-5o,
HBM4E 메모리,
엔비디아 블랙웰,
자율주행 레벨4,
Sora 영상 생성,
(이하 생략...)
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