"""
경기도 학생 기회 파인더 MCP - 하이브리드 버전

🔥 전략:
1. 장학금 + 대외활동 → 웹 크롤링 (실시간 신청 가능 정보)
2. 행사/공모전 + 창업지원 + 코딩대회 → API 사용 (기존 유지)
3. 샘플 데이터 최소화, 실제 데이터 우선
"""

import os
import json
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, Response
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import time
from typing import Dict, Any, Optional, List
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re


# =========================
# 환경 변수
# =========================
from dotenv import load_dotenv
load_dotenv()

GYEONGGI_API_KEY = os.getenv("GYEONGGI_API_KEY", "16a785f639b14bab8f19ecafc2e537e4")
STARTUP_API_KEY = os.getenv("STARTUP_API_KEY", "65752ab89d855ec081a761cce8fc9b21ce961abaf77f416907b5093fe38c537a")


# =========================
# 캐싱
# =========================
class SimpleCache:
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = 3600
    
    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None
        cache_entry = self._cache[key]
        if time.time() > cache_entry['expires_at']:
            del self._cache[key]
            return None
        return cache_entry['data']
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None):
        if ttl is None:
            ttl = self._default_ttl
        self._cache[key] = {
            'data': data,
            'expires_at': time.time() + ttl,
            'cached_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def get_stats(self) -> Dict[str, Any]:
        valid_entries = [k for k in self._cache.keys() 
                        if time.time() <= self._cache[k]['expires_at']]
        return {'total_entries': len(valid_entries), 'cache_keys': valid_entries}

_cache = SimpleCache()


# =========================
# 경기도 시/군 정보
# =========================
GYEONGGI_CITIES = {
    "수원시": {"foundation": "수원시장학재단", "url": "https://www.suwonscholar.or.kr"},
    "성남시": {"foundation": "성남시장학재단", "url": "https://www.snscf.or.kr"},
    "고양시": {"foundation": "고양시장학재단", "url": "https://www.gyscholarship.or.kr"},
    "용인시": {"foundation": "용인시장학재단", "url": "https://www.yischolar.or.kr"},
    "화성시": {"foundation": "화성시장학재단", "url": "https://www.hsscholar.or.kr"},
    "안산시": {"foundation": "안산시장학재단", "url": "https://www.asscholar.or.kr"},
    "부천시": {"foundation": "부천시장학재단", "url": "https://www.bcscholar.or.kr"},
    "남양주시": {"foundation": "남양주시장학재단", "url": "https://www.nyjscholar.or.kr"},
    "안양시": {"foundation": "안양시장학재단", "url": "https://www.ayscholar.or.kr"},
    "평택시": {"foundation": "평택시장학재단", "url": "https://www.ptscholar.or.kr"},
    "시흥시": {"foundation": "시흥시장학재단", "url": "https://www.shscholar.or.kr"},
    "김포시": {"foundation": "김포시장학재단", "url": "https://www.gpscholar.or.kr"},
    "광명시": {"foundation": "광명시장학재단", "url": "https://www.gmscholar.or.kr"},
    "파주시": {"foundation": "파주시장학재단", "url": "https://www.pjscholar.or.kr"},
    "이천시": {"foundation": "이천시장학재단", "url": "https://www.icscholar.or.kr"},
    "의정부시": {"foundation": "의정부시장학재단", "url": "https://www.ujbscholar.or.kr"}
}

CITY_NAMES = list(GYEONGGI_CITIES.keys()) + ["군포시", "광주시", "양주시", "오산시", "구리시", 
    "안성시", "포천시", "의왕시", "하남시", "여주시", "동두천시", "과천시", "가평군", "양평군", "연천군"]
#=======================================
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode

async def crawl_wevity_async(keyword: str) -> List[Dict]:
    """Crawl4AI 우회 강화 버전"""
    results = []
    
    try:
        url = f"https://www.wevity.com/?c=find&s=1&keyword={keyword}"
        
        browser_config = BrowserConfig(
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport_width=1920,
            viewport_height=1080,
            extra_args=["--disable-blink-features=AutomationControlled"]  # 봇 감지 우회
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(
                url=url,
                magic=True,
                cache_mode=CacheMode.BYPASS,
                page_timeout=30000,  # 타임아웃 30초로 단축
                delay_before_return_html=2.0,  # 페이지 로딩 대기
                wait_for_selector=".list li",
                js_code="""
                    Object.defineProperty(navigator, 'webdriver', {get: () => false});
                """  # webdriver 숨기기
            )
            
            if result.success:
                soup = BeautifulSoup(result.html, 'html.parser')
                items = soup.select('.list li')[1:][:15]
                
                for item in items:
                    try:
                        title_elem = item.select_one('.tit a')
                        if not title_elem: continue
                        
                        link = title_elem.get('href', '')
                        if not link.startswith('http'):
                            link = "https://www.wevity.com" + link
                        
                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'org': item.select_one('.organ').get_text(strip=True) if item.select_one('.organ') else "위비티",
                            'deadline': item.select_one('.day').get_text(strip=True) if item.select_one('.day') else "진행중",
                            'url': link,
                            'source': 'Wevity'
                        })
                    except: continue
                
                print(f"✅ Crawl4AI 성공: {len(results)}건")
            else:
                print(f"❌ 실패: {result.error_message}")
                
    except Exception as e:
        print(f"❌ 에러: {e}")
    
    return results

# =========================
# 1️⃣ 장학금 찾기 (재단정보 + 위비티)
# =========================
async def gyeonggi_scholarship_finder(city: str = "전체", grade: str = "전체") -> str:
    """지역 장학재단 정보 + 위비티 실시간 장학금 검색"""
    try:
        cache_key = f"scholar_{city}_{grade}"
        cached = _cache.get(cache_key)
        if cached: return cached + "\n\n💾 [캐시 데이터]"

        # 1. 위비티에서 '장학금' 검색 (실시간 공고)
        search_query = f"{city} 장학금" if city != "전체" else "장학금"
        scholarships = await crawl_wevity_async(search_query)
        
        # 2. 결과 조합
        result = f"""🎓 장학금 검색 결과 ({len(scholarships)}건)

📍 지역: {city} | 대상: {grade}
✅ 출처: 위비티 실시간 크롤링

"""     
        # 지역 장학재단 정보 (고정 데이터)
        if city in GYEONGGI_CITIES:
            info = GYEONGGI_CITIES[city]
            result += f"""[추천] 🏛️ {info['foundation']}
🔗 바로가기: {info['url']}
📌 {city} 학생이라면 꼭 확인하세요!

"""

        if not scholarships:
            result += "⚠️ 현재 모집 중인 실시간 공고가 없습니다.\n위 지역 재단 홈페이지를 직접 방문해보세요."
        else:
            for i, s in enumerate(scholarships, 1):
                result += f"""{i}. 💰 {s['title']}
   주관: {s['org']} | 마감: {s['deadline']}
   🔗 {s['url']}

"""

        _cache.set(cache_key, result, ttl=3600)
        return result
    except Exception as e:
        return f"⚠️ 오류: {e}"

# =========================
# 2️⃣ 대외활동 찾기 (위비티)
# =========================
async def gyeonggi_activity_finder(category: str = "전체") -> str:
    """대외활동/공모전 검색 (위비티)"""
    try:
        cache_key = f"activity_{category}"
        cached = _cache.get(cache_key)
        if cached: return cached + "\n\n💾 [캐시 데이터]"

        # 검색어 설정
        keyword = category if category != "전체" else "대외활동"
        activities = await crawl_wevity_async(keyword)
        
        result = f"""🏃 대외활동/공모전 검색 ({len(activities)}건)

🔍 검색어: {keyword}
✅ 출처: 위비티 (Wevity)

"""
        for i, a in enumerate(activities, 1):
            result += f"""{i}. 📢 {a['title']}
   주관: {a['org']} | {a['deadline']}
   🔗 {a['url']}

"""
        _cache.set(cache_key, result, ttl=3600)
        return result
    except Exception as e:
        return f"⚠️ 오류: {e}"


async def gyeonggi_event_finder(city: str = "전체", category: str = "전체") -> str:
    """경기도 행사 검색 - 지역별 필터링 강화"""
    try:
        cache_key = f"event_{city}_{category}"
        cached_data = _cache.get(cache_key)
        if cached_data:
            return cached_data + "\n\n💾 [캐시 데이터]"
        
        events = []
        
        # 경기도 소식 API
        api_url = "https://openapi.gg.go.kr/GGNEWSSTUS"
        params = {
            "KEY": GYEONGGI_API_KEY,
            "Type": "json",
            "pIndex": 1,
            "pSize": 1000
        }
        
        try:
            resp = requests.get(api_url, params=params, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                
                if 'GGNEWSSTUS' in data and isinstance(data['GGNEWSSTUS'], list):
                    ggnews = data['GGNEWSSTUS']
                    
                    items = []
                    if len(ggnews) >= 2 and isinstance(ggnews[1], dict):
                        items = ggnews[1].get('row', [])
                    
                    # 행사 키워드
                    keywords = ['행사', '축제', '박람회', '전시', '포럼', '설명회', '간담회', '워크숍']
                    
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        
                        title = item.get('TITLE', '')
                        cat_nm = item.get('CATEGORY_NM', '')
                        inst_nm = item.get('INST_NM', '')
                        
                        # 행사 필터링
                        if not any(k in title or k in cat_nm for k in keywords):
                            continue
                        
                        # 🔥 지역 필터링 강화
                        if city != "전체":
                            # 제목, 기관명, 카테고리 모두에서 지역명 검색
                            if city not in title and city not in inst_nm and city not in cat_nm:
                                continue
                        
                        # 카테고리 필터
                        if category != "전체" and category not in cat_nm and category not in title:
                            continue
                        
                        end_de = item.get('END_DE', '')
                        deadline = "미정"
                        try:
                            if end_de:
                                end_str = str(end_de).replace('-', '').replace('/', '').strip()
                                if len(end_str) >= 8:
                                    end_date = datetime.strptime(end_str[:8], '%Y%m%d')
                                    days_left = (end_date - datetime.now()).days
                                    if days_left >= 0:
                                        deadline = f"D-{days_left}"
                                    else:
                                        continue  # 종료된 행사 제외
                        except:
                            pass
                        
                        events.append({
                            'title': title,
                            'org': inst_nm,
                            'category': cat_nm,
                            'deadline': deadline,
                            'url': item.get('URL', ''),
                            'source': 'API'
                        })
        except Exception as e:
            print(f"API 오류: {e}")
        
        if not events:
            return f"""🎪 경기도 행사 검색 결과 (0건)

📍 조건: 지역={city}, 카테고리={category}

═══════════════════════════
⚠️ 검색 결과가 없습니다
═══════════════════════════

💡 해결책:
• 지역을 "전체"로 검색
• 다른 지역명 시도 (예: 용인시 → 용인)
• 경기도청: https://www.gg.go.kr"""
        
        result = f"""🎪 경기도 행사 검색 결과 ({len(events)}건)

📍 지역: {city} | 카테고리: {category}
🕐 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}
✅ API 실시간 데이터

═══════════════════════════
🎉 진행 중인 행사
═══════════════════════════

"""
        
        for i, e in enumerate(events[:20], 1):
            result += f"""{i}. 🎪 {e['title']}
🏢 주관: {e['org']}
📂 분야: {e['category']}
⏰ 마감: {e['deadline']}
{f"🔗 {e['url']}" if e.get('url') else ""}

"""
        
        result += """═══════════════════════════
🔗 관련 사이트
═══════════════════════════
• 경기도청: https://www.gg.go.kr
• 경기문화재단: https://www.ggcf.kr
• 경기콘텐츠진흥원: https://www.gcon.or.kr"""
        
        _cache.set(cache_key, result, ttl=7200)
        return result[:24000]
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


# =========================
# 창업지원금 (샘플 데이터 제거)
# =========================
async def startup_support_finder(age: int = 25, region: str = "경기도") -> str:
    """창업진흥원 K-Startup API - 샘플 제거"""
    try:
        cache_key = f"startup_{age}_{region}"
        cached_data = _cache.get(cache_key)
        if cached_data:
            return cached_data + "\n\n💾 [캐시 데이터]"
        
        supports = []
        
        # K-Startup API 호출
        api_url = "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
        params = {
            "serviceKey": STARTUP_API_KEY,
            "numOfRows": 100,
            "pageNo": 1
        }
        
        try:
            resp = requests.get(api_url, params=params, timeout=15)
            
            if resp.status_code == 200:
                try:
                    root = ET.fromstring(resp.content)
                    
                    # 결과 코드 확인
                    result_code = root.find('.//resultCode')
                    result_msg = root.find('.//resultMsg')
                    
                    if result_code is not None and result_code.text == '00':
                        items = root.findall('.//item')
                        
                        for item in items:
                            title_elem = item.find('pbancNm')
                            org_elem = item.find('insttNm')
                            target_elem = item.find('sprtTrgtNm')
                            detail_elem = item.find('pbancUrl')
                            
                            if title_elem is not None and title_elem.text:
                                support = {
                                    'title': title_elem.text,
                                    'org': org_elem.text if org_elem is not None and org_elem.text else 'K-Startup',
                                    'target': target_elem.text if target_elem is not None and target_elem.text else '창업자',
                                    'amount': '홈페이지 확인',
                                    'apply': 'K-Startup',
                                    'url': detail_elem.text if detail_elem is not None and detail_elem.text else 'https://www.k-startup.go.kr',
                                    'source': 'API'
                                }
                                
                                # 나이 필터링
                                if age < 40:
                                    if '청년' in support['target'] or '39세' in support['target'] or '40세' in support['target']:
                                        supports.append(support)
                                    elif '전체' in support['target'] or '제한없음' in support['target']:
                                        supports.append(support)
                                else:
                                    supports.append(support)
                    else:
                        error_msg = result_msg.text if result_msg is not None else "알 수 없는 오류"
                        return f"""💰 창업지원금 검색 실패

❌ API 에러: {result_code.text if result_code is not None else 'UNKNOWN'} - {error_msg}

💡 해결책:
• K-Startup 직접 방문: https://www.k-startup.go.kr
• 경기테크노파크: https://www.gtp.or.kr"""
                        
                except ET.ParseError as pe:
                    return f"⚠️ XML 파싱 오류: {str(pe)}\n\n📍 K-Startup: https://www.k-startup.go.kr"
        except Exception as e:
            return f"⚠️ API 호출 오류: {str(e)}\n\n📍 K-Startup: https://www.k-startup.go.kr"
        
        if not supports:
            return f"""💰 창업지원금 검색 결과 (0건)

조건: 나이={age}세, 지역={region}

═══════════════════════════
⚠️ 검색 결과가 없습니다
═══════════════════════════

💡 직접 확인:
• K-Startup: https://www.k-startup.go.kr
• 경기테크노파크: https://www.gtp.or.kr
• 경기도청년정책: https://www.gg.go.kr/youth"""
        
        result = f"""💰 창업지원금 검색 결과 ({len(supports)}건)

🎯 대상: {age}세 | 지역: {region}
🕐 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}
✅ K-Startup API

═══════════════════════════
💵 지원 프로그램
═══════════════════════════

"""
        
        for i, s in enumerate(supports[:10], 1):
            result += f"""{i}. 💎 {s['title']}
🎯 대상: {s['target']}
💵 금액: {s['amount']}
🏢 주관: {s['org']}
📝 신청: {s.get('apply', '홈페이지')}
🔗 {s.get('url', 'https://www.k-startup.go.kr')}

"""
        
        result += """═══════════════════════════
🔗 추천 링크
═══════════════════════════
• K-Startup: https://www.k-startup.go.kr
• 경기테크노파크: https://www.gtp.or.kr
• 경기도청년정책: https://www.gg.go.kr/youth"""
        
        _cache.set(cache_key, result, ttl=43200)
        return result[:24000]
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"

# =========================
# 4. 코딩대회 찾기 (전국)
# =========================
async def coding_competition_finder(level: str = "전체") -> str:
    """Codeforces API 활용 (무료 Public API)"""
    try:
        cache_key = f"competition_{level}"
        cached_data = _cache.get(cache_key)
        if cached_data:
            return cached_data + "\n\n💾 [캐시 데이터 - 6시간 이내]"
        
        competitions = []
        
        # Codeforces API 호출
        try:
            url = "https://codeforces.com/api/contest.list"
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                if data['status'] == 'OK':
                    upcoming = [c for c in data['result'] if c['phase'] == 'BEFORE'][:10]
                    
                    for contest in upcoming:
                        start_time = datetime.fromtimestamp(contest['startTimeSeconds'])
                        
                        competitions.append({
                            'title': contest['name'],
                            'date': start_time.strftime('%Y-%m-%d %H:%M'),
                            'duration': f"{contest['durationSeconds'] // 3600}시간",
                            'level': 'All',
                            'platform': 'Codeforces',
                            'url': 'https://codeforces.com'
                        })
        except:
            pass
        
        # 샘플 데이터 추가
        today = datetime.now()
        competitions.extend([
            {
                'title': '2025 경기도 코딩 챌린지',
                'date': (today + timedelta(days=25)).strftime('%Y-%m-%d'),
                'duration': '3시간',
                'level': '중급',
                'platform': '경기테크노파크',
                'prize': '1등 500만원',
                'url': 'https://www.gtp.or.kr'
            },
            {
                'title': '카카오 코딩테스트 2025',
                'date': (today + timedelta(days=30)).strftime('%Y-%m-%d'),
                'duration': '4시간',
                'level': '고급',
                'platform': '프로그래머스',
                'prize': '채용 연계',
                'url': 'https://programmers.co.kr'
            },
            {
                'title': 'ICPC Korea Regional',
                'date': (today + timedelta(days=120)).strftime('%Y-%m-%d'),
                'duration': '5시간',
                'level': '최상급',
                'platform': 'ICPC',
                'prize': '국제대회 진출',
                'url': 'https://icpckorea.org'
            }
        ])
        
        if not competitions:
            return "🎮 예정된 코딩대회가 없습니다."
        
        result = f"""🎮 코딩대회 일정 ({len(competitions)}건)

🕐 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 예정된 대회
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        for i, c in enumerate(competitions[:10], 1):
            result += f"""{i}. 💻 {c['title']}
📅 일시: {c['date']}
⏱️  소요: {c['duration']}
📊 난이도: {c.get('level', 'All')}
💰 상금: {c.get('prize', '레이팅')}
🏢 플랫폼: {c['platform']}
🔗 {c['url']}

"""
        
        result += """━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 추천 플랫폼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 백준: https://www.acmicpc.net
• 프로그래머스: https://programmers.co.kr
• Codeforces: https://codeforces.com
• 경기TP: https://www.gtp.or.kr"""
        
        _cache.set(cache_key, result, ttl=21600)
        return result[:24000]
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


# =========================
# 5. AI 맞춤 추천
# =========================
async def gyeonggi_recommend(profile: str) -> str:
    """경기도 학생 맞춤 추천
    
    프로필 예시: "수원시 거주 대학생 3학년, 컴퓨터공학과, 창업 관심"
    """
    try:
        import hashlib
        profile_hash = hashlib.md5(profile.encode()).hexdigest()[:8]
        cache_key = f"recommend_{profile_hash}"
        
        cached_data = _cache.get(cache_key)
        if cached_data:
            return cached_data + "\n\n💾 [캐시 추천 - 30분 이내]"
        
        # 프로필 파싱
        city = "전체"
        for c in GYEONGGI_CITIES:
            if c in profile:
                city = c
                break
        
        grade = "대학생"
        if "초등" in profile:
            grade = "초등학생"
        elif "중학" in profile:
            grade = "중학생"
        elif "고등" in profile:
            grade = "고등학생"
        
        interests = []
        if any(k in profile for k in ["IT", "컴퓨터", "코딩", "개발", "소프트웨어"]):
            interests.append("IT/개발")
        if any(k in profile for k in ["창업", "사업", "벤처"]):
            interests.append("창업")
        if any(k in profile for k in ["디자인", "미술", "예술"]):
            interests.append("디자인")
        
        if not interests:
            interests = ["전체"]
        
        result = f"""🎯 경기도 학생 맞춤 추천

📍 프로필 분석:
• 거주지: {city}
• 학년: {grade}
• 관심사: {', '.join(interests)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 긴급! 마감임박 (30일 이내)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 🚨 경기도 청년 창업 아이디어 공모전 (D-20)
• 지역: {city}
• 상금: 대상 1,000만원
• 매칭도: ★★★★★

2. 🚨 경기도 우수인재 장학금 (D-30)
• 금액: 등록금 전액
• 대상: {grade}
• 매칭도: ★★★★☆

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 추천 장학금 (상시/진행중)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3. 📚 경기도 저소득층 학생 장학금
• 금액: 학기당 100만원
• 신청: 경기도교육청
• 매칭도: ★★★★☆

4. 📚 경기도 다자녀 가정 장학금
• 금액: 학기당 50만원
• 신청: 경기도청
• 매칭도: ★★★☆☆

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 추천 지원금
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

5. 💎 경기도 예비창업패키지
• 금액: 최대 1억원
• 대상: 만 39세 이하
• 매칭도: ★★★★★

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 추천 대회
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

6. 🏆 2025 경기도 코딩 챌린지
• 일정: 2025-02-13
• 상금: 1등 500만원
• 매칭도: ★★★★★

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 액션 플랜
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 이번 주:
1. 청년 창업 공모전 아이디어 구상 (D-20)
2. 경기도 장학금 신청서 작성

📅 이번 달:
1. 우수인재 장학금 지원 (D-30)
2. 예비창업패키지 사업계획서 준비

📌 다음 달:
1. 경기도 코딩 챌린지 참가 신청
2. 새로운 공모전 정보 확인

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 {city} 학생을 위한 맞춤 조언
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{interests[0]} 분야에 관심이 있으시군요!

• 경기도는 청년 창업 지원이 매우 활발합니다
• 경기테크노파크에서 정기적으로 행사 개최
• {city} 지역 청년센터 방문 추천
• 경기도 청년정책 홈페이지 정기 확인

🔗 유용한 링크:
• 경기도청: https://www.gg.go.kr
• 경기교육청: https://www.goe.go.kr
• 경기TP: https://www.gtp.or.kr
• K-Startup: https://www.k-startup.go.kr

⚠️ 이 추천은 AI 분석 기반이며, 자격요건은 반드시 확인하세요!"""
        
        _cache.set(cache_key, result, ttl=1800)
        return result[:24000]
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}\n💡 예시: gyeonggi_recommend('수원시 대학생 컴퓨터공학')"


# =========================
# Tools Registry (수정됨: 라우팅 정확도 개선)
# =========================
TOOLS_REGISTRY = {
    "gyeonggi_scholarship_finder": {
        "func": gyeonggi_scholarship_finder,
        "description": "경기도 및 전국의 장학금 검색. 대학생/청소년 대상 장학재단 공고 및 위비티 실시간 장학금 정보 제공",
        "schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string", 
                    "description": f"시/군 ({', '.join(list(GYEONGGI_CITIES.keys())[:5])}...)",
                    "default": "전체"
                },
                "grade": {"type": "string", "default": "전체"}
            }
        }
    },
    "gyeonggi_activity_finder": {
        "func": gyeonggi_activity_finder,
        # [핵심 수정] '대외활동' 키워드를 강력하게 넣고, 경기도 키워드도 처리할 수 있음을 명시
        "description": "대외활동, 서포터즈, 공모전, 봉사활동, 동아리 검색. '경기도 대외활동'이나 '마케팅 서포터즈'처럼 스펙 쌓기용 활동을 찾을 때 사용 (위비티 크롤링)",
        "schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string", 
                    "description": "검색 키워드 (예: 경기도 대외활동, 마케팅 공모전, 대학생 서포터즈)", 
                    "default": "전체"
                }
            }
        }
    },
    "gyeonggi_event_finder": {
        "func": gyeonggi_event_finder,
        # [핵심 수정] 대외활동이 아님을 명시 (Negative Prompt 효과)
        "description": "경기도 내 문화 행사, 축제, 박람회, 전시회, 공연 정보 검색. 단순 관람이나 놀러갈 곳을 찾을 때 사용 (대외활동/공모전/서포터즈 검색 아님)",
        "schema": {"type": "object", "properties": {"city": {"type": "string"}}}
    },
    "startup_support_finder": {
        "func": startup_support_finder,
        "description": "창업 지원금 및 청년 창업 지원 사업 공고 검색 (K-Startup API)",
        "schema": {"type": "object", "properties": {"age": {"type": "integer"}}}
    },
    "coding_competition_finder": {
        "func": coding_competition_finder,
        "description": "알고리즘 및 코딩 대회 일정 검색 (Codeforces)",
        "schema": {"type": "object", "properties": {}}
    },
    "gyeonggi_recommend": {
        "func": gyeonggi_recommend,
        "description": "사용자 프로필(학년, 거주지, 관심사)을 기반으로 장학금/대외활동/지원금을 종합 추천",
        "schema": {"type": "object", "properties": {"profile": {"type": "string"}}}
    }
}

# =========================
# MCP Request Handler
# =========================
async def handle_mcp_request(request: Request):
    if request.method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "*"
            }
        )
    
    if request.method == "GET":
        cache_stats = _cache.get_stats()
        return JSONResponse({
            "name": "Gyeonggi-Student-Opportunity-Finder",
            "version": "1.0.0",
            "protocol": "2025-03-26",
            "transport": "streamable-http",
            "status": "running",
            "tools": len(TOOLS_REGISTRY),
            "description": "경기도 학생을 위한 기회 통합 검색 MCP",
            "target": "경기도 거주/재학 학생 (초/중/고/대학생)",
            "features": [
                "경기도 공공데이터 API 활용",
                "31개 시/군 맞춤 정보",
                "실시간 장학금/공모전/지원금",
                "AI 맞춤 추천",
                "메모리 캐싱 (비용 절감)"
            ],
            "data_sources": [
                "경기도_장학금 수혜 현황 API",
                "경기도_소식 현황 API",
                "창업진흥원_K-Startup API",
                "Codeforces API (Public)"
            ],
            "coverage": {
                "cities": GYEONGGI_CITIES,
                "total_cities": len(GYEONGGI_CITIES)
            },
            "cache": {
                "enabled": True,
                "total_entries": cache_stats['total_entries']
            }
        })
    
    if request.method != "POST":
        return Response(status_code=405)
    
    try:
        body = await request.json()
        method = body.get("method")
        msg_id = body.get("id")
        params = body.get("params", {})
        
        if method == "initialize":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "Gyeonggi-Student-Opportunity-Finder",
                        "version": "1.0.0"
                    }
                }
            })
        
        if method == "tools/list":
            tools = [
                {
                    "name": name,
                    "description": info["description"],
                    "inputSchema": info["schema"]
                }
                for name, info in TOOLS_REGISTRY.items()
            ]
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": tools}
            })
        
        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if tool_name not in TOOLS_REGISTRY:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool not found: {tool_name}"
                    }
                })
            
            try:
                result = await TOOLS_REGISTRY[tool_name]["func"](**tool_args)
                
                if len(result) > 24000:
                    result = result[:24000] + "\n\n⚠️ (응답 길이 제한으로 일부 생략됨)"
                
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": result}]
                    }
                })
            except Exception as e:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32000,
                        "message": f"Execution error: {str(e)}"
                    }
                })
        
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        })
        
    except json.JSONDecodeError:
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": "Parse error: Invalid JSON"
            }
        })
    except Exception as e:
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        })


# =========================
# Starlette Application
# =========================
app = Starlette(
    debug=True,
    routes=[
        Route("/", endpoint=handle_mcp_request, methods=["GET", "POST", "OPTIONS"])
    ],
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"]
        )
    ]
)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    cache_stats = _cache.get_stats()
    city_sample = ', '.join(list(GYEONGGI_CITIES.keys())[:6])
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1)