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
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport

# =========================
# 3. [복구] 기존 주가 분석 툴 임포트
# =========================
try:
    from tools.quant_engine import analyzer
except ImportError:
    try:
        from server.tools.quant_engine import analyzer
    except ImportError:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from tools.quant_engine import analyzer

# 4. FastMCP 초기화 (이름 복구)
mcp = FastMCP("Stock-Pattern-Analyzer")

# =========================
# 5. [복구] 주가 분석 툴 등록
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
# 6. [핵심] Starlette 앱 구성 (연결 문제 해결)
# =========================

# FastMCP 내부 서버 객체를 이용해 전송 계층 생성 (루트 경로에서 처리)
sse_transport = SseServerTransport("/")

async def handle_root(request: Request):
    """
    단일 엔드포인트(/)에서 Health Check, SSE, POST를 모두 처리
    """
    if request.method == "GET":
        # 1. SSE 연결 요청 처리 (Inspector/Claude 연결)
        accept = request.headers.get("accept", "")
        if "text/event-stream" in accept:
            async with sse_transport.connect_sse(request.scope, request.receive, request._send) as streams:
                await mcp._mcp_server.run(streams[0], streams[1], mcp._mcp_server.create_initialization_options())
            return
        
        # 2. 일반 GET 요청 (Koyeb Health Check 등) -> 200 OK 반환 (404 해결)
        return JSONResponse({
            "status": "online",
            "service": "Stock-Pattern-Analyzer",
            "endpoints": ["/ (GET: SSE)", "/ (POST: JSON-RPC)"]
        })

    elif request.method == "POST":
        # 3. Streamable HTTP 메시지 처리 (도구 실행)
        await sse_transport.handle_post_message(request.scope, request.receive, request._send)

# Starlette 앱 생성
app = Starlette(
    debug=True,
    routes=[
        Route("/", handle_root, methods=["GET", "POST"]),
    ]
)

# =========================
# 7. 서버 실행
# =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Stock Pattern Analyzer running on 0.0.0.0:{port}", file=sys.stderr)
    
    # [핵심 수정] workers=1, reload=False를 명시하여 Koyeb 환경 변수(WEB_CONCURRENCY) 무시
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1, reload=False)