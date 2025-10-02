# main.py
import os, asyncio, time
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware
import httpx
from dotenv import load_dotenv

load_dotenv()
SAFE182_ESNTL_ID = os.getenv("SAFE182_ESNTL_ID", "")
SAFE182_AUTH_KEY = os.getenv("SAFE182_AUTH_KEY", "")
KAKAO_REST_KEY   = os.getenv("KAKAO_REST_KEY", "")

assert SAFE182_ESNTL_ID and SAFE182_AUTH_KEY and KAKAO_REST_KEY, "환경변수 누락"

# --------- 모델 ---------
class Person(BaseModel):
    id: str
    name: Optional[str] = None
    status: str = "missing"
    lat: float
    lng: float
    lastSeen: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    age: Optional[int] = None

class Req(BaseModel):
    date: Optional[str] = None     # YYYYMMDD
    rowSize: int = 30
    page:   int = 1

# --------- 앱 기본 ---------
app = FastAPI(title="Safe182 Proxy")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --------- 간단 LRU 캐시(주소→좌표) ---------
GEOCACHE: Dict[str, Any] = {}
GEOCACHE_ORDER: List[str] = []
GEOCACHE_MAX = 500
def cache_get(addr: str):
    v = GEOCACHE.get(addr)
    if v:
        GEOCACHE_ORDER.remove(addr)
        GEOCACHE_ORDER.append(addr)
    return v
def cache_set(addr: str, val: Any):
    if addr in GEOCACHE: GEOCACHE_ORDER.remove(addr)
    GEOCACHE[addr] = val
    GEOCACHE_ORDER.append(addr)
    if len(GEOCACHE_ORDER) > GEOCACHE_MAX:
        old = GEOCACHE_ORDER.pop(0)
        GEOCACHE.pop(old, None)

# --------- 외부 호출 ---------
SAFE_URL = "https://www.safe182.go.kr/api/lcm/amberList.do"
KAKAO_GEO = "https://dapi.kakao.com/v2/local/search/address.json"

async def fetch_safe182(client: httpx.AsyncClient, date:str, rowSize:int, page:int):
    form = {
        "esntlId": SAFE182_ESNTL_ID,
        "authKey": SAFE182_AUTH_KEY,
        "rowSize": str(rowSize),
        "page": str(page),
        "occrde": date,  # YYYYMMDD
        # 필요 시 추가 파라미터: "writngTrgetDscd": "1" 등
    }
    r = await client.post(SAFE_URL, data=form, timeout=20.0)
    # JSON/텍스트 둘 다 대비
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}

async def geocode(client: httpx.AsyncClient, addr:str):
    if not addr: return None
    hit = cache_get(addr)
    if hit is not None: return hit
    r = await client.get(KAKAO_GEO, params={"query": addr},
                         headers={"Authorization": f"KakaoAK {KAKAO_REST_KEY}"},
                         timeout=10.0)
    j = r.json()
    doc = (j.get("documents") or [None])[0]
    if not doc:
        cache_set(addr, None)
        return None
    lat, lng = float(doc["y"]), float(doc["x"])
    coord = {"lat": lat, "lng": lng}
    cache_set(addr, coord)
    return coord

class MissingResponse(BaseModel):
    total: int
    page: int
    rowSize: int
    people: List[Person]

# --------- 엔드포인트 ---------
@app.post("/api/missing", response_model=MissingResponse)
async def list_missing(req: Req = Body(...)):
    date = req.date or time.strftime("%Y%m%d")  # 오늘 기본
    async with httpx.AsyncClient() as client:
        data = await fetch_safe182(client, date, req.rowSize, req.page)
        items = data.get("list") if isinstance(data, dict) else []
        total = int(data.get("totalCount", len(items) if items else 0))
        if not isinstance(items, list):
            # XML 등 비정형 응답 방어
            return []

        # 주소 병렬 지오코딩
        tasks = []
        for it in items:
            addr = it.get("occrAdres")
            tasks.append(geocode(client, addr))
        coords = await asyncio.gather(*tasks, return_exceptions=False)

        people: List[Person] = []
        for i, it in enumerate(items):
            c = coords[i] or {"lat": 36.5, "lng": 127.8}  # 실패 시 한국 중심
            pid = str(it.get("wrterNo") or f"{date}-{req.page}-{i}")
            age = None
            try:
                age = int(it.get("age")) if it.get("age") not in (None, "") else None
            except Exception:
                pass
            people.append(Person(
                id=pid,
                name=it.get("nm"),
                status="missing",
                lat=c["lat"], lng=c["lng"],
                lastSeen=it.get("occrde"),
                address=it.get("occrAdres"),
                description=it.get("etcSpfeatr"),
                age=age
            ))
        return MissingResponse(
            total=total,
            page=req.page,
            rowSize=req.rowSize,
            people=people,
        )
