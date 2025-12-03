import schedule
import time
import subprocess
import datetime
from datetime import datetime, timedelta
from threading import Thread, Lock
import sys
import logging
import os
from collections import deque

# 전역 변수 선언
logger = None
running_jobs = {}
job_lock = Lock()

# 작업 이력 저장 (최근 10개)
job_history = deque(maxlen=10)
job_history_lock = Lock()  # 새로운 락 추가
# 다음 실행 예정 작업 저장
next_jobs = {}

def setup_daily_logger(file_name):
    log_dir = 'log'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, f"log_{datetime.now().strftime('%Y%m%d')}.txt")
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

def is_execution_time():
    """현재 시간이 실행 가능한 시간인지 확인"""
    current_time = datetime.now()
    
    # 주말 체크
    if current_time.weekday() >= 5:  # 5: 토요일, 6: 일요일
        return False
    
    # 0시부터 1시까지 실행 중지
    if current_time.hour == 0:
        return False
    
    return True

def update_next_jobs():
    """다음 실행 예정인 작업 시간 업데이트"""
    global next_jobs
    next_jobs.clear()
    
    # 여기서 job_names를 news.py, h2.py, ppx로만 변경
    job_names = [ "news.py", "h2.py", "ppx.py" ]
    
    for job_name in job_names:
        next_run = get_next_run_time(job_name)
        if next_run:
            next_jobs[job_name] = next_run

def display_status():
    """현재 상태를 콘솔에 표시"""
    os.system('cls' if os.name == 'nt' else 'clear')
    current_time = datetime.now()
    
    print("\n=== 스케줄러 상태 ===")
    print(f"현재 시간: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n실행 중인 작업:")
    with job_lock:  # 기존 락 사용
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
    with job_history_lock:  # job_history 접근 시 락 사용
        if job_history:
            history_list = list(job_history)  # 락이 걸린 상태에서 복사
            for history in history_list:  # 복사본을 순회
                print(f"- {history}")
        else:
            print("- 기록 없음")
    
    print("\n====================================")

def run_script(script_name):
    """스크립트를 새 창에서 실행하고 결과를 반환"""
    if not is_execution_time():
        logger.info(f"{script_name} 실행 제외 시간")
        return True

    try:
        start_time = datetime.now()
        
        # script_name에서 파라미터 분리
        script_parts = script_name.split(' ') if ' ' in script_name else [script_name]
        base_script = script_parts[0]
        param = script_parts[1] if len(script_parts) > 1 else None
        
        # 시작 로그 기록
        with job_history_lock:
            if param:
                job_history.appendleft(f"{start_time.strftime('%H:%M:%S')} - {base_script} {param} 실행 시작")
            else:
                job_history.appendleft(f"{start_time.strftime('%H:%M:%S')} - {base_script} 실행 시작")
        
        # 프로세스 실행
        if param:
            process = subprocess.Popen(
                ['start', 'python', base_script, param],
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        else:
            process = subprocess.Popen(
                ['start', 'python', base_script],
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        
        # 프로세스 실행 결과 대기
        stdout, stderr = process.communicate()
        
        # 실행 결과에 따른 처리
        if process.returncode == 0:
            with job_history_lock:
                if param:
                    job_history.appendleft(f"{datetime.now().strftime('%H:%M:%S')} - {base_script} {param} 실행 완료")
                    logger.info(f"{base_script} {param} 실행 완료")
                else:
                    job_history.appendleft(f"{datetime.now().strftime('%H:%M:%S')} - {base_script} 실행 완료")
                    logger.info(f"{base_script} 실행 완료")
            return True
        else:
            with job_history_lock:
                if param:
                    job_history.appendleft(f"{datetime.now().strftime('%H:%M:%S')} - {base_script} {param} 실행 실패")
                    logger.error(f"{base_script} {param} 실행 실패: {stderr.decode()}")
                else:
                    job_history.appendleft(f"{datetime.now().strftime('%H:%M:%S')} - {base_script} 실행 실패")
                    logger.error(f"{base_script} 실행 실패: {stderr.decode()}")
            return False
            
    except Exception as e:
        with job_history_lock:
            if len(script_parts) > 1:
                job_history.appendleft(f"{datetime.now().strftime('%H:%M:%S')} - {base_script} {param} 오류 발생")
                logger.error(f"{base_script} {param} 실행 중 오류 발생: {str(e)}")
            else:
                job_history.appendleft(f"{datetime.now().strftime('%H:%M:%S')} - {base_script} 오류 발생")
                logger.error(f"{base_script} 실행 중 오류 발생: {str(e)}")
        return False

def get_next_run_time(job_name):
    """각 작업의 다음 실행 시간을 정확하게 계산"""
    current_time = datetime.now()
    base_time = current_time.replace(second=0, microsecond=0)
    
    # 여기서 news.py, h2.py, ppx 만 처리
    if job_name == "news.py":
        # 매시 정각 15분 (00:15, 01:15, 02:15 ...)
        next_time = base_time.replace(minute=15)
        if next_time <= current_time:
            next_time += timedelta(hours=1)
        return next_time

    elif job_name == "h2.py":
        # 매시 정각 16분 (00:16, 01:16, 02:16 ...)
        next_time = base_time.replace(minute=16)
        if next_time <= current_time:
            next_time += timedelta(hours=1)
        return next_time

    #elif job_name == "ppx.py":
        # 매시 정각 45분 (00:45, 01:45, 02:45 ...)
        #next_time = base_time.replace(minute=45)
        #if next_time <= current_time:
        #    next_time += timedelta(hours=1)
        #return next_time

    return None

def execute_with_retry(script_name):
    """실패 시 재시도 로직이 포함된 실행 함수"""
    with job_lock:
        if script_name in running_jobs:
            logger.info(f"{script_name}가 이미 실행 중입니다")
            return
        running_jobs[script_name] = True
    
    try:
        retries = 0
        while retries < 3:
            if run_script(script_name):
                break
            
            retries += 1
            if retries < 3:
                job_history.appendleft(f"{datetime.now().strftime('%H:%M:%S')} - {script_name} 재시도 {retries}/3")
                logger.info(f"{script_name} 재시도 {retries}/3 - 1분 대기")
                time.sleep(60)
        
        if retries == 3:
            job_history.appendleft(f"{datetime.now().strftime('%H:%M:%S')} - {script_name} 최종 실패")
            logger.error(f"{script_name} 3번 재시도 후 최종 실패")
    finally:
        with job_lock:
            running_jobs.pop(script_name, None)

def schedule_job(script_name):
    """스크립트 실행을 별도 스레드에서 처리"""
    Thread(target=execute_with_retry, args=(script_name,), daemon=True).start()

def setup_schedules():
    # 기존 모든 스케줄 제거하고 news.py, h2.py, ppx 만 스케줄

    # news.py - 매시 정각 15분에 실행
    schedule.every().hour.at("15:00").do(schedule_job, "news.py")

    # h2.py - 매시 정각 16분에 실행
    schedule.every().hour.at("16:00").do(schedule_job, "h2.py")

    # ppx - 매시 정각 45분에 실행
    #schedule.every().hour.at("45:00").do(schedule_job, "ppx.py")

def main():
    global logger
    logger = setup_daily_logger('scheduler')
    logger.info("스케줄러 시작")
    setup_schedules()
   
    try:
        while True:
            current_time = datetime.now()
           
            # 매일 자정에 새로운 로그 파일 사용을 위해 로거 재설정
            if current_time.hour == 0 and current_time.minute == 0:
                logger = setup_daily_logger('scheduler')
           
            # 상태 업데이트 및 표시 (5초마다)
            if current_time.second % 5 == 0:
                update_next_jobs()
                display_status()
           
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("스케줄러 종료")

if __name__ == "__main__":
    main()
