import os
import sys
sys.dont_write_bytecode = True
import pandas as pd
import pandas_ta as ta
import logging
from datetime import datetime, timedelta
import MetaTrader5 as mt5
from mt5_time_set import init_mt5, setup_logger, BROKER_UTC_OFFSET

# 전역 변수 설정
SYMBOL = "XAUUSD"  # 분석할 심볼 (필요시 다른 심볼로 변경 가능)

# 로거 설정
logger = setup_logger()

# 타임프레임 설정
SELECTED_TIMEFRAME = 'H2'  # 2시간 타임프레임
TIMEFRAMES = {
    'H2': mt5.TIMEFRAME_H2
}

def get_broker_time():
    """MT5 브로커 서버의 현재 시간을 가져옵니다"""
    try:
        # MT5 초기화 확인
        if not mt5.terminal_info():
            if not init_mt5():
                logger.error("MT5 연결 실패, 브로커 시간을 가져올 수 없습니다")
                return None
                
        # 브로커 서버 시간 가져오기
        server_time = mt5.symbol_info_tick(SYMBOL).time
        broker_time = datetime.fromtimestamp(server_time)
        
        logger.info(f"브로커 서버 시간: {broker_time.strftime('%Y-%m-%d %H:%M:%S')}")
        return broker_time
        
    except Exception as e:
        logger.error(f"브로커 시간 가져오기 실패: {str(e)}")
        return None
        
def get_future_time(hours_ahead=2):
    """브로커 시간보다 지정된 시간(기본 2시간) 미래의 시간을 반환합니다"""
    broker_time = get_broker_time()
    if broker_time is None:
        logger.warning("브로커 시간을 가져올 수 없어 로컬 시간을 사용합니다")
        broker_time = datetime.now()
        
    future_time = broker_time + timedelta(hours=hours_ahead)
    logger.info(f"미래 조회 시간: {future_time.strftime('%Y-%m-%d %H:%M:%S')} (브로커 시간 +{hours_ahead}시간)")
    
    return future_time

def get_candle_data(symbol, bars=100, future_hours=2):
    """MT5에서 캔들 데이터 가져오기 (브로커 시간 + future_hours 기준)"""
    try:
        print(f"\n=== 캔들 데이터 조회 시작: {symbol} ===")
        
        # 브로커 시간 + future_hours 시간을 가져오기
        target_time = get_future_time(future_hours)
        if target_time is None:
            logger.error("미래 시간 계산 실패")
            return None
            
        # 타임프레임에 맞게 시간 조정
        hour = target_time.hour
        adjusted_hour = (hour // 2) * 2  # 2시간 단위로 조정
        adjusted_time = target_time.replace(hour=adjusted_hour, minute=0, second=0, microsecond=0)
        
        print(f"조회 시간: {adjusted_time.strftime('%Y-%m-%d %H:%M')} (브로커 시간 +{future_hours}시간)")
        print(f"조회할 캔들 수: {bars}개 (타임프레임: H2)")
        
        # MT5에서 데이터 가져오기 (브로커 시간 오프셋을 더할 필요가 없음 - 이미 브로커 시간을 기준으로 함)
        rates = mt5.copy_rates_from(symbol, TIMEFRAMES[SELECTED_TIMEFRAME], adjusted_time, bars)
        if rates is None or len(rates) == 0:
            logger.error(f"데이터 없음: {symbol} (H2)")
            return None

        # 결과 데이터프레임 생성
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        print(f"조회된 캔들 수: {len(df)}개")
        return df

    except Exception as e:
        logger.error(f"데이터 조회 실패: {str(e)}")
        return None

def calculate_indicators(df):
    """EMA, 일목균형표, MACD 지표 계산"""
    try:
        # EMA 계산
        df['ema_9'] = df.ta.ema(close=df['close'], length=9)
        df['ema_21'] = df.ta.ema(close=df['close'], length=21)
        
        # 일목균형표 계산
        # 텐칸센(전환선)
        period9_high = df['high'].rolling(window=9).max()
        period9_low = df['low'].rolling(window=9).min()
        df['tenkan_sen'] = (period9_high + period9_low) / 2
        
        # 키준센(기준선)
        period26_high = df['high'].rolling(window=26).max()
        period26_low = df['low'].rolling(window=26).min()
        df['kijun_sen'] = (period26_high + period26_low) / 2
        
        # 선행스팬A
        df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2)
        
        # 선행스팬B
        period52_high = df['high'].rolling(window=52).max()
        period52_low = df['low'].rolling(window=52).min()
        df['senkou_span_b'] = ((period52_high + period52_low) / 2)
        
        # MACD 계산 (파라미터: 6, 15, 9)
        macd = df.ta.macd(close=df['close'], fast=6, slow=15, signal=9)
        df['macd'] = macd[f'MACD_6_15_9']
        df['macd_signal'] = macd[f'MACDs_6_15_9']
        df['macd_hist'] = macd[f'MACDh_6_15_9']
        
        return df
    except Exception as e:
        logger.error(f"지표 계산 실패: {str(e)}")
        return None

def analyze_trend(df):
    """
    EMA, 일목균형표, MACD를 기반으로 현재 추세 분석
    """
    try:
        if df is None or df.empty:
            return "Unable to analyze trend: No data available"
        
        # 가장 최근 데이터 가져오기
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # 디버깅용: 마지막 캔들 정보 출력
        print("\n=== 마지막 캔들 정보 (디버깅용) ===")
        print(f"시간: {current['time'].strftime('%Y-%m-%d %H:%M')}")
        print(f"시가: {current['open']:.2f}")
        print(f"고가: {current['high']:.2f}")
        print(f"저가: {current['low']:.2f}")
        print(f"종가: {current['close']:.2f}")
        print(f"변동폭: {(current['high'] - current['low']):.2f}")
        print(f"변동률: {((current['close'] - current['open']) / current['open'] * 100):.2f}%")
        print("===============================")
        
        # 각 지표별 신호 계산
        ema_signal = analyze_ema(current, previous)
        ichimoku_signal = analyze_ichimoku(current)
        macd_signal = analyze_macd(current, previous)
        
        # 각 지표 상태 디버그 출력
        print("\n=== 지표별 신호 ===")
        print(f"EMA Signal: {ema_signal}")
        print(f"Ichimoku Signal: {ichimoku_signal}")
        print(f"MACD Signal: {macd_signal}")
        
        # 종합 분석 (각 지표에 가중치 부여)
        trend_points = 0
        
        # EMA 신호 가중치 (1점)
        if ema_signal == "Bullish":
            trend_points += 1
        elif ema_signal == "Bearish":
            trend_points -= 1
            
        # 일목균형표 가중치 (2점)
        if ichimoku_signal == "Strong Bullish":
            trend_points += 2
        elif ichimoku_signal == "Bullish":
            trend_points += 1
        elif ichimoku_signal == "Bearish":
            trend_points -= 1
        elif ichimoku_signal == "Strong Bearish":
            trend_points -= 2
            
        # MACD 가중치 (1.5점)
        if macd_signal == "Bullish":
            trend_points += 1.5
        elif macd_signal == "Bearish":
            trend_points -= 1.5
        
        # 종합 추세 판단
        if trend_points >= 3:
            trend = "Strong Bullish Trend"
        elif trend_points >= 1.5:
            trend = "Bullish Trend"
        elif trend_points > 0:
            trend = "Weak Bullish Trend"
        elif trend_points == 0:
            trend = "Neutral"
        elif trend_points > -1.5:
            trend = "Weak Bearish Trend"
        elif trend_points > -3:
            trend = "Bearish Trend"
        else:
            trend = "Strong Bearish Trend"
            
        # 현재가 대비 분석 추가
        price_context = f"Current Price: {current['close']:.2f}, " \
                        f"Change: {(current['close'] - previous['close']):.2f} " \
                        f"({(current['close'] - previous['close']) / previous['close'] * 100:.2f}%)"
        
        # 최종 분석 결과
        trend_analysis = f"{trend}. {price_context}"
        print(f"\n=== 최종 추세 분석 ===\n{trend_analysis}")
        
        return trend_analysis
        
    except Exception as e:
        logger.error(f"추세 분석 실패: {str(e)}")
        return "Error analyzing trend"

def analyze_ema(current, previous):
    """EMA 신호 분석"""
    # EMA 기반 추세
    current_ema_diff = current['ema_9'] - current['ema_21']
    previous_ema_diff = previous['ema_9'] - previous['ema_21']
    
    # 가격과 EMA 위치
    price_above_ema9 = current['close'] > current['ema_9']
    price_above_ema21 = current['close'] > current['ema_21']
    
    # 골든 크로스/데드 크로스 체크
    golden_cross = current_ema_diff > 0 and previous_ema_diff <= 0
    death_cross = current_ema_diff < 0 and previous_ema_diff >= 0
    
    if golden_cross:
        return "Bullish"  # 골든 크로스
    elif death_cross:
        return "Bearish"  # 데드 크로스
    elif current_ema_diff > 0 and price_above_ema9 and price_above_ema21:
        return "Bullish"  # 상승 추세
    elif current_ema_diff < 0 and not price_above_ema9 and not price_above_ema21:
        return "Bearish"  # 하락 추세
    else:
        return "Neutral"  # 중립

def analyze_ichimoku(current):
    """일목균형표 신호 분석"""
    # 가격과 구름의 위치 체크
    price_above_cloud = current['close'] > current['senkou_span_a'] and current['close'] > current['senkou_span_b']
    price_below_cloud = current['close'] < current['senkou_span_a'] and current['close'] < current['senkou_span_b']
    price_in_cloud = not price_above_cloud and not price_below_cloud
    
    # 구름 방향 체크
    bullish_cloud = current['senkou_span_a'] > current['senkou_span_b']
    
    # 전환선과 기준선 교차 체크
    tenkan_above_kijun = current['tenkan_sen'] > current['kijun_sen']
    
    if price_above_cloud and tenkan_above_kijun and bullish_cloud:
        return "Strong Bullish"  # 강한 상승 추세
    elif price_above_cloud:
        return "Bullish"  # 상승 추세
    elif price_below_cloud and not tenkan_above_kijun and not bullish_cloud:
        return "Strong Bearish"  # 강한 하락 추세
    elif price_below_cloud:
        return "Bearish"  # 하락 추세
    else:
        return "Neutral"  # 중립 (구름 내부)

def analyze_macd(current, previous):
    """MACD 신호 분석"""
    # MACD와 시그널 라인 비교
    macd_above_signal = current['macd'] > current['macd_signal']
    
    # 히스토그램 방향 체크
    hist_increasing = current['macd_hist'] > previous['macd_hist']
    
    # 0선 위아래 체크
    macd_above_zero = current['macd'] > 0
    
    if macd_above_signal and hist_increasing and macd_above_zero:
        return "Bullish"  # 강한 상승 모멘텀
    elif not macd_above_signal and not hist_increasing and not macd_above_zero:
        return "Bearish"  # 강한 하락 모멘텀
    elif macd_above_signal and hist_increasing:
        return "Bullish"  # 상승 모멘텀
    elif not macd_above_signal and not hist_increasing:
        return "Bearish"  # 하락 모멘텀
    else:
        return "Neutral"  # 중립

def main():
    """메인 함수"""
    try:
        # MT5 초기화
        if not init_mt5():
            logger.error("MT5 초기화 실패, 프로그램 종료")
            return
        
        # 미래 시간 설정 (브로커 시간 + 2시간)
        future_hours = 2
        
        # 심볼 데이터 가져오기 (브로커 시간보다 2시간 미래 기준)
        df_gold = get_candle_data(SYMBOL, bars=100, future_hours=future_hours)
        if df_gold is None:
            logger.error(f"{SYMBOL} 데이터 가져오기 실패, 프로그램 종료")
            return
        
        # 마지막 5개 캔들 정보 출력 (디버깅용)
        print("\n=== 마지막 5개 캔들 정보 ===")
        last_candles = df_gold.tail(5).reset_index()
        for i, candle in last_candles.iterrows():
            print(f"캔들 {i+1} - 시간: {candle['time'].strftime('%Y-%m-%d %H:%M')}")
            print(f"  시가: {candle['open']:.2f}, 고가: {candle['high']:.2f}, 저가: {candle['low']:.2f}, 종가: {candle['close']:.2f}")
        print("=============================")
            
        # 지표 계산
        df_gold = calculate_indicators(df_gold)
        if df_gold is None:
            logger.error("지표 계산 실패, 프로그램 종료")
            return
            
        # 추세 분석
        current_trend = analyze_trend(df_gold)
        
        # 결과 저장
        output_folder = "trend_analysis"
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_file = os.path.join(output_folder, f"{SYMBOL}_trend_analysis_{timestamp}.txt")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"{SYMBOL} H2 Trend Analysis ({timestamp})\n")
            f.write("-" * 50 + "\n")
            f.write(current_trend + "\n")
            
        print(f"\n분석 결과가 저장되었습니다: {output_file}")
        
        # 분석 결과 반환
        return current_trend
        
    except Exception as e:
        logger.error(f"분석 중 오류 발생: {str(e)}")
        return None
    finally:
        # MT5 종료
        mt5.shutdown()

if __name__ == "__main__":
    main()