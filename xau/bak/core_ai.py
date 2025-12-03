#core_ai
import os
import sys
import traceback
from datetime import datetime, timedelta
import MetaTrader5 as mt5
from openai import OpenAI
import json
import pandas as pd
from mt5_time_set import init_mt5, logger  # Import from mt5_time_set.py
from mt5_time_set import BROKER_UTC_OFFSET  # 추가
from core_indicators import (
    calculate_indicators,
    create_technical_analysis_prompt,
    get_previous_candle,
    save_candle_data,
    TIMEFRAMES
)

overwrite_file = True

# 폴더 및 파일 설정
OUTPUT_FOLDER = "core_response"
FINE_JSON_FOLDER = "core_response"
FILE_PREFIX = "core_"

# 기본 타임프레임 설정
SELECTED_TIMEFRAME = 'H2'  # 현재 프레임 설정

def set_timeframe(timeframe):
    global SELECTED_TIMEFRAME
    if timeframe in TIMEFRAMES:
        SELECTED_TIMEFRAME = timeframe
        return True
    return False

def get_timeframe_hours(timeframe):
    timeframe_hours = {
        'D1': 24,
        'H12': 12,
        'H6': 6,
        'H4': 4,
        'H3': 3,
        'H2': 2,       
        'H1': 1,
        'M30': 0.5,
        'M15': 0.25,
        'M10': 0.1667,
        'M5': 0.0833
    }
    return timeframe_hours.get(timeframe, 1)

def get_timeframe_interval(timeframe):
    """타임프레임에 따른 분 단위 간격 반환"""
    timeframes_in_minutes = {
        'M5': 5,
        'M10': 10,
        'M15': 15,
        'M30': 30,
        'H1': 60,
        'H2': 120,
        'H3': 180,
        'H4': 240,
        'H6': 360,
        'H12': 720
    }
    return timeframes_in_minutes.get(timeframe, None)

def parse_datetime(date_str, time_str=None):
    """
    날짜와 시간 문자열을 파싱하여 datetime 객체로 반환
    time_str이 None이면 현재 시간 기준으로 가장 최근의 거래 시간을 찾음
    입력된 시간을 타임프레임에 맞게 자동 조정
    """
    try:
        # 날짜 파싱
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])
        
        # 시간이 제공된 경우
        if time_str:
            hour = int(time_str[:2]) if len(time_str) >= 2 else 0
            minute = int(time_str[2:]) if len(time_str) > 2 else 0
            
            # 타임프레임별 시간 조정
            if SELECTED_TIMEFRAME == 'M15':
                minute = (minute // 15) * 15
            elif SELECTED_TIMEFRAME == 'M30':
                minute = (minute // 30) * 30
            elif SELECTED_TIMEFRAME == 'H1':
                minute = 0
            elif SELECTED_TIMEFRAME == 'H2':
                hour = (hour // 2) * 2
                minute = 0
        else:
            # 시간이 제공되지 않은 경우 현재 시간 기준으로 처리
            current_time = datetime.now()
            hour = current_time.hour
            minute = current_time.minute
            
            if SELECTED_TIMEFRAME == 'M15':
                minute = (minute // 15) * 15
            elif SELECTED_TIMEFRAME == 'M30':
                minute = (minute // 30) * 30
            elif SELECTED_TIMEFRAME == 'H1':
                minute = 0
            elif SELECTED_TIMEFRAME == 'H2':
                hour = (hour // 2) * 2
                minute = 0
        
        dt = datetime(year, month, day, hour, minute)
        
        #if dt.weekday() >= 5:
        #    logger.error(f"주말은 거래일이 아닙니다: {dt.strftime('%Y-%m-%d')}")
         #   return None
            
        # 조정된 시간 로깅
        logger.info(f"입력 시간: {time_str if time_str else 'auto'}")
        logger.info(f"조정된 시간: {dt.strftime('%Y-%m-%d %H:%M')}")
        
        return dt
        
    except Exception as e:
        logger.error(f"날짜/시간 파싱 실패: {str(e)}")
        return None

def get_latest_complete_candle_time(target_datetime, timeframe):
    """타임프레임에 맞게 가장 최근의 완료된 캔들 시간을 반환"""
    timeframes_in_minutes = {
        'M5': 5,
        'M10': 10,
        'M15': 15,
        'M30': 30,
        'H1': 60,
        'H2': 120,
        'H3': 180,
        'H4': 240,
        'H6': 360,
        'H12': 720
    }

    if timeframe not in timeframes_in_minutes:
        raise ValueError(f"Invalid timeframe: {timeframe}")

    # 타임프레임의 분 단위
    my_time = timeframes_in_minutes[timeframe]

    # 현재 시간 기준으로 가장 가까운 이전 캔들 시간 계산
    minute = target_datetime.minute
    adjusted_minute = (minute // my_time) * my_time
    latest_candle = target_datetime.replace(minute=adjusted_minute, second=0, microsecond=0)

    # 입력 시간이 현재 캔들 시간보다 이후일 경우
    if target_datetime < latest_candle:
        latest_candle -= timedelta(minutes=my_time)

    return latest_candle

def get_candle_data(symbol, target_datetime):
    try:
        print(f"\n=== 캔들 데이터 조회 시작: {symbol} ===")
        tf = TIMEFRAMES[SELECTED_TIMEFRAME]
        
        latest_complete_time = get_latest_complete_candle_time(target_datetime, SELECTED_TIMEFRAME)

       
        
        adjusted_target = latest_complete_time + timedelta(hours=BROKER_UTC_OFFSET)
        
        
        bars = 60
        print(f"조회할 캔들 수: {bars}개 (타임프레임: {get_timeframe_interval(SELECTED_TIMEFRAME)}분)")
        
        rates = mt5.copy_rates_from(symbol, tf, adjusted_target, bars)
        if rates is None or len(rates) == 0:
            logger.error(f"데이터 없음: {symbol} ({SELECTED_TIMEFRAME})")
            return None

        # 결과 데이터프레임 생성
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        # 타겟 시간 필터링
        df = df[df['time'] <= latest_complete_time]
        if df.empty:
            logger.error(f"필터링 후 데이터 없음: {symbol}")
            return None

        print(f"조회된 캔들 수: {len(df)}개")
        return df

    except Exception as e:
        logger.error(f"데이터 조회 실패: {str(e)}")
        return None

def get_latest_trading_date(df, target_datetime):
    try:
        if df.empty:
            logger.error("데이터프레임이 비어있음")
            return None

        available_times = df[df['time'] <= target_datetime]['time']
        
        if len(available_times) == 0:
            logger.error(f"대상 시간({target_datetime})까지의 데이터가 없음")
            return None

        latest_time = available_times.iloc[-1]
        
        logger.info(f"최근 거래 시간: {latest_time.strftime('%Y-%m-%d %H:%M:%S')} ({SELECTED_TIMEFRAME})")
        return latest_time

    except Exception as e:
        logger.error(f"거래 시간 확인 실패: {str(e)}")
        return None


def get_latest_news_content():
    """
    news 폴더에서 가장 최근의 뉴스 파일을 읽어 내용을 반환합니다.
    Returns:
        str: 뉴스 파일의 내용 또는 None (에러 발생 시)
    """
    try:
        news_folder = "news"
        if not os.path.exists(news_folder):
            logger.error(f"뉴스 폴더가 존재하지 않습니다: {news_folder}")
            return None

        # 뉴스 파일 목록 가져오기 (content_로 시작하는 파일만)
        news_files = [f for f in os.listdir(news_folder) if f.startswith('content_') and f.endswith('.txt')]
        
        if not news_files:
            logger.error("뉴스 파일이 존재하지 않습니다.")
            return None

        # 파일명 기준으로 정렬하여 가장 최근 파일 선택
        latest_file = max(news_files)
        file_path = os.path.join(news_folder, latest_file)

        # 파일 읽기
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        # 뉴스 내용을 출력
        print(f"\n=== 최근 뉴스 파일 내용 출력 ===\n파일명: {latest_file}\n내용:\n{content}\n===========================\n")

        logger.info(f"최근 뉴스 파일 로드 완료: {latest_file}")
        return content

    except Exception as e:
        logger.error(f"뉴스 파일 읽기 실패: {str(e)}")
        return None


def get_prediction(analysis_text):
    try:
        print("\n=== OpenAI 예측 요청 시작 ===")
        client = OpenAI(api_key='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')
        
        # 모든 타임프레임에 대해 뉴스 데이터 먼저 초기화
        news_content = get_latest_news_content()
        if news_content is None:
            news_content = "No recent news available."

        # 기본 프롬프트 템플릿 정의
        prompt_template = """
Based on the following market data to analyze:

* Analyze the XAUUSD market data and focus on the current price flow.
* Examine the forming candle's high/low movements and how they relate to recent support and resistance levels.
* Check US dollar trends, interest rates, and major economic indicators (e.g., CPI, NFP).
* Refer to the attached analyst report to identify support and resistance prices.

Technical Indicator Data:
{analysis_text}

Recent News and Analysis Reports:
{news_content}

1. XAUUSD trend for the next 12 hours: Provide a definitive answer with "BUY" or "SELL."
2. Confidence level: Indicate a percentage between 50-100% (Strong signals must be above 76%)
3. Key factors: Explain the price trend rationale in one concise sentence using technical analysis terminology.
4. The most critical short-term (12-hour) primary resistance level: (Should be within an average range of $10 to $30 above current price.)
5. The most critical short-term (12-hour) primary support level: (Should be within an average range of $10 to $30 below current price.)
6. Short-term target price (within 12 hours): (Should be within an average range of $10 to $30 from current price.)
7. Medium-term target price (within 24 hours): (Should be within an average range of $20 to $60 from current price.)

Your response must strictly adhere to this structure and formatting:
1. Next candle trend: [buy/sell]
2. Confidence level: [Percentage]%
3. Key factors: [Brief explanation in English]
4. Resistance level (USD): [0000.00]
5. Support level (USD): [0000.00]
6. Short-term target price (USD): [0000.00]
7. Medium-term target price (USD): [0000.00]

Answer concisely and directly, using appropriate financial market terminology. Ensure the format above is followed precisely to avoid any deviation."""

        # 프롬프트 템플릿에 실제 데이터 적용
        prompt = prompt_template.format(
            analysis_text=analysis_text,
            news_content=news_content
        )
            
        print(f"\n=== OpenAI 프롬프트 내용 ===\n{prompt}\n===========================\n")

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a financial expert and market analyst."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.0
        )
        
        result_text = response.choices[0].message.content.strip()
        print(f"OpenAI 원본 응답:\n{result_text}")
        return result_text
        
    except Exception as e:
        logger.error(f"예측 요청 실패: {str(e)}")
        return None   




def save_openai_response_as_text(response_text, analysis_time, selected_timeframe):
    try:
        # PPX 폴더 사용
        output_folder = "ppx"
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        # Initialize all variables
        response_data = {
            "next_candle_trend": None,
            "confidence_level": None,
            "key_factors": None,
            "Resistance_level": None,
            "Support_level": None,
            "short_term_target": None,
            "medium_term_target": None
        }
        
        # Parse OpenAI response
        for line in response_text.split('\n'):
            line = line.strip()
            if line.startswith('1. Next'):
                response_data["next_candle_trend"] = line.split(':')[1].strip()
            elif line.startswith('2. Confidence level:'):
                confidence = line.split(':')[1].strip().rstrip('%')
                response_data["confidence_level"] = int(confidence) if confidence else None
            elif line.startswith('3. Key factors:'):
                response_data["key_factors"] = line.split(':')[1].strip()
            elif line.startswith('4. Resistance level (USD):') or line.startswith('4. USD.cents:'):
                resistance_str = line.split(':')[1].strip().strip('[]')
                response_data["Resistance_level"] = float(resistance_str) if resistance_str else None
            elif line.startswith('5. Support level (USD):') or line.startswith('5. USD.cents:'):
                support_str = line.split(':')[1].strip().strip('[]')
                response_data["Support_level"] = float(support_str) if support_str else None
            elif line.startswith('6. Short-term target price (USD):'):
                short_target_str = line.split(':')[1].strip().strip('[]')
                response_data["short_term_target"] = float(short_target_str) if short_target_str else None
            elif line.startswith('7. Medium-term target price (USD):'):
                medium_target_str = line.split(':')[1].strip().strip('[]')
                response_data["medium_term_target"] = float(medium_target_str) if medium_target_str else None
        
        # 새로운 파일명 형식 사용
        file_name = f"ppx_re_{analysis_time.strftime('%Y%m%d_%H%M')}.json"
        file_path = os.path.join(output_folder, file_name)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, indent=4)
        
        logger.info(f"OpenAI 응답 저장 완료: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"OpenAI 응답 저장 실패: {str(e)}")
        return False
    
def main(date_str=None, time_str=None, indicator_config=None):
    logger.info("core_ai.py 실행 시작")
    SELECTED_TIMEFRAME = 'H2'
    try:
        if date_str is None or time_str is None:
            now = datetime.now()
            date_str = now.strftime('%Y%m%d')
            time_str = now.strftime('%H%M')
        
        analysis_time = parse_datetime(date_str, time_str)
        if analysis_time is None:
            logger.error("날짜/시간 설정 실패")
            return
        
        # 완성된 캔들 시간 계산
        latest_complete_time = get_latest_complete_candle_time(analysis_time, SELECTED_TIMEFRAME)
        if latest_complete_time is None:
            logger.error("완성 캔들 시간 계산 실패")
            return
        
        # 파일 이름 구성
        file_name = f"{SELECTED_TIMEFRAME}_{FILE_PREFIX}{analysis_time.strftime('%Y%m%d_%H%M')}.txt"
        file_path = os.path.join(FINE_JSON_FOLDER, file_name)
        
        # 파일 존재 여부 확인
        if os.path.exists(file_path):
            if not overwrite_file:
                logger.info(f"파일이 이미 존재합니다: {file_path}. 'overwrite_file'이 False로 설정되어 실행을 중단합니다.")
                return
            else:
                logger.info(f"파일이 이미 존재합니다: {file_path}. 'overwrite_file'이 True로 설정되어 기존 파일을 덮어씁니다.")
        
        if not init_mt5():  # Using imported init_mt5
            return
        
        
        # 타임프레임 간격 계산
        interval_minutes = get_timeframe_interval(SELECTED_TIMEFRAME)
        if interval_minutes is None:
            raise ValueError(f"지원하지 않는 타임프레임입니다: {SELECTED_TIMEFRAME}")

        # 예측 목표 시간 계산
        target_time = latest_complete_time + timedelta(minutes=interval_minutes)

        logger.info(f"분석 시점(완성 캔들): {latest_complete_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"예측 목표: {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 기본 지표 설정이 없는 경우
        if indicator_config is None:
            indicator_config = {
                'selected_indicators': ['EMA', 'ICHIMOKU', 'MACD', 'RSI'],
                'parameters': {
                    'EMA': {'periods': [9, 21]},
                    'ICHIMOKU': {'tenkan': 9, 'kijun': 26, 'senkou_b': 52},
                    'MACD': {'fast': 6, 'slow': 15, 'signal': 9},
                    'RSI': {'period': 9}
                }
            }
        
        # 현재 캔들 데이터 가져오기
        df_gold = get_candle_data("XAUUSD", analysis_time)
        df_usdx = get_candle_data("USDX", analysis_time)
        
        if df_gold is None or df_usdx is None:
            logger.error("데이터 조회 실패")
            return
        
        latest_time = get_latest_trading_date(df_gold, analysis_time)
        if latest_time is None:
            return
        
        # 지표 계산
        df_gold = calculate_indicators(df_gold, indicator_config, logger)
        df_usdx = calculate_indicators(df_usdx, indicator_config, logger)
        
        if df_gold is None or df_usdx is None:
            return
            
        # 기술적 분석 프롬프트 생성
        analysis_text = create_technical_analysis_prompt(df_gold, df_usdx, latest_time, indicator_config, logger)
        if analysis_text is None:
            logger.error("기술적 분석 생성 실패")
            return
        
        print("\n=== 생성된 프롬프트 ===")
        print(analysis_text)
        print("===========================\n")
        
        logger.info("OpenAI에 예측 요청 중...")
        response_text = get_prediction(analysis_text)
        if response_text is None:
            logger.error("예측 응답 획득 실패")
            return

        # 응답 저장
        if not save_openai_response_as_text(response_text.strip(), analysis_time, SELECTED_TIMEFRAME):
            logger.error("응답 저장 실패")
            return
        
        # 분석 결과 출력
        print("\n=== 분석 결과 ===")
        print(f"분석 시점: {analysis_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"예측 목표: {target_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"예측 결과: {response_text}")
        print("================\n")
        
        logger.info("분석 완료")
        
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {str(e)}")
        logger.error(traceback.format_exc())
    
    finally:
        mt5.shutdown()
        logger.info("프로그램 종료")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(*sys.argv[1:3])
    else:
        main()