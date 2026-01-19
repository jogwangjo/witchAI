"""
경기도 학생 기회 파인더 MCP Server
경기도 거주/재학 학생을 위한 장학금, 대외활동, 행사, 코딩대회 통합 검색
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
from curl_cffi.requests import AsyncSession
from dotenv import load_dotenv

load_dotenv()

GYEONGGI_API_KEY = os.getenv("GYEONGGI_API_KEY", "16a785f639b14bab8f19ecafc2e537e4")


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

SCHOLARSHIP_DATABASE = {
    "national": {
        "한국장학재단": {
            "url": "https://www.kosaf.go.kr",
            "programs": [
                {"name": "국가장학금 1유형", "target": "대학생", "amount": "소득분위별 차등 (최대 전액)", "period": "매 학기 (3월/9월)"},
                {"name": "국가장학금 2유형", "target": "대학생", "amount": "대학 자체 기준", "period": "매 학기"},
                {"name": "국가근로장학금", "target": "대학생", "amount": "시급 지급 (월 최대 50만원)", "period": "학기 중 상시"},
                {"name": "푸른등대 기부장학금", "target": "대학생", "amount": "200~500만원", "period": "연 1~2회"},
                {"name": "희망사다리 장학금", "target": "고3/대학생", "amount": "200~350만원", "period": "연 1회"},
                {"name": "대학생 근로장학금", "target": "대학생", "amount": "교내 근로 (시급)", "period": "학기별"}
            ]
        },
        "교육부": {
            "url": "https://www.moe.go.kr",
            "programs": [
                {"name": "초중고 교육비 지원", "target": "초중고", "amount": "급식비, 방과후, 교육비", "period": "학기별 신청"},
                {"name": "다자녀 교육비 지원", "target": "초중고 (3자녀 이상)", "amount": "학비 감면", "period": "상시"},
                {"name": "한부모가정 교육비", "target": "초중고", "amount": "교육비 전액", "period": "학기별"}
            ]
        },
        "보훈처": {
            "url": "https://www.mpva.go.kr",
            "programs": [
                {"name": "보훈장학금", "target": "국가유공자 자녀", "amount": "등록금 전액", "period": "매 학기"}
            ]
        }
    },
    "gyeonggi": {
        "경기도교육청": {
            "url": "https://www.goe.go.kr",
            "contact": "031-820-0114",
            "programs": [
                {"name": "저소득층 학생 교육비", "target": "초중고", "amount": "학기당 차등 지원", "period": "3월, 9월"},
                {"name": "다문화가정 학생 지원", "target": "초중고", "amount": "교육비 지원", "period": "학기별"},
                {"name": "우수인재 장학금", "target": "고등학생", "amount": "성적우수자 학기당 100만원", "period": "학기별"},
                {"name": "농산어촌 학생 지원", "target": "초중고", "amount": "교육비", "period": "학기별"}
            ]
        },
        "경기도청": {
            "url": "https://www.gg.go.kr/youth",
            "contact": "031-120",
            "programs": [
                {"name": "경기도 청년 장학금", "target": "대학생 (도내 거주)", "amount": "학기당 200만원", "period": "3월, 9월"},
                {"name": "저소득 대학생 장학금", "target": "대학생 (기초생활수급)", "amount": "등록금 일부", "period": "학기별"},
                {"name": "다자녀 대학생 장학금", "target": "대학생 (3자녀 이상)", "amount": "학기당 150만원", "period": "학기별"}
            ]
        }
    },
    "private": {
        "삼성꿈장학재단": {
            "url": "https://www.sdream.or.kr",
            "programs": [
                {"name": "삼성 드림클래스", "target": "중고등학생", "amount": "학습지원금", "period": "연중"},
                {"name": "삼성 글로벌 희망장학금", "target": "대학생", "amount": "등록금 전액", "period": "연 1회"}
            ]
        },
        "현대차 정몽구재단": {
            "url": "https://www.hyundai-cmkfoundation.org",
            "programs": [
                {"name": "온드림스쿨", "target": "중고등학생", "amount": "교육비/멘토링", "period": "연중"},
                {"name": "H-점프스쿨", "target": "중학생", "amount": "학습지원", "period": "학기별"}
            ]
        },
        "아산사회복지재단": {
            "url": "https://www.asanfoundation.or.kr",
            "programs": [
                {"name": "아산 사회복지 장학금", "target": "대학생 (사회복지)", "amount": "등록금 전액", "period": "매 학기"}
            ]
        },
        "롯데장학재단": {
            "url": "https://scholarship.lotte.co.kr",
            "programs": [
                {"name": "롯데 장학금", "target": "대학생", "amount": "등록금 일부", "period": "매 학기"}
            ]
        },
        "신한은행 희망재단": {
            "url": "https://www.shinhanhope.org",
            "programs": [
                {"name": "신한 희망장학금", "target": "대학생 (저소득)", "amount": "학기당 300만원", "period": "매 학기"}
            ]
        }
    }
}

STARTUP_POLICIES = {
    "경기도": {
        "경기테크노파크": {
            "url": "https://www.gtp.or.kr",
            "contact": "031-500-3000",
            "programs": [
                {"name": "예비창업패키지", "target": "만 39세 이하", "amount": "최대 1억원", "desc": "사업계획서 심사 후 지원"},
                {"name": "초기창업패키지", "target": "3년 미만 창업기업", "amount": "최대 1억원", "desc": "초기 운영자금 지원"},
                {"name": "경기 스타트업 성장지원", "target": "경기도 소재 스타트업", "amount": "프로그램별 상이", "desc": "멘토링, 네트워킹 등"}
            ]
        },
        "경기콘텐츠진흥원": {
            "url": "https://www.gcon.or.kr",
            "contact": "031-8039-9000",
            "programs": [
                {"name": "콘텐츠 창업 지원", "target": "콘텐츠 분야 예비창업자", "amount": "최대 5천만원", "desc": "콘텐츠 제작 및 사업화 지원"},
                {"name": "게임 스타트업 육성", "target": "게임 개발사", "amount": "프로젝트별 차등", "desc": "게임 개발 및 마케팅 지원"}
            ]
        }
    },
    "중앙정부": {
        "K-Startup": {
            "url": "https://www.k-startup.go.kr",
            "contact": "1357",
            "programs": [
                {"name": "예비창업패키지", "target": "예비창업자", "amount": "최대 1억원", "desc": "사업화 자금, 멘토링"},
                {"name": "초기창업패키지", "target": "3년 미만", "amount": "최대 1억원", "desc": "제품/서비스 고도화"},
                {"name": "창업도약패키지", "target": "3~7년", "amount": "최대 3억원", "desc": "시장 진입 및 성장"}
            ]
        },
        "소상공인시장진흥공단": {
            "url": "https://www.semas.or.kr",
            "contact": "1357",
            "programs": [
                {"name": "청년창업사관학교", "target": "만 39세 이하", "amount": "1억원 내외", "desc": "입주 공간 및 창업 교육"},
                {"name": "소상공인 정책자금", "target": "소상공인", "amount": "업종별 차등", "desc": "저금리 융자 지원"}
            ]
        }
    }
}


async def crawl_wevity_async(keyword: str) -> List[Dict]:
    results = []
    try:
        async with AsyncSession(impersonate="chrome110") as session:
            from urllib.parse import quote
            encoded_keyword = quote(keyword)
            url = f"https://www.wevity.com/?c=find&s=1&keyword={encoded_keyword}"
            
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9",
                "Referer": "https://www.wevity.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = await session.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.select('.list li')
            
            count = 0
            for item in items:
                if count >= 12:
                    break
                
                try:
                    title_elem = item.select_one('.tit a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    if not title:
                        continue
                    
                    link = title_elem.get('href', '')
                    if link and not link.startswith('http'):
                        link = "https://www.wevity.com" + link
                    
                    org_elem = item.select_one('.organ')
                    org = org_elem.get_text(strip=True) if org_elem else "정보없음"
                    
                    day_elem = item.select_one('.day')
                    deadline = day_elem.get_text(strip=True) if day_elem else "진행중"

                    results.append({
                        'title': title,
                        'org': org,
                        'deadline': deadline,
                        'url': link
                    })
                    count += 1
                except:
                    continue
    except:
        pass
    
    return results


async def gyeonggi_scholarship_finder(city: str = "전체", grade: str = "전체") -> str:
    try:
        cache_key = f"scholar_{city}_{grade}"
        cached = _cache.get(cache_key)
        if cached:
            return cached
        
        is_elementary = "초등" in grade
        is_middle = "중학" in grade or "중등" in grade
        is_high = "고등" in grade or "고3" in grade or "고1" in grade or "고2" in grade
        is_college = "대학" in grade or "대학생" in grade
        
        if grade == "전체":
            is_elementary = is_middle = is_high = is_college = True
        
        result = f"""장학금 종합 안내

지역: {city}
대상: {grade}
업데이트: {datetime.now().strftime('%Y-%m-%d')}

"""
        
        if city in GYEONGGI_CITIES:
            info = GYEONGGI_CITIES[city]
            result += f"""[STEP 1] 거주 지역 장학재단

{info['foundation']} (최우선 확인)
{info['url']}

{city} 거주 학생 우대 선발
- 초중고대학생 모두 지원 가능
- 홈페이지에서 공고 확인 필수
- 학기별 정기 모집 (3월, 9월)

"""
        
        result += """[STEP 2] 경기도 광역 장학금

"""
        
        for org_name, org_info in SCHOLARSHIP_DATABASE["gyeonggi"].items():
            has_matching = False
            matching_progs = []
            
            for prog in org_info["programs"]:
                show_this = False
                
                if (is_elementary or is_middle or is_high) and "초중고" in prog["target"]:
                    show_this = True
                if is_college and "대학" in prog["target"]:
                    show_this = True
                if "고등학생" in prog["target"] and is_high:
                    show_this = True
                
                if show_this:
                    has_matching = True
                    matching_progs.append(prog)
            
            if has_matching:
                result += f"{org_name}\n{org_info['url']}\n연락처: {org_info.get('contact', '홈페이지 참조')}\n\n"
                
                for prog in matching_progs:
                    result += f"  - {prog['name']}\n"
                    result += f"    대상: {prog['target']}\n"
                    result += f"    금액: {prog['amount']}\n"
                    result += f"    시기: {prog['period']}\n\n"
        
        result += """[STEP 3] 전국 단위 주요 장학금

"""
        
        if is_college:
            kosaf = SCHOLARSHIP_DATABASE["national"]["한국장학재단"]
            result += f"""한국장학재단 (필수 확인)
{kosaf['url']}
앱: 한국장학재단 (App Store / Play Store)

주요 장학금:

"""
            for prog in kosaf["programs"]:
                result += f"""  {prog['name']}
  대상: {prog['target']}
  금액: {prog['amount']}
  시기: {prog['period']}

"""
            
            result += """신청 TIP:
  1. 가구원 동의 먼저 완료 (부모님)
  2. 소득분위 확인 (홈페이지/앱)
  3. 매 학기 신청 필수
  4. 성적 기준: 직전학기 80점(B학점) 이상

"""
        
        if is_elementary or is_middle or is_high:
            moe = SCHOLARSHIP_DATABASE["national"]["교육부"]
            result += f"""교육부 교육비 지원
{moe['url']}
복지로: https://www.bokjiro.go.kr

"""
            for prog in moe["programs"]:
                if "초중고" in prog["target"]:
                    result += f"""  {prog['name']}
  대상: {prog['target']}
  내용: {prog['amount']}
  신청: {prog['period']}

"""
        
        bohun = SCHOLARSHIP_DATABASE["national"]["보훈처"]
        result += f"""
보훈처 (국가유공자 자녀 전용)
{bohun['url']}
  - {bohun['programs'][0]['name']}
  - 금액: {bohun['programs'][0]['amount']}

"""
        
        result += """[STEP 4] 민간 장학재단

"""
        
        shown_private = False
        for org_name, org_info in SCHOLARSHIP_DATABASE["private"].items():
            matching_progs = []
            
            for prog in org_info["programs"]:
                show_this = False
                
                if (is_middle or is_high) and "중고" in prog["target"]:
                    show_this = True
                if is_middle and "중학생" in prog["target"]:
                    show_this = True
                if is_college and "대학" in prog["target"]:
                    show_this = True
                
                if show_this:
                    matching_progs.append(prog)
            
            if matching_progs:
                shown_private = True
                result += f"{org_name}\n{org_info['url']}\n"
                
                for prog in matching_progs:
                    result += f"  - {prog['name']} ({prog['amount']})\n"
                result += "\n"
        
        if not shown_private:
            result += "해당 학년 민간장학금은 학교를 통해 확인하세요.\n\n"
        
        result += """[신청 전략]

우선순위:
"""
        
        if city in GYEONGGI_CITIES:
            result += f"  1순위: {GYEONGGI_CITIES[city]['foundation']} (지역 우대)\n"
        else:
            result += "  1순위: 거주지역 장학재단 확인\n"
        
        result += """  2순위: 경기도교육청/경기도청
  3순위: 한국장학재단
  4순위: 민간 재단

연간 스케줄:
  - 3월: 1학기 장학금 집중 모집
  - 9월: 2학기 장학금 집중 모집
  - 수시: 민간재단 별도 일정

"""
        
        if is_college:
            result += """합격 TIP:
  - 소득분위 낮을수록 유리
  - 성적: B학점(80점) 이상 유지
  - 국가장학금 신청시 학교장학금 자동 심사
  - 복수 지원 가능
"""
        elif is_high:
            result += """합격 TIP:
  - 내신 성적 관리 (3등급 이내 권장)
  - 학교 추천 장학금 활용
  - 교육청 우수인재 장학금 확인
  - 담임선생님께 문의
"""
        else:
            result += """합격 TIP:
  - 교육비 지원은 학교 통해 신청
  - 소득 기준 확인 필요
  - 다자녀/한부모 가정 우대
  - 담임선생님께 상담
"""
        
        result += """
주의사항:
  - 허위 신청시 환수 조치
  - 서류 누락시 자동 탈락
  - 기한 엄수
  - 가족 동의 필수

준비 서류:
  - 가족관계증명서
  - 주민등록등본
  - 소득증명원
  - 재학증명서
  - 성적증명서

"""
        
        if city == "전체":
            result += """경기도 31개 시군 장학재단:

"""
            cities_list = list(GYEONGGI_CITIES.keys())
            for i in range(0, len(cities_list), 4):
                row = cities_list[i:i+4]
                result += "  " + "  ".join(row) + "\n"
            
            result += """
거주 지역명으로 재검색하면 해당 장학재단을 우선 안내합니다.
"""
        
        result += """
문의처:
  - 한국장학재단: 1599-2000
  - 경기도교육청: 031-820-0114
  - 경기도청: 031-120
"""
        
        _cache.set(cache_key, result, ttl=86400)
        return result[:24000]
        
    except Exception as e:
        return f"오류 발생: {str(e)}"


async def gyeonggi_activity_finder(category: str = "전체") -> str:
    try:
        cache_key = f"activity_{category}"
        cached = _cache.get(cache_key)
        if cached:
            return cached

        keyword = category if category != "전체" else "대외활동"
        activities = await crawl_wevity_async(keyword)
        
        result = f"""대외활동/공모전 검색 ({len(activities)}건)

검색어: {keyword}
출처: 위비티

"""
        for i, a in enumerate(activities, 1):
            result += f"""{i}. {a['title']}
   주관: {a['org']} | {a['deadline']}
   {a['url']}

"""
        _cache.set(cache_key, result, ttl=3600)
        return result
    except Exception as e:
        return f"오류: {e}"


async def gyeonggi_event_finder(city: str = "전체", category: str = "전체") -> str:
    try:
        cache_key = f"event_{city}_{category}"
        cached_data = _cache.get(cache_key)
        if cached_data:
            return cached_data
        
        events = []
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
                    
                    keywords = ['행사', '축제', '박람회', '전시', '포럼', '설명회', '간담회', '워크숍']
                    
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        
                        title = item.get('TITLE', '')
                        cat_nm = item.get('CATEGORY_NM', '')
                        inst_nm = item.get('INST_NM', '')
                        
                        if not any(k in title or k in cat_nm for k in keywords):
                            continue
                        
                        if city != "전체":
                            if city not in title and city not in inst_nm and city not in cat_nm:
                                continue
                        
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
                                        continue
                        except:
                            pass
                        
                        events.append({
                            'title': title,
                            'org': inst_nm,
                            'category': cat_nm,
                            'deadline': deadline,
                            'url': item.get('URL', '')
                        })
        except:
            pass
        
        if not events:
            return f"""경기도 행사 검색 결과 (0건)

조건: 지역={city}, 카테고리={category}

검색 결과가 없습니다.

해결책:
- 지역을 "전체"로 검색
- 다른 지역명 시도
- 경기도청: https://www.gg.go.kr"""
        
        result = f"""경기도 행사 검색 결과 ({len(events)}건)

지역: {city} | 카테고리: {category}
업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}

"""
        
        for i, e in enumerate(events[:20], 1):
            result += f"""{i}. {e['title']}
   주관: {e['org']}
   분야: {e['category']}
   마감: {e['deadline']}
   {e['url'] if e.get('url') else ''}

"""
        
        result += """
관련 사이트:
- 경기도청: https://www.gg.go.kr
- 경기문화재단: https://www.ggcf.kr
- 경기콘텐츠진흥원: https://www.gcon.or.kr"""
        
        _cache.set(cache_key, result, ttl=7200)
        return result[:24000]
        
    except Exception as e:
        return f"오류: {str(e)}"


async def startup_support_finder(age: int = 25, region: str = "경기도") -> str:
    try:
        cache_key = f"startup_{age}_{region}"
        cached_data = _cache.get(cache_key)
        if cached_data:
            return cached_data
        
        result = f"""창업 지원 정책 안내

대상: {age}세 | 지역: {region}
업데이트: {datetime.now().strftime('%Y-%m-%d')}

"""
        
        result += """[경기도 창업 지원]

"""
        for org_name, org_info in STARTUP_POLICIES["경기도"].items():
            result += f"""{org_name}
{org_info['url']}
연락처: {org_info['contact']}

"""
            for prog in org_info["programs"]:
                if age < 40 or "전체" in prog["target"] or "스타트업" in prog["target"]:
                    result += f"""  - {prog['name']}
    대상: {prog['target']}
    지원: {prog['amount']}
    설명: {prog['desc']}

"""
        
        result += """
[중앙정부 창업 지원]

"""
        for org_name, org_info in STARTUP_POLICIES["중앙정부"].items():
            result += f"""{org_name}
{org_info['url']}
연락처: {org_info['contact']}

"""
            for prog in org_info["programs"]:
                if age < 40 or "전체" in prog.get("target", "") or not prog.get("target"):
                    result += f"""  - {prog['name']}
    대상: {prog['target']}
    지원: {prog['amount']}
    설명: {prog['desc']}

"""
        
        result += """
신청 안내:
  - 각 프로그램별 공고 확인 필수
  - 사업계획서 준비 필요
  - 연 1~2회 정기 모집
  - 온라인 신청 (K-Startup 통합)

준비사항:
  - 사업자등록증 (또는 예비창업자 증빙)
  - 사업계획서
  - 재무계획서
  - 대표자 이력서

문의처:
  - K-Startup: 1357
  - 경기테크노파크: 031-500-3000
  - 경기콘텐츠진흥원: 031-8039-9000
"""
        
        _cache.set(cache_key, result, ttl=43200)
        return result[:24000]
        
    except Exception as e:
        return f"오류: {str(e)}"


async def coding_competition_finder(level: str = "전체") -> str:
    try:
        cache_key = f"competition_{level}"
        cached_data = _cache.get(cache_key)
        if cached_data:
            return cached_data
        
        competitions = []
        
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
            }
        ])
        
        if not competitions:
            return "예정된 코딩대회가 없습니다."
        
        result = f"""코딩대회 일정 ({len(competitions)}건)

업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}

"""
        
        for i, c in enumerate(competitions[:10], 1):
            result += f"""{i}. {c['title']}
   일시: {c['date']}
   소요: {c['duration']}
   난이도: {c.get('level', 'All')}
   상금: {c.get('prize', '레이팅')}
   플랫폼: {c['platform']}
   {c['url']}

"""
        
        result += """
추천 플랫폼:
- 백준: https://www.acmicpc.net
- 프로그래머스: https://programmers.co.kr
- Codeforces: https://codeforces.com
- 경기TP: https://www.gtp.or.kr"""
        
        _cache.set(cache_key, result, ttl=21600)
        return result[:24000]
        
    except Exception as e:
        return f"오류: {str(e)}"


TOOLS_REGISTRY = {
    "gyeonggi_scholarship_finder": {
        "func": gyeonggi_scholarship_finder,
        "description": "경기도 및 전국 장학금 체계적 안내. 지역·학년별 맞춤 장학재단, 한국장학재단, 민간재단 정보",
        "schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "default": "전체"},
                "grade": {"type": "string", "default": "전체"}
            }
        }
    },
    "gyeonggi_activity_finder": {
        "func": gyeonggi_activity_finder,
        "description": "대외활동, 서포터즈, 공모전, 봉사활동 검색 (위비티 크롤링)",
        "schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "default": "전체"}
            }
        }
    },
    "gyeonggi_event_finder": {
        "func": gyeonggi_event_finder,
        "description": "경기도 문화 행사, 축제, 박람회, 전시회 정보 검색",
        "schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "default": "전체"},
                "category": {"type": "string", "default": "전체"}
            }
        }
    },
    "startup_support_finder": {
        "func": startup_support_finder,
        "description": "창업 지원 정책 안내 (경기도, K-Startup 등)",
        "schema": {
            "type": "object",
            "properties": {
                "age": {"type": "integer", "default": 25},
                "region": {"type": "string", "default": "경기도"}
            }
        }
    },
    "coding_competition_finder": {
        "func": coding_competition_finder,
        "description": "코딩 대회 일정 검색",
        "schema": {
            "type": "object",
            "properties": {
                "level": {"type": "string", "default": "전체"}
            }
        }
    }
}


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
            "status": "running",
            "tools": len(TOOLS_REGISTRY),
            "cache": cache_stats
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
                    result = result[:24000]
                
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
                "message": "Parse error"
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
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1)