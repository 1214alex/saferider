"""
Safe182 실종자 API 테스트 스크립트 (올바른 엔드포인트)
JSP 예제 코드를 Python으로 변환
"""

import requests
import json
from pprint import pprint
import re
from datetime import datetime
import os

class Safe182APITester:
    def __init__(self):
        # Safe182 실종자 API 엔드포인트 (JSP 코드에서 확인)
        self.api_url = "https://www.safe182.go.kr/api/lcm/amberList.do"
        self.esntl_id = os.getenv('POLICE_ESNTL_ID', '10000843')  # JSP 예제의 기본값
        self.auth_key = os.getenv('POLICE_AUTH_KEY', '5a44c53f2b0e45e6')  # JSP 예제의 기본값
        
        # JSP 코드에서 확인한 실종자 데이터 필드들
        self.field_mapping = {
            'nm': 'name',                    # 성명
            'age': 'age_at_time',           # 당시나이  
            'ageNow': 'current_age',        # 현재나이
            'sexdstnDscd': 'gender',        # 성별구분
            'occrAdres': 'location',        # 발생장소
            'occrde': 'occurrence_date',    # 발생일시
            'alldressingDscd': 'clothing',  # 착의사항
            'height': 'height',             # 키
            'bdwgh': 'weight',              # 몸무게
            'frmDscd': 'build',             # 체격
            'faceshpeDscd': 'face_shape',   # 얼굴형
            'hairshpeDscd': 'hair_style',   # 두발형태
            'haircolrDscd': 'hair_color',   # 두발색상
            'writngTrgetDscd': 'target_category',  # 대상구분
            'msspsnIdntfccd': 'person_id',  # 실종자식별코드
            'tknphotolength': 'photo_count' # 사진 개수
        }
        
    def test_safe182_api(self):
        """Safe182 API 테스트 (JSP 예제 기반)"""
        print("=" * 70)
        print("Safe182 실종자 API 테스트 (POST 방식)")
        print("=" * 70)
        
        if not self.esntl_id or not self.auth_key:
            print("API 키가 설정되지 않았습니다.")
            print("환경변수 POLICE_ESNTL_ID와 POLICE_AUTH_KEY를 설정하거나")
            print("JSP 예제의 기본값을 사용합니다.")
        
        # JSP 코드와 동일한 파라미터 구성
        params = {
            'esntlId': self.esntl_id,
            'authKey': self.auth_key,
            'rowSize': '10',
            'page': '1',
            'writngTrgetDscds': ['010', '060', '070'],  # 정상아동, 지적장애, 치매환자
            'sexdstnDscd': '',          # 성별구분 (빈값 = 전체)
            'nm': '',                   # 성명 (빈값 = 전체)
            'detailDate1': '',          # 시작일
            'detailDate2': '',          # 종료일
            'age1': '',                 # 시작나이
            'age2': '',                 # 종료나이
            'occrAdres': '',            # 발생장소
            'xmlUseYN': ''              # XML 사용여부
        }
        
        try:
            print(f"API 호출 중... URL: {self.api_url}")
            print(f"파라미터: {params}")
            
            # POST 방식으로 요청 (JSP 코드와 동일)
            response = requests.post(self.api_url, data=params, timeout=15)
            print(f"응답 상태 코드: {response.status_code}")
            print(f"응답 헤더: {response.headers.get('content-type', 'Unknown')}")
            
            if response.status_code == 200:
                try:
                    # JSON 응답 파싱
                    data = response.json()
                    print("\nJSON 파싱 성공")
                    self.analyze_safe182_response(data)
                    
                except json.JSONDecodeError as e:
                    print(f"JSON 파싱 실패: {e}")
                    print(f"응답 내용 (처음 500자): {response.text[:500]}")
                    
            elif response.status_code == 401:
                print("인증 실패 (401) - API 키 확인 필요")
                
            elif response.status_code == 403:
                print("접근 거부 (403) - 권한 부족")
                
            elif response.status_code == 404:
                print("API 엔드포인트를 찾을 수 없습니다 (404)")
                
            else:
                print(f"API 호출 실패: {response.status_code}")
                print(f"응답 내용: {response.text[:300]}")
                
        except requests.exceptions.Timeout:
            print("API 호출 시간 초과")
        except requests.exceptions.ConnectionError:
            print("네트워크 연결 오류")
        except Exception as e:
            print(f"예상치 못한 오류: {str(e)}")
    
    def analyze_safe182_response(self, data):
        """Safe182 API 응답 분석 (JSP 구조 기반)"""
        print("\nSafe182 API 응답 구조 분석:")
        print(f"응답 타입: {type(data)}")
        
        if isinstance(data, dict):
            print(f"최상위 키들: {list(data.keys())}")
            
            # JSP 코드에서 확인한 응답 구조
            result = data.get('result', 'N/A')
            msg = data.get('msg', 'N/A')
            total_count = data.get('totalCount', 0)
            missing_list = data.get('list', [])
            
            print(f"결과 코드: {result}")
            print(f"메시지: {msg}")
            print(f"전체 개수: {total_count}")
            print(f"실종자 목록 길이: {len(missing_list)}")
            
            if missing_list and len(missing_list) > 0:
                print(f"\n첫 번째 실종자 데이터 분석:")
                self.analyze_missing_person_data(missing_list[0])
                
                if len(missing_list) > 1:
                    print(f"\n전체 {len(missing_list)}명의 실종자 데이터 요약:")
                    self.summarize_all_persons(missing_list)
            else:
                print("실종자 데이터가 없습니다.")
        else:
            print("응답이 예상한 JSON 구조가 아닙니다.")
    
    def analyze_missing_person_data(self, person_data):
        """개별 실종자 데이터 분석"""
        print("\n" + "=" * 50)
        print("실종자 데이터 상세 분석")
        print("=" * 50)
        
        print(f"전체 필드 개수: {len(person_data)}")
        print("\n모든 필드 목록:")
        for i, (key, value) in enumerate(person_data.items(), 1):
            value_str = str(value) if value else "None"
            print(f"  {i:2d}. {key:20s}: '{value_str[:50]}{'...' if len(value_str) > 50 else ''}'")
        
        # 중요 정보 추출
        print(f"\n핵심 정보 추출:")
        core_info = {}
        
        # JSP에서 확인한 필드들로 매핑
        key_fields = {
            'nm': '성명',
            'age': '당시나이', 
            'ageNow': '현재나이',
            'sexdstnDscd': '성별',
            'occrAdres': '발생장소',
            'occrde': '발생일시',
            'alldressingDscd': '착의사항',
            'height': '키',
            'bdwgh': '몸무게',
            'writngTrgetDscd': '대상구분',
            'tknphotolength': '사진개수'
        }
        
        for field, label in key_fields.items():
            if field in person_data:
                value = person_data[field]
                core_info[field] = value
                status = "있음" if value and str(value).strip() else "없음"
                print(f"  {label:12s}: {status:6s} = '{value}'")
        
        # 사진 URL 생성 (JSP 코드 참고)
        if 'msspsnIdntfccd' in person_data and 'tknphotolength' in person_data:
            person_id = person_data['msspsnIdntfccd']
            photo_count = person_data['tknphotolength']
            
            if photo_count and str(photo_count) != "0":
                photo_url = f"https://www.safe182.go.kr/api/lcm/imgView.do?msspsnIdntfccd={person_id}"
                print(f"  사진 URL      : 있음 = '{photo_url}'")
                core_info['photo_url'] = photo_url
            else:
                print(f"  사진 URL      : 없음")
                core_info['photo_url'] = None
        
        # NER 처리 시뮬레이션
        print(f"\nNER 처리 시뮬레이션:")
        processed_data = self.simulate_ner_processing(person_data, core_info)
        
        return processed_data
    
    def simulate_ner_processing(self, raw_data, core_info):
        """Safe182 데이터 NER 처리 시뮬레이션"""
        print("\n--- NER 처리 시작 ---")
        
        processed = {
            'name': core_info.get('nm', '이름 미상'),
            'age': 0,
            'current_age': 0,
            'gender': '미상',
            'description': '',
            'location': core_info.get('occrAdres', ''),
            'photo_url': core_info.get('photo_url'),
            'category': '기타',
            'occurrence_date': core_info.get('occrde', ''),
            'empty_fields': [],
            'non_empty_fields': {}
        }
        
        # 나이 처리
        try:
            if core_info.get('age'):
                processed['age'] = int(core_info['age'])
            if core_info.get('ageNow'):
                processed['current_age'] = int(core_info['ageNow'])
        except:
            pass
        
        # 성별 처리 (여자/남자로 저장됨)
        gender_value = core_info.get('sexdstnDscd', '')
        if '여자' in str(gender_value):
            processed['gender'] = '여자'
        elif '남자' in str(gender_value):
            processed['gender'] = '남자'
        
        # 대상구분으로 카테고리 결정
        target_category = core_info.get('writngTrgetDscd', '')
        if '정상아동' in str(target_category) or '010' in str(target_category):
            if processed['current_age'] <= 7:
                processed['category'] = '미취학아동'
            else:
                processed['category'] = '학령기아동'
        elif '지적장애' in str(target_category) or '060' in str(target_category):
            processed['category'] = '지적장애인'
        elif '치매' in str(target_category) or '070' in str(target_category):
            processed['category'] = '치매환자'
        
        # 설명 정보 결합
        description_parts = []
        
        # 착의사항 (가장 중요한 특징)
        if core_info.get('alldressingDscd'):
            description_parts.append(f"착의: {core_info['alldressingDscd']}")
        
        # 신체 정보
        physical_info = []
        if core_info.get('height'):
            physical_info.append(f"키 {core_info['height']}")
        if core_info.get('bdwgh'):
            physical_info.append(f"몸무게 {core_info['bdwgh']}")
        
        if physical_info:
            description_parts.append("신체: " + ", ".join(physical_info))
        
        # 기타 특징들
        feature_fields = ['frmDscd', 'faceshpeDscd', 'hairshpeDscd', 'haircolrDscd']
        features = []
        for field in feature_fields:
            if field in raw_data and raw_data[field]:
                features.append(str(raw_data[field]))
        
        if features:
            description_parts.append("특징: " + ", ".join(features))
        
        # 모든 원본 필드 분석
        for key, value in raw_data.items():
            if value and str(value).strip():
                processed['non_empty_fields'][key] = str(value)
            else:
                processed['empty_fields'].append(key)
        
        # 최종 설명 생성
        if description_parts:
            processed['description'] = ' | '.join(description_parts)
        else:
            processed['description'] = f"상세정보 없음 (빈 필드: {len(processed['empty_fields'])}개)"
        
        print(f"처리 결과:")
        print(f"  이름: '{processed['name']}'")
        print(f"  당시나이: {processed['age']} / 현재나이: {processed['current_age']}")
        print(f"  성별: '{processed['gender']}'")
        print(f"  카테고리: '{processed['category']}'")
        print(f"  위치: '{processed['location']}'")
        print(f"  발생일: '{processed['occurrence_date']}'")
        print(f"  설명 길이: {len(processed['description'])}")
        print(f"  설명: '{processed['description'][:100]}{'...' if len(processed['description']) > 100 else ''}'")
        print(f"  이미지: {'있음' if processed['photo_url'] else '없음'}")
        print(f"  비어있지 않은 필드: {len(processed['non_empty_fields'])}개")
        
        return processed
    
    def summarize_all_persons(self, missing_list):
        """전체 실종자 데이터 요약"""
        summary = {
            'total': len(missing_list),
            'with_photos': 0,
            'categories': {},
            'genders': {},
            'ages': []
        }
        
        for person in missing_list:
            # 사진 있는 사람 계산
            if person.get('tknphotolength') and str(person['tknphotolength']) != "0":
                summary['with_photos'] += 1
            
            # 대상구분별 통계
            category = person.get('writngTrgetDscd', '기타')
            summary['categories'][category] = summary['categories'].get(category, 0) + 1
            
            # 성별 통계
            gender = person.get('sexdstnDscd', '미상')
            summary['genders'][gender] = summary['genders'].get(gender, 0) + 1
            
            # 나이 수집
            if person.get('ageNow'):
                try:
                    summary['ages'].append(int(person['ageNow']))
                except:
                    pass
        
        print(f"전체 실종자 {summary['total']}명 중:")
        print(f"  사진 있음: {summary['with_photos']}명")
        print(f"  대상구분: {summary['categories']}")
        print(f"  성별분포: {summary['genders']}")
        if summary['ages']:
            avg_age = sum(summary['ages']) / len(summary['ages'])
            print(f"  평균나이: {avg_age:.1f}세 (최소: {min(summary['ages'])}, 최대: {max(summary['ages'])})")

def main():
    """메인 테스트 실행"""
    print("Safe182 실종자 API 테스트 도구 (JSP 예제 기반)")
    print("=" * 70)
    
    tester = Safe182APITester()
    tester.test_safe182_api()
    
    print("\n" + "=" * 70)
    print("테스트 완료")
    print("\n중요사항:")
    print("- POST 방식 API 사용")
    print("- 응답 구조: {result, msg, totalCount, list}")
    print("- 주요 필드: nm(성명), age(나이), alldressingDscd(착의), occrAdres(장소)")
    print("- 사진 URL: https://www.safe182.go.kr/api/lcm/imgView.do?msspsnIdntfccd=ID")
    print("=" * 70)

if __name__ == "__main__":
    main()