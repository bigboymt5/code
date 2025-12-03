# mt5_time_set.py
import logging
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5

# 계정 정보
ACCOUNT_ID = 17055878
PASSWORD = 'Realboy9989*'
SERVER = 'VantageInternational-Live 7'
BROKER_UTC_OFFSET = 2  # 브로커 서버 시간 (UTC+2)

"""ACCOUNT_ID =80498633
PASSWORD = 'Qwerasdf1290**'
SERVER = 'FPMarketsSC-Live'
"""

# 로거 설정
def setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger

logger = setup_logger()

# MT5 초기화
def init_mt5() -> bool:
    """MT5 초기화 및 로그인"""
    if not mt5.initialize():
        logger.error("MT5 초기화 실패")
        return False
    if not mt5.login(ACCOUNT_ID, password=PASSWORD, server=SERVER):
        logger.error("MT5 로그인 실패")
        mt5.shutdown()
        return False
    logger.info("MT5 연결 성공")
    return True
 