import requests
import json

# 사용자님의 키
GYEONGGI_API_KEY = "16a785f639b14bab8f19ecafc2e537e4"

def test_gyeonggi_api():
    print("🚀 경기도 장학금 API 테스트 시작...")
    
    # 1. URL 확인 (오타 확인용)
    url = "https://openapi.gg.go.kr/GGNEWSSTUS"
    
    params = {
        "KEY": GYEONGGI_API_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 5
    }
    
    try:
        # 2. 실제 요청
        resp = requests.get(url, params=params, timeout=10)
        
        print(f"📡 응답 코드: {resp.status_code}")
        
        # 3. 응답 내용 날것으로 출력
        print("\n[응답 본문]")
        print(resp.text[:500])  # 앞부분 500자만 출력
        
        # 4. JSON 파싱 시도
        data = resp.json()
        
        # 5. 에러 코드 확인
        if 'RESULT' in data:
            code = data['RESULT']['CODE']
            msg = data['RESULT']['MESSAGE']
            print(f"\n❌ API 에러 발생: {code} - {msg}")
        elif 'Schlshipbeneft' in data:
            head = data['Schlshipbeneft'][0]['head'][1]
            code = head['RESULT']['CODE']
            msg = head['RESULT']['MESSAGE']
            print(f"\n✅ API 호출 성공: {code} - {msg}")
            print(f"데이터 개수: {len(data['Schlshipbeneft'][1]['row'])}")
        else:
            print("\n❓ 알 수 없는 응답 구조")

    except Exception as e:
        print(f"\n💥 파이썬 코드 에러: {str(e)}")

if __name__ == "__main__":
    test_gyeonggi_api()