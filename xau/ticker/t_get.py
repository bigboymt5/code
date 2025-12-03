import os
import json
import logging
from datetime import datetime
from flask import Flask, request

app = Flask(__name__)

# 설정
JSON_FOLDER = './json'
LOG_FOLDER = './log'


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


def get_latest_json_file(symbol, lang='ko'):
    """
    JSON 폴더에서 특정 심볼의 최신 JSON 파일 반환
    파일 형식:
        - 한글(ko): {SYMBOL}_{YYYYMMDD}_{HHMMSS}.json
        - 영어(en): en_{SYMBOL}_{YYYYMMDD}_{HHMMSS}.json
        - 일본어(jp): jp_{SYMBOL}_{YYYYMMDD}_{HHMMSS}.json

    Args:
        symbol: 심볼명 (예: XAUUSD, BTCUSD)
        lang: 언어 (ko, en, jp) - 기본값: ko
    """
    try:
        if not os.path.exists(JSON_FOLDER):
            logger.error(f"JSON 폴더가 존재하지 않습니다: {JSON_FOLDER}")
            return None

        # 언어에 따른 접두사 설정
        if lang == 'en':
            prefix = f"en_{symbol}_"
        elif lang == 'jp':
            prefix = f"jp_{symbol}_"
        else:  # 기본값 'ko'
            prefix = f"{symbol}_"

        # 심볼로 시작하는 JSON 파일 필터링
        json_files = [
            f for f in os.listdir(JSON_FOLDER)
            if f.startswith(prefix) and f.endswith('.json') and not f.startswith('all_')
        ]

        if not json_files:
            logger.error(f"심볼 {symbol} (언어: {lang})에 해당하는 JSON 파일을 찾을 수 없습니다")
            return None

        # 수정 시간 기준으로 최신 파일 선택
        latest_file = max(
            json_files,
            key=lambda f: os.path.getmtime(os.path.join(JSON_FOLDER, f))
        )

        return os.path.join(JSON_FOLDER, latest_file)

    except Exception as e:
        logger.error(f"최신 JSON 파일 검색 실패 (심볼: {symbol}, 언어: {lang}): {str(e)}")
        return None


@app.route('/api/ticker/', methods=['GET'])
def get_ticker():
    """
    티커 데이터 반환 API
    파라미터:
        h_tic: 심볼명 (예: XAUUSD, BTCUSD)
               기본값: XAUUSD
        lang: 언어 (ko, en, jp)
              기본값: ko (한글)
    """
    try:
        # h_tic 파라미터 가져오기 (기본값: XAUUSD)
        symbol = request.args.get('h_tic', '').strip()
        if not symbol:
            symbol = 'XAUUSD'

        # lang 파라미터 가져오기 (기본값: ko)
        lang = request.args.get('lang', 'ko').strip().lower()

        # 유효한 언어 체크
        if lang not in ['ko', 'en', 'jp']:
            logger.warning(f"유효하지 않은 언어 파라미터: {lang}, 기본값 'ko' 사용")
            lang = 'ko'

        # 최신 JSON 파일 찾기
        json_file_path = get_latest_json_file(symbol, lang)

        if not json_file_path or not os.path.exists(json_file_path):
            error_msg = f"심볼 {symbol} (언어: {lang})에 해당하는 JSON 파일을 찾을 수 없습니다"
            logger.error(error_msg)
            return app.response_class(
                response=json.dumps({"error": error_msg, "symbol": symbol, "lang": lang}, ensure_ascii=False, indent=2),
                status=404,
                mimetype='application/json'
            )

        # JSON 파일 읽어서 반환
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 한글이 유니코드 이스케이프되지 않도록 설정
        return app.response_class(
            response=json.dumps(data, ensure_ascii=False, indent=2),
            status=200,
            mimetype='application/json'
        )

    except Exception as e:
        error_msg = f"요청 처리 실패: {str(e)}"
        logger.error(error_msg)
        return app.response_class(
            response=json.dumps({"error": error_msg}, ensure_ascii=False, indent=2),
            status=500,
            mimetype='application/json'
        )


if __name__ == '__main__':
    try:
        print(f"티커 서버 시작 - 포트 5004")
        print(f"API 엔드포인트: http://localhost:5004/api/ticker/")
        print(f"사용 예시:")
        print(f"  - 한글: http://localhost:5004/api/ticker/?h_tic=XAUUSD")
        print(f"  - 영어: http://localhost:5004/api/ticker/?h_tic=XAUUSD&lang=en")
        print(f"  - 일본어: http://localhost:5004/api/ticker/?h_tic=XAUUSD&lang=jp")
        print(f"\n주의: 일본어 데이터는 jp_fx.py로 생성됩니다")
        app.run(host='0.0.0.0', port=5004, threaded=True)
    except Exception as e:
        logger.error(f"서버 실행 실패: {str(e)}")




# 기본 사용 예시
# http://localhost:5004/api/ticker/                        # 기본값: XAUUSD, 한글
# http://localhost:5004/api/ticker/?h_tic=XAUUSD           # XAUUSD, 한글 (t_fx.py)
# http://localhost:5004/api/ticker/?h_tic=BTCUSD           # BTCUSD, 한글 (t_fx.py)

# 언어별 사용 예시
# http://localhost:5004/api/ticker/?h_tic=XAUUSD&lang=ko   # XAUUSD, 한글 (t_fx.py)
# http://localhost:5004/api/ticker/?h_tic=XAUUSD&lang=en   # XAUUSD, 영어 (t_fx.py)
# http://localhost:5004/api/ticker/?h_tic=XAUUSD&lang=jp   # XAUUSD, 일본어 (jp_fx.py)

# 다양한 심볼 + 언어 조합
# http://localhost:5004/api/ticker/?h_tic=BTCUSD&lang=en   # BTCUSD, 영어 (t_fx.py)
# http://localhost:5004/api/ticker/?h_tic=EURUSD&lang=jp   # EURUSD, 일본어 (jp_fx.py)

# 데이터 생성 명령어:
# 한글/영어: python t_fx.py h_val=12 h_tic=XAUUSD
# 일본어: python jp_fx.py h_val=12 h_tic=XAUUSD