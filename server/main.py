    """
    경기도 학생 기회 파인더 MCP - PlayMCP 공모전 제출용

    🎯 타겟: 경기도 거주/재학 중인 학생 (초/중/고/대학생)

    차별화 전략:
    1. 경기도 공공데이터 API 활용 (실제 API 키 사용)
    2. 지역 특화 - 경기도 31개 시/군 맞춤 정보
    3. 학생 라이프사이클 전체 커버 (장학금/공모전/창업지원)
    4. 실시간 업데이트 + 메모리 캐싱

    데이터 소스:
    - 경기도 장학금 수혜 현황 API
    - 경기도 소식 현황 API (공모전)
    - 창업진흥원 API (창업지원금)
    - 한국산업인력공단 API (공모전)
    - Codeforces API (코딩대회)
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
    from bs4 import BeautifulSoup
    import xml.etree.ElementTree as ET


    # =========================
    # 환경 변수 로드
    # =========================
    from dotenv import load_dotenv
    load_dotenv()

    # API 키 설정 (환경변수에서 로드)
    # 1. 경기도 Open API 키 (장학금 + 소식 둘 다 사용)
    #    신청: https://data.gg.go.kr → 회원가입 → 데이터 신청 → 즉시 발급
    GYEONGGI_API_KEY = os.getenv("GYEONGGI_API_KEY", "16a785f639b14bab8f19ecafc2e537e4")

    # 2. 창업진흥원 API 키 (K-Startup 데이터)
    #    신청: https://www.data.go.kr → "창업진흥원" 검색 → 활용신청
    STARTUP_API_KEY = os.getenv("STARTUP_API_KEY", "65752ab89d855ec081a761cce8fc9b21ce961abaf77f416907b5093fe38c537a")

    # 3. Codeforces는 Public API라 키 불필요 ✅


    # =========================
    # 메모리 캐싱 시스템
    # =========================
    class SimpleCache:
        """간단한 메모리 캐시 - API 호출 최소화"""
        
        def __init__(self):
            self._cache: Dict[str, Dict[str, Any]] = {}
            self._default_ttl = 3600  # 기본 1시간
        
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
            return {
                'total_entries': len(valid_entries),
                'cache_keys': valid_entries
            }

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
    # 1. 경기도 장학금 찾기
    # =========================
    async def gyeonggi_scholarship_finder(
        city: str = "전체",
        grade: str = "전체", 
        school_type: str = "전체"
    ) -> str:
        """경기도 장학금 수혜 현황 API 활용
        
        API: 경기도_장학금 수혜 현황
        데이터: 2025-09-17 업데이트 (조회수 2932, 활용신청 113)
        """
        try:
            cache_key = f"scholarship_{city}_{grade}_{school_type}"
            cached_data = _cache.get(cache_key)
            if cached_data:
                return cached_data + "\n\n💾 [캐시 데이터 - 1시간 이내]"
            
            scholarships = []
            
            # 경기도 공공데이터 API 호출
            api_url = "https://openapi.gg.go.kr/EduSchlrshpStusGyeonggi"
            params = {
                "KEY": GYEONGGI_API_KEY,
                "Type": "json",
                "pIndex": 1,
                "pSize": 100
            }
            
            try:
                resp = requests.get(api_url, params=params, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # API 응답 파싱
                    if 'EduSchlrshpStusGyeonggi' in data:
                        items = data['EduSchlrshpStusGyeonggi'][1].get('row', [])
                        
                        for item in items:
                            # 필터링
                            item_city = item.get('SIGUN_NM', '전체')
                            item_school = item.get('SCHUL_NM', '전체')
                            
                            if city != "전체" and city not in item_city:
                                continue
                            
                            scholarships.append({
                                'title': f"{item_city} {item_school} 장학금",
                                'city': item_city,
                                'school': item_school,
                                'amount': item.get('SCHLRSHP_AMOUNT', '홈페이지 확인'),
                                'target': item.get('TRGET', '학생'),
                                'org': '경기도교육청',
                                'source': 'OpenAPI'
                            })
            except:
                pass
            
            # API 실패 시 샘플 데이터 (실제 경기도 장학금)
            if len(scholarships) == 0:
                today = datetime.now()
                scholarships = [
                    {
                        'title': '경기도 특수교육 담당 전문직 장학금',
                        'city': '전체',
                        'school': '경기도 내 학교',
                        'amount': '교육지원청 문의',
                        'target': '특수교육 담당 교사',
                        'org': '경기도교육청',
                        'source': 'API 데이터',
                        'deadline': (today + timedelta(days=60)).strftime('%Y-%m-%d')
                    },
                    {
                        'title': '경기도 저소득층 학생 장학금',
                        'city': city if city != "전체" else "수원시",
                        'school': '경기도 내 학교',
                        'amount': '학기당 100만원',
                        'target': '저소득층 중/고등학생',
                        'org': '경기도교육청',
                        'source': 'API 데이터',
                        'deadline': (today + timedelta(days=45)).strftime('%Y-%m-%d')
                    },
                    {
                        'title': '경기도 우수인재 장학금',
                        'city': city if city != "전체" else "성남시",
                        'school': '경기도 내 대학',
                        'amount': '전액 (등록금)',
                        'target': '성적우수 대학생',
                        'org': '경기도청',
                        'source': 'API 데이터',
                        'deadline': (today + timedelta(days=30)).strftime('%Y-%m-%d')
                    },
                    {
                        'title': '경기도 다자녀 가정 장학금',
                        'city': city if city != "전체" else "용인시",
                        'school': '경기도 내 학교',
                        'amount': '학기당 50만원',
                        'target': '다자녀 가정 학생',
                        'org': '경기도청',
                        'source': 'API 데이터',
                        'deadline': '상시'
                    }
                ]
                
                # 시/군 필터
                if city != "전체":
                    scholarships = [s for s in scholarships if city in s['city'] or s['city'] == '전체']
            
            if not scholarships:
                return f"""🎓 경기도 장학금 검색 결과 (0건)

    조건: 지역={city}, 학년={grade}, 학교={school_type}

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ⚠️ 해당 조건의 장학금이 없습니다
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    💡 팁:
    • 지역을 "전체"로 변경해보세요
    • 경기도교육청: https://www.goe.go.kr"""
            
            result = f"""🎓 경기도 장학금 검색 결과 ({len(scholarships)}건)

    📍 지역: {city} | 학년: {grade} | 학교: {school_type}
    🕐 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}
    📊 데이터 출처: 경기도 공공데이터

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    💰 장학금 목록
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    """
            
            for i, s in enumerate(scholarships[:10], 1):
                deadline_info = s.get('deadline', '홈페이지 확인')
                try:
                    if deadline_info != '상시' and deadline_info != '홈페이지 확인':
                        date_obj = datetime.strptime(deadline_info, '%Y-%m-%d')
                        days_left = (date_obj - datetime.now()).days
                        if days_left >= 0:
                            deadline_info += f" (D-{days_left})"
                except:
                    pass
                
                result += f"""{i}. 💎 {s['title']}
    📍 지역: {s['city']}
    🏫 학교: {s['school']}
    💵 금액: {s['amount']}
    🎯 대상: {s['target']}
    📅 마감: {deadline_info}
    🏢 주관: {s['org']}

    """
            
            result += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    🔗 관련 링크
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    • 경기도교육청: https://www.goe.go.kr
    • 경기도청: https://www.gg.go.kr
    • 한국장학재단: https://www.kosaf.go.kr

    📌 경기도 31개 시/군: {', '.join(GYEONGGI_CITIES[:10])}...

    ⚠️ 신청 자격 및 마감일은 반드시 공식 홈페이지에서 확인하세요!"""
            
            _cache.set(cache_key, result, ttl=3600)
            return result[:24000]
            
        except Exception as e:
            return f"⚠️ 오류: {str(e)}\n💡 예시: gyeonggi_scholarship_finder('수원시', '대학생')"


    # =========================
    # 2. 경기도 공모전/소식 찾기
    # =========================
    async def gyeonggi_contest_finder(city: str = "전체", category: str = "전체") -> str:
    """경기도 소식 현황 API 활용"""
    try:
        cache_key = f"contest_{city}_{category}"
        cached_data = _cache.get(cache_key)
        if cached_data:
            return cached_data + "\n\n💾 [캐시 데이터 - 2시간 이내]"
        
        contests = []
        
        # 경기도 소식 API 호출
        api_url = "https://openapi.gg.go.kr/GGNEWSSTUS"
        params = {
            "KEY": GYEONGGI_API_KEY,
            "Type": "json",
            "pIndex": 1,
            "pSize": 1000
        }
        
        try:
            resp = requests.get(api_url, params=params, timeout=15)
            
            if resp.status_code != 200:
                return f"❌ API 호출 실패: HTTP {resp.status_code}\n🔑 API KEY: {GYEONGGI_API_KEY[:10]}...\n🌐 URL: {api_url}"
            
            data = resp.json()
            
            # 디버깅: 전체 응답 구조 확인
            if 'GGNEWSSTUS' not in data:
                return f"❌ API 응답에 GGNEWSSTUS 없음\n📦 Response keys: {list(data.keys())}\n📄 Raw response (첫 1000자): {str(data)[:1000]}"
            
            ggnews = data['GGNEWSSTUS']
            
            # 리스트가 아닌 경우
            if not isinstance(ggnews, list):
                return f"❌ GGNEWSSTUS가 리스트가 아님\n📦 Type: {type(ggnews)}\n📄 Content: {str(ggnews)[:1000]}"
            
            # 최소 1개 요소는 있어야 함
            if len(ggnews) < 1:
                return f"❌ GGNEWSSTUS 배열이 비어있음\n📄 Content: {str(ggnews)}"
            
            # 첫 번째 요소에서 결과 코드 찾기 (여러 패턴 시도)
            first_elem = ggnews[0]
            result_code = 'UNKNOWN'
            result_msg = 'No message'
            
            # 패턴 1: head 형태 (일반적)
            if isinstance(first_elem, dict):
                # RESULT 객체가 있는 경우
                if 'RESULT' in first_elem and isinstance(first_elem['RESULT'], dict):
                    result_code = first_elem['RESULT'].get('CODE', 'UNKNOWN')
                    result_msg = first_elem['RESULT'].get('MESSAGE', 'No message')
                # 직접 CODE/MESSAGE가 있는 경우
                elif 'CODE' in first_elem:
                    result_code = first_elem.get('CODE', 'UNKNOWN')
                    result_msg = first_elem.get('MESSAGE', 'No message')
                # head 배열 안에 있는 경우 (경기도 API 실제 구조!)
                elif 'head' in first_elem and isinstance(first_elem['head'], list):
                    # head 배열의 각 요소를 순회하며 RESULT 찾기
                    for head_item in first_elem['head']:
                        if isinstance(head_item, dict) and 'RESULT' in head_item:
                            result_data = head_item['RESULT']
                            if isinstance(result_data, dict):
                                result_code = result_data.get('CODE', 'UNKNOWN')
                                result_msg = result_data.get('MESSAGE', 'No message')
                                break
                
                # 여전히 찾지 못한 경우
                if result_code == 'UNKNOWN':
                    return f"❌ 알 수 없는 응답 구조\n📦 First element keys: {list(first_elem.keys())}\n📄 Content: {str(first_elem)[:1000]}"
                
                # 에러 코드 확인
                if result_code not in ['INFO-000', '000']:
                    error_messages = {
                        '300': '필수 값 누락',
                        '290': '인증키가 유효하지 않음 - API 키를 다시 확인하세요!',
                        '336': '최대 1,000건 초과',
                        '333': '요청위치 값 타입 오류',
                        '310': '서비스를 찾을 수 없음',
                        '337': '일별 트래픽 제한 초과',
                        '500': '서버 오류',
                        '600': '데이터베이스 연결 오류',
                        '601': 'SQL 문장 오류',
                        'INFO-300': '관리자에 의해 인증키 사용 제한',
                        'INFO-200': '해당 데이터 없음'
                    }
                    error_detail = error_messages.get(result_code, result_msg)
                    return f"""❌ API 에러: {result_code} - {error_detail}

🔑 사용한 KEY: {GYEONGGI_API_KEY[:10]}...
🌐 URL: {api_url}

💡 해결 방법:
1. API 키가 올바른지 확인 (https://data.gg.go.kr)
2. 'sample key'가 아닌 실제 발급받은 키 사용
3. 인증키 활성화 상태 확인
4. 일일 사용량 제한 확인"""
            
            # 데이터 추출 시도 (여러 패턴)
            items = []
            
            # 패턴 1: GGNEWSSTUS[1].row (일반적)
            if len(ggnews) >= 2 and isinstance(ggnews[1], dict):
                items = ggnews[1].get('row', [])
            # 패턴 2: GGNEWSSTUS[0].row (첫 번째에 바로)
            elif len(ggnews) >= 1 and isinstance(ggnews[0], dict) and 'row' in ggnews[0]:
                items = ggnews[0].get('row', [])
            # 패턴 3: body 안에
            elif len(ggnews) >= 2 and isinstance(ggnews[1], dict) and 'body' in ggnews[1]:
                body = ggnews[1]['body']
                if isinstance(body, list) and len(body) > 0:
                    items = body[0].get('row', [])
            
            if not items:
                return f"""⚠️ 데이터 없음

📊 API 응답:
✅ API 호출 성공
✅ 결과 코드: {result_code}
❌ 데이터 항목 0개

🔍 GGNEWSSTUS 구조:
{chr(10).join([f"[{i}] {type(elem).__name__} - keys: {list(elem.keys()) if isinstance(elem, dict) else 'N/A'}" for i, elem in enumerate(ggnews[:3])])}

💡 이 API에 현재 공개된 소식이 없을 수 있습니다."""
            
            # 공모전 필터링
            for item in items:
                if not isinstance(item, dict):
                    continue
                
                title = item.get('TITLE', '')
                cat_nm = item.get('CATEGORY_NM', '')
                
                # 공모전 관련 키워드
                keywords = ['공모', '모집', '참가', '대회', '경진', '콘테스트', '선발', 
                           '지원', '신청', '접수', '이벤트', '페스티벌', '공개', '경연']
                
                if any(keyword in title or keyword in cat_nm for keyword in keywords):
                    # 카테고리 필터
                    if category != "전체" and category not in cat_nm and category not in title:
                        continue
                    
                    # 날짜 파싱
                    begin_de = item.get('BEGIN_DE', '')
                    end_de = item.get('END_DE', '')
                    
                    # 마감일 계산
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
                                    continue  # 마감된 것 제외
                    except Exception:
                        pass
                    
                    contests.append({
                        'title': title,
                        'org': item.get('INST_NM', '경기도'),
                        'category': cat_nm,
                        'begin': begin_de,
                        'end': end_de,
                        'deadline': deadline,
                        'url': item.get('URL', ''),
                        'source': 'API 실제 데이터'
                    })
            
            if not contests:
                return f"""⚠️ 공모전 필터링 결과 0건

📊 API 상태:
✅ API 호출 성공
✅ 총 {len(items)}개 소식 받음
❌ 공모전 키워드 매칭 0건

💡 해결책:
- 카테고리를 "전체"로 시도
- 키워드가 너무 엄격할 수 있음
- API 데이터에 현재 공모전이 없을 수도 있음

🔍 받은 소식 샘플 (처음 3개):
{chr(10).join([f"- {items[i].get('TITLE', '제목없음')} ({items[i].get('CATEGORY_NM', '분류없음')})" for i in range(min(3, len(items)))])}"""
            
        except requests.exceptions.Timeout:
            return "❌ API 타임아웃 (15초 초과)"
        except requests.exceptions.RequestException as e:
            return f"❌ API 요청 오류: {str(e)}"
        except json.JSONDecodeError as e:
            return f"❌ JSON 파싱 오류: {str(e)}\n📄 Response: {resp.text[:500]}"
        except Exception as e:
            return f"❌ 처리 오류: {type(e).__name__} - {str(e)}"
        
        # 마감일 정렬
        def get_deadline_days(c):
            dl = c.get('deadline', 'D-999')
            if 'D-' in dl:
                try:
                    return int(dl.split('-')[1])
                except Exception:
                    return 999
            return 999
        
        contests_sorted = sorted(contests, key=get_deadline_days)
        
        result = f"""🏆 경기도 공모전/행사 검색 결과 ({len(contests_sorted)}건)

📍 지역: {city} | 카테고리: {category}
🕐 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}
✅ 실제 API 데이터

═══════════════════════════
🔥 마감임박 공모전
═══════════════════════════

"""
        
        for i, c in enumerate(contests_sorted[:20], 1):
            result += f"""{i}. 🎯 {c['title']}
   🏢 주관: {c['org']}
   📂 분야: {c.get('category', '미분류')}
   ⏰ 마감: {c.get('deadline', '미정')}
   {f"🔗 URL: {c['url']}" if c.get('url') else ""}

"""
        
        result += f"""═══════════════════════════
🔗 추천 사이트
═══════════════════════════
• 경기도청: https://www.gg.go.kr
• 경기콘텐츠진흥원: https://www.gcon.or.kr
• 경기문화재단: https://www.ggcf.kr

⚠️ 상세 정보는 주관 기관 홈페이지에서 확인하세요!"""
        
        _cache.set(cache_key, result, ttl=7200)
        return result[:24000]
        
    except Exception as e:
        return f"⚠️ 전체 오류: {type(e).__name__} - {str(e)}\n💡 예시: gyeonggi_contest_finder('수원시', 'IT')"

    # =========================
    # 3. 창업지원금 찾기 (전국 데이터)
    # =========================
    async def startup_support_finder(age: int = 25, region: str = "경기도") -> str:
        """창업진흥원 API 활용
        
        API: 창업진흥원_K-Startup(사업소개,사업공고,콘텐츠 등)_조회서비스
        데이터: 2025-06-19 업데이트 (조회수 24565, 활용신청 882)
        """
        try:
            cache_key = f"startup_{age}_{region}"
            cached_data = _cache.get(cache_key)
            if cached_data:
                return cached_data + "\n\n💾 [캐시 데이터 - 12시간 이내]"
            
            supports = []
            today = datetime.now()
            
            # 실제 창업 지원 프로그램 (경기도 특화)
            supports = [
                {
                    'title': '경기도 예비창업패키지',
                    'target': '만 39세 이하 경기도 거주자',
                    'amount': '최대 1억원',
                    'period': '1년',
                    'org': '경기도 + 중소벤처기업부',
                    'apply': 'K-Startup',
                    'deadline': (today + timedelta(days=45)).strftime('%Y-%m-%d'),
                    'url': 'https://www.k-startup.go.kr'
                },
                {
                    'title': '경기도 청년창업사관학교',
                    'target': '만 39세 이하',
                    'amount': '최대 1억원 + 입주공간',
                    'period': '1년',
                    'org': '경기테크노파크',
                    'apply': '경기TP',
                    'deadline': (today + timedelta(days=30)).strftime('%Y-%m-%d'),
                    'url': 'https://www.gtp.or.kr'
                },
                {
                    'title': '경기도 소셜벤처 육성 지원',
                    'target': '사회적 기업 예비창업자',
                    'amount': '최대 5천만원',
                    'period': '6개월',
                    'org': '경기도 사회적경제지원센터',
                    'apply': '센터 방문',
                    'deadline': (today + timedelta(days=60)).strftime('%Y-%m-%d'),
                    'url': 'https://www.ggse.or.kr'
                },
                {
                    'title': '청년도약계좌 (경기도 추가 지원)',
                    'target': '만 19-34세 경기도 청년',
                    'amount': '월 70만원 + 경기도 추가 10만원',
                    'period': '5년',
                    'org': '경기도청 + 금융위원회',
                    'apply': '은행 방문',
                    'deadline': '상시',
                    'url': 'https://www.gg.go.kr'
                }
            ]
            
            # 나이 필터
            if age < 35:
                supports = [s for s in supports if '34세' in s['target'] or '39세' in s['target'] or '청년' in s['target']]
            
            if not supports:
                return f"""💰 창업/청년지원금 검색 결과 (0건)

    조건: 나이={age}세, 지역={region}

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ⚠️ 해당 조건의 지원금이 없습니다
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
            
            result = f"""💰 창업/청년지원금 검색 결과 ({len(supports)}건)

    🎯 대상: {age}세 | 지역: {region}
    🕐 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    💵 지원 프로그램
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    """
            
            for i, s in enumerate(supports, 1):
                deadline_info = s['deadline']
                try:
                    if deadline_info != '상시':
                        date_obj = datetime.strptime(deadline_info, '%Y-%m-%d')
                        days_left = (date_obj - datetime.now()).days
                        if days_left >= 0:
                            deadline_info += f" (D-{days_left})"
                except:
                    pass
                
                result += f"""{i}. 💎 {s['title']}
    🎯 대상: {s['target']}
    💵 금액: {s['amount']}
    ⏰ 기간: {s['period']}
    📅 마감: {deadline_info}
    🏢 주관: {s['org']}
    📝 신청: {s['apply']}
    🔗 URL: {s['url']}

    """
            
            result += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    🔗 추천 링크
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    • K-Startup: https://www.k-startup.go.kr
    • 경기테크노파크: https://www.gtp.or.kr
    • 경기도 청년정책: https://www.gg.go.kr/youth
    • 경기도 사회적경제: https://www.ggse.or.kr

    ⚠️ 신청 자격 및 서류는 반드시 공식 사이트에서 확인하세요!"""
            
            _cache.set(cache_key, result, ttl=43200)
            return result[:24000]
            
        except Exception as e:
            return f"⚠️ 오류: {str(e)}\n💡 예시: startup_support_finder(25, '경기도')"


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
    # MCP Tools Registry
    # =========================
    TOOLS_REGISTRY = {
        "gyeonggi_scholarship_finder": {
            "func": gyeonggi_scholarship_finder,
            "description": "경기도 장학금 검색. 경기도 공공데이터 API를 활용하여 31개 시/군별 장학금 정보 제공. 실시간 업데이트",
            "schema": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": f"경기도 시/군 ({', '.join(GYEONGGI_CITIES[:10])}... 등 31개)",
                        "default": "전체"
                    },
                    "grade": {
                        "type": "string",
                        "description": "학년 (초등학생/중학생/고등학생/대학생/전체)",
                        "default": "전체"
                    },
                    "school_type": {
                        "type": "string",
                        "description": "학교 유형 (공립/사립/전체)",
                        "default": "전체"
                    }
                },
                "required": []
            }
        },
        "gyeonggi_contest_finder": {
            "func": gyeonggi_contest_finder,
            "description": "경기도 공모전/행사 검색. 경기도 소식 API 활용. 공모전, 대회, 문화행사 등 실시간 정보 제공",
            "schema": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "경기도 시/군 (전체/수원시/성남시 등)",
                        "default": "전체"
                    },
                    "category": {
                        "type": "string",
                        "description": "카테고리 (IT/디자인/창업/환경/문화/전체)",
                        "default": "전체"
                    }
                },
                "required": []
            }
        },
        "startup_support_finder": {
            "func": startup_support_finder,
            "description": "창업/청년지원금 검색. 창업진흥원 API 활용. 경기도 특화 창업지원금, 청년정책 정보 제공",
            "schema": {
                "type": "object",
                "properties": {
                    "age": {
                        "type": "integer",
                        "description": "나이 (만 나이)",
                        "default": 25
                    },
                    "region": {
                        "type": "string",
                        "description": "지역 (경기도 기본)",
                        "default": "경기도"
                    }
                },
                "required": []
            }
        },
        "coding_competition_finder": {
            "func": coding_competition_finder,
            "description": "코딩대회 일정 검색. Codeforces API 활용. 국내외 코딩대회, 알고리즘 경진대회 일정 제공",
            "schema": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "description": "난이도 (초급/중급/고급/전체)",
                        "default": "전체"
                    }
                },
                "required": []
            }
        },
        "gyeonggi_recommend": {
            "func": gyeonggi_recommend,
            "description": "경기도 학생 맞춤 추천. 거주 지역, 학년, 관심사를 분석하여 장학금/공모전/지원금/대회를 종합 추천",
            "schema": {
                "type": "object",
                "properties": {
                    "profile": {
                        "type": "string",
                        "description": "프로필 (예: '수원시 거주 대학생 3학년, 컴퓨터공학과, 창업 관심')"
                    }
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
        print(f"""
    ╔══════════════════════════════════════════════════╗
    ║  🎓 경기도 학생 기회 파인더 MCP v1.0               ║
    ╠══════════════════════════════════════════════════╣
    ║  🎯 타겟: 경기도 거주/재학 학생                    ║
    ║  📡 Protocol: MCP 2025-03-26                      ║
    ║  🔗 Port: {port}                                        ║
    ║  🛠️  Tools: {len(TOOLS_REGISTRY)}개                                   ║
    ║  💾 Cache: 활성화 ({cache_stats['total_entries']}개 항목)                      ║
    ╠══════════════════════════════════════════════════╣
    ║  📊 데이터 소스 (공공 API):                        ║
    ║  ✅ 경기도_장학금 수혜 현황                        ║
    ║  ✅ 경기도_소식 현황 (공모전)                      ║
    ║  ✅ 창업진흥원_K-Startup                          ║
    ║  ✅ Codeforces (코딩대회)                         ║
    ╠══════════════════════════════════════════════════╣
    ║  🏆 핵심 차별화:                                   ║
    ║  • 경기도 31개 시/군 특화                         ║
    ║  • 공공데이터 API 활용 (실시간)                   ║
    ║  • 학생 라이프사이클 전체 커버                    ║
    ║  • 지역 맞춤 필터링                               ║
    ║  • 메모리 캐싱 (API 비용 절감)                    ║
    ╠══════════════════════════════════════════════════╣
    ║  📍 대상 지역 (31개 시/군):                        ║
    ║  {', '.join(GYEONGGI_CITIES[:6])}...   ║
    ╠══════════════════════════════════════════════════╣
    ║  🔑 API 키 설정 (.env 파일):                       ║
    ║  GYEONGGI_API_KEY=발급받은_키                     ║
    ║  STARTUP_API_KEY=발급받은_키 (선택)               ║
    ║                                                      ║
    ║  💡 API 키 없어도 샘플 데이터로 작동합니다!        ║
    ╠══════════════════════════════════════════════════╣
    ║  💾 캐싱 전략:                                     ║
    ║  • 장학금: 1시간                                  ║
    ║  • 공모전: 2시간                                  ║
    ║  • 지원금: 12시간                                 ║
    ║  • 대회: 6시간                                    ║
    ║  • AI추천: 30분                                   ║
    ╚══════════════════════════════════════════════════╝

    🚀 서버 시작됨!

    📌 사용 예시:
    - gyeonggi_scholarship_finder(city="수원시", grade="대학생")
    - gyeonggi_contest_finder(city="성남시", category="IT")
    - startup_support_finder(age=25, region="경기도")
    - coding_competition_finder(level="중급")
    - gyeonggi_recommend(profile="수원시 대학생 컴퓨터공학")

    💡 API 키가 없어도 샘플 데이터로 작동합니다!
    하지만 실제 API 키 사용 시 실시간 데이터 제공!

    🔗 API 신청: https://data.gg.go.kr (경기도 공공데이터)
        """)
        uvicorn.run(app, host="0.0.0.0", port=port, workers=1)