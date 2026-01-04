"""
실제 API를 사용한 실시간 AI 정보 수집

사용 가능한 무료 API:
1. Hugging Face API - 모델 정보
2. GitHub API - 트렌딩 AI 프로젝트
3. arXiv API - 최신 논문
4. Papers with Code API - 벤치마크 결과
"""

import aiohttp
import asyncio
from typing import List, Dict, Any
from datetime import datetime, timedelta
import os

class AIDataAPI:
    """무료 API를 사용한 실시간 AI 데이터 수집"""
    
    def __init__(self):
        self.hf_token = os.getenv("HUGGINGFACE_TOKEN", "")  # 선택사항
        self.github_token = os.getenv("GITHUB_TOKEN", "")   # 선택사항
    
    async def fetch_huggingface_models(self, task: str = None, limit: int = 20) -> List[Dict]:
        """
        Hugging Face에서 모델 검색
        API 문서: https://huggingface.co/docs/hub/api
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://huggingface.co/api/models"
                params = {
                    "sort": "downloads",
                    "direction": -1,
                    "limit": limit
                }
                
                if task:
                    # 작업별 필터링
                    task_filters = {
                        "text-generation": ["gpt", "llama", "mistral"],
                        "image-generation": ["stable-diffusion", "dall-e"],
                        "translation": ["translation", "multilingual"],
                    }
                    params["filter"] = task if task in task_filters else "text-generation"
                
                headers = {}
                if self.hf_token:
                    headers["Authorization"] = f"Bearer {self.hf_token}"
                
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        models = await response.json()
                        
                        return [
                            {
                                "name": m["id"],
                                "author": m.get("author", "Unknown"),
                                "downloads": m.get("downloads", 0),
                                "likes": m.get("likes", 0),
                                "tags": m.get("tags", []),
                                "pipeline_tag": m.get("pipeline_tag", ""),
                                "created_at": m.get("createdAt", ""),
                                "last_modified": m.get("lastModified", ""),
                                "source": "Hugging Face"
                            }
                            for m in models
                        ]
                    else:
                        print(f"HF API error: {response.status}")
                        return []
        except Exception as e:
            print(f"Error fetching Hugging Face: {e}")
            return []
    
    async def fetch_github_trending_ai(self, days: int = 7) -> List[Dict]:
        """
        GitHub에서 트렌딩 AI 프로젝트
        API 문서: https://docs.github.com/en/rest
        """
        try:
            async with aiohttp.ClientSession() as session:
                # 최근 N일간 생성된 AI 관련 프로젝트
                date_filter = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                
                url = "https://api.github.com/search/repositories"
                params = {
                    "q": f"topic:artificial-intelligence+OR+topic:machine-learning+created:>{date_filter}",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 20
                }
                
                headers = {
                    "Accept": "application/vnd.github.v3+json"
                }
                if self.github_token:
                    headers["Authorization"] = f"token {self.github_token}"
                
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        repos = data.get("items", [])
                        
                        return [
                            {
                                "name": repo["full_name"],
                                "description": repo.get("description", ""),
                                "stars": repo["stargazers_count"],
                                "language": repo.get("language", "Unknown"),
                                "url": repo["html_url"],
                                "topics": repo.get("topics", []),
                                "created_at": repo["created_at"],
                                "updated_at": repo["updated_at"],
                                "source": "GitHub"
                            }
                            for repo in repos
                        ]
                    else:
                        print(f"GitHub API error: {response.status}")
                        return []
        except Exception as e:
            print(f"Error fetching GitHub: {e}")
            return []
    
    async def fetch_arxiv_papers(self, category: str = "cs.AI", max_results: int = 20) -> List[Dict]:
        """
        arXiv에서 최신 AI 논문
        API 문서: https://arxiv.org/help/api
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = "http://export.arxiv.org/api/query"
                params = {
                    "search_query": f"cat:{category}",
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                    "max_results": max_results
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        import feedparser
                        content = await response.text()
                        feed = feedparser.parse(content)
                        
                        return [
                            {
                                "title": entry.title,
                                "authors": [author.name for author in entry.authors],
                                "summary": entry.summary[:500] + "...",
                                "published": entry.published,
                                "url": entry.link,
                                "categories": [tag.term for tag in entry.tags],
                                "source": "arXiv"
                            }
                            for entry in feed.entries
                        ]
                    else:
                        print(f"arXiv API error: {response.status}")
                        return []
        except Exception as e:
            print(f"Error fetching arXiv: {e}")
            return []
    
    async def search_models_by_task(self, task_description: str) -> Dict[str, Any]:
        """작업 설명으로 적합한 모델 찾기"""
        
        # 키워드 추출
        keywords = task_description.lower().split()
        
        # 작업 유형 판단
        task_type = "text-generation"  # 기본값
        
        if any(kw in task_description.lower() for kw in ["이미지", "image", "그림"]):
            task_type = "text-to-image"
        elif any(kw in task_description.lower() for kw in ["번역", "translation"]):
            task_type = "translation"
        elif any(kw in task_description.lower() for kw in ["요약", "summary"]):
            task_type = "summarization"
        
        # Hugging Face에서 관련 모델 검색
        models = await self.fetch_huggingface_models(task_type, limit=10)
        
        # 관련도 계산
        ranked_models = []
        for model in models:
            relevance_score = 0
            reasons = []
            
            # 태그 매칭
            for keyword in keywords:
                if any(keyword in tag.lower() for tag in model["tags"]):
                    relevance_score += 10
                    reasons.append(f"'{keyword}' 태그 매칭")
            
            # 다운로드 수 고려
            if model["downloads"] > 100000:
                relevance_score += 20
                reasons.append("높은 사용률")
            
            # 최근 업데이트
            try:
                last_mod = datetime.fromisoformat(model["last_modified"].replace('Z', '+00:00'))
                if (datetime.now(last_mod.tzinfo) - last_mod).days < 30:
                    relevance_score += 10
                    reasons.append("최근 업데이트")
            except:
                pass
            
            if relevance_score > 0:
                ranked_models.append({
                    **model,
                    "relevance_score": relevance_score,
                    "reasons": reasons
                })
        
        # 점수순 정렬
        ranked_models.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return {
            "task": task_description,
            "task_type": task_type,
            "models": ranked_models[:5],
            "total_found": len(ranked_models),
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_comprehensive_ai_update(self) -> Dict[str, Any]:
        """모든 소스에서 데이터를 가져와 종합"""
        
        # 병렬로 모든 API 호출
        results = await asyncio.gather(
            self.fetch_huggingface_models(limit=10),
            self.fetch_github_trending_ai(days=7),
            self.fetch_arxiv_papers(max_results=10),
            return_exceptions=True
        )
        
        hf_models, gh_repos, arxiv_papers = results
        
        return {
            "trending_models": hf_models if isinstance(hf_models, list) else [],
            "trending_projects": gh_repos if isinstance(gh_repos, list) else [],
            "latest_papers": arxiv_papers if isinstance(arxiv_papers, list) else [],
            "updated_at": datetime.now().isoformat(),
            "sources": ["Hugging Face", "GitHub", "arXiv"]
        }

# 싱글톤 인스턴스
api_client = AIDataAPI()

# 편의 함수들
async def get_trending_ai_models(limit: int = 10) -> List[Dict]:
    """트렌딩 AI 모델 가져오기"""
    return await api_client.fetch_huggingface_models(limit=limit)

async def search_models(task: str) -> Dict[str, Any]:
    """작업에 맞는 모델 검색"""
    return await api_client.search_models_by_task(task)

async def get_latest_ai_research(max_results: int = 20) -> List[Dict]:
    """최신 AI 연구 논문"""
    return await api_client.fetch_arxiv_papers(max_results=max_results)

async def get_all_updates() -> Dict[str, Any]:
    """종합 업데이트"""
    return await api_client.get_comprehensive_ai_update()