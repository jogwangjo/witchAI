import aiohttp
import asyncio
from typing import List, Dict, Any
from datetime import datetime, timedelta
import feedparser
from bs4 import BeautifulSoup

class AINewsCollector:
    """AI 뉴스를 다양한 소스에서 수집하는 클래스"""
    
    def __init__(self):
        self.sources = {
            "arxiv": "http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL&sortBy=submittedDate&sortOrder=descending&max_results=",
            "huggingface": "https://huggingface.co/api/models",
            "github_trending": "https://api.github.com/search/repositories?q=topic:artificial-intelligence+created:>{}",
        }
    
    async def fetch_arxiv_papers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """arXiv에서 최신 AI 논문 가져오기"""
        try:
            url = self.sources["arxiv"] + str(limit)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    content = await response.text()
            
            feed = feedparser.parse(content)
            papers = []
            
            for entry in feed.entries:
                papers.append({
                    "title": entry.title,
                    "authors": [author.name for author in entry.authors],
                    "summary": entry.summary[:300] + "...",
                    "published": entry.published,
                    "url": entry.link,
                    "categories": [tag.term for tag in entry.tags],
                    "source": "arXiv",
                    "type": "research"
                })
            
            return papers
        except Exception as e:
            print(f"Error fetching arXiv papers: {e}")
            return []
    
    async def fetch_huggingface_models(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Hugging Face에서 최신 모델 정보 가져오기"""
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "sort": "lastModified",
                    "direction": -1,
                    "limit": limit,
                    "full": True
                }
                async with session.get(self.sources["huggingface"], params=params) as response:
                    if response.status == 200:
                        models = await response.json()
                    else:
                        return []
            
            formatted_models = []
            for model in models:
                formatted_models.append({
                    "title": f"New Model: {model.get('id', 'Unknown')}",
                    "model_id": model.get('id'),
                    "author": model.get('author', 'Unknown'),
                    "downloads": model.get('downloads', 0),
                    "likes": model.get('likes', 0),
                    "tags": model.get('tags', []),
                    "last_modified": model.get('lastModified'),
                    "url": f"https://huggingface.co/{model.get('id')}",
                    "source": "Hugging Face",
                    "type": "model"
                })
            
            return formatted_models
        except Exception as e:
            print(f"Error fetching Hugging Face models: {e}")
            return []
    
    async def fetch_github_trending(self, days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        """GitHub에서 최근 트렌딩 AI 프로젝트 가져오기"""
        try:
            date_filter = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            url = self.sources["github_trending"].format(date_filter)
            
            async with aiohttp.ClientSession() as session:
                headers = {"Accept": "application/vnd.github.v3+json"}
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        repos = data.get('items', [])[:limit]
                    else:
                        return []
            
            projects = []
            for repo in repos:
                projects.append({
                    "title": repo.get('full_name'),
                    "description": repo.get('description', ''),
                    "stars": repo.get('stargazers_count', 0),
                    "language": repo.get('language', 'Unknown'),
                    "url": repo.get('html_url'),
                    "created_at": repo.get('created_at'),
                    "topics": repo.get('topics', []),
                    "source": "GitHub",
                    "type": "project"
                })
            
            return projects
        except Exception as e:
            print(f"Error fetching GitHub trending: {e}")
            return []
    
    async def get_ai_news_aggregated(self, category: str = "all", limit: int = 10) -> Dict[str, Any]:
        """모든 소스에서 뉴스 수집 및 집계"""
        
        # 병렬로 모든 소스에서 데이터 수집
        results = await asyncio.gather(
            self.fetch_arxiv_papers(limit // 3 + 1),
            self.fetch_huggingface_models(limit // 3 + 1),
            self.fetch_github_trending(limit=limit // 3 + 1),
            return_exceptions=True
        )
        
        all_news = []
        for result in results:
            if isinstance(result, list):
                all_news.extend(result)
        
        # 카테고리 필터링
        if category != "all":
            category_map = {
                "research": ["research"],
                "industry": ["model", "project"],
                "products": ["model"]
            }
            allowed_types = category_map.get(category, [])
            all_news = [n for n in all_news if n.get("type") in allowed_types]
        
        # 날짜순 정렬
        all_news.sort(
            key=lambda x: x.get("published") or x.get("last_modified") or x.get("created_at") or "",
            reverse=True
        )
        
        return {
            "category": category,
            "total_count": len(all_news),
            "items": all_news[:limit],
            "sources": ["arXiv", "Hugging Face", "GitHub"],
            "updated_at": datetime.now().isoformat()
        }

# 캐싱을 위한 간단한 메모리 캐시
_cache = {}
_cache_ttl = 300  # 5분

async def get_cached_news(category: str = "all", limit: int = 10) -> Dict[str, Any]:
    """캐시된 뉴스 가져오기 (성능 최적화)"""
    cache_key = f"news_{category}_{limit}"
    
    if cache_key in _cache:
        cached_data, timestamp = _cache[cache_key]
        if (datetime.now() - timestamp).seconds < _cache_ttl:
            return cached_data
    
    # 캐시 미스 - 새로 가져오기
    collector = AINewsCollector()
    news_data = await collector.get_ai_news_aggregated(category, limit)
    _cache[cache_key] = (news_data, datetime.now())
    
    return news_data