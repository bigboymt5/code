# 표준 라이브러리
import os
import sys
sys.dont_write_bytecode = True
import traceback
import json
import requests
import argparse
import random
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

# 외부 라이브러리
import MetaTrader5 as mt5
import pandas as pd
from openai import OpenAI

# MT5 계정 정보 (필요한 경우)
# 계정 정보
ACCOUNT_ID = 17055878
PASSWORD = 'Realboy9989*'
SERVER = 'VantageInternational-Live 7'
BROKER_UTC_OFFSET = 2  # 브로커 서버 시간 (UTC+2)

# MT5 초기화 함수
def init_mt5(use_login=True):
    """MT5 초기화 및 로그인 (선택적)"""
    if not mt5.initialize():
        print(f"MT5 초기화 실패, 에러 코드: {mt5.last_error()}")
        return False

    # 로그인 시도 (선택적)
    if use_login:
        if not mt5.login(ACCOUNT_ID, password=PASSWORD, server=SERVER):
            print(f"MT5 로그인 실패, 에러 코드: {mt5.last_error()}")
            print("[정보] 로그인 없이 계속 진행합니다.")
            # 로그인 실패해도 계속 진행 (일부 데이터는 접근 가능할 수 있음)

    return True

# 전역 변수
HOURS_VALUE = 12  # 기본 시간 캔들
TICKER_SYMBOL = "XAUUSD"  # 기본 심볼

# 브로커 표준 심볼 맵
BROKER_SYMBOLS = {
    "EURUSD": "EURUSD",
    "USDJPY": "USDJPY",
    "USDKRW": "USDKRW",
    "XAUUSD": "XAUUSD",
    "BTCUSD": "BTCUSD",
    "CL-OIL": "CL-OIL",
    "TSLA": "TSLA",
    "AAPL": "AAPL",
    "GOOG": "GOOG",
    "MSFT": "MSFT",
    "NVIDIA": "NVIDIA",
    "QQQ": "QQQ",
    "NAS100": "NAS100.r",
    "VIX": "VIX.r",
    "ETHUSD": "ETHUSD",
    "AMAZON": "AMAZON"
}

# 티커 한글명 맵
TICKER_NAMES = {
    "BTCUSD": "비트코인",
    "USDJPY": "엔화",
    "USDKRW": "달러환율",
    "XAUUSD": "골드",
    "CL-OIL": "크루드오일",
    "TSLA": "테슬라",
    "AAPL": "애플",
    "GOOG": "구글",
    "MSFT": "마이크로소프트",
    "NVIDIA": "엔비디아",
    "QQQ": "QQQ",
    "NAS100": "나스닥100",
    "NAS100.r": "나스닥100",
    "VIX": "공포지수",
    "VIX.r": "공포지수",
    "ETHUSD": "이더리움",
    "AMAZON": "아마존"
}

# 최종 추천에 따른 이모지 맵 (랜덤 선택)
RECOMMENDATION_EMOJIS = {
    "Strong BUY": ["😄", "🚀", "📈", "💪", "🔥", "🌟", "✨", "💰", "🎯"],
    "BUY": ["😊", "📊", "✅", "👍", "💹", "🌱", "📉↗", "🟢"],
    "HOLD": ["😐", "⏸️", "🤔", "📍", "⚖️", "⏳", "🔒", "➖"],
    "SELL": ["😟", "📉", "⚠️", "👎", "🔻", "🟡", "↘️", "⬇️"],
    "Strong SELL": ["😱", "💔", "🆘", "❌", "⬇️", "🔴", "💥", "📉📉"]
}

def normalize_symbol(symbol):
    """
    심볼을 브로커 표준 심볼로 정규화

    Args:
        symbol: 입력 심볼 (소문자, 접미사 포함 가능)

    Returns:
        tuple: (mt5_symbol, search_keyword)
        - mt5_symbol: MT5에서 사용할 표준 심볼
        - search_keyword: API 검색용 키워드 (접미사 제거)
    """
    # 대문자로 변환
    symbol_upper = symbol.upper()

    # 접미사 제거 (.r, .m 등)
    base_symbol = symbol_upper.split('.')[0]

    # 브로커 표준 심볼 찾기
    mt5_symbol = BROKER_SYMBOLS.get(base_symbol, symbol_upper)

    # 검색용 키워드 (접미사 제거)
    search_keyword = mt5_symbol.split('.')[0]

    print(f"[심볼 정규화] 입력: {symbol} -> MT5: {mt5_symbol}, 검색: {search_keyword}")

    return mt5_symbol, search_keyword




# Updated Analysis Format class
class AnalysisFormat(BaseModel):
    current_situation: str = Field(
        ...,
        description="현재 심볼의 상황 설명 (50자 내외)"
    )
    technical_analysis: str = Field(
        ...,
        description="기술적 분석 설명 (100자 내외)"
    )
    fundamental_analysis: str = Field(
        ...,
        description="펀더멘털 및 심리적 분석 (100자 내외)"
    )
    expert_opinion: str = Field(
        ...,
        description="전문가들의 의견 BUY/SELL (50자 내외)"
    )
    final_recommendation: str = Field(
        ...,
        pattern="^(BUY|SELL)$",
        description="최종 의견 BUY/SELL (50자 내외)"
    )



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

def get_timeframe_from_hours(hours):
    """시간 값을 MT5 타임프레임으로 변환"""
    timeframe_map = {
        1: mt5.TIMEFRAME_H1,
        2: mt5.TIMEFRAME_H2,
        3: mt5.TIMEFRAME_H3,
        4: mt5.TIMEFRAME_H4,
        6: mt5.TIMEFRAME_H6,
        8: mt5.TIMEFRAME_H8,
        12: mt5.TIMEFRAME_H12,
    }
    return timeframe_map.get(hours, mt5.TIMEFRAME_H12)

def create_prompt(symbol=None, hours=None):
    """
    Args:
        symbol: 거래 심볼 (기본값: XAUUSD)
        hours: 캔들 시간 (기본값: 6)
    """
    global TICKER_SYMBOL, HOURS_VALUE

    if symbol is None:
        symbol = TICKER_SYMBOL
    if hours is None:
        hours = HOURS_VALUE

    # 심볼 정규화
    mt5_symbol, search_keyword = normalize_symbol(symbol)

    # MT5 초기화
    if not init_mt5():
        raise Exception("MT5 Initialization failed.")

    # 타임프레임 설정
    timeframe = get_timeframe_from_hours(hours)

    # 데이터 조회 (MT5 표준 심볼 사용)
    print(f"[디버그] MT5에서 {mt5_symbol} 데이터 조회 중... (타임프레임: {hours}H)")
    rates = mt5.copy_rates_from_pos(mt5_symbol, timeframe, 0, 1)
    if rates is None or len(rates) == 0:
        error = mt5.last_error()
        print(f"[에러] MT5 데이터 조회 실패 - 심볼: {mt5_symbol}, 에러: {error}")
        # 사용 가능한 심볼 목록 일부 출력
        symbols = mt5.symbols_get()
        if symbols:
            print(f"[정보] 사용 가능한 심볼 예시 (처음 10개):")
            for s in symbols[:10]:
                print(f"  - {s.name}")
        raise Exception(f"No data received from MT5 for {mt5_symbol}. Error: {error}")
    current_price = rates[0]['close']
    print(f"[디버그] {mt5_symbol} 현재가: {current_price}")

    # 날짜 정보 가져오기
    dates = get_date_ranges()
    price_range_min = current_price - PRICE_DEVIATION
    price_range_max = current_price + PRICE_DEVIATION

    # 심볼명 표시용 변환 (XAUUSD -> Gold 등)
    symbol_display = search_keyword
    if search_keyword == "XAUUSD":
        symbol_display = "XAUUSD (Gold)"

    prompt = f"""Please search for {symbol_display} analysis and news !

SEARCH REQUIREMENTS:
Search and analyze both text content AND chart images from the specified sources
Include both written market analysis AND visual technical chart analysis in the final prediction
Search content from the following dates: {dates['date_range']} = Prioritize the most recent content.

CURRENT MARKET DATA:
- Symbol: {search_keyword}
- Timeframe: {hours}H candle
- Current Price: {current_price}
- Valid price range: ${price_range_min:.2f} to ${price_range_max:.2f}

Sources to check (prioritize these websites):
1. https://www.investing.com/
2. https://www.tradingview.com/
3. https://www.fxstreet.com/
4. https://www.kitco.com/
5. https://www.barchart.com/

Search for events related to: Market sentiment, technical factors, fundamental news, expert opinions

DATE FILTERS:
- ONLY include content from these dates: {dates['date_range']}
- STRICTLY EXCLUDE any content from dates not listed above
- EXCLUDE any content where historical data deviates more than ${PRICE_DEVIATION} from the current price ({current_price})

REQUIRED RESPONSE FORMAT (JSON):
You MUST respond with ONLY a JSON object in this exact format, without any additional text:

{{
    "ko": {{
        "current_situation": "현재 {search_keyword}의 상황을 50자 내외로 설명 (예: 급락, 급상승, 완만한 상승, 횡보, 현재 12% 상승, 20% 하락 등) - 한글",
        "technical_analysis": "20일선, 볼린저밴드 등 검색된 기술적 지표를 사용한 100자 내외의 설명 - 한글",
        "fundamental_analysis": "실적발표 호재 악재 이슈 사건 펀더멘털 및 심리적 요인과 지표 등 지리적 원인등에 대한 100자 내외의 설명 - 한글",
        "expert_opinion": "검색된 전문가들의 단기적 매수 매도 의견 요약 (100자 내외) - 한글",
        "final_recommendation": "Strong BUY" 또는 "Strong SELL" 또는 "BUY" 또는 "SELL" 또는 "HOLD"
    }},
    "en": {{
        "current_situation": "Describe the current situation of {search_keyword} in about 50 characters - English",
        "technical_analysis": "Describe technical analysis using indicators like 20-day MA, Bollinger Bands in about 100 characters - English",
        "fundamental_analysis": "Describe fundamental and psychological factors, indicators, geopolitical reasons in about 100 characters - English",
        "expert_opinion": "Summarize experts' short-term buy/sell opinions in about 100 characters - English",
        "final_recommendation": "Strong BUY" or "Strong SELL" or "BUY" or "SELL" or "HOLD"
    }}
}}

IMPORTANT:
- Response must be ONLY valid JSON, no markdown, no code blocks, no explanations
- Provide analysis in TWO languages: Korean (ko) and English (en)
- All text fields in "ko" must be in Korean
- All text fields in "en" must be in English
- Stay within character limits for each field
- final_recommendation must be exactly "Strong BUY" or "BUY" or "HOLD" or "SELL" or "Strong SELL" (same value for all languages)

Answer based on comprehensive analysis of current market data, technical indicators, and expert opinions."""
    
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
    
    # </think> 태그 이후의 내용만 추출
    if '</think>' in content:
        content = content.split('</think>')[-1].strip()
    
    # 방법 1: JSON 블록 찾기 (```json 형식)
    json_match = re.search(r'```json\s*({[\s\S]*?})\s*```', content)
    if json_match:
        try:
            return json_match.group(1)
        except:
            pass
            
    # 방법 2: next_candle_trend를 포함하는 JSON 객체 찾기 (개선된 패턴)
    json_match = re.search(r'(\{[^{}]*"next_candle_trend"[^{}]*"medium_term_target"[^{}]*\})', content, re.DOTALL)
    if json_match:
        try:
            json_str = json_match.group(1)
            # 유효한 JSON인지 확인
            json.loads(json_str)
            return json_str
        except:
            pass
    
    # 방법 3: 직접 JSON 객체를 찾음
    json_match = re.search(r'({[\s\S]*})', content)
    if json_match:
        try:
            json_str = json_match.group(1)
            # 유효한 JSON인지 확인
            json.loads(json_str)
            return json_str
        except:
            pass
    
    # 방법 4: 전체 응답이 JSON인지 확인
    try:
        json.loads(content)
        return content
    except:
        pass
        
    return None

def get_market_analysis(api_key: str, symbol=None, hours=None):
    """
    시장 분석을 수행하는 함수
    Args:
        api_key: Perplexity API 키
        symbol: 거래 심볼 (기본값: XAUUSD)
        hours: 캔들 시간 (기본값: 6)
    """
    global TICKER_SYMBOL, HOURS_VALUE

    if symbol is None:
        symbol = TICKER_SYMBOL
    if hours is None:
        hours = HOURS_VALUE

    # 심볼 정규화
    mt5_symbol, search_keyword = normalize_symbol(symbol)

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.perplexity.ai"
    )

    try:
        print(f"\n[디버그] API 요청 전송... (입력: {symbol} -> MT5: {mt5_symbol}, 검색: {search_keyword}, Timeframe: {hours}H)")
        response = client.chat.completions.create(
            model="sonar-reasoning-pro",
            messages=[
                {
                    "role": "system",
                    "content": """You must respond with a JSON object only, without any surrounding text, explanation, or code formatting.
                    The JSON should be in this exact format with TWO languages:
                    {
                        "ko": {
                            "current_situation": "현재 상황 설명 (50자 내외, 한글)",
                            "technical_analysis": "기술적 분석 (100자 내외, 한글)",
                            "fundamental_analysis": "펀더멘털 분석 (100자 내외, 한글)",
                            "expert_opinion": "전문가 의견 (100자 내외, 한글)",
                            "final_recommendation": "Strong BUY" or "BUY" or "HOLD" or "SELL" or "Strong SELL"
                        },
                        "en": {
                            "current_situation": "Current situation description (about 50 chars, English)",
                            "technical_analysis": "Technical analysis (about 100 chars, English)",
                            "fundamental_analysis": "Fundamental analysis (about 100 chars, English)",
                            "expert_opinion": "Expert opinion (about 100 chars, English)",
                            "final_recommendation": "Strong BUY" or "BUY" or "HOLD" or "SELL" or "Strong SELL"
                        }
                    }
                    Do NOT include markdown code blocks, do NOT include explanations, ONLY return the JSON object."""
                },
                {
                    "role": "user",
                    "content": create_prompt(symbol, hours)
                }
            ]
        )
        
        content = response.choices[0].message.content
        print("\n[디버그] API 응답:")
        print(content)

        # JSON 부분 추출
        json_str = extract_json(content)
        if not json_str:
            print("\n[에러] JSON을 찾을 수 없습니다")
            raise ValueError("No JSON found in response")

        try:
            json_content = json.loads(json_str)

            # 2개 언어 키 확인 (한글, 영어)
            required_langs = ['ko', 'en']
            for lang in required_langs:
                if lang not in json_content:
                    print(f"\n[경고] 필수 언어 키 '{lang}'가 응답에 없습니다")
                    raise ValueError(f"Missing language key: {lang}")

            # 각 언어별 필수 키 확인
            required_keys = ['current_situation', 'technical_analysis', 'fundamental_analysis',
                            'expert_opinion', 'final_recommendation']

            for lang in required_langs:
                if lang in json_content:
                    for key in required_keys:
                        if key not in json_content[lang]:
                            print(f"\n[경고] '{lang}'에서 필수 키 '{key}'가 없습니다")

            # 티커 한글명 가져오기
            ticker_name = TICKER_NAMES.get(mt5_symbol, TICKER_NAMES.get(search_keyword, ""))

            # 각 언어별로 처리
            now = datetime.now()
            os.makedirs('json', exist_ok=True)

            # 한글(ko) 처리 - current_situation과 expert_opinion에 티커명 추가
            ko_data = json_content.get('ko', {}).copy()
            if ticker_name and 'current_situation' in ko_data:
                ko_data['current_situation'] = f"{ticker_name} {ko_data['current_situation']}"
            if ticker_name and 'expert_opinion' in ko_data:
                ko_data['expert_opinion'] = f"{ticker_name} {ko_data['expert_opinion']}"

            # final_recommendation에 "단기전망" + 이모지 추가 (한글만)
            if 'final_recommendation' in ko_data:
                recommendation = ko_data['final_recommendation']
                emoji_list = RECOMMENDATION_EMOJIS.get(recommendation, [""])
                emoji = random.choice(emoji_list) if emoji_list else ""
                ko_data['final_recommendation'] = f"단기전망 {emoji} {recommendation}"

            # 메타데이터 생성 함수
            def create_save_data(lang_data, lang_code):
                return {
                    "symbol": mt5_symbol,
                    "search_keyword": search_keyword,
                    "display_name": ticker_name,
                    "timeframe": f"{hours}H",
                    "timestamp": now.strftime('%Y-%m-%d %H:%M:%S'),
                    "language": lang_code,
                    "analysis": lang_data
                }

            # 2개 파일로 저장 (한글, 영어)
            timestamp_str = now.strftime('%Y%m%d_%H%M%S')

            # 1. 한글 파일 (기본명)
            ko_filename = f"json/{search_keyword}_{timestamp_str}.json"
            with open(ko_filename, 'w', encoding='utf-8') as f:
                json.dump(create_save_data(ko_data, 'ko'), f, ensure_ascii=False, indent=4)
            print(f"\n[완료] 한글 분석 결과 저장: {ko_filename}")

            # 2. 영어 파일 (en_ 접두사)
            en_filename = f"json/en_{search_keyword}_{timestamp_str}.json"
            with open(en_filename, 'w', encoding='utf-8') as f:
                json.dump(create_save_data(json_content['en'], 'en'), f, ensure_ascii=False, indent=4)
            print(f"[완료] 영어 분석 결과 저장: {en_filename}")

            # 원본 전체 데이터도 저장 (디버깅용)
            all_filename = f"json/all_{search_keyword}_{timestamp_str}.json"
            all_save_data = {
                "symbol": mt5_symbol,
                "search_keyword": search_keyword,
                "display_name": ticker_name,
                "timeframe": f"{hours}H",
                "timestamp": now.strftime('%Y-%m-%d %H:%M:%S'),
                "all_languages": {
                    "ko": ko_data,
                    "en": json_content['en']
                }
            }
            with open(all_filename, 'w', encoding='utf-8') as f:
                json.dump(all_save_data, f, ensure_ascii=False, indent=4)
            print(f"[완료] 전체 언어 통합 파일 저장: {all_filename}")

            # 반환은 한글 데이터 (기존 호환성)
            return ko_data

        except json.JSONDecodeError as e:
            print(f"\n[에러] JSON 파싱 실패: {str(e)}")
            print(f"문제가 된 문자열: {json_str}")
            raise ValueError(f"Invalid JSON format: {str(e)}")

    except Exception as e:
        print(f"\n[에러 발생] {str(e)}")
        print("상세 에러:")
        traceback.print_exc()
        raise


def parse_arguments():
    """명령줄 인자를 파싱하는 함수"""
    global TICKER_SYMBOL, HOURS_VALUE

    # sys.argv에서 직접 파싱
    args = sys.argv[1:]

    for arg in args:
        if arg.startswith('h_val='):
            try:
                HOURS_VALUE = int(arg.split('=')[1])
                print(f"[설정] 캔들 시간: {HOURS_VALUE}H")
            except ValueError:
                print(f"[경고] 잘못된 h_val 값: {arg}, 기본값 {HOURS_VALUE}H 사용")
        elif arg.startswith('h_tic='):
            # 입력값 그대로 저장 (대소문자 유지, normalize_symbol에서 처리)
            TICKER_SYMBOL = arg.split('=')[1]
            print(f"[설정] 입력 심볼: {TICKER_SYMBOL}")

    # 기본값 출력
    if len(args) == 0:
        print(f"[설정] 기본값 사용 - 심볼: {TICKER_SYMBOL}, 캔들: {HOURS_VALUE}H")

    return TICKER_SYMBOL, HOURS_VALUE


if __name__ == "__main__":
    API_KEY = "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"

    # 명령줄 인자 파싱
    symbol, hours = parse_arguments()

    # 분석 실행
    print(f"\n{'='*80}")
    print(f"시장 분석 시작: {symbol} ({hours}H 캔들)")
    print(f"{'='*80}\n")

    result = get_market_analysis(API_KEY, symbol, hours)

    print(f"\n{'='*80}")
    print("분석 결과:")
    print(f"{'='*80}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"{'='*80}\n")


# 금 12시간 분석
#python t_fx.py h_val=12 h_tic=XAUUSD

# 유로달러 4시간 분석
#python t_fx.py h_val=4 h_tic=EURUSD

# 비트코인 8시간 분석
#python t_fx.py h_val=8 h_tic=BTCUSD