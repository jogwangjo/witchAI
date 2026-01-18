import requests
from bs4 import BeautifulSoup

def test_wevity(keyword):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Referer': 'https://www.wevity.com/'
    }
    
    url = "https://www.wevity.com/"
    params = {"c": "find", "s": "1", "gbn": "0", "gp": "1", "keyword": keyword}
    
    print(f"\n🔍 테스트 키워드: {keyword}")
    print(f"📡 요청 URL: {url}?{requests.compat.urlencode(params)}")
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        print(f"✅ 상태 코드: {resp.status_code}")
        print(f"📄 응답 길이: {len(resp.text)} bytes")
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 다양한 선택자 시도
        selectors = [
            'ul.list_style li',
            'div.card',
            '.list-item',
            '.contest-list li',
            'ul.list li',
            '.em_list li'
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            if items:
                print(f"\n✅ 선택자 '{selector}' 발견: {len(items)}개")
                
                # 첫 아이템 구조 출력
                if items:
                    print("\n첫 번째 아이템 HTML:")
                    print(items[0].prettify()[:500])
                break
        else:
            print("\n⚠️ 아무 선택자도 매칭 안됨")
            print("\nHTML 샘플 (앞 1000자):")
            print(resp.text[:1000])
            
    except Exception as e:
        print(f"❌ 에러: {e}")

# 테스트 실행
if __name__ == "__main__":
    test_wevity("대외활동")
    test_wevity("공모전")
    test_wevity("경기 장학금")