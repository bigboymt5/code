#h2_ai.py
import logging
from core_ai import main, set_timeframe
from datetime import datetime, timedelta
from mt5_time_set import init_mt5, setup_logger, BROKER_UTC_OFFSET


current_time = datetime.now()

logger = setup_logger();
 

SELECTED_TIMEFRAME = 'H2'  # 현재 프레임 설정


def get_latest_trading_time(current_time, timeframe):
    """선택된 타임프레임에 맞게 가장 최근의 거래 시간을 반환"""
    # 타임프레임별 분 단위 계산
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
    
    my_time = timeframes_in_minutes[timeframe]  # 선택된 타임프레임의 분 단위

    # 시간 조정
    minute = current_time.minute
    adjusted_minute = (minute // my_time) * my_time
    adjusted_time = current_time.replace(minute=adjusted_minute, second=0, microsecond=0)

    # 현재 시간보다 뒤로 가지 않도록 설정
    if adjusted_time > current_time:
        adjusted_time -= timedelta(minutes=my_time)  # 이전 타임프레임으로 조정

    return adjusted_time

 

INDICATOR_CONFIG = {
    'selected_indicators': ['EMA', 'ICHIMOKU', 'FIBONACCI', 'MACD'],
    'parameters': {
        'EMA': {'periods': [9, 21]},
        'ICHIMOKU': {'tenkan': 9, 'kijun': 26, 'senkou_b': 52},
        'FIBONACCI': {'period': 14},
        'MACD': {'fast': 6, 'slow': 15, 'signal': 9}

    }
}

SELECTED_TIMEFRAME = 'H2'  # 현재 프레임 설정

if set_timeframe(SELECTED_TIMEFRAME):
    logger.info(f"타임프레임 설정 성공: {SELECTED_TIMEFRAME}")
else:
    logger.error(f"타임프레임 설정 실패: {SELECTED_TIMEFRAME}")
    sys.exit(1)  # 실패 시 프로그램 종료

if __name__ == "__main__":
    import sys
    from datetime import datetime


    # 명령줄 인자 처리
    if len(sys.argv) > 2:
        try:
            input_date = datetime.strptime(sys.argv[1] + sys.argv[2], '%Y%m%d%H%M')
            target_time = get_latest_trading_time(input_date, SELECTED_TIMEFRAME)
        except Exception as e:
            logger.error(f"잘못된 입력: {e}")
            sys.exit(1)
    else:
        now = datetime.now()
        target_time = get_latest_trading_time(now, SELECTED_TIMEFRAME)

    # 날짜와 시간 형식 변환
    date_str = target_time.strftime('%Y%m%d')
    time_str = target_time.strftime('%H%M')

    # 로그 및 출력
    logger.info(f"Target Time: {date_str} {time_str}")
    print(f"현재 시간: {datetime.now()}")
    print(f"조정된 시간 ({SELECTED_TIMEFRAME}): {target_time}")
    
    # main 함수 호출
    main(date_str, time_str, INDICATOR_CONFIG)
