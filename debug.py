import requests
from bs4 import BeautifulSoup
import time

def test_site(name, url, selectors):
    """사이트 크롤링 가능 여부 테스트"""
    print(f"\n{'='*60}")
    print(f"🔍 [{name}] 테스트 중...")
    print(f"🔗 URL: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"✅ 상태 코드: {resp.status_code}")
        
        if resp.status_code == 403:
            print(f"❌ 403 Forbidden - 봇 차단")
            return False
        
        if resp.status_code != 200:
            print(f"❌ 접속 실패")
            return False
        
        print(f"📄 응답 길이: {len(resp.text)} bytes")
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        found = False
        for selector in selectors:
            items = soup.select(selector)
            if items and len(items) > 0:
                print(f"✅ 선택자 '{selector}' 성공: {len(items)}개 발견")
                
                # 첫 3개 항목 출력
                for i, item in enumerate(items[:3]):
                    text = item.get_text(strip=True)[:60]
                    print(f"   {i+1}. {text}...")
                
                found = True
                break
        
        if not found:
            print(f"⚠️ 선택자 불일치 - HTML 구조 확인 필요")
            print(f"페이지 제목: {soup.title.string if soup.title else '없음'}")
        
        return found
        
    except requests.exceptions.Timeout:
        print(f"❌ Timeout - 응답 없음")
        return False
    except Exception as e:
        print(f"❌ 에러: {e}")
        return False

# 테스트 대상 사이트들
sites = [
    {
        "name": "콘테스트코리아",
        "url": "https://www.contestkorea.com/sub/list.php",
        "selectors": [
            ".list_style01 li",
            ".contest_list li",
            "ul.list li"
        ]
    },
    {
        "name": "올콘",
        "url": "https://www.all-con.co.kr/view/contest/list",
        "selectors": [
            ".contest-list .item",
            ".list-item",
            "ul.list li"
        ]
    },
    {
        "name": "씽유공모전",
        "url": "https://www.thinkcontest.com/Contest/List",
        "selectors": [
            ".contest_list li",
            ".list_style li",
            "div.item"
        ]
    },
    {
        "name": "캠퍼스픽",
        "url": "https://www.campuspick.com/activity",
        "selectors": [
            ".activity-list .item",
            ".card",
            "div.list-item"
        ]
    },
    {
        "name": "슥삭",
        "url": "https://ssugsak.co.kr/contest",
        "selectors": [
            ".contest-item",
            ".list li",
            "div.card"
        ]
    },
    {
        "name": "위비티",
        "url": "https://www.wevity.com/?c=find&s=1&gp=1",
        "selectors": [
            "ul.list li",
            ".contest_list li"
        ]
    },
    {
        "name": "링커리어",
        "url": "https://linkareer.com/list/hottest",
        "selectors": [
            "h3.MuiTypography-root",
            ".activity-card",
            "div[class*='Card']"
        ]
    }
]

if __name__ == "__main__":
    print("="*60)
    print("🕷️  크롤링 가능 사이트 검증 테스트")
    print("="*60)
    
    success_sites = []
    
    for site in sites:
        result = test_site(site["name"], site["url"], site["selectors"])
        if result:
            success_sites.append(site["name"])
        time.sleep(2)  # 사이트 부하 방지
    
    print("\n" + "="*60)
    print("📊 최종 결과")
    print("="*60)
    print(f"✅ 성공: {len(success_sites)}개")
    print(f"❌ 실패: {len(sites) - len(success_sites)}개")
    
    if success_sites:
        print("\n🎯 크롤링 가능 사이트:")
        for name in success_sites:
            print(f"   ✓ {name}")