import sys
import os
import json
import asyncio
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
from mcp.types import JSONRPCMessage, JSONRPCResponse

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
# 6. [핵심] Stateless Handler (라이브러리 한계 돌파)
# =========================

async def handle_stateless_jsonrpc(request: Request):
    """
    Session ID가 없는 요청을 직접 처리하는 핸들러입니다.
    라이브러리의 SseServerTransport를 우회합니다.
    """
    try:
        body = await request.json()
        method = body.get("method")
        msg_id = body.get("id")
        params = body.get("params", {})

        # 1. Initialize 요청 처리
        if method == "initialize":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"listChanged": False, "subscribe": False},
                        "prompts": {"listChanged": False},
                        "logging": {}
                    },
                    "serverInfo": {"name": "Stock-Pattern-Analyzer", "version": "1.0.0"}
                }
            })

        # 2. Initialized 알림 (응답 없음)
        if method == "notifications/initialized":
            return Response(status_code=200)

        # 3. Tools List 요청 처리
        if method == "tools/list":
            # FastMCP 내부에서 툴 목록을 가져와서 직접 포맷팅
            tools_data = []
            for tool in mcp._tool_manager.list_tools():
                tools_data.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                })
            
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": tools_data
                }
            })

        # 4. Call Tool 요청 처리
        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            # FastMCP를 통해 도구 실행
            result = await mcp.call_tool(tool_name, tool_args)
            
            # 결과 포맷팅
            content = []
            for item in result:
                if item.type == "text":
                    content.append({"type": "text", "text": item.text})
                elif item.type == "image":
                    content.append({"type": "image", "data": item.data, "mimeType": item.mimeType})

            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": content,
                    "isError": False
                }
            })
            
        # 5. Ping
        if method == "ping":
            return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "result": {}})

        # 그 외 모르는 메소드
        return JSONResponse({
            "jsonrpc": "2.0", 
            "id": msg_id, 
            "error": {"code": -32601, "message": "Method not found"}
        })

    except Exception as e:
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32000, "message": str(e)}
        })

# =========================
# 7. Starlette 라우팅
# =========================

sse_transport = SseServerTransport("/")

async def handle_root(scope, receive, send):
    """
    통합 라우터:
    - Session ID 있음 -> 라이브러리(SSE) 사용
    - Session ID 없음 -> 직접 만든 Stateless 핸들러 사용
    """
    request = Request(scope, receive)

    # 1. OPTIONS (CORS)
    if request.method == "OPTIONS":
        response = Response(status_code=200, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        })
        await response(scope, receive, send)
        return

    # 2. GET (SSE & Health Check)
    if request.method == "GET":
        accept = request.headers.get("accept", "")
        if "text/event-stream" in accept:
            async with sse_transport.connect_sse(scope, receive, send) as streams:
                await mcp._mcp_server.run(streams[0], streams[1], mcp._mcp_server.create_initialization_options())
            return
        
        response = JSONResponse({"status": "online", "mode": "Hybrid (SSE + Stateless)"})
        await response(scope, receive, send)
        return

    # 3. POST (Streamable HTTP)
    if request.method == "POST":
        session_id = request.query_params.get("session_id")
        
        if session_id:
            # 세션 ID가 있으면 라이브러리 로직 사용 (SSE 모드)
            await sse_transport.handle_post_message(scope, receive, send)
        else:
            # [핵심] 세션 ID가 없으면 우리가 만든 Stateless 핸들러 사용! (Inspector/카카오 모드)
            response = await handle_stateless_jsonrpc(request)
            await response(scope, receive, send)
        return

    response = Response(status_code=405)
    await response(scope, receive, send)

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
# 8. 실행
# =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Stock Pattern Analyzer (Hybrid Mode) running on 0.0.0.0:{port}", file=sys.stderr)
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1, reload=False)