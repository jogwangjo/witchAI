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

# 🔴 description 쓰면 안 됨
mcp = FastMCP("AI Recommender MCP")

agent_catalog = AIAgentCatalog()

# =========================
# MCP Tools
# =========================

@mcp.tool()
def list_ai_agents(category: str = "all", subcategory: Optional[str] = None) -> Dict[str, Any]:
    return agent_catalog.list_agents(category, subcategory)

@mcp.tool()
def search_ai_agents(query: str) -> Dict[str, Any]:
    return agent_catalog.search_agents(query)

@mcp.tool()
def recommend_ai_agent(task: str, experience_level: str, budget: str) -> Dict[str, Any]:
    return agent_catalog.recommend_for_task(task, experience_level, budget)

@mcp.tool()
async def get_ai_news(category: str = "all", limit: int = 10):
    return await get_cached_news(category, limit)

@mcp.tool()
async def get_trending_models(limit: int = 10):
    return await get_trending_ai_models(limit)

@mcp.tool()
async def search_model_for_task(task: str):
    return await search_models(task)

@mcp.tool()
async def latest_ai_research(limit: int = 10):
    return await get_latest_ai_research(limit)

@mcp.tool()
async def ai_overview():
    return await get_all_updates()

@mcp.tool()
async def realtime_model_rankings(benchmark: str = "artificial-analysis"):
    return await get_realtime_rankings(benchmark)

@mcp.tool()
async def recommend_model(task: str):
    return await recommend_model_for_task(task)

# =========================
# Run
# =========================
if __name__ == "__main__":
    mode = os.getenv("MCP_MODE", "http")

    if mode == "stdio":
        mcp.run()
    else:
        port = int(os.environ.get("PORT", 8000))
        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=port,
            path="/mcp",
        )
