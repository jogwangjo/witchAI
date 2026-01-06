import sys
from pathlib import Path
from typing import Dict, Any, Optional
import os

# =========================
# PYTHONPATH 보정 (필수)
# =========================
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# =========================
# MCP
# =========================
from mcp.server.fastmcp import FastMCP

from tools import (
    AINewsCollector,
    get_cached_news,
    AIAgentCatalog,
)

from tools.api_integrations import (
    get_trending_ai_models,
    search_models,
    get_latest_ai_research,
    get_all_updates,
)

from tools.realtime_collector import (
    get_realtime_rankings,
    recommend_model_for_task,
)

# MCP 서버 초기화
mcp = FastMCP("AI Recommender MCP")

agent_catalog = AIAgentCatalog()

# =========================
# MCP Tools
# =========================

@mcp.tool()
def list_ai_agents(category: str = "all", subcategory: Optional[str] = None) -> Dict[str, Any]:
    """AI Agent 목록을 카테고리별로 조회합니다."""
    return agent_catalog.list_agents(category, subcategory)

@mcp.tool()
def search_ai_agents(query: str) -> Dict[str, Any]:
    """키워드로 AI Agent를 검색합니다."""
    return agent_catalog.search_agents(query)

@mcp.tool()
def recommend_ai_agent(task: str, experience_level: str = "intermediate", budget: str = "any") -> Dict[str, Any]:
    """특정 작업에 맞는 AI Agent를 추천합니다."""
    return agent_catalog.recommend_for_task(task, experience_level, budget)

@mcp.tool()
async def get_ai_news(category: str = "all", limit: int = 10):
    """최신 AI 뉴스와 논문을 가져옵니다."""
    return await get_cached_news(category, limit)

@mcp.tool()
async def get_trending_models(limit: int = 10):
    """트렌딩 AI 모델을 가져옵니다."""
    return await get_trending_ai_models(limit)

@mcp.tool()
async def search_model_for_task(task: str):
    """작업에 맞는 모델을 검색합니다."""
    return await search_models(task)

@mcp.tool()
async def latest_ai_research(max_results: int = 10):
    """최신 AI 연구 논문을 가져옵니다."""
    return await get_latest_ai_research(max_results)

@mcp.tool()
async def ai_overview():
    """AI 생태계 종합 업데이트를 가져옵니다."""
    return await get_all_updates()

@mcp.tool()
async def realtime_model_rankings(benchmark: str = "artificial-analysis"):
    """실시간 AI 모델 순위를 가져옵니다."""
    return await get_realtime_rankings(benchmark)

@mcp.tool()
async def recommend_model(task: str):
    """작업에 최적화된 모델을 추천합니다."""
    return await recommend_model_for_task(task)

def get_mcp_app():
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import JSONResponse
    from starlette.requests import Request
    
    async def health_check(request: Request):
        return JSONResponse({"status": "ok", "service": "AI Recommender MCP"})
    
    async def root_handler(request: Request):
        if request.method == "GET":
            return await health_check(request)
        elif request.method == "POST":
            # MCP 메시지 처리
            body = await request.json()
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "tools": [
                        {"name": "list_ai_agents", "description": "AI Agent 목록 조회"},
                        {"name": "search_ai_agents", "description": "AI Agent 검색"},
                        {"name": "recommend_ai_agent", "description": "작업에 맞는 Agent 추천"},
                        {"name": "get_ai_news", "description": "최신 AI 뉴스"},
                        {"name": "get_trending_models", "description": "트렌딩 모델"},
                        {"name": "search_model_for_task", "description": "작업용 모델 검색"},
                        {"name": "latest_ai_research", "description": "최신 AI 연구"},
                        {"name": "ai_overview", "description": "AI 생태계 업데이트"},
                        {"name": "realtime_model_rankings", "description": "실시간 모델 순위"},
                        {"name": "recommend_model", "description": "모델 추천"}
                    ]
                }
            })
        return JSONResponse({"error": "Method not allowed"}, status_code=405)
    
    return Starlette(
        routes=[
            Route("/", root_handler, methods=["GET", "POST"]),
        ]
    )

app = get_mcp_app()

# =========================
# Run
# =========================
if __name__ == "__main__":
    import uvicorn
    
    mode = os.getenv("MCP_MODE", "stdio")
    
    print(f"🔥 MAIN BLOCK EXECUTING", file=sys.stderr)
    print(f"🚀 Starting MCP Server in {mode} mode", file=sys.stderr)
    
    if mode == "sse":
        port = int(os.getenv("PORT", 8000))
        host = "0.0.0.0"
        
        print(f"📡 SSE server at http://{host}:{port}", file=sys.stderr)
        
        # uvicorn 패치 방식 ⭐
        original_run = uvicorn.run
        
        def patched_run(app, **kwargs):
            kwargs['host'] = host
            kwargs['port'] = port
            return original_run(app, **kwargs)
        
        uvicorn.run = patched_run
        
        # 이제 mcp.run() 호출하면 패치된 uvicorn 사용
        mcp.run(transport="streamable-http")