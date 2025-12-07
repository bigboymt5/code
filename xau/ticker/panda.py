import os
import json
import logging
import traceback
import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, Response
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# 설정
LOG_FOLDER = './log'

# MT5 계정 정보
ACCOUNT_ID = 17055878
PASSWORD = 'Realboy9989*'
SERVER = 'VantageInternational-Live 7'

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

# 심볼 한글 표시명 맵
SYMBOL_DISPLAY_NAMES = {
    "XAUUSD": "골드",
    "BTCUSD": "비트코인",
    "ETHUSD": "이더리움"
}


def setup_daily_logger():
    """일별 로거 설정"""
    if not os.path.exists(LOG_FOLDER):
        os.makedirs(LOG_FOLDER)

    log_file = os.path.join(LOG_FOLDER, f"error_{datetime.now().strftime('%Y%m%d')}.txt")
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.ERROR)

    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_daily_logger()


def init_mt5():
    """MT5 초기화 및 로그인"""
    if not mt5.initialize():
        logger.error(f"MT5 초기화 실패: {mt5.last_error()}")
        return False

    if not mt5.login(ACCOUNT_ID, password=PASSWORD, server=SERVER):
        logger.error(f"MT5 로그인 실패: {mt5.last_error()}")
        return False

    return True


def normalize_symbol(symbol):
    """심볼을 브로커 표준 심볼로 정규화"""
    symbol_upper = symbol.upper()
    base_symbol = symbol_upper.split('.')[0]
    mt5_symbol = BROKER_SYMBOLS.get(base_symbol, symbol_upper)
    return mt5_symbol


def get_candle_data(symbol, timeframe=mt5.TIMEFRAME_D1, count=100):
    """MT5에서 캔들 데이터 조회"""
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            logger.error(f"데이터 조회 실패: {symbol}, 에러: {mt5.last_error()}")
            return None

        # pandas DataFrame으로 변환
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    except Exception as e:
        logger.error(f"캔들 데이터 조회 오류: {str(e)}")
        return None


def calculate_bollinger_bands(df, period=20, std_dev=2):
    """볼린저밴드 계산"""
    df['bb_middle'] = df['close'].rolling(window=period).mean()
    df['bb_std'] = df['close'].rolling(window=period).std()
    df['bb_upper'] = df['bb_middle'] + (std_dev * df['bb_std'])
    df['bb_lower'] = df['bb_middle'] - (std_dev * df['bb_std'])
    return df


def calculate_ema(df):
    """EMA 계산 (7, 21, 50)"""
    df['ema7'] = df['close'].ewm(span=7, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    return df


def check_golden_cross(df):
    """골든크로스 확인 (단기선이 장기선을 상향 돌파)"""
    # EMA7이 EMA21을 상향 돌파
    gc_7_21 = False
    if len(df) >= 2:
        gc_7_21 = (df['ema7'].iloc[-2] <= df['ema21'].iloc[-2]) and (df['ema7'].iloc[-1] > df['ema21'].iloc[-1])

    # EMA21이 EMA50을 상향 돌파
    gc_21_50 = False
    if len(df) >= 2:
        gc_21_50 = (df['ema21'].iloc[-2] <= df['ema50'].iloc[-2]) and (df['ema21'].iloc[-1] > df['ema50'].iloc[-1])

    return {
        "golden_cross_7_21": bool(gc_7_21),
        "golden_cross_21_50": bool(gc_21_50)
    }


def calculate_macd(df, fast=12, slow=26, signal=9):
    """MACD 계산"""
    df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd'] = df['ema_fast'] - df['ema_slow']
    df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    return df


def calculate_rsi(df, period=14):
    """RSI 계산"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df


def calculate_stochastic(df, k_period=14, d_period=3):
    """스토캐스틱 계산"""
    # %K 계산
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    df['stoch_k'] = 100 * (df['close'] - low_min) / (high_max - low_min)

    # %D 계산 (K의 이동평균)
    df['stoch_d'] = df['stoch_k'].rolling(window=d_period).mean()

    return df


def calculate_atr(df, period=14):
    """ATR (Average True Range) 계산"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())

    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['atr'] = true_range.rolling(window=period).mean()

    return df


def calculate_fibonacci_retracement(df, window=50):
    """피보나치 되돌림 계산"""
    # 최근 window 기간의 최고가와 최저가
    recent_high = df['high'].tail(window).max()
    recent_low = df['low'].tail(window).min()

    diff = recent_high - recent_low

    # 피보나치 레벨
    fib_levels = {
        "level_0": recent_high,
        "level_236": recent_high - (diff * 0.236),
        "level_382": recent_high - (diff * 0.382),
        "level_500": recent_high - (diff * 0.500),
        "level_618": recent_high - (diff * 0.618),
        "level_786": recent_high - (diff * 0.786),
        "level_100": recent_low
    }

    return fib_levels


def find_support_resistance(df, window=20):
    """지지선/저항선 찾기"""
    # 최근 window 기간의 고점/저점
    recent_high = df['high'].tail(window).max()
    recent_low = df['low'].tail(window).min()

    # 전고점/전저점 (전체 기간)
    all_time_high = df['high'].max()
    all_time_low = df['low'].min()

    return {
        "recent_high": recent_high,
        "recent_low": recent_low,
        "all_time_high": all_time_high,
        "all_time_low": all_time_low
    }


def analyze_technical(df):
    """종합 기술적 분석"""
    if df is None or len(df) == 0:
        return None

    # 각종 지표 계산
    df = calculate_bollinger_bands(df)
    df = calculate_ema(df)
    df = calculate_macd(df)
    df = calculate_rsi(df)
    df = calculate_stochastic(df)
    df = calculate_atr(df)

    # 최신 데이터
    latest = df.iloc[-1]
    yesterday = df.iloc[-2] if len(df) >= 2 else latest

    # 골든크로스 확인
    golden_cross = check_golden_cross(df)

    # 지지/저항선
    support_resistance = find_support_resistance(df)

    # 피보나치 되돌림
    fibonacci = calculate_fibonacci_retracement(df)

    # 분석 결과 (모든 값을 Python native 타입으로 변환)
    analysis = {
        "bollinger_bands": {
            "upper": float(round(latest['bb_upper'], 2)),
            "middle": float(round(latest['bb_middle'], 2)),
            "lower": float(round(latest['bb_lower'], 2)),
            "position": "상단돌파" if float(latest['close']) > float(latest['bb_upper']) else
                       "하단돌파" if float(latest['close']) < float(latest['bb_lower']) else "중간"
        },
        "ema": {
            "ema7": float(round(latest['ema7'], 2)),
            "ema21": float(round(latest['ema21'], 2)),
            "ema50": float(round(latest['ema50'], 2))
        },
        "golden_cross": {
            "golden_cross_7_21": bool(golden_cross['golden_cross_7_21']),
            "golden_cross_21_50": bool(golden_cross['golden_cross_21_50'])
        },
        "macd": {
            "macd": float(round(latest['macd'], 4)),
            "signal": float(round(latest['macd_signal'], 4)),
            "histogram": float(round(latest['macd_histogram'], 4)),
            "trend": "상승" if float(latest['macd']) > float(latest['macd_signal']) else "하락"
        },
        "rsi": {
            "value": float(round(latest['rsi'], 2)),
            "status": "과매수" if float(latest['rsi']) > 70 else "과매도" if float(latest['rsi']) < 30 else "중립"
        },
        "stochastic": {
            "k": float(round(latest['stoch_k'], 2)),
            "d": float(round(latest['stoch_d'], 2)),
            "status": "과매수" if float(latest['stoch_k']) > 80 else "과매도" if float(latest['stoch_k']) < 20 else "중립"
        },
        "atr": {
            "value": float(round(latest['atr'], 2)),
            "volatility": "높음" if float(latest['atr']) > float(df['atr'].mean()) * 1.5 else
                         "낮음" if float(latest['atr']) < float(df['atr'].mean()) * 0.5 else "보통"
        },
        "fibonacci_retracement": {
            "level_0": float(round(fibonacci['level_0'], 2)),
            "level_236": float(round(fibonacci['level_236'], 2)),
            "level_382": float(round(fibonacci['level_382'], 2)),
            "level_500": float(round(fibonacci['level_500'], 2)),
            "level_618": float(round(fibonacci['level_618'], 2)),
            "level_786": float(round(fibonacci['level_786'], 2)),
            "level_100": float(round(fibonacci['level_100'], 2))
        },
        "support_resistance": {
            "recent_high": float(round(support_resistance['recent_high'], 2)),
            "recent_low": float(round(support_resistance['recent_low'], 2)),
            "all_time_high": float(round(support_resistance['all_time_high'], 2)),
            "all_time_low": float(round(support_resistance['all_time_low'], 2))
        }
    }

    return analysis, latest, yesterday


@app.route('/api/ticker/', methods=['GET'])
def get_ticker_analysis():
    """
    티커 기술적 분석 API
    파라미터:
        h_tic: 심볼명 (예: XAUUSD, BTCUSD) - 기본값: XAUUSD
        timeframe: 캔들 타임프레임 (1d, 1h, 4h 등) - 기본값: 1d
    """
    try:
        # 파라미터 가져오기
        symbol_input = request.args.get('h_tic', 'XAUUSD').strip()
        timeframe_str = request.args.get('timeframe', '1d').strip().lower()
        mode = request.args.get('mode', '').strip().lower()

        print(f"[요청] symbol: {symbol_input}, timeframe: {timeframe_str}, mode: {mode}")

        # 심볼 정규화
        symbol = normalize_symbol(symbol_input)
        print(f"[정규화] {symbol_input} -> {symbol}")

        # 타임프레임 변환
        timeframe_map = {
            '1m': mt5.TIMEFRAME_M1,
            '5m': mt5.TIMEFRAME_M5,
            '15m': mt5.TIMEFRAME_M15,
            '30m': mt5.TIMEFRAME_M30,
            '1h': mt5.TIMEFRAME_H1,
            '4h': mt5.TIMEFRAME_H4,
            '1d': mt5.TIMEFRAME_D1,
            '1w': mt5.TIMEFRAME_W1,
            '1mn': mt5.TIMEFRAME_MN1
        }
        timeframe = timeframe_map.get(timeframe_str, mt5.TIMEFRAME_D1)

        # MT5 초기화
        print(f"[MT5] 초기화 시작...")
        if not init_mt5():
            print(f"[MT5] 초기화 실패")
            return jsonify({
                "error": "MT5 초기화 실패",
                "symbol": symbol
            }), 500
        print(f"[MT5] 초기화 성공")

        # 캔들 데이터 조회
        print(f"[데이터] {symbol} 조회 시작...")
        df = get_candle_data(symbol, timeframe, count=100)
        if df is None:
            print(f"[데이터] {symbol} 조회 실패")
            return jsonify({
                "error": f"심볼 {symbol}의 데이터를 찾을 수 없습니다",
                "symbol": symbol
            }), 404
        print(f"[데이터] {symbol} 조회 성공 - {len(df)}개 캔들")

        # 기술적 분석 수행
        print(f"[분석] 시작...")
        analysis_result, latest, yesterday = analyze_technical(df)

        if analysis_result is None:
            print(f"[분석] 실패")
            return jsonify({
                "error": "기술적 분석 실패",
                "symbol": symbol
            }), 500
        print(f"[분석] 완료")

        # 현재 시간
        now = datetime.now()

        # 가격 변동 계산
        current_price = round(latest['close'], 2)
        yesterday_price = round(yesterday['close'], 2)

        # mode=test일 때 current_price에 랜덤 10% 변동 적용
        if mode == 'test':
            # 랜덤으로 +10% 또는 -10%
            random_factor = random.choice([1.10, 0.90])
            current_price = round(current_price * random_factor, 2)
            print(f"[테스트 모드] 가격 변동: {latest['close']} -> {current_price} (배율: {random_factor})")

        # 상승/하락 금액 계산 (오늘 - 어제)
        price_change = current_price - yesterday_price
        price_change_rounded = round(price_change)

        # 천단위 콤마 포맷
        price_change_formatted = f"{price_change_rounded:,}"

        # 상승/하락률 계산 (어제 가격 대비 백분율)
        if yesterday_price != 0:
            price_change_percent = (price_change / yesterday_price) * 100
            price_change_percent_rounded = round(price_change_percent, 2)
        else:
            price_change_percent_rounded = 0.0

        # 심볼 한글 표시명
        base_name = SYMBOL_DISPLAY_NAMES.get(symbol, symbol)
        symbol_display_name = f"오늘의 {base_name} 시세"

        # 등락 상황 (날짜 + 등락)
        date_str = now.strftime('%y년%m월%d일')
        if price_change_percent_rounded < 0:
            trend_text = f"{date_str} {abs(price_change_percent_rounded)}% 하락"
        else:
            trend_text = f"{date_str} {price_change_percent_rounded}% 상승"

        # JSON 응답 생성
        response_data = {
            "symbol": symbol,
            "symbol_display_name": symbol_display_name,
            "date": now.strftime('%y%m%d'),
            "time": now.strftime('%H%M'),
            "current_price": current_price,
            "yesterday_price": yesterday_price,
            "price_change": price_change_formatted,
            "price_change_percent": price_change_percent_rounded,
            "price_trend": trend_text,
            "candle": timeframe_str,
            "analysis": analysis_result
        }

        print(f"[응답] 성공 - {symbol} @ {response_data['current_price']} (변동: {price_change_formatted}, {price_change_percent_rounded}%)")
        return Response(json.dumps(response_data, ensure_ascii=False), mimetype='application/json'), 200

    except Exception as e:
        error_msg = f"요청 처리 실패: {str(e)}"
        print(f"[에러] {error_msg}")
        print(traceback.format_exc())
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return jsonify({"error": error_msg}), 500
    finally:
        # MT5 종료
        mt5.shutdown()


if __name__ == '__main__':
    try:
        print(f"Panda 기술적 분석 서버 시작 - 포트 5003")
        print(f"API 엔드포인트: http://localhost:5003/api/ticker/")
        print(f"사용 예시:")
        print(f"  - 기본 (XAUUSD 1일봉): http://localhost:5003/api/ticker/")
        print(f"  - BTCUSD 1일봉: http://localhost:5003/api/ticker/?h_tic=BTCUSD")
        print(f"  - XAUUSD 4시간봉: http://localhost:5003/api/ticker/?h_tic=XAUUSD&timeframe=4h")
        print(f"  - EURUSD 1시간봉: http://localhost:5003/api/ticker/?h_tic=EURUSD&timeframe=1h")
        app.run(host='0.0.0.0', port=5003, debug=True, threaded=True)
    except Exception as e:
        logger.error(f"서버 실행 실패: {str(e)}")
#http://localhost:5003/api/ticker/?h_tic=BTCUSD 