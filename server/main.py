import sys
import os
import json
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
    return response

# =========================
# 6. [핵심 1] MCP 라이브러리 연결 다리 (Bridge)
# =========================
class ASGIResponder(Response):
    """
    Starlette의 Request/Response 구조 안에서 
    MCP 라이브러리의 Raw ASGI 동작을 실행시켜주는 래퍼입니다.
    이것이 있으면 TypeError가 나지 않습니다.
    """
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)

# =========================
# 7. [핵심 2] Stateless Handler (Inspector/카카오 지원)
# =========================
async def handle_stateless_jsonrpc(request: Request):
    """
    Session ID가 없는 Streamable HTTP 요청을 직접 처리합니다.
    """
    try:
        body = await request.json()
        method = body.get("method")
        msg_id = body.get("id")
        params = body.get("params", {})

        # 1. Initialize
        if method == "initialize":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "Stock-Pattern-Analyzer", "version": "1.0.0"}
                }
            })

        # 2. Initialized
        if method == "notifications/initialized":
            return Response(status_code=200)

        # 3. Tools List
        if method == "tools/list":
            tools_data = []
            # FastMCP 내부 툴 매니저에서 정보 추출
            for tool in mcp._tool_manager.list_tools():
                tools_data.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                })
            return JSONResponse({
                "jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools_data}
            })

        # 4. Call Tool
        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            result = await mcp.call_tool(tool_name, tool_args)
            
            # 결과 변환
            content = []
            for item in result:
                if item.type == "text":
                    content.append({"type": "text", "text": item.text})
            
            return JSONResponse({
                "jsonrpc": "2.0", "id": msg_id, "result": {"content": content, "isError": False}
            })
            
        return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "result": {}})

    except Exception as e:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}})

# =========================
# 8. 통합 라우터 (handle_root)
# =========================

sse_transport = SseServerTransport("/")

# [수정됨] 다시 표준 Request 핸들러로 돌아왔습니다. (TypeError 해결)
async def handle_root(request: Request):
    
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
            # MCP 라이브러리(SSE)를 ASGIResponder로 감싸서 실행
            return ASGIResponder(lambda s, r, send: sse_transport.connect_sse(
                s, r, send, mcp._mcp_server.create_initialization_options()
            ))
        
        return JSONResponse({"status": "online", "mode": "Hybrid"})

    # 3. POST (Streamable HTTP)
    if request.method == "POST":
        session_id = request.query_params.get("session_id")
        
        if session_id:
            # ID 있으면 -> 라이브러리 사용 (ASGIResponder로 감싸기)
            return ASGIResponder(sse_transport.handle_post_message)
        else:
            # ID 없으면 -> 우리가 만든 Stateless Handler 사용! (여기가 핵심)
            return await handle_stateless_jsonrpc(request)

    return Response(status_code=405)

# CORS 미들웨어
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
        Route("/", endpoint=handle_root, methods=["GET", "POST", "OPTIONS"]),
    ],
    middleware=middleware
)

# =========================
# 9. 서버 실행
# =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Stock Pattern Analyzer running on 0.0.0.0:{port}", file=sys.stderr)
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1, reload=False)