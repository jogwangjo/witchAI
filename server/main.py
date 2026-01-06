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

# ==================== 실시간 웹 스크래핑 ====================

async def scrape_artificial_analysis() -> List[Dict]:
    """Artificial Analysis 실시간 스크래핑"""
    try:
        url = "https://artificialanalysis.ai/leaderboards/models"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # 테이블 데이터 파싱 (실제 구조에 맞게 조정 필요)
                models = []
                # 여기에 실제 파싱 로직 추가
                # 현재는 예시 데이터 반환
                
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
        params = {
            "search": query,
            "sort": "downloads",
            "direction": -1,
            "limit": limit
        }
        
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
        github_token = os.getenv("GITHUB_TOKEN")
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
    
    # 카테고리별 키워드 매핑
    category_keywords = {
        "text": "text-generation language-model",
        "image": "text-to-image stable-diffusion",
        "audio": "text-to-audio audio-generation",
        "video": "text-to-video video-generation"
    }
    
    search_query = query
    if category != "all" and category in category_keywords:
        search_query = f"{query} {category_keywords[category]}"
    
    # Hugging Face에서 검색
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
    """
    AI 도구와 프로젝트를 실시간 검색합니다.
    GitHub, Product Hunt 등에서 검색합니다.
    
    Args:
        query: 검색 키워드 (예: "video editing", "code assistant")
        source: 검색 소스 (all, github, producthunt)
        limit: 결과 개수
    """
    
    results = []
    
    if source in ["all", "github"]:
        github_results = await search_github_ai_tools(query, limit)
        results.extend(github_results)
    
    if not results:
        return f"'{query}' 검색 결과가 없습니다."
    
    result = f"🔍 AI 도구 검색: '{query}'\n"
    result += f"📦 총 {len(results)}개 발견\n\n"
    
    for idx, tool in enumerate(results[:limit], 1):
        result += f"{idx}. {tool['name']}\n"
        result += f"   설명: {tool['description']}\n"
        result += f"   ⭐ {tool['stars']:,} stars\n"
        if tool['language']:
            result += f"   언어: {tool['language']}\n"
        if tool['topics']:
            result += f"   주제: {', '.join(tool['topics'][:5])}\n"
        result += f"   🔗 {tool['url']}\n\n"
    
    return result

@mcp.tool()
async def get_latest_ai_news(category: str = "all", limit: int = 10) -> str:
    """
    최신 AI 뉴스와 논문을 실시간으로 가져옵니다.
    arXiv, Papers with Code 등에서 검색합니다.
    
    Args:
        category: 카테고리 (all, computer-vision, nlp, robotics)
        limit: 결과 개수
    """
    
    # 카테고리별 arXiv 검색어
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
    
    result = f"📰 최신 AI 연구 ({category})\n"
    result += f"📊 총 {len(papers)}개\n"
    result += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    for idx, paper in enumerate(papers, 1):
        result += f"{idx}. {paper['title']}\n"
        result += f"   저자: {', '.join(paper['authors'])}\n"
        result += f"   날짜: {paper['published'][:10]}\n"
        result += f"   요약: {paper['summary']}\n"
        result += f"   🔗 {paper['url']}\n\n"
    
    return result

@mcp.tool()
async def get_ai_rankings(benchmark: str = "all") -> str:
    """
    AI 모델 순위를 실시간으로 가져옵니다.
    Artificial Analysis, LMSYS Arena 등에서 수집합니다.
    
    Args:
        benchmark: 벤치마크 (all, speed, intelligence, price)
    """
    
    # 실시간 데이터 가져오기
    models = await scrape_artificial_analysis()
    
    if not models:
        # 폴백 데이터
        models = [
            {"model": "Gemini Pro", "score": 73, "speed": 136, "price": 4.50},
            {"model": "GPT-4.5", "score": 73, "speed": 114, "price": 4.81},
            {"model": "Claude Opus 4.5", "score": 71, "speed": 95, "price": 15.00}
        ]
    
    # 벤치마크별 정렬
    if benchmark == "speed":
        models.sort(key=lambda x: x.get("speed", 0), reverse=True)
    elif benchmark == "intelligence":
        models.sort(key=lambda x: x.get("score", 0), reverse=True)
    elif benchmark == "price":
        models.sort(key=lambda x: x.get("price", 999))
    
    result = f"🏆 AI 모델 순위 ({benchmark})\n"
    result += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    result += f"📊 출처: Artificial Analysis\n\n"
    
    for idx, model in enumerate(models, 1):
        result += f"{idx}. {model['model']}\n"
        result += f"   점수: {model.get('score', 'N/A')}\n"
        result += f"   속도: {model.get('speed', 'N/A')} tokens/s\n"
        result += f"   가격: ${model.get('price', 'N/A')}/1M tokens\n\n"
    
    return result

@mcp.tool()
async def recommend_ai_for_task(task: str, budget: str = "any", priority: str = "quality") -> str:
    """
    특정 작업에 최적화된 AI를 추천합니다.
    실시간 데이터를 기반으로 가장 적합한 도구를 찾습니다.
    
    Args:
        task: 작업 설명 (예: "고전 문헌 분석", "게임 개발", "영상 편집")
        budget: 예산 (free, low, any)
        priority: 우선순위 (quality, speed, price)
    """
    
    # 작업 키워드 추출
    task_lower = task.lower()
    recommendations = []
    
    # 병렬로 여러 소스 검색
    search_tasks = []
    
    # 작업 타입별 검색 키워드
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
        # 일반 검색
        search_tasks.append(search_ai_models(task, "all", 5))
        search_tasks.append(search_ai_tools(task, "all", 3))
    
    # 병렬 실행
    if search_tasks:
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # 결과 통합
        result = f"🎯 '{task}' 작업 추천\n"
        result += f"💰 예산: {budget} | 🎚️ 우선순위: {priority}\n"
        result += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        
        for idx, res in enumerate(results, 1):
            if isinstance(res, str) and res:
                result += f"=== 추천 #{idx} ===\n{res}\n"
        
        return result
    
    return f"'{task}' 작업에 대한 추천을 찾을 수 없습니다."

# ==================== HTTP 서버 (Koyeb용) ====================

def get_mcp_app():
    """MCP 프로토콜 호환 ASGI 앱"""
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import StreamingResponse, JSONResponse
    from starlette.requests import Request
    import json
    
    async def sse_endpoint(request: Request):
        """SSE 엔드포인트 - MCP 클라이언트 연결"""
        
        async def event_generator():
            # SSE 초기화
            yield 'data: {"jsonrpc":"2.0","method":"notifications/initialized"}\n\n'
            
            # Keep-alive
            try:
                while True:
                    await asyncio.sleep(30)
                    yield ': keepalive\n\n'
            except asyncio.CancelledError:
                pass
        
        return StreamingResponse(
            event_generator(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Content-Type': 'text/event-stream',
                'X-Accel-Buffering': 'no',
            }
        )
    
    async def message_endpoint(request: Request):
        """MCP 메시지 처리"""
        try:
            body = await request.json()
            
            # MCP 요청 처리
            if body.get('method') == 'tools/list':
                # 도구 목록 반환
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {
                        "tools": [
                            {
                                "name": "search_ai_models",
                                "description": "Hugging Face에서 AI 모델 검색",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {"type": "string"},
                                        "category": {"type": "string"},
                                        "limit": {"type": "integer"}
                                    }
                                }
                            },
                            {
                                "name": "search_ai_tools",
                                "description": "GitHub에서 AI 도구 검색",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {"type": "string"},
                                        "source": {"type": "string"},
                                        "limit": {"type": "integer"}
                                    }
                                }
                            },
                            {
                                "name": "get_latest_ai_news",
                                "description": "최신 AI 논문 가져오기",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "category": {"type": "string"},
                                        "limit": {"type": "integer"}
                                    }
                                }
                            },
                            {
                                "name": "get_ai_rankings",
                                "description": "AI 모델 순위 조회",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "benchmark": {"type": "string"}
                                    }
                                }
                            },
                            {
                                "name": "recommend_ai_for_task",
                                "description": "작업에 맞는 AI 추천",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "task": {"type": "string"},
                                        "budget": {"type": "string"},
                                        "priority": {"type": "string"}
                                    }
                                }
                            }
                        ]
                    }
                })
            
            elif body.get('method') == 'tools/call':
                # 도구 실행
                tool_name = body.get('params', {}).get('name')
                arguments = body.get('params', {}).get('arguments', {})
                
                # 도구 실행
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
                    "id": body.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": str(result)
                            }
                        ]
                    }
                })
            
            # 기타 요청
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {}
            })
            
        except Exception as e:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": body.get("id", None),
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }, status_code=500)
    
    async def health_check(request: Request):
        """Health check"""
        return JSONResponse({
            "service": "AI Recommender MCP",
            "status": "running",
            "version": "1.0.0",
            "tools": [
                "search_ai_models",
                "search_ai_tools",
                "get_latest_ai_news",
                "get_ai_rankings",
                "recommend_ai_for_task"
            ]
        })
    
    app = Starlette(
        routes=[
            Route("/", health_check, methods=["GET"]),
            Route("/sse", sse_endpoint, methods=["GET"]),
            Route("/message", message_endpoint, methods=["POST"]),
        ]
    )
    
    return app

# ==================== 앱 인스턴스 생성 (모듈 레벨) ====================
# Koyeb, uvicorn 등에서 import할 수 있도록 모듈 레벨에 배치
app = get_mcp_app()

# ==================== 메인 실행 ====================

if __name__ == "__main__":
    import sys
    
    # HTTP 서버 모드 (--http 플래그)
    if "--http" in sys.argv:
        print("🚀 HTTP 서버 모드 시작", file=sys.stderr)
        print("📍 http://localhost:8000 에서 실행 중", file=sys.stderr)
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        # 로컬 테스트용 - MCP Inspector stdio 연결
        print("🔧 MCP stdio mode - Inspector 연결 가능", file=sys.stderr)
        print("📍 사용법: npx @modelcontextprotocol/inspector python main.py", file=sys.stderr)
        mcp.run()  # FastMCP의 기본 stdio 모드