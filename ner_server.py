import os, json, re, time
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
import numpy as np

class RawDataList(BaseModel):
    raw_data_list: List[dict]

class ProcessedPerson(BaseModel):
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
            'B-PS_NAME', 'I-PS_NAME',
            'B-AF_BUILDING', 'I-AF_BUILDING',
            'B-TM_DIRECTION', 'I-TM_DIRECTION',
            'B-CV_OCCUPATION', 'I-CV_OCCUPATION',
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
            "transport": [],
            "names": [],
            "buildings": [],
            "directions": [],
            "occupations": []
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
            'AF_TRANSPORT': 'transport',
            'PS_NAME': 'names',
            'AF_BUILDING': 'buildings',
            'TM_DIRECTION': 'directions',
            'CV_OCCUPATION': 'occupations'
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
            "transport": [],
            "physical_features": [],
            "behaviors": [],
            "items": []
        }
        
        keywords = {
            "diseases": ["치매", "알츠하이머", "파킨슨", "우울증", "조현병", "정신", "뇌전증", "간질"],
            "drugs": ["약", "복용", "투약", "의약품", "처방", "치료"],
            "clothing": ["상의", "하의", "바지", "치마", "셔츠", "티셔츠", "모자", "신발", "양말", "속옷"],
            "colors": ["빨간", "파란", "노란", "검은", "흰", "회색", "갈색", "초록", "보라", "분홍"],
            "locations": ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"],
            "transport": ["휠체어", "지팡이", "보행기", "택시", "버스", "차량"],
            "physical_features": ["키", "몸무게", "체격", "머리", "얼굴", "눈", "코", "입", "귀", "목소리", "걸음", "보행"],
            "behaviors": ["배회", "혼잣말", "반복", "고집", "화", "우울", "불안", "떨림"],
            "items": ["지갑", "핸드폰", "카드", "현금", "가방", "안경", "시계", "반지", "목걸이"]
        }
        
        for category, keyword_list in keywords.items():
            for keyword in keyword_list:
                if keyword in text:
                    entities[category].append(keyword)
        
        return {k: list(set(v)) for k, v in entities.items() if v}
    
    def extract_detailed_features(self, text: str) -> Dict[str, List[str]]:
        features = {
            "physical": [],
            "clothing": [],
            "medical": [],
            "behavior": [],
            "items": [],
            "additional": []
        }
        
        if not text:
            return features
        
        medical_patterns = [
            r'(치매|알츠하이머|파킨슨|우울증|조현병|정신질환).*?(?:약|복용|치료|진료)',
            r'(약|의약품|처방약).*?복용',
            r'(병원|의원|클리닉).*?(?:다니|진료|치료)'
        ]
        
        for pattern in medical_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            features["medical"].extend([match if isinstance(match, str) else match[0] for match in matches])
        
        physical_patterns = [
            r'키.*?(\d+(?:\.\d+)?)\s*(?:cm|센티)',
            r'몸무게.*?(\d+(?:\.\d+)?)\s*(?:kg|킬로)',
            r'(허리.*?굽|등.*?굽|다리.*?절)',
            r'(걸음걸이|보행).*?(불편|어려움|힘들|굽)',
            r'(목소리|말).*?(어눌|부정확|불분명)'
        ]
        
        for pattern in physical_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            features["physical"].extend([match if isinstance(match, str) else ' '.join(match) for match in matches])
        
        clothing_patterns = [
            r'(상의|윗옷).*?([\w\s색]+)',
            r'(하의|바지|치마).*?([\w\s색]+)',
            r'(신발|운동화|구두).*?([\w\s색]+)',
            r'(모자|캡|안경).*?착용'
        ]
        
        for pattern in clothing_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            features["clothing"].extend([' '.join(match) if isinstance(match, tuple) else match for match in matches])
        
        behavior_patterns = [
            r'(혼자서|혼자).*?(다니|이동|외출)',
            r'(택시|버스|대중교통).*?(?:이용|타고)',
            r'(대화|말).*?(가능|불가능|어려움)',
            r'(기억|인지).*?(어려움|힘들|불가능)'
        ]
        
        for pattern in behavior_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            features["behavior"].extend([' '.join(match) if isinstance(match, tuple) else match for match in matches])
        
        items_patterns = [
            r'(현금|돈|지갑).*?(없음|소지|가져감|놓고)',
            r'(카드|복지카드|신용카드).*?(없음|소지|가져감|놓고)',
            r'(핸드폰|휴대폰|전화).*?(없음|소지|가져감|놓고)'
        ]
        
        for pattern in items_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            features["items"].extend([' '.join(match) if isinstance(match, tuple) else match for match in matches])
        
        additional_patterns = [
            r'평상시.*?([\w\s]+)',
            r'주로.*?([\w\s]+)',
            r'자주.*?([\w\s]+)'
        ]
        
        for pattern in additional_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            features["additional"].extend(matches)
        
        return {k: list(set(v)) for k, v in features.items() if v}
    
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
        
        if text and any(keyword in text.lower() for keyword in ["혼자", "독거", "홀로"]):
            risk_factors.append("독거 생활")
        
        if text and any(keyword in text.lower() for keyword in ["배회", "길잃음", "방향감각"]):
            risk_factors.append("배회 위험")
        
        return list(set(risk_factors))

    def determine_category(self, text: str, age: Optional[int] = None, gender: Optional[str] = None) -> str:
        if not text:
            text = ""
        
        text_lower = text.lower()
        
        if age:
            if age <= 8:
                return "미취학아동"
            elif age <= 18:
                return "학령기아동"
            elif age >= 65:
                if any(keyword in text_lower for keyword in ["치매", "알츠하이머", "기억", "인지"]):
                    return "치매환자"
        
        if any(keyword in text_lower for keyword in ["지적장애", "발달장애", "정신지체"]):
            return "지적장애인"
        
        if any(keyword in text_lower for keyword in ["자폐", "아스퍼거", "자폐스펙트럼"]):
            return "자폐장애인"
        
        if any(keyword in text_lower for keyword in ["정신질환", "조현병", "우울증", "정신병"]):
            return "정신장애인"
        
        if age and age >= 19:
            if any(keyword in text_lower for keyword in ["가출", "실종신고", "연락두절", "의도적"]):
                return "성인가출"
        
        return "기타"

def process_base64_image(base64_string: str) -> str:
    if not base64_string:
        return None
    
    try:
        if base64_string.startswith('data:'):
            return base64_string
        
        return f"data:image/jpeg;base64,{base64_string}"
    except Exception as e:
        print(f"이미지 처리 오류: {e}")
        return None

def process_missing_person(raw_data: dict, ner_model: KPFBertNER) -> ProcessedPerson:
    description = raw_data.get("etcSpfeatr", "") or ""
    photo_base64 = raw_data.get("tknphotoFile", "") or ""
    
    name = raw_data.get('nm', '이름없음')
    print(f"NER 서버에서 처리 중: {name}")
    
    age = None
    try:
        age_value = raw_data.get("ageNow") or raw_data.get("age")
        if age_value:
            age = int(age_value)
    except (ValueError, TypeError):
        pass
    
    gender = raw_data.get("sexdstnDscd", "")
    
    ner_entities = ner_model.extract_entities(description) if description else {}
    extracted_features = ner_model.extract_detailed_features(description) if description else {}
    risk_factors = ner_model.extract_risk_factors(description, age)
    
    priority = "MEDIUM"
    
    if age:
        if age <= 8 or age >= 80:
            priority = "HIGH"
        elif age >= 65 and description and any(keyword in description.lower() for keyword in ["치매", "알츠하이머", "기억", "인지", "배회"]):
            priority = "HIGH"
        elif any(factor in risk_factors for factor in ["치매 관련 질환", "정신건강 관련", "거동 불편"]):
            priority = "HIGH"
    
    category = "기타"
    
    if age:
        if age <= 8:
            category = "미취학아동"
        elif age <= 18:
            category = "학령기아동"
        elif age >= 65:
            if description and any(keyword in description.lower() for keyword in ["치매", "알츠하이머", "기억", "인지", "배회"]):
                category = "치매환자"
            else:
                category = "고령자"
        elif age >= 19:
            category = "성인가출"
    
    if description:
        text_lower = description.lower()
        
        if any(keyword in text_lower for keyword in ["지적장애", "발달장애", "정신지체"]):
            category = "지적장애인"
        elif any(keyword in text_lower for keyword in ["자폐", "아스퍼거", "자폐스펙트럼"]):
            category = "자폐장애인"
        elif any(keyword in text_lower for keyword in ["정신질환", "조현병", "우울증", "정신병"]):
            category = "정신장애인"
        elif any(keyword in text_lower for keyword in ["치매", "알츠하이머", "기억", "인지", "배회"]):
            category = "치매환자"
    
    if category == "치매환자":
        priority = "HIGH"
    
    if age:
        if age <= 8:
            risk_factors.append("미취학 아동")
        elif age <= 18:
            risk_factors.append("학령기 아동")
        elif age >= 80:
            risk_factors.append("고령자(80세 이상)")
        elif age >= 65:
            risk_factors.append("고령자(65세 이상)")
    
    photo_url = None
    if photo_base64 and len(photo_base64) > 50:
        try:
            if photo_base64.startswith('data:'):
                photo_url = photo_base64
            elif photo_base64.startswith('/9j/'):
                photo_url = f"data:image/jpeg;base64,{photo_base64}"
            elif photo_base64.startswith('iVBORw0'):
                photo_url = f"data:image/png;base64,{photo_base64}"
            else:
                photo_url = f"data:image/jpeg;base64,{photo_base64}"
        except Exception as e:
            print(f"사진 처리 오류: {e}")
            photo_url = None
    
    return ProcessedPerson(
        id=str(raw_data.get("msspsnIdntfccd", f"temp_{int(time.time())}")),
        name=name,
        age=age,
        gender=gender,
        location=raw_data.get("occrAdres"),
        description=description,
        photo_url=photo_url,
        photo_base64=photo_base64,
        priority=priority,
        risk_factors=risk_factors,
        ner_entities=ner_entities,
        extracted_features=extracted_features,
        category=category,
        created_at=datetime.now().isoformat()
    )

app = FastAPI(title="NER 처리 서버")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ner_model = KPFBertNER()

@app.post("/api/process_missing_persons")
async def process_missing_persons_endpoint(request: RawDataList):
    try:
        print(f"NER 서버: {len(request.raw_data_list)}명의 실종자 데이터 처리 시작")
        
        processed_persons = []
        for raw_data in request.raw_data_list:
            processed_person = process_missing_person(raw_data, ner_model)
            processed_persons.append(processed_person.dict())
        
        print(f"NER 서버: {len(processed_persons)}명의 데이터 처리 완료")
        return processed_persons
        
    except Exception as e:
        print(f"NER 처리 오류: {e}")
        raise HTTPException(status_code=500, detail=f"NER 처리 실패: {str(e)}")

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": ner_model.model is not None,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/")
async def root():
    return {"message": "NER 처리 서버가 실행 중입니다", "port": 8000}

if __name__ == "__main__":
    import uvicorn
    print("NER 서버를 시작합니다 (포트 8000)")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)