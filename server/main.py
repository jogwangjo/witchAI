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


# =========================
# Run
# =========================
if __name__ == "__main__":
    mode = os.getenv("MCP_MODE", "stdio")
    
    print(f"🚀 Starting MCP Server in {mode} mode", file=sys.stderr)
    
    if mode == "sse":
        # 로컬 SSE 테스트용
        port = int(os.getenv("PORT", 8000))
        print(f"📡 SSE server at http://localhost:{port}", file=sys.stderr)
        mcp.run(transport="sse", port=port)
    else:
        # stdio 모드 (MCP Inspector용)
        print("📟 stdio mode - Connect with MCP Inspector", file=sys.stderr)
        mcp.run()