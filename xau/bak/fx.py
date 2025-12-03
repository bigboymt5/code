# 표준 라이브러리
import os
import sys
sys.dont_write_bytecode = True
import traceback
import json
import requests
from fx_trend import main as get_trend_analysis 
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

# 외부 라이브러리
import MetaTrader5 as mt5
import pandas as pd
from openai import OpenAI

# 로컬 모듈
from mt5_time_set import init_mt5, logger, BROKER_UTC_OFFSET
from core_indicators import (
    calculate_indicators,
    create_technical_analysis_prompt,
    get_previous_candle,
    save_candle_data,
    TIMEFRAMES
)




# After - Updated GoldAnalysisFormat class
class GoldAnalysisFormat(BaseModel):
    next_candle_trend: str = Field(
        ..., 
        pattern="^(BUY|SELL)$"
    )
    confidence_level: int = Field(
        ...,
        ge=60,
        le=90
    )
    key_factors: str
    resistance_level: float
    support_level: float
    short_term_target: float
    medium_term_target: float



def get_formatted_dates():
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    def add_ordinal(day):
        if 10 <= day % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        return str(day) + suffix
    
    today_str = today.strftime("%B ") + add_ordinal(today.day)
    yesterday_str = yesterday.strftime("%B ") + add_ordinal(yesterday.day)
    
    return today_str, yesterday_str

def get_rounded_time():
    """현재 시간을 1시간 단위로 반올림"""
    current_time = datetime.now()
    # 30분을 기준으로 반올림
    if current_time.minute >= 30:
        current_time = current_time + timedelta(hours=1)
    
    # 시간만 남기고 분,초,마이크로초는 0으로 설정
    rounded_time = current_time.replace(minute=0, second=0, microsecond=0)
    return rounded_time


    

def get_date_ranges():
    """현재 날짜/시간을 기준으로 검색 날짜 범위를 생성"""
    current_time = datetime.now()
    today = current_time.date()
    weekday = current_time.weekday()  # 0=월요일, 6=일요일
    
    def add_ordinal(day):
        if 10 <= day % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        return str(day) + suffix
    
    def format_date_with_day(date):
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return f"{date.strftime('%B')} {add_ordinal(date.day)} ({weekdays[date.weekday()]})"
    
    def format_date_without_day(date):
        return f"{date.strftime('%B')} {add_ordinal(date.day)}"
    
    search_dates = []
    
    if weekday >= 5:  # 주말인 경우
        if weekday == 5:  # 토요일
            # 금요일과 토요일
            friday = today - timedelta(days=1)
            search_dates = [friday, today]
        else:  # 일요일
            # 금요일, 토요일, 일요일
            friday = today - timedelta(days=2)
            saturday = today - timedelta(days=1)
            search_dates = [friday, saturday, today]
    else:  # 평일인 경우
        if current_time.hour < 12:  # 오전
            yesterday = today - timedelta(days=1)
            search_dates = [yesterday, today]
        else:  # 오후
            search_dates = [today]
    
    # 날짜 범위 문자열 생성 (요일 포함)
    date_range = ", ".join([format_date_with_day(date) for date in search_dates])
    
    # 기존 포맷 호환성 유지를 위한 today_str, yesterday_str
    today_str = format_date_without_day(today)
    yesterday_str = format_date_without_day(today - timedelta(days=1))
    
    # MDY 형식의 날짜들
    dates_mdy = [d.strftime("%m-%d-%Y") for d in search_dates]
    
    return {
        'search_dates': search_dates,
        'date_range': date_range,
        'dates_mdy': dates_mdy,
        'today_str': today_str,
        'yesterday_str': yesterday_str,
        'today_mdy': today.strftime("%m-%d-%Y"),
        'yesterday_mdy': (today - timedelta(days=1)).strftime("%m-%d-%Y"),
        'old_date_example': (today - timedelta(days=30)).strftime("%m-%d-%Y"),
        'year': str(today.year)
    }

PRICE_DEVIATION = 5.0  # 허용 가격 편차 ($)

def create_prompt():
    # MT5 초기화 및 로그인 코드는 그대로 유지...
    if not init_mt5():
        raise Exception("MT5 Initialization failed.")
    
    symbol = "XAUUSD"
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)
    if rates is None or len(rates) == 0:
        raise Exception("No data received from MT5.")
    current_price = rates[0]['close']

    # 날짜 정보 가져오기
    dates = get_date_ranges()
    price_range_min = current_price - PRICE_DEVIATION
    price_range_max = current_price + PRICE_DEVIATION
    
    trend_analysis_result = get_trend_analysis()
    
    prompt = f"""Please search for XAUUSD (Gold) analysis and news !

SEARCH REQUIREMENTS:
Search and analyze both text content AND chart images from the specified sources
Include both written market analysis AND visual technical chart analysis in the final prediction
Search content from the following dates: {dates['date_range']} = Prioritize the most recent content.

CRITICAL TECHNICAL ANALYSIS DATA:

{trend_analysis_result}

IMPORTANT: This is my own verified technical analysis based on EMA, Ichimoku Cloud, and MACD indicators. 
must be incorporated into your analysis. 
Give this technical data significant weight in your final recommendation. 


Sources to check (ONLY use these five websites, no other sources are permitted):
1. https://primexbt.com/kr/price-chart/currencies/xau-usd
2. https://www.ifcmfx.com/ko/market-data/precious-metals-prices/xauusd
3. https://www.kitco.com/charts/gold
4. https://www.fxstreet.com/markets/commodities/metals/gold
5. https://www.barchart.com/forex/quotes/%5EXAUUSD
DO NOT use any additional sources or websites other than these five listed above!!

Search for events related to: US Federal Reserve (Fed) policy direction, geopolitical risks, US economic indicators and Trump policy announcements,
xauusd market sentiment and technical factors, and global gold demand and supply trends.

DATE FILTERS:
- ONLY include content from these dates: {dates['date_range']}
- STRICTLY EXCLUDE any content from dates not listed above
- Format all dates as: MM-DD-YYYY
- EXCLUDE any content where historical data deviates more than ${PRICE_DEVIATION} from the current price ({current_price})
- Valid price range: ${price_range_min:.2f} to ${price_range_max:.2f}


REQUIRED URL DATE FORMAT:
- Valid format examples: {', '.join([f'"...{date}/"' for date in dates['dates_mdy']])}
- Reject any URLs containing older dates

This prompt specifies:
- Prioritize searching the specified 5 websites, and additional sources may be included if they provide the latest content that meets the criteria.
- Focus keywords - "XAUUSD" "Gold" "Live" "Analysis" "News" "FX"
- The current price of the XAUUD/Gold asset is {current_price}
- Time constraint (only content from {dates['yesterday_str']} or later)
- Search for confidence indicators in technical analysis and strong market signals to determine confidence level
- The most critical aspect of the search is to find the latest news and analysis on XAUUSD and to identify future price trends for XAUUSD.

1. XAUUSD trend for the next 12 hours: Provide a definitive answer with "BUY" or "SELL."
2. Confidence level: Indicate a percentage between 50-100% (Strong signals must be above 76%)
3. Key factors: Explain the price trend rationale in one concise sentence using technical analysis terminology.
4. The most critical short-term (12-hour) primary resistance level: (Should be within an average range of $10 to $30 above the {current_price}.)
5. The most critical short-term (12-hour) primary support level: (Should be within an average range of $10 to $30 below the {current_price}.)
6. Short-term target price (within 12 hours): (Should be within an average range of $10 to $30 from the {current_price}.)
7. Medium-term target price (within 24 hours): (Should be within an average range of $20 to $60 from the {current_price}.)


Your response must strictly adhere to this structure and formatting:
1. Next candle trend: [buy/sell]
2. Confidence level: [Percentage]%
3. Key factors: [Brief explanation in English]
4. Resistance level (USD): [0000.00]
5. Support level (USD): [0000.00]
6. Short-term target price (USD): [0000.00]
7. Medium-term target price (USD): [0000.00]

Answer concisely and directly, using appropriate financial market terminology. Ensure the format above is followed precisely to avoid any deviation."""
    
    print("\n[디버그] 생성된 프롬프트:")
    print("="*80)
    print(prompt)
    print("="*80)
    return prompt



def parse_response(response_text):
   print("\n[디버그] API 응답 내용:")
   print("="*80)
   print(response_text)
   print("="*80)
   
   response_json = json.loads(response_text)
   print("\n[디버그] 파싱된 JSON 데이터:")
   print(json.dumps(response_json, indent=4, ensure_ascii=False))
   
   return response_json
 

def extract_json(content):
    """JSON 부분만 추출하는 함수 - 개선된 버전"""
    import re
    import json
    
    # 방법 1: JSON 블록 찾기 (```json 형식)
    json_match = re.search(r'```json\s*({[\s\S]*?})\s*```', content)
    if json_match:
        try:
            return json_match.group(1)
        except:
            pass
            
    # 방법 2: 직접 JSON 객체를 찾음
    json_match = re.search(r'({[\s\S]*})', content)
    if json_match:
        try:
            json_str = json_match.group(1)
            # 유효한 JSON인지 확인
            json.loads(json_str)
            return json_str
        except:
            pass
    
    # 방법 3: 전체 응답이 JSON인지 확인
    try:
        json.loads(content)
        return content
    except:
        pass
        
    return None

def get_gold_analysis(api_key: str):
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.perplexity.ai"
    )
    
    try:
        print("\n[디버그] API 요청 전송...")
        response = client.chat.completions.create(
           # model="sonar-reasoning-pro",
           model="sonar-reasoning-pro",
            messages=[
                {
                    "role": "system",
                    "content": """You must respond with a JSON object only, without any surrounding text, explanation, or code formatting. 
                    The JSON should be in this exact format:
                    {
                        "next_candle_trend": "BUY" or "SELL",
                        "confidence_level": number between 50-100,
                        "key_factors": "brief explanation",
                        "resistance_level": numeric price,
                        "support_level": numeric price,
                        "short_term_target": numeric price,
                        "medium_term_target": numeric price
                    }"""
                },
                {
                    "role": "user",
                    "content": create_prompt()
                }
            ]
        )
        
        content = response.choices[0].message.content
        print("\n[디버그] API 응답:")
        print(content)
        
        # JSON 부분 추출 (개선된 함수 사용)
        json_str = extract_json(content)
        if not json_str:
            print("\n[에러] JSON을 찾을 수 없습니다")
            # 가능하면 일부 구조화된 데이터라도 추출 시도
            try:
                # 직접 라인별로 파싱 시도
                lines = content.strip().split('\n')
                result = {}
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        value = value.strip().replace(',', '')
                        if key == 'next_candle_trend' or key == 'trend':
                            if 'buy' in value.lower():
                                result['next_candle_trend'] = 'BUY'
                            elif 'sell' in value.lower():
                                result['next_candle_trend'] = 'SELL'
                        elif 'confidence' in key:
                            try:
                                # 숫자만 추출
                                import re
                                nums = re.findall(r'\d+', value)
                                if nums:
                                    result['confidence_level'] = int(nums[0])
                            except:
                                pass
                        # 나머지 키도 비슷하게 추출...
                
                if result and 'next_candle_trend' in result and 'confidence_level' in result:
                    print("\n[경고] JSON 파싱 실패, 일부 데이터만 추출 성공")
                    return result
            except:
                pass
                
            raise ValueError("No JSON found in response")
            
        try:
            json_content = json.loads(json_str)
            
            # 키 이름 표준화 (대소문자 일치시키기)
            # 키 이름 표준화 (대소문자 일치시키기)
            standardized_json = {}
            key_mapping = {
                'next_candle_trend': 'next_candle_trend',
                'confidence_level': 'confidence_level', 
                'key_factors': 'key_factors',
                'resistance_level': 'Resistance_level',  # 대문자로 변경
                'resistance': 'Resistance_level',        # 대문자로 변경
                'support_level': 'Support_level',        # 대문자로 변경
                'support': 'Support_level',              # 대문자로 변경
                'short_term_target': 'short_term_target',
                'medium_term_target': 'medium_term_target'
            }
            
            for key, value in json_content.items():
                lowercase_key = key.lower()
                for mapping_key, standard_key in key_mapping.items():
                    if mapping_key in lowercase_key:
                        standardized_json[standard_key] = value
                        break
            
            # 필수 키가 있는지 확인
            # 필수 키가 있는지 확인
            required_keys = ['next_candle_trend', 'confidence_level', 'key_factors', 
                            'Resistance_level', 'Support_level', 'short_term_target', 'medium_term_target']
            
            for key in required_keys:
                if key not in standardized_json:
                    print(f"\n[경고] 필수 키 '{key}'가 응답에 없습니다")
            
            # 저장
            rounded_time = get_rounded_time()
            filename = f"ppx/ppx_re_{rounded_time.strftime('%Y%m%d_%H%M')}.json"
            os.makedirs('ppx', exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(standardized_json, f, ensure_ascii=False, indent=4)
                
            return standardized_json
            
        except json.JSONDecodeError as e:
            print(f"\n[에러] JSON 파싱 실패: {str(e)}")
            print(f"문제가 된 문자열: {json_str}")
            raise ValueError(f"Invalid JSON format: {str(e)}")

    except Exception as e:
        print(f"\n[에러 발생] {str(e)}")
        print("상세 에러:")
        traceback.print_exc()
        raise

if __name__ == "__main__":
    API_KEY = "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"
    get_gold_analysis(API_KEY)