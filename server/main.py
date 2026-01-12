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
# 6. Starlette 앱 구성 (RuntimeError 완벽 해결)
# =========================

sse_transport = SseServerTransport("/")

# [핵심] scope, receive, send를 직접 받는 Raw ASGI 핸들러 함수
async def handle_root(scope, receive, send):
    """
    모든 요청을 처리하는 통합 핸들러.
    Starlette의 자동 Response 처리를 우회하여 중복 응답 에러를 방지합니다.
    """
    request = Request(scope, receive)
    
    # 1. OPTIONS (CORS Preflight)
    if request.method == "OPTIONS":
        response = Response(status_code=200, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        })
        await response(scope, receive, send)
        return

    # 2. GET (SSE 연결 및 Health Check)
    if request.method == "GET":
        accept = request.headers.get("accept", "")
        
        if "text/event-stream" in accept:
            # SSE 연결: 통신 제어권을 mcp 라이브러리에 완전히 넘김
            async with sse_transport.connect_sse(scope, receive, send) as streams:
                await mcp._mcp_server.run(
                    streams[0], 
                    streams[1], 
                    mcp._mcp_server.create_initialization_options()
                )
            return

        # 일반 접속 (Health Check)
        response = JSONResponse({
            "status": "online",
            "service": "Stock-Pattern-Analyzer",
            "endpoints": ["/ (GET: SSE)", "/ (POST: JSON-RPC)"]
        })
        await response(scope, receive, send)
        return

    # 3. POST (Streamable HTTP)
    if request.method == "POST":
        # [중요] handle_post_message가 응답을 보내면, 함수를 바로 종료(return)해야 함
        await sse_transport.handle_post_message(scope, receive, send)
        return

    # 4. 그 외 메소드 (405)
    response = Response(status_code=405)
    await response(scope, receive, send)

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
        # endpoint에 함수 자체를 넘기면 Raw ASGI 앱으로 작동
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