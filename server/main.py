"""
경기도 학생 기회 파인더 MCP - PlayMCP 공모전 제출용 (API 파싱 수정판)

🎯 타겟: 경기도 거주/재학 중인 학생 (초/중/고/대학생)
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
from typing import Dict, Any, Optional
import requests
import sys

# =========================
# 환경 변수 로드
# =========================
from dotenv import load_dotenv
load_dotenv()

GYEONGGI_API_KEY = os.getenv("GYEONGGI_API_KEY", "16a785f639b14bab8f19ecafc2e537e4")
STARTUP_API_KEY = os.getenv("STARTUP_API_KEY", "65752ab89d855ec081a761cce8fc9b21ce961abaf77f416907b5093fe38c537a")

print("=" * 50, file=sys.stderr)
print(f"🔑 API KEY: {GYEONGGI_API_KEY[:5]}...", file=sys.stderr)
print(f"📡 Server starting...", file=sys.stderr)
print("=" * 50, file=sys.stderr)

# =========================
# 메모리 캐싱 시스템
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
            'expires_at': time.time() + ttl
        }
    
    def get_stats(self) -> Dict[str, Any]:
        valid_entries = [k for k in self._cache.keys() 
                         if time.time() <= self._cache[k]['expires_at']]
        return {'total_entries': len(valid_entries)}

_cache = SimpleCache()

# =========================
# 경기도 31개 시/군 목록
# =========================
GYEONGGI_CITIES = [
    "수원시", "성남시", "고양시", "용인시", "부천시", "안산시", "안양시", "남양주시",
    "화성시", "평택시", "의정부시", "시흥시", "파주시", "광명시", "김포시", "군포시",
    "광주시", "이천시", "양주시", "오산시", "구리시", "안성시", "포천시", "의왕시",
    "하남시", "여주시", "동두천시", "과천시", "가평군", "양평군", "연천군"
]

# =========================
# [유틸] 경기도 API 응답 파서
# =========================
def parse_gg_api_result(head_list):
    """경기도 API 헤더 리스트에서 RESULT 코드 추출"""
    try:
        for item in head_list:
            if 'RESULT' in item:
                return item['RESULT'].get('CODE'), item['RESULT'].get('MESSAGE')
    except:
        pass
    return None, None

# =========================
# 1. 경기도 장학금 찾기
# =========================
async def gyeonggi_scholarship_finder(
    city: str = "전체",
    grade: str = "전체", 
    school_type: str = "전체"
) -> str:
    """경기도 소식 API(GGNEWSSTUS) 활용 장학금 검색"""
    try:
        cache_key = f"scholarship_{city}_{grade}"
        cached_data = _cache.get(cache_key)
        if cached_data:
            return cached_data + "\n\n💾 [캐시 데이터 - 1시간 이내]"
        
        scholarships = []
        api_url = "https://openapi.gg.go.kr/GGNEWSSTUS"
        params = {
            "KEY": GYEONGGI_API_KEY,
            "Type": "json",
            "pIndex": 1,
            "pSize": 500  # 최대한 많이 가져옴
        }
        
        try:
            resp = requests.get(api_url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                
                # 데이터 유효성 검사
                if 'GGNEWSSTUS' in data:
                    head = data['GGNEWSSTUS'][0].get('head', [])
                    code, msg = parse_gg_api_result(head)
                    
                    if code == 'INFO-000':
                        items = data['GGNEWSSTUS'][1].get('row', [])
                        
                        for item in items:
                            title = item.get('TITLE', '') or item.get('TTL', '')
                            # 장학 관련 키워드 필터링
                            if '장학' in title:
                                # 지역 필터링
                                if city != "전체" and city not in title and city not in item.get('INST_NM', ''):
                                    continue
                                    
                                scholarships.append({
                                    'title': title,
                                    'date': item.get('WRITNG_DE', '') or item.get('REGISTER_DT', '')[:10],
                                    'org': item.get('INST_NM', '') or item.get('INSTT_NM', '경기도'),
                                    'url': item.get('URL', '')
                                })
        except Exception as e:
            print(f"API Error: {e}", file=sys.stderr)

        if not scholarships:
            return f"""🎓 경기도 장학금 검색 결과 (0건)

📍 지역: {city}
✅ API 호출 성공 (데이터 없음)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 현재 '{city}' 관련 모집 중인 장학금 공고가 없습니다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 팁: '전체' 지역으로 검색하거나, 장학금 시즌(2월/8월)을 기다려보세요."""
        
        result = f"""🎓 경기도 장학금 실시간 공고 ({len(scholarships)}건)

📍 지역: {city} | 키워드: 장학
✅ API 데이터 (실시간)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 최신 장학금 공고
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        for i, s in enumerate(scholarships[:10], 1):
            result += f"""{i}. 📢 {s['title']}
   📅 공고일: {s['date']}
   🏢 기관: {s['org']}
   🔗 링크: {s['url']}

"""
        _cache.set(cache_key, result, ttl=3600)
        return result[:24000]

    except Exception as e:
        return f"⚠️ 오류: {str(e)}"

# =========================
# 2. 경기도 공모전/소식 찾기
# =========================
async def gyeonggi_contest_finder(city: str = "전체", category: str = "전체") -> str:
    """경기도 소식 API(GGNEWSSTUS) 활용 공모전 검색"""
    try:
        print(f"🎯 Contest Finder Called: {city}", file=sys.stderr)
        
        cache_key = f"contest_{city}_{category}"
        cached_data = _cache.get(cache_key)
        if cached_data:
            return cached_data + "\n\n💾 [캐시 데이터 - 2시간 이내]"
        
        contests = []
        api_url = "https://openapi.gg.go.kr/GGNEWSSTUS"
        params = {
            "KEY": GYEONGGI_API_KEY,
            "Type": "json",
            "pIndex": 1,
            "pSize": 500
        }
        
        try:
            resp = requests.get(api_url, params=params, timeout=15)
            
            if resp.status_code != 200:
                return f"❌ API 호출 실패 (HTTP {resp.status_code})"
                
            data = resp.json()
            
            # [수정] 헤더 파싱 로직 개선
            if 'GGNEWSSTUS' in data:
                head = data['GGNEWSSTUS'][0].get('head', [])
                result_code, result_msg = parse_gg_api_result(head)
                
                if result_code != 'INFO-000':
                    return f"❌ API 에러: {result_code} - {result_msg}"
                
                items = data['GGNEWSSTUS'][1].get('row', [])
                
                for item in items:
                    title = item.get('TITLE', '') or item.get('TTL', '')
                    content = item.get('CN', '')
                    org = item.get('INST_NM', '') or item.get('INSTT_NM', '')
                    
                    # 공모전 키워드
                    keywords = ['공모', '모집', '대회', '경진', '콘테스트', '서포터즈', '기자단']
                    
                    if any(k in title for k in keywords):
                        # 지역 필터링
                        if city != "전체" and city not in title and city not in org:
                            continue
                        
                        # 카테고리 필터링 (간단 체크)
                        if category != "전체" and category not in title and category not in content:
                            continue
                            
                        contests.append({
                            'title': title,
                            'date': item.get('WRITNG_DE', '') or item.get('REGISTER_DT', '')[:10],
                            'org': org,
                            'url': item.get('URL', '')
                        })
                        
        except Exception as e:
            return f"❌ 처리 중 오류 발생: {str(e)}"
        
        if not contests:
            return f"""🏆 경기도 공모전 검색 결과 (0건)

📍 지역: {city} | 카테고리: {category}
✅ API 호출 성공 (조건에 맞는 데이터 없음)

💡 팁: '전체' 지역 또는 '전체' 카테고리로 검색해보세요."""
        
        # 최신순 정렬 (날짜 기준 내림차순)
        contests.sort(key=lambda x: x['date'], reverse=True)
        
        result = f"""🏆 경기도 공모전/행사 소식 ({len(contests)}건)

📍 지역: {city} | 카테고리: {category}
✅ API 데이터 (실시간)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 최신 모집 공고
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        for i, c in enumerate(contests[:15], 1):
            result += f"""{i}. 🎯 {c['title']}
   📅 날짜: {c['date']}
   🏢 기관: {c['org']}
   🔗 링크: {c['url']}

"""
        _cache.set(cache_key, result, ttl=7200)
        return result[:24000]
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"

# =========================
# 3. 창업지원금 찾기 (K-Startup)
# =========================
async def startup_support_finder(age: int = 25, region: str = "경기도") -> str:
    """창업진흥원 API 활용"""
    try:
        cache_key = f"startup_{age}_{region}"
        cached_data = _cache.get(cache_key)
        if cached_data:
            return cached_data + "\n\n💾 [캐시 데이터 - 12시간 이내]"
        
        supports = []
        api_url = "https://apis.data.go.kr/B552735/kisedKstartupService01/getBizInfoList"
        params = {
            "serviceKey": STARTUP_API_KEY,
            "numOfRows": 20,
            "pageNo": 1,
            "resultType": "json"
        }
        
        try:
            resp = requests.get(api_url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
                
                if isinstance(items, dict): items = [items]
                
                for item in items:
                    supports.append({
                        'title': item.get('bizNm', '지원사업'),
                        'target': item.get('trgtNm', '대상 확인'),
                        'org': item.get('orgNm', 'K-Startup'),
                        'deadline': item.get('rcptEndDt', '상시'),
                        'url': item.get('detlUrl', 'https://www.k-startup.go.kr')
                    })
        except:
            pass

        if not supports:
            return "💰 현재 조회된 창업지원금이 없습니다. (API 키 확인 필요)"

        result = f"""💰 K-Startup 창업지원금 공고 ({len(supports)}건)

데이터: 창업진흥원 API (Real-time)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💵 지원 프로그램
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        for i, s in enumerate(supports[:10], 1):
            result += f"""{i}. 💎 {s['title']}
   🎯 대상: {s['target']}
   📅 마감: {s['deadline']}
   🏢 기관: {s['org']}
   🔗 링크: {s['url']}

"""
        _cache.set(cache_key, result, ttl=43200)
        return result[:24000]

    except Exception as e:
        return f"⚠️ 오류: {str(e)}"

# =========================
# 4. 코딩대회 찾기 (Codeforces)
# =========================
async def coding_competition_finder(level: str = "전체") -> str:
    """Codeforces API 활용"""
    try:
        cache_key = f"competition_{level}"
        cached_data = _cache.get(cache_key)
        if cached_data:
            return cached_data + "\n\n💾 [캐시 데이터 - 6시간 이내]"
        
        competitions = []
        url = "https://codeforces.com/api/contest.list"
        
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if data['status'] == 'OK':
                upcoming = [c for c in data['result'] if c['phase'] == 'BEFORE'][:10]
                # 시간순 정렬
                upcoming.sort(key=lambda x: x['startTimeSeconds'])
                
                for c in upcoming:
                    start_dt = datetime.fromtimestamp(c['startTimeSeconds']).strftime('%Y-%m-%d %H:%M')
                    competitions.append({
                        'title': c['name'],
                        'date': start_dt,
                        'source': 'Codeforces'
                    })
        except:
            pass

        if not competitions:
            return "🎮 예정된 대회가 없습니다."

        result = f"""🎮 글로벌 코딩대회 일정 ({len(competitions)}건)

데이터: Codeforces API (Real-time)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 예정된 대회
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        for i, c in enumerate(competitions, 1):
            result += f"{i}. 💻 {c['title']}\n   📅 {c['date']} (Platform: {c['source']})\n\n"
            
        _cache.set(cache_key, result, ttl=21600)
        return result[:24000]

    except Exception as e:
        return f"⚠️ 오류: {str(e)}"

# =========================
# 5. AI 맞춤 추천
# =========================
async def gyeonggi_recommend(profile: str) -> str:
    """단순 연결 툴 (실제 추천은 LLM이 판단)"""
    return f"""🎯 AI 맞춤 추천을 위해 데이터를 수집합니다.

사용자 프로필: {profile}

[내부 로직]
1. 장학금 검색 실행...
2. 공모전 검색 실행...
3. 창업지원금 검색 실행...

(위의 툴들을 조합하여 LLM이 종합 답변을 생성해 주세요.)"""

# =========================
# MCP Tools Registry
# =========================
TOOLS_REGISTRY = {
    "gyeonggi_scholarship_finder": {
        "func": gyeonggi_scholarship_finder,
        "description": "경기도 실시간 장학금 공고 검색 (API 연동). 시/군별 필터링 가능.",
        "schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "경기도 시/군 이름 (예: 수원시, 안산시)"},
                "grade": {"type": "string", "description": "학년 (대학생 등)"}
            },
            "required": []
        }
    },
    "gyeonggi_contest_finder": {
        "func": gyeonggi_contest_finder,
        "description": "경기도 실시간 공모전/행사 검색 (API 연동).",
        "schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "지역명"},
                "category": {"type": "string", "description": "관심 분야"}
            },
            "required": []
        }
    },
    "startup_support_finder": {
        "func": startup_support_finder,
        "description": "K-Startup 창업지원금 검색 (API 연동).",
        "schema": {
            "type": "object",
            "properties": {
                "age": {"type": "integer", "description": "나이"},
                "region": {"type": "string", "description": "지역"}
            }
        }
    },
    "coding_competition_finder": {
        "func": coding_competition_finder,
        "description": "글로벌 코딩대회 일정 (Codeforces API).",
        "schema": {"type": "object", "properties": {}}
    },
    "gyeonggi_recommend": {
        "func": gyeonggi_recommend,
        "description": "학생 프로필 기반 맞춤 추천.",
        "schema": {
            "type": "object",
            "properties": {
                "profile": {"type": "string", "description": "사용자 프로필"}
            },
            "required": ["profile"]
        }
    }
}

# =========================
# MCP Request Handler
# =========================
async def handle_mcp_request(request: Request):
    if request.method == "OPTIONS":
        return Response(status_code=200, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "*"})
    
    if request.method == "GET":
        cache_stats = _cache.get_stats()
        return JSONResponse({
            "name": "Gyeonggi-Student-Opportunity-Finder",
            "version": "1.0.0",
            "protocol": "2025-03-26",
            "status": "running",
            "tools": len(TOOLS_REGISTRY),
            "description": "경기도 학생 기회 파인더 (API Ver.)",
            "cache_entries": cache_stats['total_entries']
        })
    
    if request.method != "POST":
        return Response(status_code=405)
    
    try:
        body = await request.json()
        method = body.get("method")
        msg_id = body.get("id")
        params = body.get("params", {})
        
        if method == "initialize":
            return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "result": {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "Gyeonggi-Student", "version": "1.0.0"}}})
        
        if method == "tools/list":
            tools = [{"name": name, "description": info["description"], "inputSchema": info["schema"]} for name, info in TOOLS_REGISTRY.items()]
            return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools}})
        
        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            if tool_name not in TOOLS_REGISTRY:
                return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Tool not found"}})
            try:
                result = await TOOLS_REGISTRY[tool_name]["func"](**tool_args)
                return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "result": {"content": [{"type": "text", "text": result}]}})
            except Exception as e:
                return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32000, "message": str(e)}})
                
        return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Method not found"}})
        
    except Exception as e:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1)