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
# 6. Starlette 앱 구성 (Raw ASGI 방식 - 에러 원천 차단)
# =========================

sse_transport = SseServerTransport("/")

# [중요] 여기를 Raw ASGI 형태(scope, receive, send)로 만들어야 
# "Response already started" 에러와 "NoneType" 에러가 안 납니다.
async def handle_root(scope, receive, send):
    """
    모든 요청(GET/POST/OPTIONS)을 처리하는 통합 핸들러
    """
    request = Request(scope, receive)
    
    # 1. OPTIONS (CORS 예비 요청) 처리
    if request.method == "OPTIONS":
        response = JSONResponse({}, status_code=200, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        })
        await response(scope, receive, send)
        return

    # 2. GET 요청 처리 (SSE 연결 및 Health Check)
    elif request.method == "GET":
        accept = request.headers.get("accept", "")
        
        # SSE 연결 (Inspector 등)
        if "text/event-stream" in accept:
            # sse_transport가 통신을 직접 제어하므로 return Response() 절대 금지
            async with sse_transport.connect_sse(scope, receive, send) as streams:
                await mcp._mcp_server.run(
                    streams[0], 
                    streams[1], 
                    mcp._mcp_server.create_initialization_options()
                )
            return

        # Health Check (브라우저 접속 시)
        response = JSONResponse({
            "status": "online",
            "service": "Stock-Pattern-Analyzer",
            "endpoints": ["/ (GET: SSE)", "/ (POST: JSON-RPC)"]
        })
        await response(scope, receive, send)
        return

    # 3. POST 요청 처리 (Streamable HTTP)
    elif request.method == "POST":
        # sse_transport가 내부적으로 응답을 보내므로, 추가적인 return Response() 절대 금지
        await sse_transport.handle_post_message(scope, receive, send)
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
    
    # workers=1, reload=False 유지
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1, reload=False)