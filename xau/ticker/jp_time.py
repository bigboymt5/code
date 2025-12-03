import schedule
import time
import subprocess
import datetime
from datetime import datetime, timedelta
from threading import Thread, Lock
import logging
import os
from collections import deque

# ============= 설정 변수 =============
오전실행 = 5  # 오전 실행 시간 (시)
오후실행 = 19  # 오후 실행 시간 (시)
주말실행 = True  # 주말 실행 여부 (True/False)
실행간격 = 3  # 실행 간격 (분)

# 28개 일본 시장용 심볼 목록
외환쌍목록 = [
    "USDJPY",
    "EURJPY",
    "GBPJPY",
    "AUDJPY",
    "EURUSD",
    "GBPUSD",
    "USDMXN",
    "USDTRY",
    "USDZAR",
    "XRPJPY",
    "XRPUSD",
    "BTCJPY",
    "BTCUSD",
    "ETHUSD",
    "Nikkei225",
    "NAS100.r",
    "SP500.r",
    "XAUUSD",
    "CL-OIL",
    "VIX.r",
    "NVIDIA",
    "TSLA",
    "COIN",
    "PLTR",
    "AAPL",
    "AMAZON",
    "MSFT",
    "GOOG"
]
# =====================================

# 전역 변수 선언
logger = None
running_jobs = {}
job_lock = Lock()

# 작업 이력 저장 (최근 10개)
job_history = deque(maxlen=10)
job_history_lock = Lock()
# 다음 실행 예정 작업 저장
next_jobs = {}

def setup_daily_logger(file_name):
    log_dir = 'log'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, f"jp_log_{datetime.now().strftime('%Y%m%d')}.txt")
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        for handler in logger.handlers[:]:
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

def update_next_jobs():
    """다음 실행 예정인 작업 시간 업데이트"""
    global next_jobs
    next_jobs.clear()

    job_names = [f"jp_fx.py ({ticker})" for ticker in 외환쌍목록]

    for job_name in job_names:
        next_run = get_next_run_time(job_name)
        if next_run:
            next_jobs[job_name] = next_run

def display_status():
    """현재 상태를 콘솔에 표시"""
    os.system('cls' if os.name == 'nt' else 'clear')
    current_time = datetime.now()

    print("\n=== 일본 시장 스케줄러 상태 ===")
    print(f"현재 시간: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n실행 중인 작업:")
    with job_lock:
        if running_jobs:
            for job in running_jobs:
                print(f"- {job}")
        else:
            print("- 없음")

    print("\n다음 예정 작업:")
    sorted_jobs = sorted(next_jobs.items(), key=lambda x: x[1])
    for job_name, next_run in sorted_jobs:
        time_diff = next_run - current_time
        total_minutes = int(time_diff.total_seconds() / 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        seconds = int(time_diff.total_seconds() % 60)

        time_str = f"{next_run.strftime('%H:%M:%S')} ("
        if hours > 0:
            time_str += f"{hours}시간 "
        time_str += f"{minutes}분 {seconds}초 후)"

        print(f"- {job_name}: {time_str}")

    print("\n최근 실행 이력:")
    with job_history_lock:
        if job_history:
            history_list = list(job_history)
            for history in history_list:
                print(f"- {history}")
        else:
            print("- 기록 없음")

    print("\n====================================")

def run_script(script_name, args):
    """스크립트를 새 창에서 실행하고 결과를 반환 (오류 발생 시에도 계속 진행)"""
    try:
        start_time = datetime.now()

        # 시작 로그 기록
        with job_history_lock:
            job_history.appendleft(f"{start_time.strftime('%H:%M:%S')} - {script_name} {args} 실행 시작")

        # 프로세스 실행
        cmd = ['start', 'python', script_name] + args.split()
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # 프로세스 실행 결과 대기
        stdout, stderr = process.communicate()

        # 실행 결과에 따른 처리
        if process.returncode == 0:
            with job_history_lock:
                job_history.appendleft(f"{datetime.now().strftime('%H:%M:%S')} - {script_name} {args} 실행 완료")
                logger.info(f"{script_name} {args} 실행 완료")
            return True
        else:
            with job_history_lock:
                job_history.appendleft(f"{datetime.now().strftime('%H:%M:%S')} - {script_name} {args} 실행 실패 (계속 진행)")
                logger.warning(f"{script_name} {args} 실행 실패: {stderr.decode()} (계속 진행)")
            return True  # 실패해도 True 반환하여 계속 진행

    except Exception as e:
        with job_history_lock:
            job_history.appendleft(f"{datetime.now().strftime('%H:%M:%S')} - {script_name} {args} 오류 발생 (계속 진행)")
            logger.warning(f"{script_name} {args} 실행 중 오류 발생: {str(e)} (계속 진행)")
        return True  # 오류 발생해도 True 반환하여 계속 진행

def get_next_run_time(job_name):
    """각 작업의 다음 실행 시간을 정확하게 계산 (5분 간격으로 28개 심볼 실행)"""
    current_time = datetime.now()
    today = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    # 주말 확인 (0=월요일, 6=일요일)
    is_weekend = current_time.weekday() >= 5

    # 주말 실행이 False이고 현재 주말이면 다음 평일 찾기
    if not 주말실행 and is_weekend:
        days_ahead = 1
        while (current_time + timedelta(days=days_ahead)).weekday() >= 5:
            days_ahead += 1
        next_weekday = today + timedelta(days=days_ahead)
        # 다음 평일 오전 시작 시간 반환
        return next_weekday.replace(hour=오전실행, minute=0)

    # 28개 심볼의 인덱스 찾기
    ticker_index = -1
    for idx, ticker in enumerate(외환쌍목록):
        if ticker in job_name:
            ticker_index = idx
            break

    if ticker_index == -1:
        return None

    # 각 심볼의 시작 분 계산 (5분 간격)
    total_minutes = ticker_index * 실행간격

    # 시간과 분으로 분리 (60분 넘어가면 시간 증가)
    오전시 = 오전실행 + (total_minutes // 60)
    오전분 = total_minutes % 60
    오후시 = 오후실행 + (total_minutes // 60)
    오후분 = total_minutes % 60

    # 오전 및 오후 실행 시간
    times = [
        today.replace(hour=오전시, minute=오전분),
        today.replace(hour=오후시, minute=오후분)
    ]

    # 현재 시간보다 큰 가장 가까운 실행 시간 찾기
    for next_time in times:
        if next_time > current_time:
            return next_time

    # 오늘 실행할 시간이 없으면 내일 오전 시간 반환
    next_day = tomorrow
    # 주말 실행이 False이고 내일이 주말이면 다음 평일 찾기
    if not 주말실행:
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)

    return next_day.replace(hour=오전시, minute=오전분)

def execute_with_retry(script_name, args, job_key):
    """오류 발생 시에도 계속 진행하는 실행 함수"""
    with job_lock:
        if job_key in running_jobs:
            logger.info(f"{job_key}가 이미 실행 중입니다")
            return
        running_jobs[job_key] = True

    try:
        # 오류 발생 시에도 계속 진행 (run_script 함수에서 처리)
        run_script(script_name, args)
    except Exception as e:
        # 예외 발생 시 로그 기록 후 계속 진행
        with job_history_lock:
            job_history.appendleft(f"{datetime.now().strftime('%H:%M:%S')} - {job_key} 예외 발생 (계속 진행)")
        logger.warning(f"{job_key} 예외 발생: {str(e)} (계속 진행)")
    finally:
        with job_lock:
            running_jobs.pop(job_key, None)

def schedule_job(script_name, args, job_key):
    """스크립트 실행을 별도 스레드에서 처리"""
    Thread(target=execute_with_retry, args=(script_name, args, job_key), daemon=True).start()

def setup_schedules():
    """설정 변수를 기반으로 스케줄 설정 (5분 간격으로 28개 심볼 실행)"""
    logger.info(f"일본 시장 스케줄 설정 시작 - 오전: {오전실행}시, 오후: {오후실행}시, 주말실행: {주말실행}, 실행간격: {실행간격}분")

    # 28개 심볼에 대해 순차적으로 스케줄 등록
    for idx, ticker in enumerate(외환쌍목록):
        # 각 심볼의 시작 분 계산 (5분 간격)
        total_minutes = idx * 실행간격

        # 시간과 분으로 분리 (60분 넘어가면 시간 증가)
        오전시 = 오전실행 + (total_minutes // 60)
        오전분 = total_minutes % 60
        오후시 = 오후실행 + (total_minutes // 60)
        오후분 = total_minutes % 60

        # 시간 포맷팅 (HH:MM)
        오전시간 = f"{오전시:02d}:{오전분:02d}"
        오후시간 = f"{오후시:02d}:{오후분:02d}"

        job_key = f"jp_fx.py ({ticker})"
        args = f"h_val=12 h_tic={ticker}"

        # 주말 실행 여부에 따라 스케줄 등록
        if 주말실행:
            # 매일 실행
            schedule.every().day.at(오전시간).do(schedule_job, "jp_fx.py", args, job_key)
            schedule.every().day.at(오후시간).do(schedule_job, "jp_fx.py", args, job_key)
            logger.info(f"{ticker} 스케줄 등록 완료 - 매일 {오전시간}, {오후시간}")
        else:
            # 평일만 실행
            for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
                getattr(schedule.every(), day).at(오전시간).do(schedule_job, "jp_fx.py", args, job_key)
                getattr(schedule.every(), day).at(오후시간).do(schedule_job, "jp_fx.py", args, job_key)
            logger.info(f"{ticker} 스케줄 등록 완료 - 평일 {오전시간}, {오후시간}")

    logger.info("모든 일본 시장 스케줄 등록 완료")

def main():
    global logger
    logger = setup_daily_logger('jp_scheduler')
    logger.info("일본 시장 스케줄러 시작")
    setup_schedules()

    try:
        while True:
            current_time = datetime.now()

            # 매일 자정에 새로운 로그 파일 사용을 위해 로거 재설정
            if current_time.hour == 0 and current_time.minute == 0:
                logger = setup_daily_logger('jp_scheduler')

            # 상태 업데이트 및 표시 (5초마다)
            if current_time.second % 100 == 0:
                update_next_jobs()
                display_status()

            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("일본 시장 스케줄러 종료")

if __name__ == "__main__":
    main()
