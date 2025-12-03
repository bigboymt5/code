import os
import json
import csv
import logging
import traceback
from datetime import datetime
from flask import Flask, request, jsonify
from account import ALLOWED_ACCOUNTS, is_valid_account
import economic_events  # 새로 작성한 모듈 임포트
from threading import Thread

# 상수 정의
version_nick = 'Gold40'
app = Flask(__name__)
PPX_FOLDER = './ppx'
CORE_RESPONSE_FOLDER = './core_response'
GET_LIST_CSV_PATH = os.path.join(PPX_FOLDER, 'get_list.csv')
 

def setup_daily_logger(file_name):
    """일별 로거 설정"""
    log_dir = 'log'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, f"log_{datetime.now().strftime('%Y%m%d')}.txt")
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # 이전 핸들러 제거
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info(f"파일 {file_name} 실행 시작")
    return logger

def log_to_account_csv(ip, timestamp, data):
    """계좌별 CSV 파일에 거래 데이터 기록"""
    try:
        account = data.get('account', 'unknown')
        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        year_month = dt.strftime("%Y%m")
        
        base_dir = 'account'
        month_dir = os.path.join(base_dir, year_month)
        os.makedirs(month_dir, exist_ok=True)
        #logger.info(f"계좌 데이터 저장 경로 생성: {month_dir}")
        
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
            #logger.info(f"계좌 {account} 데이터 기록 완료")
            
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
            error_message = f"JSON 파일을 찾을 수 없습니다. 폴더({PPX_FOLDER})에 파일이 없습니다."
            logger.error(error_message)
            return None
            
        latest_file = max(json_files, key=lambda f: os.path.getmtime(os.path.join(PPX_FOLDER, f)))
        full_path = os.path.join(PPX_FOLDER, latest_file)
        
        #logger.info(f"선택된 파일: {latest_file}")
        return full_path
        
    except Exception as e:
        logger.error(f"최신 JSON 파일 검색 실패: {e}")
        return None

def handle_license_check(account, nickname):
    """라이센스 검증 처리"""
    try:
        # 1. 계좌번호 확인
        if not account or not is_valid_account(account):
            logger.warning(f"미등록 계좌 접근 시도: {account}")
            with open('./account/license_nook.json', 'r', encoding='utf-8') as f:
                response_data = json.load(f)
                #logger.info(f"미등록 계좌에 대한 응답: {json.dumps(response_data, ensure_ascii=False)}")
                return response_data
        
        # 2. 데모 계정 확인
        if nickname.lower() == 'demo':
            logger.info("데모 모드 응답")
            with open('./account/demo.json', 'r', encoding='utf-8') as f:
                response_data = json.load(f)
                #logger.info(f"데모 응답: {json.dumps(response_data, ensure_ascii=False)}")
                return response_data
        
        # 3. 버전 확인
        allowed_versions = [version_nick, 'Gold365']  # Gold40(기본값)과 Gold365 모두 허용
        
        if nickname not in allowed_versions:
            logger.info(f"버전 불일치: {nickname} - 허용 버전: {allowed_versions}")
            with open('./account/update.json', 'r', encoding='utf-8') as f:
                response_data = json.load(f)
                #logger.info(f"업데이트 필요 응답: {json.dumps(response_data, ensure_ascii=False)}")
                return response_data
        else:
            #logger.info(f"버전 확인 통과: {nickname}")
        
        # 모든 검증 통과
        #logger.info(f"등록된 계좌 접근: {account}")
            with open('./account/license_ok.json', 'r', encoding='utf-8') as f:
                response_data = json.load(f)
                #logger.info(f"등록 계좌에 대한 응답: {json.dumps(response_data, ensure_ascii=False)}")
                return response_data
            
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
    
    #logger.info(f"요청 받음 - 계좌: {account}, 닉네임: {nickname}, 라이센스체크: {licensecheck}")
    
    try:
        # 요청 데이터 로깅
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
        
        # 라이센스 체크 처리
        if licensecheck.lower() == 'yes':
            response = handle_license_check(account, nickname)
            if response:
                return jsonify(response)
        
        # 일반 요청 처리
        latest_file = get_latest_json_file()
        if latest_file and os.path.exists(latest_file):
            with open(latest_file, 'r', encoding='utf-8') as f:
                response_data = json.load(f)
                
                # 디버깅을 위해 원본 JSON을 로깅
                #logger.debug(f"원본 JSON: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
                
                try:
                    # 경제 이벤트 추가 시도
                    event_data = economic_events.get_next_economic_event()
                    #logger.debug(f"경제 이벤트 데이터: {json.dumps(event_data, ensure_ascii=False, indent=2) if event_data else 'None'}")
                    
                    # 경제 이벤트를 JSON에 추가
                    response_data = economic_events.add_event_to_json(response_data)
                except Exception as e:
                    logger.error(f"경제 이벤트 추가 중 오류 발생: {str(e)}")
                    logger.error(traceback.format_exc())
                
                # 최종 JSON 로깅
                logger.debug(f"JSON 응답: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
                
                return jsonify(response_data)
                
    except Exception as e:
        logger.error(f"요청 처리 실패: {e}")
        logger.error(f"상세 에러:\n{traceback.format_exc()}")
    
    # 오류 시 기본 응답
    default_response = {
        "next_candle_trend": "",
        "confidence_level": 44,
        "key_factors": "오류 발생",
        "timestamp": "",
        "Resistance_level": "",
        "Support_level": ""
    }
    #logger.info(f"기본 응답 전송: {json.dumps(default_response, ensure_ascii=False)}")
    return jsonify(default_response)

# 로거 초기화
logger = setup_daily_logger("get_fx.py")


def run_app_on_port(app, port):
    try:
        app.run(host='0.0.0.0', port=port, threaded=True, use_reloader=False)
        logger.info(f"서버 포트 {port}에서 시작")
    except Exception as e:
        logger.error(f"서버 실행 실패 (포트 {port}): {e}")

if __name__ == '__main__':
    try:
        # 첫 번째 포트(5005)에서 실행할 스레드 생성
        t1 = Thread(target=run_app_on_port, args=(app, 5005))
        t1.daemon = True
        t1.start()
        logger.info("포트 5005에서 서버 시작")
        
        # 두 번째 포트(32988)에서 실행
        run_app_on_port(app, 32988)
        logger.info("포트 32988에서 서버 시작")
    except Exception as e:
        logger.error(f"서버 실행 실패: {e}")