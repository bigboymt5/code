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
    "USDJPY": "USDJPY",
    "EURJPY": "EURJPY",
    "GBPJPY": "GBPJPY",
    "AUDJPY": "AUDJPY",
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "USDMXN": "USDMXN",
    "USDTRY": "USDTRY",
    "USDZAR": "USDZAR",
    "XRPJPY": "XRPJPY",
    "XRPUSD": "XRPUSD",
    "BTCJPY": "BTCJPY",
    "BTCUSD": "BTCUSD",
    "ETHUSD": "ETHUSD",
    "NIKKEI225": "Nikkei225",
    "NAS100": "NAS100.r",
    "SP500": "SP500.r",
    "XAUUSD": "XAUUSD",
    "CL-OIL": "CL-OIL",
    "VIX": "VIX.r",
    "NVIDIA": "NVIDIA",
    "TSLA": "TSLA",
    "COIN": "COIN",
    "PLTR": "PLTR",
    "AAPL": "AAPL",
    "AMAZON": "AMAZON",
    "MSFT": "MSFT",
    "GOOG": "GOOG"
}

# 티커 일본어명 맵
TICKER_NAMES_JP = {
    "USDJPY": "ドル円",
    "EURJPY": "ユーロ円",
    "GBPJPY": "ポンド円",
    "AUDJPY": "豪ドル円",
    "EURUSD": "ユーロドル",
    "GBPUSD": "ポンドドル",
    "USDMXN": "ドルペソ",
    "USDTRY": "ドルリラ",
    "USDZAR": "ドルランド",
    "XRPJPY": "リップル円",
    "XRPUSD": "リップルドル",
    "BTCJPY": "ビットコイン円",
    "BTCUSD": "ビットコイン",
    "ETHUSD": "イーサリアム",
    "Nikkei225": "日経225",
    "NIKKEI225": "日経225",
    "NAS100": "ナスダック100",
    "NAS100.r": "ナスダック100",
    "SP500": "S&P500",
    "SP500.r": "S&P500",
    "XAUUSD": "ゴールド",
    "CL-OIL": "原油",
    "VIX": "恐怖指数",
    "VIX.r": "恐怖指数",
    "NVIDIA": "エヌビディア",
    "TSLA": "テスラ",
    "COIN": "コインベース",
    "PLTR": "パランティア",
    "AAPL": "アップル",
    "AMAZON": "アマゾン",
    "MSFT": "マイクロソフト",
    "GOOG": "グーグル"
}

# 最終推奨に応じた絵文字マップ (ランダム選択)
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
        description="現在のシンボルの状況説明（50文字程度）"
    )
    technical_analysis: str = Field(
        ...,
        description="テクニカル分析の説明（100文字程度）"
    )
    fundamental_analysis: str = Field(
        ...,
        description="ファンダメンタルおよび心理的分析（100文字程度）"
    )
    expert_opinion: str = Field(
        ...,
        description="専門家の意見 BUY/SELL（50文字程度）"
    )
    final_recommendation: str = Field(
        ...,
        pattern="^(BUY|SELL)$",
        description="最終意見 BUY/SELL（50文字程度）"
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
    """現在時刻を1時間単位に丸める"""
    current_time = datetime.now()
    # 30分を基準に丸める
    if current_time.minute >= 30:
        current_time = current_time + timedelta(hours=1)

    # 時間のみ残して分、秒、マイクロ秒は0に設定
    rounded_time = current_time.replace(minute=0, second=0, microsecond=0)
    return rounded_time




def get_date_ranges():
    """現在の日付/時刻を基準に検索日付範囲を生成"""
    current_time = datetime.now()
    today = current_time.date()
    weekday = current_time.weekday()  # 0=月曜日, 6=日曜日

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

    if weekday >= 5:  # 週末の場合
        if weekday == 5:  # 土曜日
            # 金曜日と土曜日
            friday = today - timedelta(days=1)
            search_dates = [friday, today]
        else:  # 日曜日
            # 金曜日、土曜日、日曜日
            friday = today - timedelta(days=2)
            saturday = today - timedelta(days=1)
            search_dates = [friday, saturday, today]
    else:  # 平日の場合
        if current_time.hour < 12:  # 午前
            yesterday = today - timedelta(days=1)
            search_dates = [yesterday, today]
        else:  # 午後
            search_dates = [today]

    # 日付範囲文字列生成（曜日含む）
    date_range = ", ".join([format_date_with_day(date) for date in search_dates])

    # 既存フォーマット互換性維持のためのtoday_str, yesterday_str
    today_str = format_date_without_day(today)
    yesterday_str = format_date_without_day(today - timedelta(days=1))

    # MDY形式の日付
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

PRICE_DEVIATION = 5.0  # 許容価格偏差 ($)

def get_timeframe_from_hours(hours):
    """時間値をMT5タイムフレームに変換"""
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
        symbol: 取引シンボル (デフォルト: XAUUSD)
        hours: ローソク足時間 (デフォルト: 6)
    """
    global TICKER_SYMBOL, HOURS_VALUE

    if symbol is None:
        symbol = TICKER_SYMBOL
    if hours is None:
        hours = HOURS_VALUE

    # シンボル正規化
    mt5_symbol, search_keyword = normalize_symbol(symbol)

    # MT5初期化
    if not init_mt5():
        raise Exception("MT5 Initialization failed.")

    # タイムフレーム設定
    timeframe = get_timeframe_from_hours(hours)

    # データ照会 (MT5標準シンボル使用)
    print(f"[デバッグ] MT5から{mt5_symbol}データ照会中... (タイムフレーム: {hours}H)")
    rates = mt5.copy_rates_from_pos(mt5_symbol, timeframe, 0, 1)
    if rates is None or len(rates) == 0:
        error = mt5.last_error()
        print(f"[エラー] MT5データ照会失敗 - シンボル: {mt5_symbol}, エラー: {error}")
        # 使用可能なシンボルリストの一部を出力
        symbols = mt5.symbols_get()
        if symbols:
            print(f"[情報] 使用可能なシンボル例（最初の10個）:")
            for s in symbols[:10]:
                print(f"  - {s.name}")
        raise Exception(f"No data received from MT5 for {mt5_symbol}. Error: {error}")
    current_price = rates[0]['close']
    print(f"[デバッグ] {mt5_symbol} 現在価格: {current_price}")

    # 日付情報取得
    dates = get_date_ranges()
    price_range_min = current_price - PRICE_DEVIATION
    price_range_max = current_price + PRICE_DEVIATION

    # シンボル名表示用変換 (XAUUSD -> Gold 等)
    symbol_display = search_keyword
    if search_keyword == "XAUUSD":
        symbol_display = "XAUUSD (Gold)"

    # 日本円ペア用の追加検索サイトマップ
    jpy_additional_sources = {
        "USDJPY": "https://finance.yahoo.co.jp/quote/USDJPY=X",
        "EURJPY": "https://finance.yahoo.co.jp/quote/EURJPY=X",
        "GBPJPY": "https://finance.yahoo.co.jp/quote/GBPJPY=X",
        "AUDJPY": "https://finance.yahoo.co.jp/quote/AUDJPY=X",
        "XRPJPY": "https://finance.yahoo.co.jp/quote/XRPJPY=CC",
        "BTCJPY": "https://finance.yahoo.co.jp/quote/BTCJPY=CC"
    }

    # 基本検索サイト
    sources_text = """Sources to check (prioritize these websites):
1. https://www.investing.com/
2. https://www.tradingview.com/
3. https://www.fxstreet.com/
4. https://www.kitco.com/
5. https://www.barchart.com/"""

    # 日本円ペアの場合 Yahoo Finance Japan 追加
    if search_keyword in jpy_additional_sources:
        yahoo_jp_url = jpy_additional_sources[search_keyword]
        sources_text += f"""

ADDITIONAL SOURCE FOR JPY PAIRS (検索補助サイト):
- Yahoo Finance Japan: {yahoo_jp_url}
  (日本円ペアは通常の検索サイトで情報が少ないため、このサイトを必ず検索に含めてください)"""

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

{sources_text}

Search for events related to: Market sentiment, technical factors, fundamental news, expert opinions

DATE FILTERS:
- ONLY include content from these dates: {dates['date_range']}
- STRICTLY EXCLUDE any content from dates not listed above
- EXCLUDE any content where historical data deviates more than ${PRICE_DEVIATION} from the current price ({current_price})

REQUIRED RESPONSE FORMAT (JSON):
You MUST respond with ONLY a JSON object in this exact format, without any additional text:

{{
    "current_situation": "{search_keyword}の現在の状況を50文字程度で説明（例：急落、急上昇、緩やかな上昇、横ばい、現在12%上昇、20%下落など）- 日本語",
    "technical_analysis": "20日線、ボリンジャーバンドなど検索されたテクニカル指標を使用した100文字程度の説明 - 日本語",
    "fundamental_analysis": "業績発表の好材料や悪材料、イシュー、事件、ファンダメンタルおよび心理的要因、指標、地政学的要因などについて100文字程度の説明 - 日本語",
    "expert_opinion": "検索された専門家の短期的な買い/売り意見の要約（100文字程度）- 日本語",
    "final_recommendation": "Strong BUY" または "Strong SELL" または "BUY" または "SELL" または "HOLD"
}}

IMPORTANT:
- Response must be ONLY valid JSON, no markdown, no code blocks, no explanations
- All text fields must be in Japanese
- Stay within character limits for each field
- final_recommendation must be exactly "Strong BUY" or "BUY" or "HOLD" or "SELL" or "Strong SELL"

Answer based on comprehensive analysis of current market data, technical indicators, and expert opinions."""

    print("\n[デバッグ] 生成されたプロンプト:")
    print("="*80)
    print(prompt)
    print("="*80)
    return prompt



def parse_response(response_text):
   print("\n[デバッグ] API応答内容:")
   print("="*80)
   print(response_text)
   print("="*80)

   response_json = json.loads(response_text)
   print("\n[デバッグ] パース済みJSONデータ:")
   print(json.dumps(response_json, indent=4, ensure_ascii=False))

   return response_json


def extract_json(content):
    """JSON部分のみを抽出する関数 - 改善版"""
    import re
    import json

    # </think> タグ以降の内容のみ抽出
    if '</think>' in content:
        content = content.split('</think>')[-1].strip()

    # 方法1: JSONブロックを見つける (```json 形式)
    json_match = re.search(r'```json\s*({[\s\S]*?})\s*```', content)
    if json_match:
        try:
            return json_match.group(1)
        except:
            pass

    # 方法2: next_candle_trendを含むJSONオブジェクトを見つける (改善されたパターン)
    json_match = re.search(r'(\{[^{}]*"next_candle_trend"[^{}]*"medium_term_target"[^{}]*\})', content, re.DOTALL)
    if json_match:
        try:
            json_str = json_match.group(1)
            # 有効なJSONかどうか確認
            json.loads(json_str)
            return json_str
        except:
            pass

    # 方法3: 直接JSONオブジェクトを探す
    json_match = re.search(r'({[\s\S]*})', content)
    if json_match:
        try:
            json_str = json_match.group(1)
            # 有効なJSONかどうか確認
            json.loads(json_str)
            return json_str
        except:
            pass

    # 方法4: 全体の応答がJSONかどうか確認
    try:
        json.loads(content)
        return content
    except:
        pass

    return None

def get_market_analysis(api_key: str, symbol=None, hours=None):
    """
    市場分析を実行する関数
    Args:
        api_key: Perplexity API キー
        symbol: 取引シンボル (デフォルト: XAUUSD)
        hours: ローソク足時間 (デフォルト: 6)
    """
    global TICKER_SYMBOL, HOURS_VALUE

    if symbol is None:
        symbol = TICKER_SYMBOL
    if hours is None:
        hours = HOURS_VALUE

    # シンボル正規化
    mt5_symbol, search_keyword = normalize_symbol(symbol)

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.perplexity.ai"
    )

    try:
        print(f"\n[デバッグ] API要求送信... (入力: {symbol} -> MT5: {mt5_symbol}, 検索: {search_keyword}, Timeframe: {hours}H)")
        response = client.chat.completions.create(
            model="sonar-reasoning-pro",
            messages=[
                {
                    "role": "system",
                    "content": """You must respond with a JSON object only, without any surrounding text, explanation, or code formatting.
                    The JSON should be in this exact format in Japanese:
                    {
                        "current_situation": "現在の状況説明（50文字程度、日本語）",
                        "technical_analysis": "テクニカル分析（100文字程度、日本語）",
                        "fundamental_analysis": "ファンダメンタル分析（100文字程度、日本語）",
                        "expert_opinion": "専門家の意見（100文字程度、日本語）",
                        "final_recommendation": "Strong BUY" or "BUY" or "HOLD" or "SELL" or "Strong SELL"
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
        print("\n[デバッグ] API応答:")
        print(content)

        # JSON部分抽出
        json_str = extract_json(content)
        if not json_str:
            print("\n[エラー] JSONが見つかりません")
            raise ValueError("No JSON found in response")

        try:
            json_content = json.loads(json_str)

            # 必須キー確認
            required_keys = ['current_situation', 'technical_analysis', 'fundamental_analysis',
                            'expert_opinion', 'final_recommendation']

            for key in required_keys:
                if key not in json_content:
                    print(f"\n[警告] 必須キー '{key}' が応答にありません")

            # ティッカー日本語名取得
            ticker_name = TICKER_NAMES_JP.get(mt5_symbol, TICKER_NAMES_JP.get(search_keyword, ""))

            # current_situationとexpert_opinionの前にティッカー名を追加
            if ticker_name and 'current_situation' in json_content:
                json_content['current_situation'] = f"{ticker_name} {json_content['current_situation']}"

            if ticker_name and 'expert_opinion' in json_content:
                json_content['expert_opinion'] = f"{ticker_name} {json_content['expert_opinion']}"

            # final_recommendationに「短期見通し」 + 絵文字追加
            if 'final_recommendation' in json_content:
                recommendation = json_content['final_recommendation']
                emoji_list = RECOMMENDATION_EMOJIS.get(recommendation, [""])
                emoji = random.choice(emoji_list) if emoji_list else ""
                json_content['final_recommendation'] = f"短期見通し {emoji} {recommendation}"

            # JSONファイルとして保存 (検索キーワード使用、jp_接頭辞)
            now = datetime.now()
            filename = f"json/jp_{search_keyword}_{now.strftime('%Y%m%d_%H%M%S')}.json"
            os.makedirs('json', exist_ok=True)

            # メタデータ追加
            save_data = {
                "symbol": mt5_symbol,
                "search_keyword": search_keyword,
                "display_name": ticker_name,
                "timeframe": f"{hours}H",
                "timestamp": now.strftime('%Y-%m-%d %H:%M:%S'),
                "language": "jp",
                "analysis": json_content
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=4)

            print(f"\n[完了] 分析結果保存: {filename}")
            return json_content

        except json.JSONDecodeError as e:
            print(f"\n[エラー] JSONパース失敗: {str(e)}")
            print(f"問題の文字列: {json_str}")
            raise ValueError(f"Invalid JSON format: {str(e)}")

    except Exception as e:
        print(f"\n[エラー発生] {str(e)}")
        print("詳細エラー:")
        traceback.print_exc()
        raise


def parse_arguments():
    """コマンドライン引数をパースする関数"""
    global TICKER_SYMBOL, HOURS_VALUE

    # sys.argvから直接パース
    args = sys.argv[1:]

    for arg in args:
        if arg.startswith('h_val='):
            try:
                HOURS_VALUE = int(arg.split('=')[1])
                print(f"[設定] ローソク足時間: {HOURS_VALUE}H")
            except ValueError:
                print(f"[警告] 不正なh_val値: {arg}, デフォルト値 {HOURS_VALUE}H 使用")
        elif arg.startswith('h_tic='):
            # 入力値そのまま保存（大文字小文字維持、normalize_symbolで処理）
            TICKER_SYMBOL = arg.split('=')[1]
            print(f"[設定] 入力シンボル: {TICKER_SYMBOL}")

    # デフォルト値出力
    if len(args) == 0:
        print(f"[設定] デフォルト値使用 - シンボル: {TICKER_SYMBOL}, ローソク足: {HOURS_VALUE}H")

    return TICKER_SYMBOL, HOURS_VALUE


if __name__ == "__main__":
    API_KEY = "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"

    # コマンドライン引数パース
    symbol, hours = parse_arguments()

    # 分析実行
    print(f"\n{'='*80}")
    print(f"市場分析開始: {symbol} ({hours}Hローソク足)")
    print(f"{'='*80}\n")

    result = get_market_analysis(API_KEY, symbol, hours)

    print(f"\n{'='*80}")
    print("分析結果:")
    print(f"{'='*80}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"{'='*80}\n")


# 金 12時間分析
#python jp_fx.py h_val=12 h_tic=XAUUSD

# ユーロドル 4時間分析
#python jp_fx.py h_val=4 h_tic=EURUSD

# ビットコイン 8時間分析
#python jp_fx.py h_val=8 h_tic=BTCUSD
