# test_firebase.py
import os
from dotenv import load_dotenv

load_dotenv()

def test_firebase():
    firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")
    
    print(f"Firebase 키 파일 경로: {firebase_credentials}")
    print(f"파일 존재 여부: {os.path.exists(firebase_credentials) if firebase_credentials else 'None'}")
    
    if firebase_credentials and os.path.exists(firebase_credentials):
        try:
            import firebase_admin
            from firebase_admin import credentials
            
            cred = credentials.Certificate(firebase_credentials)
            app = firebase_admin.initialize_app(cred)
            print("✅ Firebase 초기화 성공!")
            
            # 정리
            firebase_admin.delete_app(app)
            
        except Exception as e:
            print(f"❌ Firebase 초기화 실패: {e}")
    else:
        print("⚠️ Firebase 키 파일을 찾을 수 없습니다")

if __name__ == "__main__":
    test_firebase()