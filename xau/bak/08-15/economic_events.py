#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta
import pytz  # pip install pytz

# 로거 가져오기
logger = logging.getLogger(__name__)

# 시간대 정의
EASTERN_TZ = pytz.timezone('US/Eastern')  # 미국 동부 시간대
UTC_TZ = pytz.UTC
KST_TZ = pytz.timezone('Asia/Seoul')  # 한국 시간대

# 경제 이벤트 데이터를 배열로 정의
# 각 이벤트는 [날짜, 시간, 이벤트명(영문), 중요도, 이벤트명(한글)] 형식으로 저장
ECONOMIC_EVENTS = [
 
    ["2025-04-03T11:00:00Z", "U.S. International Trade in Goods and Services February 2025", 1, "444 미국 상품 및 서비스 무역수지"],
    ["2025-04-03T12:30:00Z", "U.S. International Trade in Goods and Services February 2025", 1, "555미국 상품 및 서비스 무역수지"],
    ["2025-04-30T12:30:00Z", "Gross Domestic Product 1st Quarter 2025 (Advance Estimate)", 3, "미국 GDP 1분기 (속보치)"],
    ["2025-04-16T15:30:00Z", "Fed Chair Jerome Powell Speech", 3, "연방준비제도 의장 제롬 파월 연설"],
    ["2025-04-30T14:00:00Z", "Personal Income and Outlays March 2025", 3, "개인소득 및 지출"],
    ["2025-05-06T12:30:00Z", "U.S. International Trade in Goods and Services March 2025", 2, "미국 상품 및 서비스 무역수지"],
    ["2025-05-29T12:30:00Z", "Gross Domestic Product 1st Quarter 2025 (Second Estimate) and Corporate Profits (Preliminary)", 3, "미국 GDP 1분기 (수정치) 및 기업이익"],
    ["2025-05-30T12:30:00Z", "Personal Income and Outlays April 2025", 3, "개인소득 및 지출"],
    ["2025-06-05T12:30:00Z", "U.S. International Trade in Goods and Services Annual Update", 2, "미국 상품 및 서비스 무역수지 연간 업데이트"],
    ["2025-06-05T12:30:00Z", "U.S. International Trade in Goods and Services April 2025", 2, "미국 상품 및 서비스 무역수지"],
    ["2025-06-24T12:30:00Z", "U.S. International Transactions 1st Quarter 2025 and Annual Update", 2, "미국 국제 거래"],
    ["2025-06-26T12:30:00Z", "Gross Domestic Product 1st Quarter 2025 (Third Estimate) GDP by Industry and Corporate Profits (Revised)", 3, "미국 GDP 1분기 (확정치)"],
    ["2025-06-27T12:30:00Z", "Personal Income and Outlays May 2025", 3, "개인소득 및 지출"],
    ["2025-06-27T14:00:00Z", "Gross Domestic Product by State and Personal Income by State 1st Quarter 2025", 3, "주별 GDP 및 개인소득"],
    ["2025-06-30T12:30:00Z", "U.S. International Investment Position 1st Quarter 2025 and Annual Update", 1, "미국 국제투자위치"],
    ["2025-07-03T12:30:00Z", "U.S. International Trade in Goods and Services May 2025", 2, "미국 상품 및 서비스 무역수지"],
    ["2025-07-03T14:00:00Z", "U.S. Trade in Services Detailed Tables 2024", 1, "미국 서비스 무역 상세표"],
    ["2025-07-11T12:30:00Z", "New Foreign Direct Investment in the United States 2024", 1, "미국 내 해외직접투자"],
    ["2025-07-22T12:30:00Z", "Direct Investment by Country and Industry 2024", 1, "국가 및 산업별 직접투자"],
    ["2025-07-30T12:30:00Z", "Gross Domestic Product 2nd Quarter 2025 (Advance Estimate)", 3, "미국 GDP 2분기 (속보치)"],
    ["2025-07-31T12:30:00Z", "Personal Income and Outlays June 2025", 3, "개인소득 및 지출"],
    ["2025-08-05T12:30:00Z", "U.S. International Trade in Goods and Services June 2025", 2, "미국 상품 및 서비스 무역수지"],
    ["2025-08-22T12:30:00Z", "Activities of U.S. Multinational Enterprises 2023", 1, "미국 다국적기업 활동"],
    ["2025-08-28T12:30:00Z", "Gross Domestic Product 2nd Quarter 2025 (Second Estimate) and Corporate Profits (Preliminary)", 3, "미국 GDP 2분기 (수정치) 및 기업이익"],
    ["2025-08-29T12:30:00Z", "Personal Income and Outlays July 2025", 3, "개인소득 및 지출"],
    ["2025-09-04T12:30:00Z", "U.S. International Trade in Goods and Services July 2025", 2, "미국 상품 및 서비스 무역수지"],
    ["2025-09-23T12:30:00Z", "U.S. International Transactions 2nd Quarter 2025", 2, "미국 국제 거래"],
    ["2025-09-25T12:30:00Z", "Gross Domestic Product 2nd Quarter 2025 (Third Estimate) GDP by Industry and Corporate Profits (Revised)", 3, "미국 GDP 2분기 (확정치)"],
    ["2025-09-26T12:30:00Z", "Personal Income and Outlays August 2025", 3, "개인소득 및 지출"],
    ["2025-09-26T14:00:00Z", "Gross Domestic Product by State and Personal Income by State 2nd Quarter 2025 and Personal Consumption Expenditures by State 2024", 3, "주별 GDP 및 개인소득"],
    ["2025-09-29T12:30:00Z", "U.S. International Investment Position 2nd Quarter 2025", 1, "미국 국제투자위치"],
    ["2025-10-07T12:30:00Z", "U.S. International Trade in Goods and Services August 2025", 2, "미국 상품 및 서비스 무역수지"],
    ["2025-10-07T14:00:00Z", "Services Supplied Through Affiliates 2023", 1, "계열사를 통한 서비스 공급"],
    ["2025-10-30T12:30:00Z", "Gross Domestic Product 3rd Quarter 2025 (Advance Estimate)", 3, "미국 GDP 3분기 (속보치)"],
    ["2025-10-31T12:30:00Z", "Personal Income and Outlays September 2025", 3, "개인소득 및 지출"],
    ["2025-11-04T12:30:00Z", "U.S. International Trade in Goods and Services September 2025", 2, "미국 상품 및 서비스 무역수지"],
    ["2025-11-21T12:30:00Z", "Activities of U.S. Affiliates of Foreign Multinational Enterprises 2023", 1, "외국 다국적기업 미국 계열사 활동"],
    ["2025-11-26T12:30:00Z", "Gross Domestic Product 3rd Quarter 2025 (Second Estimate) and Corporate Profits (Preliminary)", 3, "미국 GDP 3분기 (수정치) 및 기업이익"],
    ["2025-11-26T14:00:00Z", "Personal Income and Outlays October 2025", 3, "개인소득 및 지출"],
    ["2025-12-03T12:30:00Z", "Gross Domestic Product by County and Metropolitan Area and Personal Income by County and Metropolitan Area 2024", 3, "카운티별 및 대도시권별 GDP 및 개인소득"],
    ["2025-12-04T12:30:00Z", "U.S. International Trade in Goods and Services October 2025", 2, "미국 상품 및 서비스 무역수지"],
    ["2025-12-11T12:30:00Z", "Real Personal Consumption Expenditures by State and Real Personal Income by State and Metropolitan Area 2024", 3, "주별 실질 개인소비지출 및 소득"],
    ["2025-12-18T12:30:00Z", "U.S. International Transactions 3rd Quarter 2025", 2, "미국 국제 거래"],
    ["2025-12-19T12:30:00Z", "Gross Domestic Product 3rd Quarter 2025 (Third Estimate) GDP by Industry and Corporate Profits (Revised)", 3, "미국 GDP 3분기 (확정치)"],
    ["2025-12-19T14:00:00Z", "Personal Income and Outlays November 2025", 3, "개인소득 및 지출"],
    ["2025-12-22T12:30:00Z", "Gross Domestic Product by State and Personal Income by State 3rd Quarter 2025", 3, "주별 GDP 및 개인소득"],
    ["2025-12-23T12:30:00Z", "U.S. International Investment Position 3rd Quarter 2025", 1, "미국 국제투자위치"]
]
def parse_date_time(date_str, time_str):
    """
    날짜와 시간 문자열을 파싱하여 datetime 객체로 변환
    
    Args:
        date_str (str): 'YYYY.MM.DD' 형식의 날짜 문자열
        time_str (str): 'HH:MM AM/PM' 형식의 시간 문자열
        
    Returns:
        datetime: 파싱된 datetime 객체 (US Eastern Time)
    """
    try:
        # 날짜 파싱 (YYYY.MM.DD -> YYYY-MM-DD)
        year, month, day = date_str.split('.')
        date_formatted = f"{year}-{month}-{day}"
        
        # 시간 파싱
        datetime_str = f"{date_formatted} {time_str}"
        dt = datetime.strptime(datetime_str, "%Y-%m-%d %I:%M %p")
        
        # 미국 동부 시간대로 설정
        eastern_dt = EASTERN_TZ.localize(dt)
        return eastern_dt
        
    except Exception as e:
        logger.error(f"날짜/시간 파싱 실패: {date_str} {time_str}, 오류: {e}")
        return None

def convert_to_utc(eastern_dt):
    """미국 동부 시간을 UTC로 변환"""
    if eastern_dt is None:
        return None
    return eastern_dt.astimezone(UTC_TZ)

def convert_to_kst(eastern_dt):
    """미국 동부 시간을 한국 시간(KST)으로 변환"""
    if eastern_dt is None:
        return None
    return eastern_dt.astimezone(KST_TZ)

def get_next_economic_event():
    """
    앞으로 48시간 내에 발생할 가장 가까운 경제 이벤트 하나만 가져옴
    """
    try:
        # 디버깅을 위한 로그 추가
        logger.debug("get_next_economic_event 함수 시작")
        
        # 현재 UTC 시간 가져오기
        now_utc = datetime.now(UTC_TZ)
        logger.debug(f"현재 UTC 시간: {now_utc.isoformat()}")
        
        # 48시간 후 시간 계산
        future_48h_utc = now_utc + timedelta(hours=48)
        logger.debug(f"48시간 후 UTC 시간: {future_48h_utc.isoformat()}")
        
        closest_event = None
        min_time_diff = float('inf')
        
        # 이벤트 배열 구조 디버깅
        if ECONOMIC_EVENTS:
            logger.debug(f"첫 이벤트 구조 확인: {ECONOMIC_EVENTS[0]}")
        
        # 모든 이벤트 확인
        for event in ECONOMIC_EVENTS:
            # 로그 추가
            logger.debug(f"이벤트 확인: {event}")
            
            # 배열 구조 확인 및 적절히 파싱
            event_datetime_str = event[0]  # ISO 형식의 날짜 문자열
            event_en = event[1]
            importance = event[2]
            event_kr = event[3]
            
            try:
                # ISO 8601 형식 날짜 파싱
                # 'Z'를 포함하는 ISO 형식 처리
                event_dt_utc = datetime.fromisoformat(event_datetime_str.replace('Z', '+00:00'))
                logger.debug(f"이벤트 시간(UTC): {event_dt_utc.isoformat()}")
                
                # 미래 이벤트이면서 48시간 이내인 경우만 고려
                if now_utc < event_dt_utc <= future_48h_utc:
                    logger.debug(f"적합한 이벤트 발견: {event_en}")
                    time_diff = (event_dt_utc - now_utc).total_seconds()
                    
                    # 가장 가까운 미래 이벤트 찾기
                    if time_diff < min_time_diff:
                        min_time_diff = time_diff
                        logger.debug(f"새로운 가장 가까운 이벤트: {event_en}, 시간 차이: {time_diff}초")
                        
                        # 미국 동부 시간과 한국 시간으로 변환
                        event_dt_eastern = event_dt_utc.astimezone(EASTERN_TZ)
                        event_dt_kst = event_dt_utc.astimezone(KST_TZ)
                        
                        closest_event = {
                            'next_economic_event': {
                                'us_date': event_dt_eastern.strftime("%Y-%m-%d"),
                                'us_time': event_dt_eastern.strftime("%I:%M %p"),
                                'kr_date': event_dt_kst.strftime("%Y-%m-%d"),
                                'kr_time': event_dt_kst.strftime("%H:%M"),
                                'event_en': event_en,
                                'event_kr': event_kr,
                                'importance': importance
                            }
                        }
                else:
                    logger.debug(f"이벤트 제외됨: {event_en}, 시간: {event_dt_utc}")
            except Exception as e:
                logger.error(f"이벤트 처리 중 오류: {e}, 이벤트: {event}")
                continue
        
        if closest_event:
            logger.info(f"다음 48시간 내 경제 이벤트 찾음: {closest_event['next_economic_event']['event_en']}")
            return closest_event
        else:
            logger.info("48시간 내 경제 이벤트를 찾을 수 없음")
            return {
                'next_economic_event': {
                    'us_date': 'N/A',
                    'us_time': 'N/A',
                    'kr_date': 'N/A',
                    'kr_time': 'N/A',
                    'event_en': 'No upcoming economic events within 48 hours',
                    'event_kr': '48시간 내 예정된 경제 이벤트 없음',
                    'importance': 0
                }
            }
            
    except Exception as e:
        logger.error(f"경제 이벤트 가져오기 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None
    



def add_event_to_json(json_data):
    """
    기존 JSON 데이터에 다음 경제 이벤트 정보 추가
    
    Args:
        json_data (dict): 기존 JSON 데이터
        
    Returns:
        dict: 경제 이벤트가 추가된 JSON 데이터
    """
    try:
        next_event = get_next_economic_event()
        if next_event and json_data:
            # 기존 JSON에 next_economic_event 키를 추가
            json_data.update(next_event)
            logger.info("JSON에 경제 이벤트 정보 추가 완료")
        elif json_data:
            # 이벤트 없음 메시지 추가
            json_data.update({
                'next_economic_event': {
                    'us_date': 'N/A',
                    'us_time': 'N/A',
                    'kr_date': 'N/A',
                    'kr_time': 'N/A',
                    'event_en': 'No upcoming economic events',
                    'event_kr': '예정된 경제 이벤트 없음',
                    'importance': 0
                }
            })
            logger.info("JSON에 '이벤트 없음' 메시지 추가")
        return json_data
    except Exception as e:
        logger.error(f"JSON에 이벤트 추가 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return json_data  # 원본 JSON 반환

# 테스트 코드
if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 다음 이벤트 가져오기
    event = get_next_economic_event()
    if event:
        print("다음 경제 이벤트:")
        import json
        print(json.dumps(event, indent=4, ensure_ascii=False))
    else:
        print("다음 경제 이벤트를 찾을 수 없습니다.")