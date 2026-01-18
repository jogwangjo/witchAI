import requests
from bs4 import BeautifulSoup

def check_site(name, url, selector):
    print(f"\n🔍 [{name}] 접속 테스트 중...")
    
    # 봇 탐지 회피를 위한 강력한 헤더
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"❌ 접속 실패 (상태코드: {resp.status_code})")
            return False
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select(selector)
        
        print(f"📡 응답 길이: {len(resp.text)} bytes")
        print(f"📊 찾은 항목 수: {len(items)}개")
        
        if len(items) > 0:
            print("✅ 크롤링 성공!")
            # 첫 번째 항목 제목만 출력해서 확인
            first_item = items[0].get_text().strip()[:50]
            print(f"   👉 첫 번째 데이터: {first_item}...")
            return True
        else:
            print("⚠️ 접속은 됐으나 데이터 못 찾음 (선택자 불일치 또는 동적 로딩)")
            # 디버깅용 타이틀 출력
            print(f"   👉 페이지 제목: {soup.title.string if soup.title else '제목 없음'}")
            return False
            
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return False

if __name__ == "__main__":
    print("=== 🕵️ 크롤링 생존 확인 테스트 ===")
    
    # 1. 네이버 뉴스 (선택자: a.news_tit)
    check_site("네이버 뉴스", 
               "https://search.naver.com/search.naver?where=news&query=%EA%B2%BD%EA%B8%B0%EB%8F%84+%EC%9E%A5%ED%95%99%EA%B8%88", 
               "a.news_tit")
    
    # 2. 위비티 (선택자: .list li .tit a) -> 정적 사이트라 성공 확률 높음
    check_site("위비티", 
               "https://www.wevity.com/?c=find&s=1&gub=1&cidx=21", 
               ".tit a")
               
    # 3. 링커리어 (선택자: .activity-title) -> 동적 사이트라 실패 확률 높음
    check_site("링커리어", 
               "https://linkareer.com/list/hottest", 
               "h3.MuiTypography-root") # 링커리어의 복잡한 클래스명