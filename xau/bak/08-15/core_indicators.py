#core_indicators.py
import os 
import sys
import re
import json
import time
import random
import logging
import traceback
import requests
from numpy import nan as npNaN
import pandas as pd
import pandas_ta as ta
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import glob
SELECTED_TIMEFRAME = 'H2'  # 현재 프레임 설정
 
# 폴더 및 파일 설정
OUTPUT_FOLDER = "core_response"
FINE_DATA_FOLDER = "core_response"  
FINE_JSON_FOLDER = "core_response"  
FILE_PREFIX = "core_"
FILE_EXTENSION = ".json"
GET_FOLDER = "core_response"
METALS_FOLDER = "metals"

# 타임프레임별 지표 설정
TIMEFRAMES = {
    'D1': mt5.TIMEFRAME_D1,
    'H12': mt5.TIMEFRAME_H12,
    'H6': mt5.TIMEFRAME_H6,
    'H4': mt5.TIMEFRAME_H4,
    'H3': mt5.TIMEFRAME_H3,
    'H2': mt5.TIMEFRAME_H2,
    'H1': mt5.TIMEFRAME_H1,
    'M30': mt5.TIMEFRAME_M30,
    'M15': mt5.TIMEFRAME_M15,
    'M10': mt5.TIMEFRAME_M10,
    'M5': mt5.TIMEFRAME_M5
}

 
ICHIMOKU_PARAMS = {
    'TENKAN': 9,
    'KIJUN': 26,
    'SENKOU_B': 52,
    'DISPLACEMENT': 26
}

PRICE_MOVEMENT_THRESHOLDS = {
    'RALLY': 0.35,
    'DRIFT_UP': 0.1,
    'DRIFT_DOWN': -0.1,
    'SLUMP': -0.35
}

SESSION_WEIGHTS = {
    'ASIA': 0.8,
    'EUROPE': 1.2,
    'US': 1.1,
    'OVERLAP': 1.3
}


CANDLE_ANALYSIS_CONSTANTS = {
    'PATTERN_LENGTH': 5,       # 분석할 캔들 수
    'DOJI_THRESHOLD': 0.3,     # 도지로 판단할 몸통 비율 임계값
    'TREND_THRESHOLD': 0.2,    # 트렌드 판단 임계값
    'LONG_CANDLE_FACTOR': 1.5  # 장대 캔들 판단을 위한 ATR 배수
}


 


def analyze_all_timeframes(target_time, logger):
    """
    각 타임프레임별 분석 정보를 자연어 텍스트 형식으로 반환
    """
    try:
        timeframes = ['M10', 'M15', 'M30', 'H1', 'H2', 'H3', 'H4', 'H6', 'H12', 'D1']
        result = []
        
        # 헤더 생성
        timeframe_text = f"(Current Time: {target_time.strftime('%Y-%m-%d %H:%M')}):\n"
        
        for tf in timeframes:
            try:
                file_pattern = os.path.join(FINE_DATA_FOLDER, f"{tf}_core_*.txt")
                files = glob.glob(file_pattern)
                
                if not files:
                    logger.warning(f"No files found for timeframe {tf}")
                    continue
                    
                latest_file = max(files, key=os.path.getctime)
                
                with open(latest_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                trend = None
                factors = None
                
                for line in content.split('\n'):
                    if "Next candle trend:" in line:
                        trend = line.split(': ')[1].strip()
                    elif "Key factors:" in line:
                        factors = line.split(': ')[1].strip()
                
                if trend and factors:
                    # 타임프레임별 설명 추가
                    timeframe_desc = {
                        'M10': '10 Minutes',
                        'M15': '15 Minutes', 
                        'M30': '30 Minutes'
                    }
                    
                    timeframe_text += f"\n{tf} ({timeframe_desc[tf]}) Trend: {trend.upper()}\n"
                    timeframe_text += f"Analysis: {factors}\n"
                    
            except Exception as e:
                logger.error(f"Error processing timeframe {tf}: {str(e)}")
                continue
                
        return timeframe_text
        
    except Exception as e:
        logger.error(f"Error in analyze_all_timeframes: {str(e)}")
        return "Error analyzing timeframes"




def calculate_indicators(df, indicator_config, logger):
    """
    선택된 지표들을 계산하는 함수
    """
    try:
        logger.info(f"Starting calculation of selected indicators: {indicator_config['selected_indicators']}")
        
        # ATR은 get_price_pattern에서 필요하므로 항상 계산
        df['atr'] = df.ta.atr(high=df['high'], low=df['low'], close=df['close'], length=14)

                # EMA 계산 추가
        if 'EMA' in indicator_config['selected_indicators']:
            df['ema_9'] = df.ta.ema(close=df['close'], length=9)
            df['ema_21'] = df.ta.ema(close=df['close'], length=21)
        
        
        # RSI 계산
        if 'RSI' in indicator_config['selected_indicators']:
            period = indicator_config['parameters']['RSI']['period']
            df['rsi'] = df.ta.rsi(close=df['close'], length=period)
            
        # Stochastic 계산
        if 'STOCHASTIC' in indicator_config['selected_indicators']:
            params = indicator_config['parameters']['STOCHASTIC']
            
            # Stochastic 계산
            stoch = df.ta.stoch(
                high=df['high'], 
                low=df['low'], 
                close=df['close'], 
                k=params['k'], 
                d=params['d'], 
                smooth_k=params['smooth_k']
            )
            
            # 반환된 열 이름 확인 후 일치시킴
            if 'STOCHk_14_3_3' in stoch.columns:
                df['stoch_k'] = stoch['STOCHk_14_3_3']
                df['stoch_d'] = stoch['STOCHd_14_3_3']
            elif 'STOCHk_10_3_3' in stoch.columns:
                df['stoch_k'] = stoch['STOCHk_10_3_3']
                df['stoch_d'] = stoch['STOCHd_10_3_3']
            else:
                raise ValueError("Stochastic columns not found in the output.")

            
        # SuperTrend 계산
        if 'SUPERTREND' in indicator_config['selected_indicators']:
            params = indicator_config['parameters']['SUPERTREND']
            indicators = TechnicalIndicators()
            df = indicators.calculate_supertrend(df, period=params['period'], 
                                              multiplier=params['multiplier'])
            
        # ADX 계산
        if 'ADX' in indicator_config['selected_indicators']:
            params = indicator_config['parameters']['ADX']
            adx = df.ta.adx(high=df['high'], low=df['low'], close=df['close'], 
                          length=params['period'])
            df['adx'] = adx[f'ADX_{params["period"]}']
            df['dmp'] = adx[f'DMP_{params["period"]}']
            df['dmn'] = adx[f'DMN_{params["period"]}']
            
        # MACD 계산
        if 'MACD' in indicator_config['selected_indicators']:
            params = indicator_config['parameters'].get('MACD', {'fast': 12, 'slow': 26, 'signal': 9})
            macd = df.ta.macd(close=df['close'], 
                            fast=params['fast'], 
                            slow=params['slow'], 
                            signal=params['signal'])
            df['macd'] = macd[f'MACD_{params["fast"]}_{params["slow"]}_{params["signal"]}']
            df['macd_signal'] = macd[f'MACDs_{params["fast"]}_{params["slow"]}_{params["signal"]}']
            df['macd_hist'] = macd[f'MACDh_{params["fast"]}_{params["slow"]}_{params["signal"]}']
            
        # ATR 계산
        if 'ATR' in indicator_config['selected_indicators']:
            atr_period = indicator_config['parameters'].get('ATR', {}).get('period', 14)
            df['atr'] = df.ta.atr(high=df['high'], low=df['low'], close=df['close'], length=atr_period)


        if 'FIBONACCI' in indicator_config['selected_indicators']:
            high = df['high'].rolling(window=14).max()
            low = df['low'].rolling(window=14).min()
            diff = high - low

            df['fib_236'] = high - (diff * 0.236)
            df['fib_382'] = high - (diff * 0.382)
            df['fib_500'] = high - (diff * 0.500)
            df['fib_618'] = high - (diff * 0.618)
            df['fib_786'] = high - (diff * 0.786)


        # 일목균형표 계산
        if 'ICHIMOKU' in indicator_config['selected_indicators']:
            ichimoku_params = indicator_config['parameters'].get('ICHIMOKU', {
                'tenkan': 9,
                'kijun': 26,
                'senkou_b': 52
            })

            period9_high = df['high'].rolling(window=ichimoku_params['tenkan']).max()
            period9_low = df['low'].rolling(window=ichimoku_params['tenkan']).min()
            df['tenkan_sen'] = (period9_high + period9_low) / 2

            period26_high = df['high'].rolling(window=ichimoku_params['kijun']).max()
            period26_low = df['low'].rolling(window=ichimoku_params['kijun']).min()
            df['kijun_sen'] = (period26_high + period26_low) / 2

            df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2)

            period52_high = df['high'].rolling(window=ichimoku_params['senkou_b']).max()
            period52_low = df['low'].rolling(window=ichimoku_params['senkou_b']).min()
            df['senkou_span_b'] = ((period52_high + period52_low) / 2)

            df['cloud_thickness'] = abs(df['senkou_span_a'] - df['senkou_span_b'])
            df['chikou_span'] = df['close'].shift(-26)
            
            # 기존 계산 유지하면서 파라미터 적용
            period9_high = df['high'].rolling(window=ichimoku_params['tenkan']).max()
            period9_low = df['low'].rolling(window=ichimoku_params['tenkan']).min()
            df['tenkan_sen'] = (period9_high + period9_low) / 2
            
            period26_high = df['high'].rolling(window=ichimoku_params['kijun']).max()
            period26_low = df['low'].rolling(window=ichimoku_params['kijun']).min()
            df['kijun_sen'] = (period26_high + period26_low) / 2
            
            df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2)
            
            period52_high = df['high'].rolling(window=ichimoku_params['senkou_b']).max()
            period52_low = df['low'].rolling(window=ichimoku_params['senkou_b']).min()
            df['senkou_span_b'] = ((period52_high + period52_low) / 2)
            
            df['cloud_thickness'] = abs(df['senkou_span_a'] - df['senkou_span_b'])
            df['chikou_span'] = df['close'].shift(-26)

        # 볼린저 밴드 기본 변수 계산 (이전 코드에서 누락됨)
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        df['bb_std'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # 볼린저 밴드 추가 상태 계산
        df['bb_middle_slope'] = df['bb_middle'].diff()
        df['bb_width_state'] = 'normal'
        df.loc[df['bb_width'] > df['bb_width'].mean() + df['bb_width'].std(), 'bb_width_state'] = 'wide'
        df.loc[df['bb_width'] < df['bb_width'].mean() - df['bb_width'].std(), 'bb_width_state'] = 'narrow'
        
        # 가격 위치 상태
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # 강한 돌파/되돌림 상태
        df['strong_breakout'] = (df['close'] > df['bb_upper']) & (df['close'].shift(1) <= df['bb_upper'].shift(1))
        df['strong_reversal'] = (df['close'] < df['bb_lower']) & (df['close'].shift(1) >= df['bb_lower'].shift(1))

        df = df.bfill()
        
        logger.info("Successfully calculated selected indicators")
        return df
        
    except Exception as e:
        logger.error(f"Error calculating indicators: {str(e)}")
        return None

def get_price_pattern(df, current_idx):
    """
    Analyze the overall pattern of the last 5 candlesticks.
    """
    if current_idx < 5:
        return "Insufficient historical data for pattern analysis"

    # Extract the last 5 candlesticks
    candles = df.iloc[current_idx-4:current_idx+1]

    current = candles.iloc[-1]
    prev1 = candles.iloc[-2]
    prev2 = candles.iloc[-3]

    print("\n=== Last 5 Candlesticks Analysis ===")
    for i, (idx, candle) in enumerate(candles.iterrows()):
        direction = "BULL" if candle['close'] > candle['open'] else "BEAR"
        body_size = abs(candle['close'] - candle['open'])
        body_ratio = body_size / (candle['high'] - candle['low'])
        
        print(f"\nCandle {i+1} (Index {idx}):")
        print(f"Direction: {direction}")
        print(f"Open:     {candle['open']:.2f}")
        print(f"High:     {candle['high']:.2f}")
        print(f"Low:      {candle['low']:.2f}")
        print(f"Close:    {candle['close']:.2f}")
        print(f"Body Size: {body_size:.2f}")
        print(f"Body Ratio: {body_ratio:.2%}")
        if 'atr' in candle:
            print(f"ATR:      {candle['atr']:.2f}")

    # Analyze candlestick properties
    body_sizes = abs(candles['close'] - candles['open'])
    avg_atr = candles['atr'].mean()
    current_body = abs(current['close'] - current['open'])
    current_direction = "Bullish" if current['close'] > current['open'] else "Bearish"
    upper_shadow = current['high'] - max(current['open'], current['close'])
    lower_shadow = min(current['open'], current['close']) - current['low']
    body_ratio = current_body / (current['high'] - current['low'])

    # ATR comparison
    body_to_atr = current_body / avg_atr
    atr_size = ""
    if body_to_atr > 2.0:
        atr_size = f"showing very large body size ({body_to_atr:.1f}x ATR)"
    elif body_to_atr > 1.5:
        atr_size = f"showing large body size ({body_to_atr:.1f}x ATR)"
    elif body_to_atr < 0.5:
        atr_size = f"showing small body size ({body_to_atr:.1f}x ATR)"

    # Highlight important current candle conditions
    if current_body > (prev1['high'] - prev1['low']) * 1.5:
        important_pattern = f"Current candle strongly exceeds previous candle size, indicating dominant {current_direction} momentum."
    elif current['close'] > prev1['high']:
        important_pattern = "Current candle closes above the previous candle's high, confirming breakout to the upside."
    elif current['close'] < prev1['low']:
        important_pattern = "Current candle closes below the previous candle's low, confirming breakdown to the downside."
    elif upper_shadow > avg_atr:
        important_pattern = "Current candle shows a long upper shadow, indicating strong rejection at higher levels."
    elif lower_shadow > avg_atr:
        important_pattern = "Current candle shows a long lower shadow, indicating strong buying pressure at lower levels."
    else:
        important_pattern = None

    # Check for extreme conditions to suppress 5-candle trend analysis
    suppress_trend = current_body > avg_atr * 2.0 or abs(current['close'] - prev1['close']) > avg_atr * 1.5

    # Current candle analysis
    if current_body > avg_atr * 1.5:
        current_pattern = f"Current candle displays Strong {current_direction} Momentum {atr_size} with notable shadows: upper shadow {upper_shadow:.2f}, lower shadow {lower_shadow:.2f}."
    elif body_ratio < 0.2:
        current_pattern = f"Current candle shows Doji formation {atr_size} with significant indecision."
    else:
        current_pattern = f"Current candle shows Normal {current_direction} movement {atr_size}."

    # Suppress 5-candle trend analysis if extreme conditions are met
    if suppress_trend:
        pattern = "Significant price action detected: No further pattern analysis performed due to strong current candle movement."
    else:
        # Analyze 5-candle trend
        size_trend = body_sizes.pct_change().mean()
        bull_count = sum(candles['close'] > candles['open'])
        bear_count = 5 - bull_count

        if size_trend > 0.2 and bull_count >= 3:
            pattern = "Increasing Bullish Candlestick Pattern: Starts with small bullish candles that evolve into larger bullish candles, indicating strengthening upward momentum."
        elif size_trend > 0.2 and bear_count >= 3:
            pattern = "Increasing Bearish Candlestick Pattern: Starts with small bearish candles that evolve into larger bearish candles, signaling accelerating downward momentum."
        elif size_trend < -0.2 and bull_count >= 3:
            pattern = "Diminishing Bullish Candlestick Pattern: Begins with strong bullish candles that gradually decrease in size, reflecting weakening upward momentum."
        elif size_trend < -0.2 and bear_count >= 3:
            pattern = "Diminishing Bearish Candlestick Pattern: Starts with strong bearish candles that gradually shrink, indicating fading downward momentum."
        else:
            pattern = "No clear 5-candle trend pattern detected."

    # Market sentiment
    if suppress_trend:
        sentiment = f"Market dominated by {current_direction} sentiment with heightened activity in the current candle."
    else:
        if bull_count > bear_count:
            sentiment = "Bullish Sentiment: Buyers dominate over sellers."
        elif bear_count > bull_count:
            sentiment = "Bearish Sentiment: Sellers overpower buyers."
        else:
            sentiment = "Neutral Sentiment: Buyers and sellers are evenly matched."

    if important_pattern:
        return f"{important_pattern} | {current_pattern}. {sentiment}"
    else:
        return f"{current_pattern} | {pattern}. {sentiment}"


def get_next_candle_data(symbol, target_datetime, timeframe, logger):
    """다음 캔들 정보만 별도로 가져오는 함수"""
    try:
        tf = TIMEFRAMES[timeframe]
        
        timeframe_minutes = {
            'M5': 5, 'M10': 10, 'M15': 15, 'M30': 30,
            'H1': 60, 'H2': 120, 'H3': 180, 'H4': 240,
            'H6': 360, 'H12': 720
        }
        
        interval = timeframe_minutes.get(timeframe, 5)
        next_candle_time = target_datetime + timedelta(minutes=interval)
        
        # 현재 시간과 비교
        current_time = datetime.now()
        if abs((target_datetime - current_time).total_seconds()) < interval * 60:
            logger.info("실시간 분석: 다음 캔들 정보 없음")
            return None

        # MT5에 직접 시간 전달 (시간 조정 없이)
        rates = mt5.copy_rates_from(symbol, tf, next_candle_time, 1)
        if rates is None or len(rates) == 0:
            logger.warning(f"다음 캔들 데이터 없음: {next_candle_time}")
            return None

        next_candle = {
            'time': pd.to_datetime(rates[0]['time'], unit='s'),  # 시간 조정 없음
            'high': rates[0]['high'],
            'low': rates[0]['low']
        }
        
        logger.info(f"다음 캔들 정보 찾음 - Time: {next_candle['time']}, High: {next_candle['high']}, Low: {next_candle['low']}")
        return next_candle
        
    except Exception as e:
        logger.error(f"다음 캔들 데이터 조회 실패: {str(e)}")
        return None
 

def calculate_dynamic_indicators(df, selected_indicators, parameters, logger):
    """
    선택된 지표들만 계산하는 함수
    
    Args:
        df: DataFrame
        selected_indicators: 계산할 지표 목록
        parameters: 지표별 파라미터
        logger: 로거
    """
    try:
        logger.info(f"Starting calculation of selected indicators: {selected_indicators}")
        indicators = TechnicalIndicators()
        results = {}
        
        for indicator in selected_indicators:
            method_name = f"calculate_{indicator.lower()}"
            if hasattr(indicators, method_name):
                method = getattr(indicators, method_name)
                params = parameters.get(indicator, {})
                results[indicator] = method(df, **params)
                
        logger.info("Successfully calculated selected indicators")
        return results
        
    except Exception as e:
        logger.error(f"Error calculating indicators: {str(e)}")
        return None
INDICATOR_TEMPLATES = {
    'EMA': (
        "EMA Analysis:\n"
        "  EMA9: {ema_9:.2f}\n"
        "  EMA21: {ema_21:.2f}\n"
        "  Trend Structure: {ema_trend}\n"
        "  Price Position: {ema_position}"
    ),
    
    'MACD': (
        "MACD Analysis:\n"
        "  MACD Line: {macd:.2f}\n"
        "  Signal Line: {macd_signal:.2f}\n"
        "  Histogram: {macd_hist:.2f}\n"
        "  Momentum: {macd_momentum}\n"
        "  Signal: {macd_signal_type}"
    ),
    
    'RSI': (
        "RSI Analysis:\n"
        "  Current Value: {rsi:.1f}\n"
        "  Status: {rsi_status}\n"
        "  Trend: {rsi_trend}\n"
        "  Divergence: {rsi_divergence}"
    ),
    
    'BOLLINGER': (
        "Bollinger Bands Analysis:\n"
        "  Middle Band: {bb_middle:.2f} ({trend_direction})\n"
        "  Upper Band: {bb_upper:.2f}\n"
        "  Lower Band: {bb_lower:.2f}\n"
        "  Band Width: {bb_status}\n"
        "  Price Position: {bb_position_desc}\n"
        "  Volatility: {bb_volatility}"
    ),
    
    'STOCHASTIC': (
        "Stochastic Analysis:\n"
        "  %K Line: {stoch_k:.2f}\n"
        "  %D Line: {stoch_d:.2f}\n"
        "  Status: {stoch_status}\n"
        "  Cross: {stoch_cross}\n"
        "  Trend Direction: {stoch_trend}"
    ),
    
    'ADX': (
        "ADX Analysis:\n"
        "  ADX Value: {adx:.2f}\n"
        "  +DI Line: {dmp:.2f}\n"
        "  -DI Line: {dmn:.2f}\n"
        "  Trend Strength: {adx_strength}\n"
        "  Trend Quality: {trend_quality}"
    ),
    
    'ICHIMOKU': (  # 추가된 부분
        "Ichimoku Cloud Analysis:\n"
        "  Tenkan-sen: {tenkan_sen:.2f}\n"
        "  Kijun-sen: {kijun_sen:.2f}\n"
        "  Senkou Span A: {senkou_span_a:.2f}\n"
        "  Senkou Span B: {senkou_span_b:.2f}\n"
        "  Cloud Status: {cloud_status}"
    ),
    
    'SUPERTREND': (
        "SuperTrend Analysis:\n"
        "  Current Value: {supertrend:.2f}\n"
        "  Trend Direction: {trend_direction}\n"
        "  Price Distance: {price_distance:.2f}\n"
        "  Signal Type: {signal}\n"
        "  Trend Strength: {trend_strength}\n"
        "  Position Change: {position_change}"
    ),
    
    'ATR': (
        "ATR Analysis:\n"
        "  Current ATR: {atr:.2f}\n"
        "  ATR Trend: {atr_trend}\n"
        "  Volatility Level: {volatility_level}\n"
        "  Price Range: {price_range:.2f}\n"
        "  Movement Quality: {movement_quality}"
    ),
    
    'FIBONACCI': (  # 추가된 부분
        "Fibonacci Analysis:\n"
        "  23.6% Level: {fib_236:.2f}\n"
        "  38.2% Level: {fib_382:.2f}\n"
        "  50.0% Level: {fib_500:.2f}\n"
        "  61.8% Level: {fib_618:.2f}\n"
        "  78.6% Level: {fib_786:.2f}\n"
        "  Key Level: {key_fib_level}\n"
        "  Position: {fib_position}"
    )
}


def get_latest_price(symbol="XAUUSD", logger=None):
    """
    Get the most recent tick price for the specified symbol
    """
    try:
        # Get last tick
        last_tick = mt5.symbol_info_tick(symbol)
        if last_tick is None:
            if logger:
                logger.error(f"Failed to get latest tick for {symbol}")
            return None
            
        # Return the bid price (or you could use ask price depending on your needs)
        latest_price = last_tick.bid
        
        if logger:
            logger.info(f"Latest {symbol} price: {latest_price}")
            
        return latest_price
        
    except Exception as e:
        if logger:
            logger.error(f"Error getting latest price: {str(e)}")
        return None
    

def create_technical_analysis_prompt(df_gold, df_usdx, target_time, indicator_config, logger):
 
  
 
    try:
        print("\n=== 기술적 분석 프롬프트 생성 시작 ===")

                # 기본 데이터 준비
        gold_data = df_gold[df_gold['time'] == target_time]
        if gold_data.empty:
            logger.error(f"XAUUSD 데이터 없음: {target_time}")
            return None
        
        current_idx = gold_data.index[0]
        prev_idx = current_idx - 1 if current_idx > 0 else current_idx
        current_gold = df_gold.iloc[current_idx]

 




        # 기존 데이터 확인
        required_columns = ['time', 'open', 'high', 'low', 'close']
        if not all(col in df_gold.columns for col in required_columns):
            logger.error("Required columns missing from XAUUSD DataFrame")
            return None
       

        # 필수 컬럼 확인
        required_columns = ['time', 'open', 'high', 'low', 'close']
        if not all(col in df_gold.columns for col in required_columns):
            logger.error("Required columns missing from XAUUSD DataFrame")
            return None
            
        if not all(col in df_usdx.columns for col in required_columns):
            logger.error("Required columns missing from USDX DataFrame")
            return None


        timeframe_analysis = analyze_all_timeframes(target_time, logger)    


        # 이전 데이터 가져오기
        previous_gold = get_previous_candle(df_gold, target_time, logger)
        if previous_gold is None:
            logger.error(f"XAUUSD 1봉 전 데이터 없음: {target_time}")
            return None

        # USDX 데이터 준비
        usdx_data = df_usdx.iloc[(df_usdx['time'] - target_time).abs().argsort()[:1]]
        if usdx_data.empty:
            logger.error("USDX 데이터 없음")
            return None
        current_usdx = usdx_data.iloc[0]

        previous_usdx = get_previous_candle(df_usdx, target_time, logger)
        if previous_usdx is None:
            logger.error("USDX 1봉 전 데이터 없음")
            return None

        # USDX 분석을 데이터 준비 후에 수행
        usdx_analysis = calculate_usdx_analysis(current_usdx, logger)
        if usdx_analysis is None:
            usdx_analysis = {'rsi': None, 'rsi_status': 'N/A'}

        # 가격 패턴 분석
        five_candle_pattern = get_price_pattern(df_gold, current_idx)

 
        
    # 가격 차이 분석
        current_close = current_gold['close']
        latest_price = get_latest_price("XAUUSD", logger)

        if latest_price:
            price_diff = round(current_close - latest_price, 2)
            price_diff_pct = round((price_diff / latest_price) * 100, 2)
            
            # 현재 캔들 전체 레인지 계산 (고가-저가 사용)
            candle_range = abs(current_gold['high'] - current_gold['low'])
            if candle_range > 0:
                # 현재가의 위치 계산을 위한 로직 변경
                if latest_price > current_gold['high']:
                    range_position = "100% (Above High)"
                elif latest_price < current_gold['low']:
                    range_position = "0% (Below Low)"
                else:
                    # 레인지 내부일 때만 퍼센트 계산
                    position_pct = round(((latest_price - current_gold['low']) / candle_range) * 100, 1)
                    range_position = f"{position_pct}%"
            else:
                range_position = "N/A (No Range)"

            if abs(price_diff) > 0:
                # 가격 변동 강도 세분화
                if abs(price_diff_pct) > 3.0:
                    movement_desc = 'Very Strong'
                elif abs(price_diff_pct) > 2.0:
                    movement_desc = 'Strong'  
                elif abs(price_diff_pct) > 1.0:
                    movement_desc = 'Moderate'
                elif abs(price_diff_pct) > 0.2:
                    movement_desc = 'Mild'
                else:
                    movement_desc = 'Weak'

                # 움직임 방향과 강도를 더 자연스럽게 표현
 
                direction_text = (
                    "bullish momentum" if price_diff > 0 and movement_desc in ['Very Strong', 'Strong'] else
                    "bearish momentum" if price_diff < 0 and movement_desc in ['Very Strong', 'Strong'] else
                    "upward price action" if price_diff > 0 else
                    "downward price action"
                )

                price_movement = (
                    f"Price Movement Analysis:\n"
                    f"- Current Close Price: ${current_close:.2f}\n"
                    f"- Real-Time Market Price: ${latest_price:.2f}\n"
                    f"- Net Price Change: ${price_diff:+.2f} ({price_diff_pct:+.2f}%)\n"
                    f"- Position in Current Candle: {range_position} from low to high\n"
                    f"- Market Momentum: {movement_desc} {direction_text}\n"
                )
            else:
                price_movement = "Price remains stable with minimal variation.\n"
        else:
            price_movement = "Unable to analyze price movement due to missing data.\n"


        # 기술적 지표 섹션 생성
        technical_sections = ["Technical Indicators:"]
        
        # 각 지표별 분석 수행
        for indicator in indicator_config['selected_indicators']:
            # 지표 이름을 대문자로 변환
            indicator = indicator.upper()
            
            # 지표별 데이터 계산
            indicator_data = None
            
            if indicator == 'MACD':
                indicator_data = calculate_macd_analysis(current_gold, df_gold['macd_hist'].iloc[current_idx-1], df_gold, logger)
            elif indicator == 'RSI':
                indicator_data = calculate_rsi_analysis(current_gold, prev_idx, df_gold, previous_gold['close'], logger)
            elif indicator == 'EMA':
                indicator_data = calculate_ema_analysis(current_gold, logger)
            elif indicator == 'ICHIMOKU':
                indicator_data = calculate_ichimoku_analysis(current_gold, logger)
            elif indicator == 'FIBONACCI':
                indicator_data = calculate_fibonacci_analysis(current_gold, logger)
            elif indicator == 'BOLLINGER':
                indicator_data = calculate_bollinger_analysis(current_gold, df_gold['bb_width'].iloc[prev_idx], logger)
            elif indicator == 'STOCHASTIC':
                indicator_data = calculate_stochastic_analysis(current_gold, df_gold['stoch_k'].iloc[prev_idx], logger)
            elif indicator == 'ADX':
                indicator_data = calculate_adx_analysis(current_gold, logger)
            elif indicator == 'SUPERTREND':
                indicator_data = calculate_supertrend_analysis(current_gold, df_gold['supertrend_trend'].iloc[prev_idx], logger)
            elif indicator == 'ATR':
                indicator_data = calculate_atr_analysis(current_gold, df_gold['atr'].iloc[prev_idx], df_gold, current_idx, logger)

            # 지표 데이터가 있고 템플릿이 있는 경우에만 섹션 추가
            if indicator_data and indicator in INDICATOR_TEMPLATES:
                section = format_indicator_section(indicator, indicator_data, INDICATOR_TEMPLATES[indicator], logger)
                if section:
                    technical_sections.append(section)
                    logger.info(f"Added {indicator} analysis section")
                else:
                    logger.warning(f"Failed to format {indicator} section")
            else:
                logger.warning(f"No data or template for indicator: {indicator}")
            
                    # 타임프레임 정보 매핑
        
        from core_ai import SELECTED_TIMEFRAME

        timeframe_desc = {
            'M5': '5 Minutes',
            'M10': '10 Minutes',
            'M15': '15 Minutes',
            'M30': '30 Minutes',
            'H1': '1 Hour',
            'H2': '2 Hours',
            'H3': '3 Hours',
            'H4': '4 Hours'
        }


        # 현재 타임프레임 설명 가져오기
        current_timeframe_display = f"[{SELECTED_TIMEFRAME} ({timeframe_desc.get(SELECTED_TIMEFRAME, 'Unknown')})]"


        # 다음 캔들 정보 가져오기
        # 다음 캔들 정보 가져오기 (별도의 MT5 호출)
        next_candle = get_next_candle_data("XAUUSD", target_time, SELECTED_TIMEFRAME, logger)
        if next_candle:
            next_candle_time = next_candle['time'].strftime('%H:%M')
            next_candle_info = f"Next Candle ({next_candle_time}): High: {next_candle['high']:.2f}, Low: {next_candle['low']:.2f}"
        else:
            next_candle_info = "Next Candle: Data not available"

        # 최종 프롬프트 생성
        prompt = f"""XAUUSD {current_timeframe_display} Technical Analysis:
Timestamp: {current_gold['time'].strftime('%Y-%m-%d %H:%M')} ({current_gold['time'].strftime('%A')})

Previous Candle:
Open: {previous_gold['open']:.2f}, 
High: {previous_gold['high']:.2f}, 
Low: {previous_gold['low']:.2f}, 
Close: {previous_gold['close']:.2f}

 

{price_movement}  

{chr(10).join(technical_sections)}

USDX Context:
Candle Data: Open: {current_usdx['open']:.2f}, High: {current_usdx['high']:.2f}, Low: {current_usdx['low']:.2f}, Close: {current_usdx['close']:.2f}

XAUUSD Market Context:
5-Candle Pattern: {five_candle_pattern}
"""
#{latest_price_metals}{price_movement} 최근시세 메탈 api 
#Important! Currently Forming  {next_candle_info} Check most !!  
#Previous AI Response Analysis : {timeframe_analysis}"""
#Gold Market Analyst: {timeframe_analysis}

        return prompt.strip()

    except Exception as e:
        logger.error(f"기술적 분석 생성 실패: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def calculate_indicator_data(df, indicator_type, config, logger):
    """지표 데이터 계산"""
    try:
        if indicator_type == 'MACD' and not all(col in df.columns for col in ['macd', 'macd_signal', 'macd_hist']):
            params = config['parameters'].get('MACD', {'fast': 12, 'slow': 26, 'signal': 9})
            macd_data = df.ta.macd(close=df['close'], 
                                fast=params['fast'], 
                                slow=params['slow'], 
                                signal=params['signal'])
            df['macd'] = macd_data[f'MACD_{params["fast"]}_{params["slow"]}_{params["signal"]}']
            df['macd_signal'] = macd_data[f'MACDs_{params["fast"]}_{params["slow"]}_{params["signal"]}']
            df['macd_hist'] = macd_data[f'MACDh_{params["fast"]}_{params["slow"]}_{params["signal"]}']
            
        elif indicator_type == 'RSI' and 'rsi' not in df.columns:
            params = config['parameters'].get('RSI', {'period': 14})
            df['rsi'] = df.ta.rsi(close=df['close'], length=params['period'])
            
        elif indicator_type == 'ICHIMOKU' and not all(col in df.columns for col in ['tenkan_sen', 'kijun_sen', 'senkou_span_a', 'senkou_span_b']):
            params = config['parameters'].get('ICHIMOKU', {
                'tenkan': 9,
                'kijun': 26,
                'senkou_b': 52
            })
            
            # 텐칸센 계산
            period9_high = df['high'].rolling(window=params['tenkan']).max()
            period9_low = df['low'].rolling(window=params['tenkan']).min()
            df['tenkan_sen'] = (period9_high + period9_low) / 2

            # 키준센 계산
            period26_high = df['high'].rolling(window=params['kijun']).max()
            period26_low = df['low'].rolling(window=params['kijun']).min()
            df['kijun_sen'] = (period26_high + period26_low) / 2

            # 선행스팬A 계산
            df['senkou_span_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2)

            # 선행스팬B 계산
            period52_high = df['high'].rolling(window=params['senkou_b']).max()
            period52_low = df['low'].rolling(window=params['senkou_b']).min()
            df['senkou_span_b'] = ((period52_high + period52_low) / 2)

            # 차이쿠 스팬 계산 (26일 이동평균)
            df['chikou_span'] = df['close'].shift(-26)

            # 구름 두께 계산
            df['cloud_thickness'] = abs(df['senkou_span_a'] - df['senkou_span_b'])

        elif indicator_type == 'FIBONACCI' and not all(col in df.columns for col in ['fib_236', 'fib_382', 'fib_500', 'fib_618', 'fib_786']):
            params = config['parameters'].get('FIBONACCI', {'period': 14})
            period = params['period']
            
            # 고가와 저가 계산
            high = df['high'].rolling(window=period).max()
            low = df['low'].rolling(window=period).min()
            diff = high - low

            # 피보나치 레벨 계산
            df['fib_236'] = high - (diff * 0.236)
            df['fib_382'] = high - (diff * 0.382)
            df['fib_500'] = high - (diff * 0.500)
            df['fib_618'] = high - (diff * 0.618)
            df['fib_786'] = high - (diff * 0.786)

        return df
            
    except Exception as e:
        logger.error(f"Error calculating {indicator_type} indicator: {str(e)}")
        return df
            
  
            
    except Exception as e:
        logger.error(f"Error calculating {indicator_type} indicator: {str(e)}")

def safe_get_indicator(data, indicator_name):
    """
    안전하게 지표 값을 가져오는 함수
    """
    try:
        if isinstance(data, pd.Series):
            return data[indicator_name]
        return data.get(indicator_name)
    except Exception:
        return None
    

def calculate_rsi_analysis(current_gold, prev_idx, df_gold, prev_close, logger):
    """RSI 지표 분석"""
    try:
        rsi_value = safe_get_indicator(current_gold, 'rsi')
        prev_rsi = safe_get_indicator(df_gold.iloc[prev_idx], 'rsi')
        if rsi_value is not None and prev_rsi is not None:
            rsi_trend = (
                "Strengthening" if rsi_value > prev_rsi
                else "Weakening"
            )
            rsi_divergence = (
                "Bullish" if current_gold['close'] < prev_close and rsi_value > prev_rsi
                else "Bearish" if current_gold['close'] > prev_close and rsi_value < prev_rsi
                else "None"
            )
            return {
                'rsi': rsi_value,
                'rsi_status': "Overbought" if rsi_value > 70 else "Oversold" if rsi_value < 30 else "Neutral",
                'rsi_trend': rsi_trend,
                'rsi_divergence': rsi_divergence
            }
    except Exception as e:
        if logger:
            logger.warning(f"Error processing RSI indicator: {str(e)}")
        return None
    


def calculate_macd_analysis(current_gold, prev_macd_hist, df_gold,logger):
    """MACD 지표 분석"""
    try:
        if all(col in df_gold.columns for col in ['macd', 'macd_signal', 'macd_hist']):
            macd_momentum = (
                "Strong Bullish" if current_gold['macd_hist'] > prev_macd_hist and current_gold['macd_hist'] > 0
                else "Weak Bullish" if current_gold['macd_hist'] > 0
                else "Strong Bearish" if current_gold['macd_hist'] < prev_macd_hist and current_gold['macd_hist'] < 0
                else "Weak Bearish"
            )
            return {
                'macd': current_gold['macd'],
                'macd_signal': current_gold['macd_signal'],
                'macd_hist': current_gold['macd_hist'],
                'macd_momentum': macd_momentum,
                'macd_signal_type': "Bullish Cross" if current_gold['macd'] > current_gold['macd_signal'] and current_gold['macd_hist'] > 0 
                            else "Bearish Cross" if current_gold['macd'] < current_gold['macd_signal'] and current_gold['macd_hist'] < 0
                            else "No Clear Signal"
            }
    except Exception as e:
        if logger:
            logger.warning(f"Error processing RSI indicator: {str(e)}")
        return None

def calculate_ema_analysis(current_gold, logger):
    """EMA 지표 분석"""
    try:
        if all(col in current_gold.index for col in ['ema_9', 'ema_21']):
            price_vs_ema9 = "Above EMA9" if current_gold['close'] > current_gold['ema_9'] else "Below EMA9"
            ema_trend = "Bullish" if current_gold['ema_9'] > current_gold['ema_21'] else "Bearish"
            return {
                'ema_9': current_gold['ema_9'],
                'ema_21': current_gold['ema_21'],
                'ema_trend': ema_trend,
                'ema_position': price_vs_ema9
            }
    except Exception as e:
        if logger:
            logger.warning(f"Error processing EMA indicator: {str(e)}")
        return None

def calculate_bollinger_analysis(current_gold, prev_bb_width,logger):
    """볼린저 밴드 지표 분석"""
    try:
        bb_volatility = (
            "Increasing" if current_gold['bb_width'] > prev_bb_width
            else "Decreasing" if current_gold['bb_width'] < prev_bb_width
            else "Stable"
        )
        return {
            'bb_middle': current_gold['bb_middle'],
            'bb_upper': current_gold['bb_upper'],
            'bb_lower': current_gold['bb_lower'],
            'trend_direction': "Bullish" if current_gold['bb_middle_slope'] > 0 else "Bearish",
            'bb_status': (
                "expanding" if current_gold['bb_width_state'] == 'wide'
                else "contracting" if current_gold['bb_width_state'] == 'narrow'
                else "normal"
            ),
            'bb_position_desc': (
                "near upper band" if current_gold['bb_position'] > 0.8
                else "near lower band" if current_gold['bb_position'] < 0.2
                else "in middle area"
            ),
            'bb_volatility': bb_volatility
        }
    except Exception as e:
        logger.warning(f"Error processing Bollinger Bands indicator: {str(e)}")
        return None

def calculate_stochastic_analysis(current_gold, prev_stoch_k,logger):
    """스토캐스틱 지표 분석"""
    try:
        stoch_trend = (
            "Strong Uptrend" if current_gold['stoch_k'] > 80 and current_gold['stoch_k'] > prev_stoch_k
            else "Strong Downtrend" if current_gold['stoch_k'] < 20 and current_gold['stoch_k'] < prev_stoch_k
            else "Moderate Uptrend" if current_gold['stoch_k'] > prev_stoch_k
            else "Moderate Downtrend"
        )
        return {
            'stoch_k': current_gold['stoch_k'],
            'stoch_d': current_gold['stoch_d'],
            'stoch_status': "Overbought" if current_gold['stoch_k'] > 80 else "Oversold" if current_gold['stoch_k'] < 20 else "Neutral",
            'stoch_cross': "Bullish Cross" if current_gold['stoch_k'] > current_gold['stoch_d'] else "Bearish Cross",
            'stoch_trend': stoch_trend
        }
    except Exception as e:
        logger.warning(f"Error processing Stochastic indicator: {str(e)}")
        return None

def calculate_adx_analysis(current_gold,logger):
    """ADX 지표 분석"""
    try:
        trend_quality = (
            "Very Strong" if current_gold['adx'] > 40
            else "Strong" if current_gold['adx'] > 25
            else "Moderate" if current_gold['adx'] > 20
            else "Weak" if current_gold['adx'] > 15
            else "No Trend"
        )
        return {
            'adx': current_gold['adx'],
            'dmp': current_gold['dmp'],
            'dmn': current_gold['dmn'],
            'adx_strength': "Strong Trend" if current_gold['adx'] > 25 else "Weak Trend",
            'trend_quality': trend_quality
        }
    except Exception as e:
        logger.warning(f"Error processing ADX indicator: {str(e)}")
        return None
    



def calculate_ichimoku_analysis(current_gold, logger):
    try:
        # 일목균형표 데이터가 있는지 확인
        required_columns = ['tenkan_sen', 'kijun_sen', 'senkou_span_a', 'senkou_span_b']
        if not all(col in current_gold.index for col in required_columns):
            return None

        # 클라우드 상태 판단 로직 개선
        cloud_status = 'Neutral'
        if current_gold['close'] > current_gold['senkou_span_a'] and current_gold['close'] > current_gold['senkou_span_b']:
            cloud_status = 'Strong Bullish (Price Above Cloud)'
        elif current_gold['close'] < current_gold['senkou_span_a'] and current_gold['close'] < current_gold['senkou_span_b']:
            cloud_status = 'Strong Bearish (Price Below Cloud)'
        elif current_gold['senkou_span_a'] > current_gold['senkou_span_b']:
            cloud_status = 'Bullish Cloud'
        elif current_gold['senkou_span_a'] < current_gold['senkou_span_b']:
            cloud_status = 'Bearish Cloud'

        return {
            'tenkan_sen': current_gold['tenkan_sen'],
            'kijun_sen': current_gold['kijun_sen'],
            'senkou_span_a': current_gold['senkou_span_a'],
            'senkou_span_b': current_gold['senkou_span_b'],
            'cloud_status': cloud_status
        }
    except Exception as e:
        logger.warning(f"Ichimoku 분석 중 오류: {str(e)}")
        return None


def calculate_supertrend_analysis(current_gold, prev_supertrend_trend,logger):
    """슈퍼트렌드 지표 분석"""
    try:
        position_change = (
            "New Bullish" if current_gold['supertrend_trend'] == 1 and prev_supertrend_trend == -1
            else "New Bearish" if current_gold['supertrend_trend'] == -1 and prev_supertrend_trend == 1
            else "Maintaining Bullish" if current_gold['supertrend_trend'] == 1
            else "Maintaining Bearish"
        )
        return {
            'supertrend': current_gold['supertrend'],
            'trend_direction': "BULLISH" if current_gold['supertrend_trend'] == 1 else "BEARISH",
            'price_distance': current_gold['price_distance'],
            'signal': current_gold['supertrend_signal'],
            'trend_strength': "STRONG" if current_gold['trend_strength'] > 1.0 else "MODERATE",
            'position_change': position_change
        }
    except Exception as e:
        logger.warning(f"Error processing SuperTrend indicator: {str(e)}")
        return None

def calculate_atr_analysis(current_gold, prev_atr, df_gold, current_idx,logger):
    """ATR 지표 분석"""
    try:
        atr_trend = (
            "Increasing" if current_gold['atr'] > prev_atr
            else "Decreasing" if current_gold['atr'] < prev_atr
            else "Stable"
        )
        
        # ATR 평균 계산 (14기간)
        atr_mean = df_gold['atr'].rolling(14).mean().iloc[current_idx]
        
        volatility_level = (
            "High" if current_gold['atr'] > atr_mean
            else "Low" if current_gold['atr'] < atr_mean
            else "Normal"
        )
        return {
            'atr': current_gold['atr'],
            'atr_trend': atr_trend,
            'volatility_level': volatility_level,
            'price_range': current_gold['high'] - current_gold['low'],
            'movement_quality': "Clean" if current_gold['high'] - current_gold['low'] > current_gold['atr'] else "Choppy"
        }
    except Exception as e:
        logger.warning(f"Error processing ATR indicator: {str(e)}")
        return None


def calculate_fibonacci_analysis(current_gold, logger):
    try:
        # 피보나치 레벨 데이터가 있는지 확인
        required_columns = ['fib_236', 'fib_382', 'fib_500', 'fib_618', 'fib_786']
        if not all(col in current_gold.index for col in required_columns):
            return None

        current_price = current_gold['close']
        key_level = None
        min_distance = float('inf')
        fib_levels = {
            'fib_236': current_gold['fib_236'],
            'fib_382': current_gold['fib_382'],
            'fib_500': current_gold['fib_500'],
            'fib_618': current_gold['fib_618'],
            'fib_786': current_gold['fib_786']
        }
        
        # 가장 가까운 피보나치 레벨 찾기
        for level_name, level_value in fib_levels.items():
            distance = abs(current_price - level_value)
            if distance < min_distance:
                min_distance = distance
                key_level = level_name.upper()

        # 가격 위치 판단
        position = "Above 50% Level" if current_price > current_gold['fib_500'] else "Below 50% Level"
        
        return {
            'fib_236': current_gold['fib_236'],
            'fib_382': current_gold['fib_382'],
            'fib_500': current_gold['fib_500'],
            'fib_618': current_gold['fib_618'],
            'fib_786': current_gold['fib_786'],
            'fib_position': position,
            'key_fib_level': f"Near {key_level}"
        }
    except Exception as e:
        logger.warning(f"Fibonacci 분석 중 오류: {str(e)}")
        return None




def calculate_stochastic_rsi(df, params, logger):
    """Stochastic RSI 계산"""
    try:
        # RSI 계산
        rsi = df.ta.rsi(close=df['close'], length=params['rsi_period'])
        
        # RSI에 대한 Stochastic 계산
        stoch_rsi = pd.Series(index=df.index)
        k_period = params['stoch_period']
        
        # %K 계산
        rsi_min = rsi.rolling(window=k_period).min()
        rsi_max = rsi.rolling(window=k_period).max()
        stoch_rsi = 100 * (rsi - rsi_min) / (rsi_max - rsi_min)
        
        # %D (Signal) 계산
        signal = stoch_rsi.rolling(window=params['d']).mean()
        
        # 상태 판단
        status = pd.Series(index=df.index)
        status.loc[stoch_rsi > params['overbought']] = 'overbought'
        status.loc[stoch_rsi < params['oversold']] = 'oversold'
        status.loc[(stoch_rsi >= params['oversold']) & (stoch_rsi <= params['overbought'])] = 'neutral'
        
        # 교차 신호 감지
        cross_signal = pd.Series('none', index=df.index)
        cross_signal.loc[
            (stoch_rsi > signal) & (stoch_rsi.shift(1) <= signal.shift(1))
        ] = 'bullish_cross'
        cross_signal.loc[
            (stoch_rsi < signal) & (stoch_rsi.shift(1) >= signal.shift(1))
        ] = 'bearish_cross'
        
        return {
            'stoch_rsi': stoch_rsi,
            'signal': signal,
            'status': status,
            'cross': cross_signal
        }
        
    except Exception as e:
        if logger:
            logger.error(f"Stochastic RSI 계산 중 오류: {str(e)}")
        return None

def calculate_atr_bands(df, params, logger):
    """ATR Bands 계산"""
    try:
        # ATR 계산
        atr = df.ta.atr(high=df['high'], low=df['low'], close=df['close'], 
                       length=params['atr_period'])
        
        # 중심선 (이동평균)
        middle = df['close'].rolling(window=params['atr_period']).mean()
        
        # 각 멀티플라이어에 대한 밴드 계산
        bands = {}
        for mult in params['band_multiplier']:
            bands[f'upper_{mult}'] = middle + (atr * mult)
            bands[f'lower_{mult}'] = middle - (atr * mult)
        
        # 돌파 강도 계산
        breach_strength = (df['close'] - middle) / atr
        
        # 반전 신호 계산
        lookback = params['reversal_lookback']
        reversal = pd.Series('none', index=df.index)
        
        # 상단 반전
        upper_breach = df['high'] > bands[f'upper_{params["band_multiplier"][-1]}']
        upper_reversal = (
            upper_breach & 
            (df['close'] < df['open']) &
            (df['close'].rolling(lookback).max().shift(1) > df['close'])
        )
        reversal.loc[upper_reversal] = 'bearish_reversal'
        
        # 하단 반전
        lower_breach = df['low'] < bands[f'lower_{params["band_multiplier"][-1]}']
        lower_reversal = (
            lower_breach & 
            (df['close'] > df['open']) &
            (df['close'].rolling(lookback).min().shift(1) < df['close'])
        )
        reversal.loc[lower_reversal] = 'bullish_reversal'
        
        return {
            'atr': atr,
            'middle': middle,
            'bands': bands,
            'breach_strength': breach_strength,
            'reversal': reversal
        }
        
    except Exception as e:
        if logger:
            logger.error(f"ATR Bands 계산 중 오류: {str(e)}")
        return None

def calculate_momentum(df, params, logger):
    """모멘텀 지표 계산"""
    try:
        momentum = {}
        
        # 각 기간별 모멘텀 계산
        periods = {
            'short': params['short_period'],
            'medium': params['medium_period'],
            'long': params['long_period']
        }
        
        for period_name, period in periods.items():
            # ROC(Rate of Change) 계산
            momentum[f'roc_{period_name}'] = (
                (df['close'] - df['close'].shift(period)) / 
                df['close'].shift(period) * 100
            )
        
        # 모멘텀 강도 판단
        strength = pd.Series('none', index=df.index)
        avg_momentum = (
            momentum['roc_short'] * 0.5 + 
            momentum['roc_medium'] * 0.3 + 
            momentum['roc_long'] * 0.2
        )
        
        strength.loc[abs(avg_momentum) > params['threshold']['strong']] = 'strong'
        strength.loc[
            (abs(avg_momentum) <= params['threshold']['strong']) & 
            (abs(avg_momentum) > params['threshold']['medium'])
        ] = 'medium'
        strength.loc[
            (abs(avg_momentum) <= params['threshold']['medium']) & 
            (abs(avg_momentum) > params['threshold']['weak'])
        ] = 'weak'
        
        # 방향 판단
        direction = pd.Series('neutral', index=df.index)
        direction.loc[avg_momentum > 0] = 'bullish'
        direction.loc[avg_momentum < 0] = 'bearish'
        
        return {
            'momentum': momentum,
            'strength': strength,
            'direction': direction,
            'average': avg_momentum
        }
        
    except Exception as e:
        if logger:
            logger.error(f"Momentum 계산 중 오류: {str(e)}")
        return None
 

def calculate_usdx_analysis(current_usdx,logger):
    """USDX 분석"""
    try:
        usdx_rsi = safe_get_indicator(current_usdx, 'rsi')
        if usdx_rsi is not None:
            usdx_rsi_status = "overbought" if usdx_rsi > 70 else \
                             "oversold" if usdx_rsi < 30 else "neutral"
        else:
            usdx_rsi_status = "N/A"
            
        return {
            'rsi': usdx_rsi,
            'rsi_status': usdx_rsi_status
        }
    except Exception as e:
        logger.warning(f"Error processing USDX analysis: {str(e)}")
        return None

def format_indicator_section(indicator_type, data, template, logger):
    """지표 섹션 포맷팅"""
    try:
        if data is not None:
            return template.format(**data)
    except Exception as e:
        if logger:
            logger.warning(f"Error formatting {indicator_type} section: {str(e)}")
    return None


 

    
def get_previous_candle(df, target_time, logger):
    """
    1봉 전 캔들 정보를 반환
    """
    try:
        previous_candle = df[df['time'] < target_time].iloc[-1]
        return previous_candle
    except Exception as e:
        logger.error(f"1봉 전 데이터 추출 실패: {str(e)}")
        return None

def save_candle_data(gold_current, gold_previous, usdx_current, usdx_previous, logger):
    try:
        candle_folder = 'candle'
        if not os.path.exists(candle_folder):
            os.makedirs(candle_folder)
            
        current_time = gold_current['time']
        file_name = f"candle_{current_time.strftime('%Y%m%d_%H%M')}.txt"
        file_path = os.path.join(candle_folder, file_name)
        
        candle_info = f"""=== XAUUSD Candles ===
Current Candle ({gold_current['time'].strftime('%Y-%m-%d %H:%M')})
Open: {gold_current['open']:.2f}
High: {gold_current['high']:.2f}
Low: {gold_current['low']:.2f}
Close: {gold_current['close']:.2f}

Previous Candle ({gold_previous['time'].strftime('%Y-%m-%d %H:%M')})
Open: {gold_previous['open']:.2f}
High: {gold_previous['high']:.2f}
Low: {gold_previous['low']:.2f}
Close: {gold_previous['close']:.2f}

=== USDX Candles ===
Current Candle ({usdx_current['time'].strftime('%Y-%m-%d %H:%M')})
Open: {usdx_current['open']:.2f}
High: {usdx_current['high']:.2f}
Low: {usdx_current['low']:.2f}
Close: {usdx_current['close']:.2f}

Previous Candle ({usdx_previous['time'].strftime('%Y-%m-%d %H:%M')})
Open: {usdx_previous['open']:.2f}
High: {usdx_previous['high']:.2f}
Low: {usdx_previous['low']:.2f}
Close: {usdx_previous['close']:.2f}"""

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(candle_info)
            
        logger.info(f"캔들 정보 저장 완료: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"캔들 정보 저장 실패: {str(e)}")
        return False

 

class TechnicalIndicators:
    @staticmethod
    def calculate_rsi(df, period=14):
        """RSI 계산"""
        return df.ta.rsi(close=df['close'], length=period)
    
    @staticmethod
    def calculate_bollinger_bands(df, period=20, std=2):
        """볼린저 밴드 계산"""
        middle = df['close'].rolling(window=period).mean()
        std_dev = df['close'].rolling(window=period).std()
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        return middle, upper, lower
        
    @staticmethod
    def calculate_atr(df, period=14):
        """ATR 계산"""
        return df.ta.atr(high=df['high'], low=df['low'], close=df['close'], length=period)
        
    @staticmethod
    def calculate_ichimoku(df, tenkan=9, kijun=26, senkou_b=52):
        """일목균형표 계산"""
        period9_high = df['high'].rolling(window=tenkan).max()
        period9_low = df['low'].rolling(window=tenkan).min()
        tenkan_sen = (period9_high + period9_low) / 2
        
        period26_high = df['high'].rolling(window=kijun).max()
        period26_low = df['low'].rolling(window=kijun).min()
        kijun_sen = (period26_high + period26_low) / 2
        
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2)
        
        period52_high = df['high'].rolling(window=senkou_b).max()
        period52_low = df['low'].rolling(window=senkou_b).min()
        senkou_span_b = ((period52_high + period52_low) / 2)
        
        return tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b

    @staticmethod
    def calculate_macd(df, fast=12, slow=26, signal=9):
        """MACD 계산"""
        return df.ta.macd(close=df['close'], fast=fast, slow=slow, signal=signal)
        
    @staticmethod
    def calculate_adx(df, length=14):
        """ADX 계산"""
        return df.ta.adx(high=df['high'], low=df['low'], close=df['close'], length=length)
        
    @staticmethod
    def calculate_stochastic(df, k=14, d=3, smooth_k=3):
        """Stochastic 계산"""
        return df.ta.stoch(high=df['high'], low=df['low'], close=df['close'], k=k, d=d, smooth_k=smooth_k)
        
    @staticmethod
    def calculate_ema(df, periods=[20, 50, 200]):
        """EMA 계산"""
        ema_values = {}
        for period in periods:
            ema_values[f'EMA_{period}'] = df.ta.ema(close=df['close'], length=period)
        return ema_values
    
    @staticmethod
    def calculate_supertrend(df, period=10, multiplier=2.0):
        """
        SuperTrend 지표 계산
        """
        try:
            # ATR 계산
            tr1 = pd.DataFrame(df['high'] - df['low'])
            tr2 = pd.DataFrame(abs(df['high'] - df['close'].shift(1)))
            tr3 = pd.DataFrame(abs(df['low'] - df['close'].shift(1)))
            frames = [tr1, tr2, tr3]
            tr = pd.concat(frames, axis=1, join='inner').max(axis=1)
            atr = tr.rolling(period).mean()

            # 기본 상단 및 하단 밴드 계산
            basic_upperband = ((df['high'] + df['low']) / 2) + (multiplier * atr)
            basic_lowerband = ((df['high'] + df['low']) / 2) - (multiplier * atr)
            
            # SuperTrend 계산
            supertrend = pd.DataFrame(index=df.index)
            supertrend['upperband'] = basic_upperband
            supertrend['lowerband'] = basic_lowerband
            supertrend['supertrend'] = 0.0
            supertrend['trend'] = 1  # 1: 상승추세, -1: 하락추세
            
            # 첫 번째 값 설정
            if df['close'][0] <= basic_upperband[0]:
                supertrend.loc[0, 'supertrend'] = basic_upperband[0]
                supertrend.loc[0, 'trend'] = -1
            else:
                supertrend.loc[0, 'supertrend'] = basic_lowerband[0]
                supertrend.loc[0, 'trend'] = 1
            
            # SuperTrend 값 계산
            for i in range(1, len(df)):
                curr_close = df['close'][i]
                prev_supertrend = supertrend['supertrend'][i-1]
                curr_upperband = basic_upperband[i]
                curr_lowerband = basic_lowerband[i]
                prev_trend = supertrend['trend'][i-1]
                
                if prev_supertrend <= curr_close:
                    curr_trend = 1
                    curr_st = max(curr_lowerband, prev_supertrend)
                else:
                    curr_trend = -1
                    curr_st = min(curr_upperband, prev_supertrend)
                
                supertrend.loc[i, 'supertrend'] = curr_st
                supertrend.loc[i, 'trend'] = curr_trend
            
            # 결과 데이터프레임에 추가
            df['supertrend'] = supertrend['supertrend']
            df['supertrend_trend'] = supertrend['trend']
            
            # 추가 분석 데이터 계산
            df['price_distance'] = abs(df['close'] - df['supertrend'])
            df['trend_strength'] = df['price_distance'] / df['supertrend'] * 100
            
            # 시그널 생성
            df['supertrend_signal'] = 'HOLD'
            df.loc[(df['supertrend_trend'] == 1) & (df['supertrend_trend'].shift(1) == -1), 'supertrend_signal'] = 'BUY'
            df.loc[(df['supertrend_trend'] == -1) & (df['supertrend_trend'].shift(1) == 1), 'supertrend_signal'] = 'SELL'
            
            return df
            
        except Exception as e:
            print(f"SuperTrend 계산 중 오류 발생: {str(e)}")
            return None
        
    @staticmethod
    def calculate_fibonacci(df, period=14):
        """Fibonacci Retracement 계산"""
        high = df['high'].rolling(window=period).max()
        low = df['low'].rolling(window=period).min()
        diff = high - low
        
        fib_levels = {
            'fib_236': high - (diff * 0.236),
            'fib_382': high - (diff * 0.382),
            'fib_500': high - (diff * 0.500),
            'fib_618': high - (diff * 0.618),
            'fib_786': high - (diff * 0.786)
        }
        return fib_levels