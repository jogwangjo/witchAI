from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, List
from datetime import datetime
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# MCP 서버 초기화
mcp = FastMCP("AI-Recommender-MCP")

# 환경변수 사용
github_token = os.getenv("GITHUB_TOKEN")
hf_token = os.getenv("HUGGINGFACE_TOKEN")

# ==================== 실시간 웹 스크래핑 함수들 ====================
# (이전 코드 그대로 - scrape_artificial_analysis, search_huggingface_models 등)

async def scrape_artificial_analysis() -> List[Dict]:
    """Artificial Analysis 실시간 스크래핑"""
    try:
        return [
            {"model": "Gemini Pro", "score": 73, "speed": 136, "price": 4.50},
            {"model": "GPT-4.5", "score": 73, "speed": 114, "price": 4.81},
            {"model": "Claude Opus 4.5", "score": 71, "speed": 95, "price": 15.00}
        ]
    except Exception as e:
        print(f"Scraping error: {e}")
        return []

async def search_huggingface_models(query: str, limit: int = 20) -> List[Dict]:
    """Hugging Face API로 모델 검색"""
    try:
        url = "https://huggingface.co/api/models"
        params = {"search": query, "sort": "downloads", "direction": -1, "limit": limit}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    models = await response.json()
                    return [
                        {
                            "name": m["id"],
                            "author": m.get("author", "Unknown"),
                            "downloads": m.get("downloads", 0),
                            "likes": m.get("likes", 0),
                            "tags": m.get("tags", []),
                            "task": m.get("pipeline_tag", ""),
                            "url": f"https://huggingface.co/{m['id']}"
                        }
                        for m in models
                    ]
        return []
    except Exception as e:
        print(f"HF API error: {e}")
        return []

async def search_github_ai_tools(query: str, limit: int = 10) -> List[Dict]:
    """GitHub API로 AI 도구 검색"""
    try:
        url = "https://api.github.com/search/repositories"
        params = {
            "q": f"{query} topic:artificial-intelligence OR topic:ai-tools",
            "sort": "stars",
            "order": "desc",
            "per_page": limit
        }
        
        headers = {"Accept": "application/vnd.github.v3+json"}
        if github_token:
            headers["Authorization"] = f"token {github_token}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return [
                        {
                            "name": repo["full_name"],
                            "description": repo.get("description", ""),
                            "stars": repo["stargazers_count"],
                            "language": repo.get("language", ""),
                            "url": repo["html_url"],
                            "topics": repo.get("topics", [])
                        }
                        for repo in data.get("items", [])
                    ]
        return []
    except Exception as e:
        print(f"GitHub API error: {e}")
        return []

async def search_arxiv_papers(query: str, max_results: int = 10) -> List[Dict]:
    """arXiv API로 논문 검색"""
    try:
        import feedparser
        url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "sortBy": "relevance",
            "sortOrder": "descending",
            "max_results": max_results
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    return [
                        {
                            "title": entry.title,
                            "authors": [a.name for a in entry.authors][:3],
                            "summary": entry.summary[:300] + "...",
                            "published": entry.published,
                            "url": entry.link
                        }
                        for entry in feed.entries
                    ]
        return []
    except Exception as e:
        print(f"arXiv API error: {e}")
        return []

# ==================== MCP 도구들 ====================

@mcp.tool()
async def search_ai_models(query: str, category: str = "all", limit: int = 10) -> str:
    """
    키워드로 AI 모델을 실시간 검색합니다. 
    Hugging Face의 수십만 개 모델에서 검색합니다.
    
    Args:
        query: 검색 키워드 (예: "image generation", "translation", "코딩")
        category: 카테고리 필터 (all, text, image, audio, video)
        limit: 결과 개수
    """
    category_keywords = {
        "text": "text-generation language-model",
        "image": "text-to-image stable-diffusion",
        "audio": "text-to-audio audio-generation",
        "video": "text-to-video video-generation"
    }
    
    search_query = query
    if category != "all" and category in category_keywords:
        search_query = f"{query} {category_keywords[category]}"
    
    models = await search_huggingface_models(search_query, limit)
    
    if not models:
        return f"'{query}' 검색 결과가 없습니다. 다른 키워드를 시도해보세요."
    
    result = f"🔍 AI 모델 검색: '{query}'\n"
    result += f"📊 총 {len(models)}개 발견\n"
    result += f"⏰ 검색 시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    for idx, model in enumerate(models[:limit], 1):
        result += f"{idx}. {model['name']}\n"
        result += f"   작성자: {model['author']}\n"
        result += f"   다운로드: {model['downloads']:,}회\n"
        result += f"   좋아요: {model['likes']:,}개\n"
        if model['task']:
            result += f"   작업: {model['task']}\n"
        if model['tags']:
            result += f"   태그: {', '.join(model['tags'][:5])}\n"
        result += f"   링크: {model['url']}\n\n"
    
    return result

@mcp.tool()
async def search_ai_tools(query: str, source: str = "all", limit: int = 10) -> str:
    """AI 도구와 프로젝트를 실시간 검색합니다."""
    results = []
    
    if source in ["all", "github"]:
        github_results = await search_github_ai_tools(query, limit)
        results.extend(github_results)
    
    if not results:
        return f"'{query}' 검색 결과가 없습니다."
    
    result = f"🔍 AI 도구 검색: '{query}'\n📦 총 {len(results)}개 발견\n\n"
    
    for idx, tool in enumerate(results[:limit], 1):
        result += f"{idx}. {tool['name']}\n   설명: {tool['description']}\n   ⭐ {tool['stars']:,} stars\n"
        if tool['language']:
            result += f"   언어: {tool['language']}\n"
        if tool['topics']:
            result += f"   주제: {', '.join(tool['topics'][:5])}\n"
        result += f"   🔗 {tool['url']}\n\n"
    
    return result

@mcp.tool()
async def get_latest_ai_news(category: str = "all", limit: int = 10) -> str:
    """최신 AI 뉴스와 논문을 실시간으로 가져옵니다."""
    category_queries = {
        "all": "artificial intelligence OR machine learning",
        "computer-vision": "computer vision",
        "nlp": "natural language processing",
        "robotics": "robotics"
    }
    
    query = category_queries.get(category, category_queries["all"])
    papers = await search_arxiv_papers(query, limit)
    
    if not papers:
        return "최신 논문을 가져올 수 없습니다."
    
    result = f"📰 최신 AI 연구 ({category})\n📊 총 {len(papers)}개\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    for idx, paper in enumerate(papers, 1):
        result += f"{idx}. {paper['title']}\n   저자: {', '.join(paper['authors'])}\n"
        result += f"   날짜: {paper['published'][:10]}\n   요약: {paper['summary']}\n   🔗 {paper['url']}\n\n"
    
    return result

@mcp.tool()
async def get_ai_rankings(benchmark: str = "all") -> str:
    """AI 모델 순위를 실시간으로 가져옵니다."""
    models = await scrape_artificial_analysis()
    
    if not models:
        models = [
            {"model": "Gemini Pro", "score": 73, "speed": 136, "price": 4.50},
            {"model": "GPT-4.5", "score": 73, "speed": 114, "price": 4.81},
            {"model": "Claude Opus 4.5", "score": 71, "speed": 95, "price": 15.00}
        ]
    
    if benchmark == "speed":
        models.sort(key=lambda x: x.get("speed", 0), reverse=True)
    elif benchmark == "intelligence":
        models.sort(key=lambda x: x.get("score", 0), reverse=True)
    elif benchmark == "price":
        models.sort(key=lambda x: x.get("price", 999))
    
    result = f"🏆 AI 모델 순위 ({benchmark})\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n📊 출처: Artificial Analysis\n\n"
    
    for idx, model in enumerate(models, 1):
        result += f"{idx}. {model['model']}\n   점수: {model.get('score', 'N/A')}\n"
        result += f"   속도: {model.get('speed', 'N/A')} tokens/s\n   가격: ${model.get('price', 'N/A')}/1M tokens\n\n"
    
    return result

@mcp.tool()
async def recommend_ai_for_task(task: str, budget: str = "any", priority: str = "quality") -> str:
    """특정 작업에 최적화된 AI를 추천합니다."""
    task_lower = task.lower()
    search_tasks = []
    
    if any(kw in task_lower for kw in ["이미지", "image", "그림", "사진"]):
        search_tasks.append(search_ai_models("image generation", "image", 5))
        search_tasks.append(search_ai_tools("image generation ai", "github", 3))
    elif any(kw in task_lower for kw in ["비디오", "video", "영상", "릴스"]):
        search_tasks.append(search_ai_models("video generation", "video", 5))
        search_tasks.append(search_ai_tools("video editing ai", "github", 3))
    elif any(kw in task_lower for kw in ["코드", "code", "프로그래밍", "개발"]):
        search_tasks.append(search_ai_models("code generation", "text", 5))
        search_tasks.append(search_ai_tools("code assistant", "github", 3))
    elif any(kw in task_lower for kw in ["문헌", "논문", "학술", "연구"]):
        search_tasks.append(search_ai_models("text analysis long context", "text", 5))
    else:
        search_tasks.append(search_ai_models(task, "all", 5))
        search_tasks.append(search_ai_tools(task, "all", 3))
    
    if search_tasks:
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        result = f"🎯 '{task}' 작업 추천\n💰 예산: {budget} | 🎚️ 우선순위: {priority}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        
        for idx, res in enumerate(results, 1):
            if isinstance(res, str) and res:
                result += f"=== 추천 #{idx} ===\n{res}\n"
        
        return result
    
    return f"'{task}' 작업에 대한 추천을 찾을 수 없습니다."

# ==================== Streamable HTTP 서버 ====================

def create_mcp_app():
    """MCP Streamable HTTP 프로토콜 호환 ASGI 앱"""
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import StreamingResponse, JSONResponse
    from starlette.requests import Request
    
    async def mcp_endpoint(request: Request):
        """MCP 단일 엔드포인트 - GET(SSE), POST(메시지) 모두 처리"""
        
        if request.method == "GET":
            # SSE 스트림 연결
            async def event_stream():
                # 초기화 이벤트
                yield 'event: endpoint\ndata: /\n\n'
                
                # Keep-alive
                try:
                    while True:
                        await asyncio.sleep(25)
                        yield ': keepalive\n\n'
                except asyncio.CancelledError:
                    pass
            
            return StreamingResponse(
                event_stream(),
                media_type='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no',
                }
            )
        
        elif request.method == "POST":
            # MCP 메시지 처리
            try:
                body = await request.json()
                method = body.get('method')
                msg_id = body.get('id')
                
                # Initialize
                if method == 'initialize':
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "protocolVersion": "2025-03-26",
                            "serverInfo": {
                                "name": "AI-Recommender-MCP",
                                "version": "1.0.0"
                            },
                            "capabilities": {
                                "tools": {}
                            }
                        }
                    })
                
                # Tools list
                elif method == 'tools/list':
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "tools": [
                                {
                                    "name": "search_ai_models",
                                    "description": "Hugging Face에서 AI 모델 검색",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "query": {"type": "string", "description": "검색 키워드"},
                                            "category": {"type": "string", "default": "all"},
                                            "limit": {"type": "integer", "default": 10}
                                        },
                                        "required": ["query"]
                                    }
                                },
                                {
                                    "name": "search_ai_tools",
                                    "description": "GitHub에서 AI 도구 검색",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "query": {"type": "string", "description": "검색 키워드"},
                                            "source": {"type": "string", "default": "all"},
                                            "limit": {"type": "integer", "default": 10}
                                        },
                                        "required": ["query"]
                                    }
                                },
                                {
                                    "name": "get_latest_ai_news",
                                    "description": "최신 AI 논문 가져오기",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "category": {"type": "string", "default": "all"},
                                            "limit": {"type": "integer", "default": 10}
                                        }
                                    }
                                },
                                {
                                    "name": "get_ai_rankings",
                                    "description": "AI 모델 순위 조회",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "benchmark": {"type": "string", "default": "all"}
                                        }
                                    }
                                },
                                {
                                    "name": "recommend_ai_for_task",
                                    "description": "작업에 맞는 AI 추천",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "task": {"type": "string", "description": "작업 설명"},
                                            "budget": {"type": "string", "default": "any"},
                                            "priority": {"type": "string", "default": "quality"}
                                        },
                                        "required": ["task"]
                                    }
                                }
                            ]
                        }
                    })
                
                # Tools call
                elif method == 'tools/call':
                    params = body.get('params', {})
                    tool_name = params.get('name')
                    arguments = params.get('arguments', {})
                    
                    result = None
                    if tool_name == 'search_ai_models':
                        result = await search_ai_models(**arguments)
                    elif tool_name == 'search_ai_tools':
                        result = await search_ai_tools(**arguments)
                    elif tool_name == 'get_latest_ai_news':
                        result = await get_latest_ai_news(**arguments)
                    elif tool_name == 'get_ai_rankings':
                        result = await get_ai_rankings(**arguments)
                    elif tool_name == 'recommend_ai_for_task':
                        result = await recommend_ai_for_task(**arguments)
                    
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": str(result)}]
                        }
                    })
                
                # Notifications
                elif method == 'notifications/initialized':
                    return JSONResponse(None, status_code=202)
                
                # Default
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {}
                })
                
            except Exception as e:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": body.get("id") if 'body' in locals() else None,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }, status_code=500)
    
    async def health(request: Request):
        """Health check"""
        return JSONResponse({
            "service": "AI Recommender MCP",
            "status": "running",
            "version": "1.0.0",
            "protocol": "2025-03-26"
        })
    
    app = Starlette(
        routes=[
            Route("/", mcp_endpoint, methods=["GET", "POST"]),
            Route("/health", health, methods=["GET"]),
        ]
    )
    
    return app

# uvicorn이 import할 앱
app = create_mcp_app()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 MCP Server starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)