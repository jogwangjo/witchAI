import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
from starlette.responses import JSONResponse, Response

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
    """
    주식의 현재 차트 패턴을 분석하고, 과거 10년 치 데이터 중 가장 유사했던 시점을 찾아줍니다.
    """
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
- 분석 알고리즘: Z-Score Normalization + Pearson Correlation
- 분석 기간: 최근 {window_days}일 ({result.get('current_period', {}).get('start', '?')} ~ {result.get('current_period', {}).get('end', '?')})

발견된 가장 유사한 과거 사례 (Top {len(matches)}):
"""
    for i, match in enumerate(matches, 1):
        trend = "상승" if match['after_5days_return'] > 0 else "하락"
        response += f"""
{i}. **{match['start_date']} ~ {match['end_date']}** (유사도: {match['similarity']}%)
   - 당시 패턴 종료 후 5일간 주가: {match['after_5days_return']}% {trend}
   - [LLM 요청 사항]: 위 기간({match['start_date']}~{match['end_date']}) 동안 {ticker}와 관련된 주요 뉴스와 시장 이슈를 검색해서, 현재 상황과 비교 설명해주세요.
"""
    response += "\n⚠️ 이 분석은 과거의 통계적 유사성만을 보여주며, 미래의 수익을 보장하지 않습니다."
    return response

# =========================
# 6. Starlette 앱 구성 (Streamable HTTP 완전 지원)
# =========================

sse_transport = SseServerTransport("/")

async def handle_root(request: Request):
    # OPTIONS 요청 처리 (CORS preflight - Streamable HTTP에 필수!)
    if request.method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Max-Age": "86400",  # 24시간 캐시
            }
        )
    
    if request.method == "GET":
        accept = request.headers.get("accept", "")
        if "text/event-stream" in accept:
            # SSE 연결
            async with sse_transport.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await mcp._mcp_server.run(
                    streams[0], streams[1], 
                    mcp._mcp_server.create_initialization_options()
                )
            return Response()
        
        # Health check
        return JSONResponse({
            "status": "online",
            "service": "Stock-Pattern-Analyzer",
            "transport": ["SSE", "Streamable HTTP"],
            "endpoints": {
                "sse": "GET / with Accept: text/event-stream",
                "streamable_http": "POST / with JSON-RPC"
            }
        })

    elif request.method == "POST":
        # Streamable HTTP (JSON-RPC over POST)
        await sse_transport.handle_post_message(
            request.scope, request.receive, request._send
        )
        return Response()

    return Response(status_code=405)

# CORS 미들웨어 설정 (모든 도메인 허용)
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
]

app = Starlette(
    debug=True,
    routes=[
        Route("/", handle_root, methods=["GET", "POST", "OPTIONS"]),
    ],
    middleware=middleware
)

# =========================
# 7. 서버 실행
# =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Stock Pattern Analyzer MCP Server", file=sys.stderr)
    print(f"📡 Listening on 0.0.0.0:{port}", file=sys.stderr)
    print(f"✅ Transport: SSE + Streamable HTTP", file=sys.stderr)
    
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1, reload=False)