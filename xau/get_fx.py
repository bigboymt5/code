import os
import json
import csv
import logging
import traceback
from datetime import datetime
from flask import Flask, request, jsonify
from account import ALLOWED_ACCOUNTS, ALLOWED_ACCOUNTS_BIG, is_valid_account
import economic_events  # 새로 작성한 모듈 임포트
from threading import Thread

# 상수 정의
version_nick = 'Gold40'
app = Flask(__name__)
PPX_FOLDER = './ppx'
CORE_RESPONSE_FOLDER = './core_response'
GET_LIST_CSV_PATH = os.path.join(PPX_FOLDER, 'get_list.csv')


def setup_daily_logger(file_name):
    """일별 로거 설정 - 경고 및 오류만 기록"""
    log_dir = 'log'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, f"log_{datetime.now().strftime('%Y%m%d')}.txt")
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.WARNING)

    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# ✅ 로거 초기화 - 함수 정의 직후, 다른 함수들보다 먼저
logger = setup_daily_logger("get_fx.py")


def log_to_account_csv(ip, timestamp, data):
    """계좌별 CSV 파일에 거래 데이터 기록"""
    try:
        account = data.get('account', 'unknown')
        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        year_month = dt.strftime("%Y%m")
        
        base_dir = 'account'
        month_dir = os.path.join(base_dir, year_month)
        os.makedirs(month_dir, exist_ok=True)
        
        file_path = os.path.join(month_dir, f"{account}.csv")
        file_exists = os.path.isfile(file_path)
        
        row_data = [
            dt.strftime("%Y-%m-%d"),
            dt.strftime("%H:%M:%S"),
            request.args.get('balance', ''),
            request.args.get('equity', ''),
            request.args.get('profit', ''),
            request.args.get('floating_profit', ''),
            request.args.get('drawdown', ''),
            request.args.get('today_profit', ''),
            request.args.get('yesterday_profit', ''),
            request.args.get('week_profit', ''),
            request.args.get('month_profit', ''),
            request.args.get('total_profit', ''),
            request.args.get('server', ''),
            request.args.get('symbol', ''),
            request.args.get('nickname', ''),
            ip
        ]
        
        with open(file_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(['date', 'time', 'balance', 'equity', 'profit', 
                               'floating_profit', 'drawdown', 'today_profit',
                               'yesterday_profit', 'week_profit', 'month_profit',
                               'total_profit', 'server', 'symbol', 'nickname', 'ip'])
            writer.writerow(row_data)
            
    except Exception as e:
        logger.error(f"계좌별 CSV 기록 실패: {str(e)}")
        logger.error(traceback.format_exc())
        raise


def get_latest_json_file():
    """PPX_FOLDER에서 최신 ppx_re_ JSON 파일 경로 반환"""
    try:
        json_files = [f for f in os.listdir(PPX_FOLDER) 
                     if f.startswith('ppx_re_') and f.endswith('.json')]
        
        if not json_files:
            logger.error(f"JSON 파일을 찾을 수 없습니다: {PPX_FOLDER}")
            return None
            
        latest_file = max(json_files, key=lambda f: os.path.getmtime(os.path.join(PPX_FOLDER, f)))
        full_path = os.path.join(PPX_FOLDER, latest_file)
        
        return full_path
        
    except Exception as e:
        logger.error(f"최신 JSON 파일 검색 실패: {e}")
        return None


def handle_license_check(account, nickname, plan=None):
    """라이센스 검증 처리"""
    try:
        # 디버깅 로그 추가
        logger.warning(f"handle_license_check 시작: account={account}, nickname={nickname}, plan={plan}")
        
        if not account or not is_valid_account(account, plan):
            logger.warning(f"미등록 계좌: {account}, plan: {plan}")
            with open('./account/license_nook.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        
        if nickname.lower() == 'demo':
            logger.warning(f"데모 계좌 응답")
            with open('./account/demo.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        
        allowed_versions = [version_nick, 'Gold365']
        if nickname not in allowed_versions:
            logger.warning(f"버전 불일치: {nickname}")
            with open('./account/update.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        
        if plan == 'big':
            from account import get_expiry_date
            expiry_date = get_expiry_date(account, plan)
            
            logger.warning(f"BIG 플랜 계좌: expiry_date={expiry_date}")
            
            return {
                "next_candle_trend": "OK",
                "confidence_level": 65,
                "key_factors": "정상 등록 계좌",
                "timestamp": "0",
                "Resistance_level": expiry_date if expiry_date else "0",
                "Support_level": "0"
            }
        else:
            logger.warning(f"일반 계좌: license_ok.json 반환")
            with open('./account/license_ok.json', 'r', encoding='utf-8') as f:
                return json.load(f)
            
    except Exception as e:
        logger.error(f"라이센스 검증 실패: {e}")
        logger.error(traceback.format_exc())
        return None


@app.route('/api/xau/', methods=['GET'])
def get_price_data():
    """XAU 가격 데이터 API 엔드포인트"""
    ip = request.remote_addr
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    account = request.args.get('account', '')
    nickname = request.args.get('nickname', '')
    licensecheck = request.args.get('licensecheck', '')
    plan = request.args.get('plan', '')
    
    try:
        request_data = {
            'account': account,
            'balance': request.args.get('balance', ''),
            'equity': request.args.get('equity', ''),
            'profit': request.args.get('profit', ''),
            'floating_profit': request.args.get('floating_profit', ''),
            'drawdown': request.args.get('drawdown', ''),
            'today_profit': request.args.get('today_profit', ''),
            'yesterday_profit': request.args.get('yesterday_profit', ''),
            'week_profit': request.args.get('week_profit', ''),
            'month_profit': request.args.get('month_profit', ''),
            'total_profit': request.args.get('total_profit', ''),
            'server': request.args.get('server', ''),
            'symbol': request.args.get('symbol', ''),
            'nickname': nickname
        }
        log_to_account_csv(ip, timestamp, request_data)
        
        # 라이센스 체크 로직 개선
        if licensecheck.lower() == 'yes':
            # plan 파라미터 정규화: 빈 문자열이면 None, 아니면 소문자로 변환
            plan_normalized = plan.lower() if plan else None
            
            # 디버깅 로그 추가
            logger.warning(f"라이센스 체크: account={account}, plan={plan_normalized}, nickname={nickname}")
            
            response = handle_license_check(account, nickname, plan_normalized)
            
            if response:
                logger.warning(f"라이센스 응답 반환: {response.get('key_factors', 'N/A')}")
                return jsonify(response), 200
            else:
                logger.error(f"라이센스 체크 실패: response가 None")
        
        # 일반 JSON 파일 반환
        latest_file = get_latest_json_file()
        if latest_file and os.path.exists(latest_file):
            with open(latest_file, 'r', encoding='utf-8') as f:
                response_data = json.load(f)
                
                try:
                    response_data = economic_events.add_event_to_json(response_data)
                except Exception as e:
                    logger.error(f"경제 이벤트 추가 실패: {str(e)}")
                    logger.error(traceback.format_exc())
                
                return jsonify(response_data), 200
                
    except Exception as e:
        logger.error(f"요청 처리 실패: {e}")
        logger.error(traceback.format_exc())
    
    default_response = {
        "next_candle_trend": "",
        "confidence_level": 44,
        "key_factors": "오류 발생",
        "timestamp": "",
        "Resistance_level": "",
        "Support_level": ""
    }
    return jsonify(default_response), 500


def run_app_on_port(app, port):
    try:
        app.run(host='0.0.0.0', port=port, threaded=True, use_reloader=False)
    except Exception as e:
        logger.error(f"서버 실행 실패 (포트 {port}): {e}")


if __name__ == '__main__':
    try:
        t1 = Thread(target=run_app_on_port, args=(app, 5005))
        t1.daemon = True
        t1.start()
        
        run_app_on_port(app, 32988)
    except Exception as e:
        logger.error(f"서버 실행 실패: {e}")