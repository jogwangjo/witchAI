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
# 5. 툴 등록
# =========================

# [Tool 1] 주가 분석
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

# [Tool 2] 에코 메시지 (심사 통과 및 테스트용)
@mcp.tool(
    name="echo_message",
    description="입력한 메시지를 그대로 반환합니다. 연결 상태를 확인하는 테스트용 도구입니다."
)
async def echo_message(message: str) -> str:
    return f"Echo check: {message}"

# =========================
# 6. Bridge Class (Starlette <-> MCP 연결)
# =========================
class ASGIResponder(Response):
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)

# =========================
# 7. Stateless Handler (Inspector/카카오 호환)
# =========================
async def handle_stateless_jsonrpc(request: Request):
    """Session ID가 없는 Streamable HTTP 요청 처리"""
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
            for tool in mcp._tool_manager.list_tools():
                safe_desc = tool.description if tool.description else "No description available."
                safe_schema = tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}}

                tools_data.append({
                    "name": tool.name,
                    "description": safe_desc,
                    "inputSchema": safe_schema
                })
            
            return JSONResponse({
                "jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools_data}
            })

        # 4. Call Tool
        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            result = await mcp.call_tool(tool_name, tool_args)
            
            content = []
            for item in result:
                if item.type == "text":
                    content.append({"type": "text", "text": item.text})
                elif item.type == "image":
                    content.append({"type": "image", "data": item.data, "mimeType": item.mimeType})
            
            return JSONResponse({
                "jsonrpc": "2.0", "id": msg_id, "result": {"content": content, "isError": False}
            })

        # 5. Ping
        if method == "ping":
            return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "result": {}})

        return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "result": {}})

    except Exception as e:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}})

# =========================
# 8. 통합 라우터 (여기가 핵심 수정됨!)
# =========================

sse_transport = SseServerTransport("/")

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
            
            # [수정] lambda 대신 정석적인 async 함수 정의
            # 인자 개수 오류(TypeError)를 완벽하게 해결합니다.
            async def sse_app(scope, receive, send):
                # connect_sse에는 scope, receive, send만 전달 (options 제거)
                async with sse_transport.connect_sse(scope, receive, send) as streams:
                    # options는 run() 함수에 전달
                    await mcp._mcp_server.run(
                        streams[0], 
                        streams[1], 
                        mcp._mcp_server.create_initialization_options()
                    )
            
            return ASGIResponder(sse_app)
        
        return JSONResponse({
            "status": "online", 
            "mode": "Hybrid", 
            "desc_fix": "OK",
            "sse_fix": "OK"
        })

    # 3. POST (Streamable HTTP)
    if request.method == "POST":
        session_id = request.query_params.get("session_id")
        
        if session_id:
            return ASGIResponder(sse_transport.handle_post_message)
        else:
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