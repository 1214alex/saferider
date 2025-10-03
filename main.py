import os, asyncio, time, json, re
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
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
import numpy as np

load_dotenv()
SAFE182_ESNTL_ID = os.getenv("SAFE182_ESNTL_ID", "")
SAFE182_AUTH_KEY = os.getenv("SAFE182_AUTH_KEY", "")
KAKAO_REST_KEY = os.getenv("KAKAO_REST_KEY", "")
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS", "")

class MissingPerson(BaseModel):
    id: str
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None
    priority: str = "MEDIUM"
    risk_factors: List[str] = []
    ner_entities: Dict[str, List[str]] = {}
    lat: float = 36.5
    lng: float = 127.8
    created_at: str = ""
    status: str = "ACTIVE"

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

class KPFBertNER:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.labels = [
            'O',
            'B-TMM_DISEASE', 'I-TMM_DISEASE',
            'B-TMM_DRUG', 'I-TMM_DRUG',
            'B-CV_CLOTHING', 'I-CV_CLOTHING',
            'B-TM_COLOR', 'I-TM_COLOR',
            'B-QT_AGE', 'I-QT_AGE',
            'B-LCP_CITY', 'I-LCP_CITY',
            'B-LCP_COUNTY', 'I-LCP_COUNTY',
            'B-AF_TRANSPORT', 'I-AF_TRANSPORT',
        ]
        self.label2id = {label: i for i, label in enumerate(self.labels)}
        self.id2label = {i: label for label, i in self.label2id.items()}
        self.load_model()
    
    def load_model(self):
        try:
            model_name = "klue/bert-base"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForTokenClassification.from_pretrained(
                model_name, 
                num_labels=len(self.labels)
            )
            print("KPF-BERT-NER 모델 로드 완료")
        except Exception as e:
            print(f"모델 로드 실패, 백업 키워드 방식 사용: {e}")
            self.model = None
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        if not text or not self.model:
            return self._fallback_keyword_extraction(text)
        
        try:
            inputs = self.tokenizer(
                text, 
                truncation=True, 
                padding=True, 
                return_tensors="pt",
                max_length=512
            )
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                predictions = torch.argmax(outputs.logits, dim=-1)
            
            tokens = self.tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
            predictions = predictions[0].tolist()
            
            entities = self._parse_bio_tags(tokens, predictions, text)
            return entities
            
        except Exception as e:
            print(f"NER 처리 오류: {e}")
            return self._fallback_keyword_extraction(text)
    
    def _parse_bio_tags(self, tokens: List[str], predictions: List[int], original_text: str) -> Dict[str, List[str]]:
        entities = {
            "diseases": [],
            "drugs": [],
            "clothing": [],
            "colors": [],
            "ages": [],
            "locations": [],
            "transport": []
        }
        
        current_entity = None
        current_text = []
        
        for token, pred_id in zip(tokens, predictions):
            if token.startswith('##'):
                continue
            
            label = self.id2label[pred_id]
            
            if label.startswith('B-'):
                if current_entity:
                    self._add_entity(entities, current_entity, ' '.join(current_text))
                
                current_entity = label[2:]
                current_text = [token]
                
            elif label.startswith('I-') and current_entity == label[2:]:
                current_text.append(token)
                
            else:
                if current_entity:
                    self._add_entity(entities, current_entity, ' '.join(current_text))
                current_entity = None
                current_text = []
        
        if current_entity:
            self._add_entity(entities, current_entity, ' '.join(current_text))
        
        return {k: list(set(v)) for k, v in entities.items() if v}
    
    def _add_entity(self, entities: dict, entity_type: str, text: str):
        text = text.replace('▁', '').strip()
        if not text:
            return
            
        mapping = {
            'TMM_DISEASE': 'diseases',
            'TMM_DRUG': 'drugs',
            'CV_CLOTHING': 'clothing',
            'TM_COLOR': 'colors',
            'QT_AGE': 'ages',
            'LCP_CITY': 'locations',
            'LCP_COUNTY': 'locations',
            'AF_TRANSPORT': 'transport'
        }
        
        key = mapping.get(entity_type)
        if key and text not in entities[key]:
            entities[key].append(text)
    
    def _fallback_keyword_extraction(self, text: str) -> Dict[str, List[str]]:
        if not text:
            return {}
        
        text = text.lower()
        entities = {
            "diseases": [],
            "drugs": [],
            "clothing": [],
            "colors": [],
            "locations": [],
            "transport": []
        }
        
        keywords = {
            "diseases": ["치매", "알츠하이머", "파킨슨", "우울증", "조현병"],
            "drugs": ["약", "복용", "투약", "의약품"],
            "clothing": ["상의", "하의", "바지", "치마", "셔츠", "티셔츠", "모자"],
            "colors": ["빨간", "파란", "노란", "검은", "흰", "회색"],
            "locations": ["서울", "부산", "대구", "인천", "광주", "대전", "울산"],
            "transport": ["휠체어", "지팡이", "보행기", "택시", "버스"]
        }
        
        for category, keyword_list in keywords.items():
            for keyword in keyword_list:
                if keyword in text:
                    entities[category].append(keyword)
        
        return {k: list(set(v)) for k, v in entities.items() if v}
    
    def extract_risk_factors(self, text: str, age: Optional[int] = None) -> List[str]:
        risk_factors = []
        
        if age:
            if age >= 80:
                risk_factors.append("고령자(80세 이상)")
            elif age >= 65:
                risk_factors.append("고령자(65세 이상)")
            elif age <= 10:
                risk_factors.append("어린이(10세 이하)")
            elif age <= 15:
                risk_factors.append("청소년(15세 이하)")
        
        entities = self.extract_entities(text)
        
        if entities.get("diseases"):
            for disease in entities["diseases"]:
                if any(d in disease for d in ["치매", "알츠하이머"]):
                    risk_factors.append("치매 관련 질환")
                elif any(d in disease for d in ["우울증", "조현병"]):
                    risk_factors.append("정신건강 관련")
        
        if entities.get("transport"):
            for transport in entities["transport"]:
                if any(t in transport for t in ["휠체어", "보행기", "지팡이"]):
                    risk_factors.append("거동 불편")
        
        if entities.get("drugs"):
            risk_factors.append("투약 중")
        
        return list(set(risk_factors))

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
    
    polling_task = asyncio.create_task(start_optimized_polling())
    
    yield
    
    polling_task.cancel()

app = FastAPI(title="최적화된 실시간 실종자 알림 시스템", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()
ner_model = KPFBertNER()
api_manager = OptimizedAPIManager()

SAFE_URL = "https://www.safe182.go.kr/api/lcm/amberList.do"
KAKAO_GEO = "https://dapi.kakao.com/v2/local/search/address.json"

async def init_database():
    conn = sqlite3.connect('missing_persons.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS missing_persons (
            id TEXT PRIMARY KEY,
            name TEXT,
            age INTEGER,
            gender TEXT,
            location TEXT,
            description TEXT,
            photo_url TEXT,
            priority TEXT,
            risk_factors TEXT,
            ner_entities TEXT,
            lat REAL,
            lng REAL,
            created_at TEXT,
            status TEXT DEFAULT 'ACTIVE'
        )
    ''')
    
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
            "rowSize": "50",
            "page": "1",
            "occrde": time.strftime("%Y%m%d"),
        }
        
        try:
            print(f"Safe182 API 요청 ({time.strftime('%H:%M:%S')})")
            response = await client.post(SAFE_URL, data=form, timeout=30.0)
            data = response.json()
            result = data.get("list", [])
            
            api_manager.update_cache(result)
            await log_api_request(len(result), True)
            
            print(f"API 응답: {len(result)}개 항목")
            return result
            
        except Exception as e:
            print(f"Safe182 API 오류: {e}")
            await log_api_request(0, False)
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
                headers={"Authorization": f"KakaoAK {KAKAO_REST_KEY}"},
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

def process_missing_person(raw_data: dict) -> MissingPerson:
    description = raw_data.get("etcSpfeatr", "")
    
    age = None
    try:
        age_value = raw_data.get("ageNow") or raw_data.get("age")
        if age_value:
            age = int(age_value)
    except (ValueError, TypeError):
        pass
    
    ner_entities = ner_model.extract_entities(description)
    risk_factors = ner_model.extract_risk_factors(description, age)
    
    priority = "HIGH" if any([
        age and (age >= 80 or age <= 10),
        "치매 관련 질환" in risk_factors,
        "정신건강 관련" in risk_factors,
        "거동 불편" in risk_factors
    ]) else "MEDIUM"
    
    return MissingPerson(
        id=str(raw_data.get("msspsnIdntfccd", f"temp_{int(time.time())}")),
        name=raw_data.get("nm"),
        age=age,
        gender=raw_data.get("sexdstnDscd"),
        location=raw_data.get("occrAdres"),
        description=description,
        photo_url=None,
        priority=priority,
        risk_factors=risk_factors,
        ner_entities=ner_entities,
        created_at=datetime.now().isoformat()
    )

def save_missing_person(person: MissingPerson):
    conn = sqlite3.connect('missing_persons.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO missing_persons 
        (id, name, age, gender, location, description, photo_url, priority, 
         risk_factors, ner_entities, lat, lng, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        person.id, person.name, person.age, person.gender, person.location,
        person.description, person.photo_url, person.priority,
        json.dumps(person.risk_factors, ensure_ascii=False),
        json.dumps(person.ner_entities, ensure_ascii=False),
        person.lat, person.lng, person.created_at, person.status
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
                        "risk_factors": json.dumps(person.risk_factors, ensure_ascii=False),
                        "lat": str(person.lat),
                        "lng": str(person.lng)
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
            new_persons = []
            
            for raw_data in raw_data_list:
                person = process_missing_person(raw_data)
                
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
        person_dict['risk_factors'] = json.loads(person_dict['risk_factors'] or '[]')
        person_dict['ner_entities'] = json.loads(person_dict['ner_entities'] or '{}')
        persons.append(person_dict)
    
    conn.close()
    return {"data": persons, "count": len(persons)}

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

@app.get("/")
async def get_admin_dashboard():
    return HTMLResponse(open("dashboard.html", "r", encoding="utf-8").read())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)