import os
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

# =============================
# tools import
# =============================
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

# =============================
# MCP 서버 생성
# =============================
mcp = FastMCP(
    name="AI Recommender MCP",
    description="AI 도구, 에이전트, 모델, 논문, 트렌드를 추천하는 MCP 서버"
)

agent_catalog = AIAgentCatalog()
news_collector = AINewsCollector()

# =============================
# MCP tools 등록
# =============================

@mcp.tool(
    name="list_ai_agents",
    description="카테고리별 AI Agent 목록 조회"
)
def list_ai_agents(category: str = "all", subcategory: str | None = None) -> Dict[str, Any]:
    return agent_catalog.list_agents(category, subcategory)


@mcp.tool(
    name="search_ai_agents",
    description="키워드 기반 AI Agent 검색"
)
def search_ai_agents(query: str) -> Dict[str, Any]:
    return agent_catalog.search_agents(query)


@mcp.tool(
    name="recommend_ai_agent",
    description="작업, 경험 수준, 예산 기반 AI Agent 추천"
)
def recommend_ai_agent(task: str, experience_level: str, budget: str) -> Dict[str, Any]:
    return agent_catalog.recommend_for_task(task, experience_level, budget)


@mcp.tool(
    name="get_ai_news",
    description="최신 AI 뉴스 및 연구, 프로젝트 조회"
)
async def get_ai_news(category: str = "all", limit: int = 10) -> Dict[str, Any]:
    return await get_cached_news(category, limit)


@mcp.tool(
    name="get_trending_models",
    description="현재 트렌딩 중인 AI 모델 조회"
)
async def get_trending_models(limit: int = 10):
    return await get_trending_ai_models(limit)


@mcp.tool(
    name="search_model_for_task",
    description="작업 설명 기반 AI 모델 검색"
)
async def search_model_for_task(task: str):
    return await search_models(task)


@mcp.tool(
    name="latest_ai_research",
    description="최신 AI 연구 논문 조회"
)
async def latest_ai_research(limit: int = 10):
    return await get_latest_ai_research(limit)


@mcp.tool(
    name="ai_overview",
    description="모델, 프로젝트, 논문 종합 AI 업데이트"
)
async def ai_overview():
    return await get_all_updates()


@mcp.tool(
    name="realtime_model_rankings",
    description="실시간 AI 모델 랭킹 조회"
)
async def realtime_model_rankings(benchmark: str = "artificial-analysis"):
    return await get_realtime_rankings(benchmark)


@mcp.tool(
    name="recommend_model",
    description="작업에 가장 적합한 AI 모델 추천"
)
async def recommend_model(task: str):
    return await recommend_model_for_task(task)

# =============================
# 실행부 (중요)
# =============================
if __name__ == "__main__":
    mode = os.getenv("MCP_MODE", "http")

    if mode == "stdio":
        # 🔹 로컬 / Inspector용
        mcp.run()
    else:
        # 🔹 Koyeb / PlayMCP용
        port = int(os.environ.get("PORT", 8000))
        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=port,
            path="/mcp"
        )
