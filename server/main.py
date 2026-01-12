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
from starlette.responses import JSONResponse, Response
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport

# =========================
# 3. 기존 주가 분석 툴 임포트 (유지)
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
# 5. 주가 분석 툴 등록 (유지)
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
    return response

# =========================
# 6. Starlette 앱 구성 (Custom Response 방식 - 에러 완전 차단)
# =========================

sse_transport = SseServerTransport("/")

# [핵심 1] SSE 연결을 처리하는 특수 응답 클래스
class MCP_SSE_Response(Response):
    def __init__(self, transport, mcp_server):
        self.transport = transport
        self.mcp_server = mcp_server
        # 부모 클래스 초기화 (media_type은 SSE 필수)
        super().__init__(media_type="text/event-stream")

    async def __call__(self, scope, receive, send):
        # Starlette이 응답을 보내라고 할 때, MCP에게 제어권을 넘깁니다.
        async with self.transport.connect_sse(scope, receive, send) as streams:
            await self.mcp_server.run(
                streams[0], 
                streams[1], 
                self.mcp_server.create_initialization_options()
            )

# [핵심 2] POST 요청(Streamable HTTP)을 처리하는 특수 응답 클래스
class MCP_POST_Response(Response):
    def __init__(self, transport):
        self.transport = transport
        super().__init__()

    async def __call__(self, scope, receive, send):
        # 여기서 MCP가 직접 응답을 쓰고 종료하므로, Starlette의 중복 응답 에러가 발생하지 않습니다.
        await self.transport.handle_post_message(scope, receive, send)

# [핵심 3] 핸들러 함수 복구 (Starlette 표준 방식인 request 인자 사용)
async def handle_root(request: Request):
    """
    이제 표준 request 핸들러로 동작하되, 반환값으로 특수 Response 객체를 줍니다.
    """
    # 1. OPTIONS (CORS)
    if request.method == "OPTIONS":
        return Response(status_code=200, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        })

    # 2. GET (SSE & Health Check)
    if request.method == "GET":
        accept = request.headers.get("accept", "")
        if "text/event-stream" in accept:
            # 특수 SSE 응답 객체 반환
            return MCP_SSE_Response(sse_transport, mcp._mcp_server)
        
        # 일반 Health Check
        return JSONResponse({
            "status": "online",
            "service": "Stock-Pattern-Analyzer",
            "endpoints": ["/ (GET: SSE)", "/ (POST: JSON-RPC)"]
        })

    # 3. POST (Streamable HTTP)
    if request.method == "POST":
        # 특수 POST 응답 객체 반환
        return MCP_POST_Response(sse_transport)

    return Response(status_code=405)

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
        # 표준 Route 사용 (이제 handle_root가 request를 받으므로 문제 없음)
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