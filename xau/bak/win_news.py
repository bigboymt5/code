from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re
import os
from datetime import datetime

def create_news_directory():
    """뉴스 저장을 위한 디렉토리 생성"""
    news_dir = "news"
    if not os.path.exists(news_dir):
        os.makedirs(news_dir)
    return news_dir

def get_timestamp():
    """현재 날짜와 시간으로 파일명 생성"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def wait_for_page_load(driver):
    """페이지가 완전히 로드될 때까지 대기"""
    WebDriverWait(driver, 20).until(
        lambda driver: driver.execute_script('return document.readyState') == 'complete'
    )

def clean_text(text):
    """텍스트 정제 함수"""
    text = re.sub(r'\n\s*\n', '\n', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_gold_content(html_content):
    """모든 골드 관련 컨텐츠 추출"""
    soup = BeautifulSoup(html_content, 'html.parser')
    content_sections = []
    
    # Technical Overview 섹션
    content_sections.append("=== Technical Overview ===\n")
    tech_overview = soup.find('div', class_='editorialhighlight_technical')
    if tech_overview:
        paragraphs = tech_overview.find_all(['p'])
        for p in paragraphs:
            text = clean_text(p.get_text())
            if text:
                content_sections.append(f"{text}\n\n")

    # Fundamental Overview 섹션
    content_sections.append("=== Fundamental Overview ===\n")
    fund_overview = soup.find('div', class_='editorialhighlight_fundamental')
    if fund_overview:
        paragraphs = fund_overview.find_all(['p'])
        for p in paragraphs:
            text = clean_text(p.get_text())
            if text:
                content_sections.append(f"{text}\n\n")

    # Latest Gold News 섹션
    content_sections.append("=== Latest Gold News ===\n")
    news_section = soup.find('div', class_='fxs_col_50')
    if news_section:
        news_items = news_section.find_all(class_='fxs_entryHeadline')
        for item in news_items:
            # 제목
            title = clean_text(item.get_text())
            if title:
                content_sections.append(f"\n{title}\n")
            
            # 작성자와 날짜 정보
            meta_info = item.find_next(class_='fxs_flexbox')
            if meta_info:
                author_date = clean_text(meta_info.get_text())
                if author_date:
                    content_sections.append(f"{author_date}\n")
    
    return '\n'.join(content_sections)

def scrape_content(url):
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    
    # 모바일 디바이스 에뮬레이션 설정
    mobile_emulation = {
        "deviceMetrics": { "width": 360, "height": 640, "pixelRatio": 3.0 },
        "userAgent": "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36"
    }
    options.add_experimental_option("mobileEmulation", mobile_emulation)
    
    # 기본 설정
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # 자동화 감지 회피 설정
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        # news 디렉토리 생성
        news_dir = create_news_directory()
        
        # 타임스탬프 생성
        timestamp = get_timestamp()
        
        # 직접 컨텐츠 페이지로 이동
        driver.get(url)
        time.sleep(5)  # 초기 로딩 대기
        
        # 페이지 로드 완료 대기
        wait_for_page_load(driver)
        
        # HTML 콘텐츠 가져오기
        content = driver.page_source
        
        # HTML 파일로 저장
        html_filename = os.path.join(news_dir, f"content_{timestamp}.html")
        with open(html_filename, "w", encoding="utf-8") as f:
            f.write(content)
            
        # 모든 골드 관련 컨텐츠 추출하여 저장
        extracted_content = extract_gold_content(content)
        text_filename = os.path.join(news_dir, f"content_{timestamp}.txt")
        with open(text_filename, "w", encoding="utf-8") as f:
            f.write(extracted_content)

        print(f"파일이 성공적으로 저장되었습니다:")
        print(f"HTML: {html_filename}")
        print(f"Text: {text_filename}")

    except Exception as e:
        print(f"오류 발생: {str(e)}")

    finally:
        driver.quit()

if __name__ == "__main__":
    url = "https://www.fxstreet.com/markets/commodities/metals/gold"
    scrape_content(url)