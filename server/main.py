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
from starlette.responses import JSONResponse, Response  # Response 추가
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
# 6. Starlette 앱 구성 (버그 수정됨)
# =========================

sse_transport = SseServerTransport("/")

# [핵심 수정 1] MCP의 내부 로직을 Starlette Response처럼 포장해주는 클래스
class ASGIResponder(Response):
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)

async def handle_root(request: Request):
    """단일 엔드포인트(/)에서 모든 요청 처리"""
    
    if request.method == "GET":
        accept = request.headers.get("accept", "")
        # SSE 연결 요청 (Inspector/Claude)
        if "text/event-stream" in accept:
            # 람다 함수로 감싸서 ASGIResponder에 전달
            return ASGIResponder(lambda s, r, send: sse_transport.connect_sse(
                s, r, send, mcp._mcp_server.create_initialization_options()
            ))
        
        # 일반 GET 요청 (Health Check)
        return JSONResponse({
            "status": "online",
            "service": "Stock-Pattern-Analyzer",
            "endpoints": ["/ (GET: SSE)", "/ (POST: JSON-RPC)"]
        })

    elif request.method == "POST":
        # [핵심 수정 2] 단순히 await 하는 게 아니라, ASGIResponder를 '반환(return)' 해야 함
        # 이렇게 하면 Starlette가 이 객체를 받아서 안전하게 실행합니다.
        return ASGIResponder(sse_transport.handle_post_message)
    
    elif request.method == "OPTIONS":
        return Response(status_code=200)

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
        Route("/", handle_root, methods=["GET", "POST", "OPTIONS"]),
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