import os, asyncio, time, json, re, base64
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv
import sqlite3
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

load_dotenv()
SAFE182_ESNTL_ID = os.getenv("SAFE182_ESNTL_ID", "")
SAFE182_AUTH_KEY = os.getenv("SAFE182_AUTH_KEY", "")
KAKAO_JAVASCRIPT_KEY = os.getenv("KAKAO_JAVASCRIPT_KEY", "")
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS", "")
ITS_CCTV_API_KEY = os.getenv("ITS_CCTV_API_KEY", "")
NER_SERVER_URL = "http://localhost:8000"

class MissingPerson(BaseModel):
    id: str
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None
    photo_base64: Optional[str] = None
    priority: str = "MEDIUM"
    risk_factors: List[str] = []
    ner_entities: Dict[str, List[str]] = {}
    extracted_features: Dict[str, List[str]] = {}
    lat: float = 36.5
    lng: float = 127.8
    created_at: str = ""
    status: str = "ACTIVE"
    category: Optional[str] = None

class NotificationRequest(BaseModel):
    person: MissingPerson
    target_tokens: List[str] = []
    test_mode: bool = False

class TokenRegistration(BaseModel):
    token: str
    user_id: str
    platform: str = "flutter"

class SightingReport(BaseModel):
    person_id: str
    reporter_location: Dict[str, float]
    timestamp: str

class CCTVRequest(BaseModel):
    lat: float
    lng: float
    radius: int = 1000

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"관리자 연결됨. 총 {len(self.active_connections)}명")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"관리자 연결 해제됨. 총 {len(self.active_connections)}명")
    
    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message, ensure_ascii=False))
            except:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

class OptimizedAPIManager:
    def __init__(self):
        self.last_request_time = 0
        self.min_interval = 300
        self.cache_duration = 3600
        self.cached_data = {}
        self.cache_timestamp = 0
        
    def should_make_request(self) -> bool:
        current_time = time.time()
        return (current_time - self.last_request_time) >= self.min_interval
    
    def get_cached_data(self):
        current_time = time.time()
        if self.cached_data and (current_time - self.cache_timestamp) < self.cache_duration:
            return self.cached_data
        return None
    
    def update_cache(self, data):
        self.cached_data = data
        self.cache_timestamp = time.time()
        self.last_request_time = time.time()

firebase_admin = None
firebase_messaging = None

async def init_firebase():
    global firebase_admin, firebase_messaging
    
    if not FIREBASE_CREDENTIALS:
        print("FIREBASE_CREDENTIALS 환경변수가 설정되지 않았습니다")
        print(".env 파일에 FIREBASE_CREDENTIALS=./firebase_key.json 추가하세요")
        return False
    
    if not os.path.exists(FIREBASE_CREDENTIALS):
        print(f"Firebase 키 파일을 찾을 수 없습니다: {FIREBASE_CREDENTIALS}")
        print("Firebase Console에서 서비스 계정 키를 다운로드하세요")
        return False
    
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
        
        try:
            existing_app = firebase_admin.get_app()
            firebase_admin.delete_app(existing_app)
            print("기존 Firebase 앱 삭제됨")
        except ValueError:
            pass
        
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        app = firebase_admin.initialize_app(cred)
        firebase_messaging = messaging
        
        with open(FIREBASE_CREDENTIALS, 'r') as f:
            data = json.load(f)
        
        print("Firebase 초기화 성공")
        print(f"프로젝트 ID: {data.get('project_id', 'Unknown')}")
        print(f"클라이언트 이메일: {data.get('client_email', 'Unknown')}")
        
        return True
        
    except Exception as e:
        print(f"Firebase 초기화 실패: {e}")
        print("다음을 확인하세요:")
        print("1. firebase_key.json 파일이 유효한지")
        print("2. Firebase 프로젝트가 활성화되어 있는지")
        print("3. 서비스 계정에 적절한 권한이 있는지")
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    firebase_initialized = await init_firebase()
    
    if firebase_initialized:
        print("Firebase 사용 가능")
    else:
        print("Firebase 사용 불가 - FCM 기능 제한됨")
    
    await check_ner_server()
    
    polling_task = asyncio.create_task(start_optimized_polling())
    
    yield
    
    polling_task.cancel()

app = FastAPI(title="실종자 요청 처리 시스템", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()
api_manager = OptimizedAPIManager()

SAFE_URL = "https://www.safe182.go.kr/api/lcm/amberList.do"
KAKAO_GEO = "https://dapi.kakao.com/v2/local/search/address.json"
ITS_CCTV_URL = "https://www.its.go.kr/opendata/bizdata/safdriveInfoSvc"

async def check_ner_server():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{NER_SERVER_URL}/api/health")
            if response.status_code == 200:
                print("NER 서버 연결 확인됨")
                return True
    except Exception as e:
        print(f"NER 서버 연결 실패: {e}")
        print("ner_server.py를 먼저 실행해주세요")
    return False

async def init_database():
    conn = sqlite3.connect('missing_persons.db')
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(missing_persons)")
    columns = [column[1] for column in cursor.fetchall()]
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS missing_persons (
            id TEXT PRIMARY KEY,
            name TEXT,
            age INTEGER,
            gender TEXT,
            location TEXT,
            description TEXT,
            photo_url TEXT,
            photo_base64 TEXT,
            priority TEXT,
            risk_factors TEXT,
            ner_entities TEXT,
            extracted_features TEXT,
            lat REAL,
            lng REAL,
            created_at TEXT,
            status TEXT DEFAULT 'ACTIVE',
            category TEXT
        )
    ''')
    
    try:
        if 'photo_base64' not in columns:
            cursor.execute('ALTER TABLE missing_persons ADD COLUMN photo_base64 TEXT')
            print("photo_base64 컬럼이 추가되었습니다.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("photo_base64 컬럼이 이미 존재합니다.")
        else:
            raise e
    
    try:
        if 'extracted_features' not in columns:
            cursor.execute('ALTER TABLE missing_persons ADD COLUMN extracted_features TEXT')
            print("extracted_features 컬럼이 추가되었습니다.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("extracted_features 컬럼이 이미 존재합니다.")
        else:
            raise e
    
    try:
        if 'category' not in columns:
            cursor.execute('ALTER TABLE missing_persons ADD COLUMN category TEXT')
            print("category 컬럼이 추가되었습니다.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("category 컬럼이 이미 존재합니다.")
        else:
            raise e
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_time TEXT,
            result_count INTEGER,
            success INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fcm_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE,
            user_id TEXT,
            platform TEXT,
            registered_at TEXT,
            is_test INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id TEXT,
            sent_at TEXT,
            target_count INTEGER,
            success_count INTEGER,
            error_message TEXT,
            FOREIGN KEY (person_id) REFERENCES missing_persons (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sighting_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id TEXT,
            reporter_lat REAL,
            reporter_lng REAL,
            reported_at TEXT,
            status TEXT DEFAULT 'PENDING'
        )
    ''')
    
    conn.commit()
    conn.close()
    print("데이터베이스 초기화 및 마이그레이션이 완료되었습니다.")

async def fetch_safe182_data():
    cached = api_manager.get_cached_data()
    if cached:
        print("캐시된 데이터 사용")
        return cached
    
    if not api_manager.should_make_request():
        print("API 요청 제한으로 대기 중")
        return []
    
    async with httpx.AsyncClient() as client:
        form = {
            "esntlId": SAFE182_ESNTL_ID,
            "authKey": SAFE182_AUTH_KEY,
            "rowSize": "20",
            "page": "1",
            "occrde": time.strftime("%Y%m%d"),
        }
        
        try:
            print(f"Safe182 API 요청 ({time.strftime('%H:%M:%S')})")
            print(f"요청 파라미터: rowSize={form['rowSize']}, page={form['page']}, occrde={form['occrde']}")
            
            response = await client.post(SAFE_URL, data=form, timeout=30.0)
            
            if response.status_code != 200:
                print(f"API 응답 오류: {response.status_code}")
                return []
            
            data = response.json()
            result = data.get("list", [])
            
            photo_stats = {"total": len(result), "has_photo": 0, "photo_lengths": []}
            for item in result:
                photo = item.get("tknphotoFile", "")
                if photo:
                    photo_stats["has_photo"] += 1
                    photo_stats["photo_lengths"].append(len(photo))
            
            print(f"API 응답: {len(result)}개 항목")
            print(f"사진 포함: {photo_stats['has_photo']}/{photo_stats['total']}개")
            if photo_stats["photo_lengths"]:
                avg_length = sum(photo_stats["photo_lengths"]) / len(photo_stats["photo_lengths"])
                max_length = max(photo_stats["photo_lengths"])
                min_length = min(photo_stats["photo_lengths"])
                print(f"사진 길이: 평균 {avg_length:.0f}, 최대 {max_length}, 최소 {min_length}")
            
            api_manager.update_cache(result)
            await log_api_request(len(result), True)
            
            return result
            
        except Exception as e:
            print(f"Safe182 API 오류: {e}")
            await log_api_request(0, False)
            return []

async def send_to_ner_server(raw_data_list: List[dict]):
    try:
        print(f"NER 서버로 {len(raw_data_list)}개 데이터 전송 중...")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{NER_SERVER_URL}/api/process_missing_persons",
                json={"raw_data_list": raw_data_list}
            )
            
            if response.status_code == 200:
                processed_data = response.json()
                print(f"NER 서버에서 {len(processed_data)}개 데이터 처리 완료")
                return processed_data
            else:
                print(f"NER 서버 응답 오류: {response.status_code}")
                return []
                
    except Exception as e:
        print(f"NER 서버 연결 오류: {e}")
        return []

async def fetch_cctv_data(lat: float, lng: float, radius: int = 1000):
    if not ITS_CCTV_API_KEY:
        print("ITS CCTV API 키가 설정되지 않았습니다")
        return []
    
    async with httpx.AsyncClient() as client:
        params = {
            "apiKey": ITS_CCTV_API_KEY,
            "type": "도로유형",
            "cctvType": "실시간스트리밍",
            "minX": lng - 0.01,
            "maxX": lng + 0.01,
            "minY": lat - 0.01,
            "maxY": lat + 0.01,
            "getType": "json"
        }
        
        try:
            print(f"ITS CCTV API 요청: lat={lat}, lng={lng}, radius={radius}")
            response = await client.get(ITS_CCTV_URL, params=params, timeout=30.0)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
            else:
                print(f"CCTV API 오류: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"CCTV API 요청 실패: {e}")
            return []

async def log_api_request(result_count: int, success: bool):
    conn = sqlite3.connect('missing_persons.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO api_requests (request_time, result_count, success)
        VALUES (?, ?, ?)
    ''', (datetime.now().isoformat(), result_count, 1 if success else 0))
    conn.commit()
    conn.close()

async def geocode_address(address: str):
    if not address:
        return {"lat": 36.5, "lng": 127.8}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                KAKAO_GEO,
                params={"query": address},
                headers={"Authorization": f"KakaoAK {KAKAO_JAVASCRIPT_KEY}"},
                timeout=10.0
            )
            data = response.json()
            documents = data.get("documents", [])
            if documents:
                doc = documents[0]
                return {"lat": float(doc["y"]), "lng": float(doc["x"])}
        except Exception as e:
            print(f"지오코딩 오류: {e}")
    
    return {"lat": 36.5, "lng": 127.8}

def save_missing_person(person: MissingPerson):
    conn = sqlite3.connect('missing_persons.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO missing_persons 
        (id, name, age, gender, location, description, photo_url, photo_base64, priority, 
         risk_factors, ner_entities, extracted_features, lat, lng, created_at, status, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        person.id, person.name, person.age, person.gender, person.location,
        person.description, person.photo_url, person.photo_base64, person.priority,
        json.dumps(person.risk_factors, ensure_ascii=False),
        json.dumps(person.ner_entities, ensure_ascii=False),
        json.dumps(person.extracted_features, ensure_ascii=False),
        person.lat, person.lng, person.created_at, person.status, person.category
    ))
    
    conn.commit()
    conn.close()

def get_existing_person_ids():
    conn = sqlite3.connect('missing_persons.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM missing_persons WHERE status = "ACTIVE"')
    ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    return ids

async def get_active_tokens():
    conn = sqlite3.connect('missing_persons.db')
    cursor = conn.cursor()
    cursor.execute('SELECT token FROM fcm_tokens WHERE active = 1 AND is_test = 0')
    tokens = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tokens

async def send_fcm_notification(person: MissingPerson, tokens: List[str] = None):
    if not firebase_admin or not firebase_messaging:
        print("Firebase가 초기화되지 않아 알림을 보낼 수 없습니다")
        return {"success": 0, "total": 0, "error": "Firebase not initialized"}
    
    if not tokens:
        tokens = await get_active_tokens()
        if not tokens:
            print("실제 FCM 토큰이 없어서 시뮬레이션합니다")
            return {"success": 1, "total": 1, "simulation": True}
    
    try:
        success_count = 0
        errors = []
        
        for i, token in enumerate(tokens):
            try:
                message = firebase_messaging.Message(
                    notification=firebase_messaging.Notification(
                        title=f"실종자 발생: {person.name or '이름 미상'}",
                        body=f"{person.age or '나이 미상'}세, {person.location or '위치 미상'}"
                    ),
                    data={
                        "person_id": person.id,
                        "name": person.name or "",
                        "age": str(person.age or 0),
                        "location": person.location or "",
                        "priority": person.priority,
                        "category": person.category or "",
                        "risk_factors": json.dumps(person.risk_factors, ensure_ascii=False),
                        "lat": str(person.lat),
                        "lng": str(person.lng),
                        "photo_url": person.photo_url or ""
                    },
                    android=firebase_messaging.AndroidConfig(
                        notification=firebase_messaging.AndroidNotification(
                            icon="ic_notification",
                            color="#FF3B30" if person.priority == "HIGH" else "#FF9500",
                            sound="default",
                            channel_id="missing_person_alerts"
                        ),
                        priority="high"
                    ),
                    apns=firebase_messaging.APNSConfig(
                        payload=firebase_messaging.APNSPayload(
                            aps=firebase_messaging.Aps(
                                sound="default",
                                badge=1,
                                alert=firebase_messaging.ApsAlert(
                                    title=f"실종자 발생: {person.name or '이름 미상'}",
                                    body=f"{person.age or '나이 미상'}세, {person.location or '위치 미상'}"
                                )
                            )
                        )
                    ),
                    token=token
                )
                
                response = firebase_messaging.send(message)
                success_count += 1
                print(f"FCM 메시지 전송 성공: {response}")
                
            except Exception as e:
                error_msg = f"Token {i}: {str(e)}"
                errors.append(error_msg)
                print(f"FCM 메시지 전송 실패: {e}")
        
        conn = sqlite3.connect('missing_persons.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO notifications (person_id, sent_at, target_count, success_count, error_message)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            person.id, 
            datetime.now().isoformat(), 
            len(tokens), 
            success_count,
            json.dumps(errors) if errors else None
        ))
        conn.commit()
        conn.close()
        
        result = {
            "success": success_count,
            "total": len(tokens),
            "errors": errors if errors else None
        }
        
        print(f"FCM 알림 전송 결과: {success_count}/{len(tokens)}")
        return result
        
    except Exception as e:
        print(f"FCM 전송 중 오류: {e}")
        return {"success": 0, "total": len(tokens) if tokens else 0, "error": str(e)}

async def start_optimized_polling():
    existing_ids = get_existing_person_ids()
    
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 실종자 데이터 확인 중...")
            
            raw_data_list = await fetch_safe182_data()
            
            if not raw_data_list:
                print("Safe182 API에서 데이터를 가져오지 못했습니다.")
                await asyncio.sleep(300)
                continue
            
            processed_data = await send_to_ner_server(raw_data_list)
            
            if not processed_data:
                print("NER 서버에서 데이터 처리에 실패했습니다.")
                await asyncio.sleep(300)
                continue
            
            new_persons = []
            
            for person_data in processed_data:
                person = MissingPerson(**person_data)
                
                if person.id not in existing_ids:
                    coord = await geocode_address(person.location)
                    person.lat = coord["lat"]
                    person.lng = coord["lng"]
                    
                    save_missing_person(person)
                    new_persons.append(person)
                    existing_ids.add(person.id)
            
            if new_persons:
                print(f"새로운 실종자 {len(new_persons)}명 발견")
                
                for person in new_persons:
                    fcm_result = await send_fcm_notification(person)
                    
                    await manager.broadcast({
                        "type": "new_missing_person",
                        "data": person.dict(),
                        "fcm_result": fcm_result
                    })
            else:
                print("새로운 실종자 없음")
            
            await asyncio.sleep(300)
            
        except Exception as e:
            print(f"폴링 오류: {e}")
            await asyncio.sleep(600)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/register_token")
async def register_token(request: TokenRegistration):
    try:
        conn = sqlite3.connect('missing_persons.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO fcm_tokens (user_id, token, platform, registered_at, is_test)
            VALUES (?, ?, ?, ?, ?)
        ''', (request.user_id, request.token, request.platform, datetime.now().isoformat(), 0))
        
        conn.commit()
        conn.close()
        
        print(f"토큰 등록 성공: {request.user_id} ({request.platform})")
        return {"status": "success", "message": "토큰이 등록되었습니다"}
        
    except Exception as e:
        print(f"토큰 등록 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/register_test_token")
async def register_test_token():
    test_token = f"test_token_{int(time.time())}"
    
    conn = sqlite3.connect('missing_persons.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO fcm_tokens (token, user_id, platform, registered_at, is_test)
        VALUES (?, ?, ?, ?, ?)
    ''', (test_token, "test_user", "web", datetime.now().isoformat(), 1))
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "test_token": test_token}

@app.get("/api/test_tokens")
async def get_test_tokens():
    conn = sqlite3.connect('missing_persons.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT token, registered_at FROM fcm_tokens WHERE is_test = 1 ORDER BY registered_at DESC LIMIT 10')
    tokens = [{"token": row[0], "registered_at": row[1]} for row in cursor.fetchall()]
    
    conn.close()
    return {"tokens": tokens}

@app.post("/api/search_cctv")
async def search_cctv(request: CCTVRequest):
    try:
        cctv_data = await fetch_cctv_data(request.lat, request.lng, request.radius)
        
        processed_cctvs = []
        for cctv in cctv_data:
            processed_cctv = {
                "id": cctv.get("roadsectionid", f"cctv_{len(processed_cctvs)}"),
                "name": cctv.get("cctvname", "CCTV"),
                "address": f"{cctv.get('coordy', '')}, {cctv.get('coordx', '')}",
                "distance": 0,
                "status": "정상" if cctv.get("cctvresolution") else "점검중",
                "type": cctv.get("cctvtype", "교통감시"),
                "operator": "한국도로공사",
                "streamUrl": cctv.get("cctvurl", ""),
                "coords": {
                    "lat": float(cctv.get("coordy", 0)),
                    "lng": float(cctv.get("coordx", 0))
                },
                "resolution": cctv.get("cctvresolution", ""),
                "format": cctv.get("cctvformat", "")
            }
            processed_cctvs.append(processed_cctv)
        
        return {"cctvs": processed_cctvs, "count": len(processed_cctvs)}
        
    except Exception as e:
        print(f"CCTV 검색 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/report_sighting")
async def report_sighting(request: SightingReport):
    try:
        conn = sqlite3.connect('missing_persons.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO sighting_reports (person_id, reporter_lat, reporter_lng, reported_at)
            VALUES (?, ?, ?, ?)
        ''', (
            request.person_id,
            request.reporter_location['lat'],
            request.reporter_location['lng'],
            request.timestamp
        ))
        
        conn.commit()
        conn.close()
        
        await manager.broadcast({
            "type": "sighting_reported",
            "data": {
                "person_id": request.person_id,
                "location": request.reporter_location,
                "timestamp": request.timestamp
            }
        })
        
        print(f"발견 신고 접수: {request.person_id}")
        return {"status": "success", "message": "신고가 접수되었습니다"}
        
    except Exception as e:
        print(f"신고 접수 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/missing_persons")
async def get_missing_persons():
    conn = sqlite3.connect('missing_persons.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM missing_persons 
        WHERE status = "ACTIVE" 
        ORDER BY created_at DESC 
        LIMIT 50
    ''')
    
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    
    persons = []
    for row in rows:
        person_dict = dict(zip(columns, row))
        
        person_dict['risk_factors'] = json.loads(person_dict.get('risk_factors') or '[]')
        person_dict['ner_entities'] = json.loads(person_dict.get('ner_entities') or '{}')
        
        if 'extracted_features' in person_dict:
            person_dict['extracted_features'] = json.loads(person_dict.get('extracted_features') or '{}')
        else:
            person_dict['extracted_features'] = {}
        
        if 'category' not in person_dict:
            person_dict['category'] = '기타'
        
        if 'photo_base64' not in person_dict:
            person_dict['photo_base64'] = None
            
        persons.append(person_dict)
    
    conn.close()
    return {"data": persons, "count": len(persons)}

@app.get("/api/person/{person_id}")
async def get_person_detail(person_id: str):
    conn = sqlite3.connect('missing_persons.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM missing_persons WHERE id = ?', (person_id,))
    row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="실종자를 찾을 수 없습니다")
    
    columns = [desc[0] for desc in cursor.description]
    person_dict = dict(zip(columns, row))
    
    person_dict['risk_factors'] = json.loads(person_dict.get('risk_factors') or '[]')
    person_dict['ner_entities'] = json.loads(person_dict.get('ner_entities') or '{}')
    
    if 'extracted_features' in person_dict:
        person_dict['extracted_features'] = json.loads(person_dict.get('extracted_features') or '{}')
    else:
        person_dict['extracted_features'] = {}
    
    if 'category' not in person_dict:
        person_dict['category'] = '기타'
    
    if 'photo_base64' not in person_dict:
        person_dict['photo_base64'] = None
    
    conn.close()
    return person_dict

@app.get("/api/statistics")
async def get_statistics():
    conn = sqlite3.connect('missing_persons.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM missing_persons WHERE status = "ACTIVE"')
    total_active = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM missing_persons WHERE priority = "HIGH" AND status = "ACTIVE"')
    high_priority = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM api_requests WHERE DATE(request_time) = DATE("now")')
    today_requests = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM api_requests WHERE success = 1 AND DATE(request_time) = DATE("now")')
    today_success = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM notifications WHERE DATE(sent_at) = DATE("now")')
    today_notifications = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(success_count) FROM notifications WHERE DATE(sent_at) = DATE("now")')
    today_fcm_success = cursor.fetchone()[0] or 0
    
    next_request_time = api_manager.last_request_time + api_manager.min_interval
    time_until_next = max(0, int(next_request_time - time.time()))
    
    conn.close()
    
    return {
        "total_active": total_active,
        "high_priority": high_priority,
        "today_requests": today_requests,
        "today_success": today_success,
        "today_notifications": today_notifications,
        "today_fcm_success": today_fcm_success,
        "firebase_status": "활성" if firebase_admin else "비활성",
        "ner_server_status": "활성",
        "next_request_in_seconds": time_until_next,
        "api_limit_status": f"{today_requests}/288 (일일 제한 내)"
    }

@app.post("/api/send_notification")
async def send_notification(request: NotificationRequest):
    try:
        result = await send_fcm_notification(request.person, request.target_tokens)
        
        await manager.broadcast({
            "type": "manual_notification_sent",
            "data": {
                "person": request.person.dict(),
                "result": result,
                "test_mode": request.test_mode
            }
        })
        
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/active_tokens")
async def get_active_tokens_api():
    try:
        tokens = await get_active_tokens()
        return {"tokens": tokens, "count": len(tokens)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/force_update")
async def force_update():
    try:
        print("수동 업데이트 요청")
        
        raw_data_list = await fetch_safe182_data()
        if not raw_data_list:
            return {"status": "error", "message": "Safe182 API에서 데이터를 가져올 수 없습니다"}
        
        processed_data = await send_to_ner_server(raw_data_list)
        if not processed_data:
            return {"status": "error", "message": "NER 서버에서 데이터 처리에 실패했습니다"}
        
        existing_ids = get_existing_person_ids()
        new_count = 0
        updated_count = 0
        
        for person_data in processed_data:
            person = MissingPerson(**person_data)
            
            coord = await geocode_address(person.location)
            person.lat = coord["lat"]
            person.lng = coord["lng"]
            
            if person.id not in existing_ids:
                new_count += 1
            else:
                updated_count += 1
            
            save_missing_person(person)
        
        return {
            "status": "success", 
            "message": f"업데이트 완료: 신규 {new_count}명, 갱신 {updated_count}명",
            "new": new_count,
            "updated": updated_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"업데이트 실패: {str(e)}")

@app.get("/")
async def get_admin_dashboard():
    if not KAKAO_JAVASCRIPT_KEY:
        print("경고: KAKAO_JAVASCRIPT_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        kakao_key = "YOUR_KAKAO_API_KEY"
    else:
        kakao_key = KAKAO_JAVASCRIPT_KEY
    
    try:
        with open("dashboard.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        
        html_content = html_content.replace("YOUR_KAKAO_API_KEY", kakao_key)
        
        return HTMLResponse(html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="dashboard.html 파일을 찾을 수 없습니다")

if __name__ == "__main__":
    import uvicorn
    print("실종자 요청 처리 서버를 시작합니다 (포트 8001)")
    print("먼저 ner_server.py (포트 8000)가 실행되어 있는지 확인하세요")
    print(f"카카오 JavaScript 키 설정 상태: {'설정됨' if KAKAO_JAVASCRIPT_KEY else '미설정'}")
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)