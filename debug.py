import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode
from bs4 import BeautifulSoup

async def test_wevity_crawl():
    print("🚀 Crawl4AI로 위비티 테스트 시작...")
    
    # 검색어 설정
    keyword = "경기도 장학금"
    url = f"https://www.wevity.com/?c=find&s=1&keyword={keyword}"

    # 1. 브라우저 설정
    # (stealth_mode 삭제, user_agent 직접 설정)
    browser_config = BrowserConfig(
        headless=True,       # 브라우저 창 안 띄우기
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # 2. 크롤러 실행
    # [수정] browser_config=... 대신 config=... 로 변경하여 중복 전달 에러 해결
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url=url,
            magic=True,  # 봇 차단 회피 및 동적 로딩 자동 처리 옵션
            cache_mode=CacheMode.BYPASS, 
            wait_for_selector=".list li" 
        )

        if result.success:
            print(f"✅ 페이지 로드 성공! (길이: {len(result.html)} chars)")
            
            # 3. 파싱 테스트
            soup = BeautifulSoup(result.html, 'html.parser')
            items = soup.select('.list li')[:5]
            
            if not items:
                print("⚠️ 항목을 찾지 못했습니다. HTML 구조를 확인하세요.")
                with open("debug_wevity.html", "w", encoding="utf-8") as f:
                    f.write(result.html)
                print("📁 debug_wevity.html 저장 완료")
            
            for i, item in enumerate(items, 1):
                try:
                    title_tag = item.select_one('.tit a')
                    if title_tag:
                        title = title_tag.get_text(strip=True)
                        print(f"{i}. {title}")
                except:
                    continue
        else:
            print(f"❌ 크롤링 실패: {result.error_message}")

# 비동기 실행
if __name__ == "__main__":
    asyncio.run(test_wevity_crawl())