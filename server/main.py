import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

# 1. 경로 보정
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# 2. 필수 모듈 임포트
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport

# =========================
# 3. 기존 주가 분석 툴 임포트
# =========================
try:
    from tools.quant_engine import analyzer
except ImportError:
    try:
        from server.tools.quant_engine import analyzer
    except ImportError:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from tools.quant_engine import analyzer

# 4. FastMCP 초기화
mcp = FastMCP("Stock-Pattern-Analyzer")

# =========================
# 5. 주가 분석 툴 등록
# =========================
@mcp.tool(
    name="analyze_stock_pattern",
    description="주식의 현재 차트 패턴을 분석하고, 과거 10년 치 데이터 중 가장 유사했던 시점을 찾아줍니다."
)
async def analyze_stock_pattern(ticker: str, window_days: int = 30) -> str:
    """주식의 현재 차트 패턴을 분석하고, 과거 10년 치 데이터 중 가장 유사했던 시점을 찾아줍니다."""
    try:
        result = await analyzer.find_similar_patterns(ticker, window_size=window_days)
    except Exception as e:
        return f"서버 내부 오류 발생: {str(e)}"
    
    if "error" in result:
        return f"분석 중 오류 발생: {result['error']}"
    
    matches = result.get("top_matches", [])
    if not matches:
        return f"'{ticker}'의 현재 패턴과 유사도 80% 이상인 과거 패턴을 찾을 수 없습니다."
    
    response = f"""
📊 **[{ticker}] 주가 패턴 정밀 분석 결과**
- 분석 기간: 최근 {window_days}일 ({result.get('current_period', {}).get('start', '?')} ~ {result.get('current_period', {}).get('end', '?')})

발견된 가장 유사한 과거 사례 (Top {len(matches)}):
"""
    for i, match in enumerate(matches, 1):
        trend = "상승" if match['after_5days_return'] > 0 else "하락"
        response += f"""
{i}. **{match['start_date']} ~ {match['end_date']}** (유사도: {match['similarity']}%)
   - 당시 패턴 종료 후 5일간 주가: {match['after_5days_return']}% {trend}
"""
    response += "\n⚠️ 이 분석은 과거의 통계적 유사성만을 보여주며, 미래의 수익을 보장하지 않습니다."
    return response

# =========================
# 6. Starlette 앱 구성 (Raw ASGI 모드로 수정)
# =========================

sse_transport = SseServerTransport("/")

# [핵심 수정] Request/Response 객체 대신 Raw ASGI scope를 직접 다룹니다.
# 이렇게 하면 Starlette의 Response 규칙을 우회하여 에러를 방지합니다.
async def handle_root(scope, receive, send):
    """
    Raw ASGI Endpoint: 
    Starlette의 Request/Response 래퍼를 거치지 않고 직접 통신을 제어합니다.
    """
    request = Request(scope, receive)
    
    if request.method == "GET":
        accept = request.headers.get("accept", "")
        
        # 1. SSE 연결 (Inspector/Claude)
        if "text/event-stream" in accept:
            # [수정된 부분] connect_sse에는 options를 넣지 않고, 내부 run()에 넣습니다.
            async with sse_transport.connect_sse(scope, receive, send) as streams:
                await mcp._mcp_server.run(
                    streams[0], 
                    streams[1], 
                    mcp._mcp_server.create_initialization_options()
                )
            return

        # 2. Health Check (Koyeb/Browser)
        # Raw ASGI에서는 JSON 응답도 직접 send로 보내야 하므로 JSONResponse를 호출하여 실행합니다.
        response = JSONResponse({
            "status": "online",
            "service": "Stock-Pattern-Analyzer",
            "endpoints": ["/ (GET: SSE)", "/ (POST: JSON-RPC)"]
        })
        await response(scope, receive, send)
        return

    elif request.method == "POST":
        # 3. Streamable HTTP 메시지 처리
        # handle_post_message가 알아서 응답을 보내고 종료하므로 return이 없어도 안전합니다.
        await sse_transport.handle_post_message(scope, receive, send)
        return

    elif request.method == "OPTIONS":
        response = JSONResponse({}, status_code=200)
        await response(scope, receive, send)
        return

# CORS 미들웨어 설정
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = Starlette(
    debug=True,
    routes=[
        # endpoint에 함수 자체를 넘기면 Raw ASGI 앱으로 인식합니다.
        Route("/", endpoint=handle_root, methods=["GET", "POST", "OPTIONS"]),
    ],
    middleware=middleware
)

# =========================
# 7. 서버 실행
# =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Stock Pattern Analyzer running on 0.0.0.0:{port}", file=sys.stderr)
    
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1, reload=False)