# n8n_auto_sync.py
import time
import json
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path

# ===== 설정 =====
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhYWMyM2ZkNi1iODhmLTQ5YTgtYjZiMS1kMGI0ODRhNjM3ODEiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY0NzYwNDcyfQ.USuRSX-MqDz9D574GIcvM90tDtdYUOx4aP9ESXGbnOg"
N8N_BASE_URL = "https://kein.app.n8n.cloud/api/v1"
WORKFLOW_ID = "E8pfPqrItpsG2w1o"
WATCH_FILE = "shorts.json"
# ==================

class N8nJsonHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_modified = 0
        
    def on_modified(self, event):
        if event.src_path.endswith(WATCH_FILE):
            current_time = time.time()
            if current_time - self.last_modified < 1:
                return
            self.last_modified = current_time
            
            print(f"\n[{time.strftime('%H:%M:%S')}] 파일 변경 감지: {WATCH_FILE}")
            self.upload_to_n8n(event.src_path)
    
    def upload_to_n8n(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read().strip()
                if not content:
                    print("❌ 파일이 비어있습니다")
                    return
                workflow_data = json.loads(content)
            
            url = f"{N8N_BASE_URL}/workflows/{WORKFLOW_ID}"
            headers = {
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json"
            }
            
            response = requests.put(url, json=workflow_data, headers=headers)
            
            if response.status_code == 200:
                print("✅ n8n 업로드 성공!")
            else:
                print(f"❌ 업로드 실패: {response.status_code}")
                print(f"   에러: {response.text}")
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 에러: {e}")
        except Exception as e:
            print(f"❌ 에러 발생: {e}")

def main():
    path = Path.cwd()
    
    print("=" * 50)
    print("n8n 워크플로우 자동 동기화 시작")
    print("=" * 50)
    print(f"감시 경로: {path}")
    print(f"감시 파일: {WATCH_FILE}")
    print(f"워크플로우 ID: {WORKFLOW_ID}")
    print(f"\n파일을 수정하고 저장(Ctrl+S)하면 자동으로 n8n에 업로드됩니다.")
    print("종료하려면 Ctrl+C 를 누르세요.\n")
    
    event_handler = N8nJsonHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n\n프로그램 종료")
    
    observer.join()

if __name__ == "__main__":
    main()