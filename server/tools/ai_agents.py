from typing import List, Dict, Any
import json
from pathlib import Path

class AIAgentCatalog:
    """AI Agent 데이터베이스 및 추천 시스템"""
    
    def __init__(self):
        self.agents = self._load_agent_catalog()
        self.categories = self._load_categories()
    
    def _load_agent_catalog(self) -> List[Dict[str, Any]]:
        """Agent 카탈로그 로드 (실제로는 JSON 파일이나 DB에서)"""
        return [
            # 개발 도구
            {
                "id": "cursor",
                "name": "Cursor",
                "category": "development",
                "subcategory": "coding",
                "description": "AI-powered code editor with intelligent suggestions",
                "features": [
                    "Natural language to code",
                    "Code completion",
                    "Bug detection and fixing",
                    "Refactoring suggestions",
                    "Multi-file editing"
                ],
                "tech_stack": ["VSCode-based", "GPT-4"],
                "pricing": {"free": True, "paid": True, "price_range": "$20/month"},
                "experience_level": ["beginner", "intermediate", "advanced"],
                "url": "https://cursor.sh",
                "rating": 4.8,
                "popularity": 9500,
                "last_updated": "2025-01-01"
            },
            {
                "id": "github-copilot",
                "name": "GitHub Copilot",
                "category": "development",
                "subcategory": "coding",
                "description": "AI pair programmer",
                "features": [
                    "Code completion",
                    "Function generation",
                    "Test generation",
                    "Multiple language support"
                ],
                "tech_stack": ["OpenAI Codex"],
                "pricing": {"free": False, "paid": True, "price_range": "$10/month"},
                "experience_level": ["intermediate", "advanced"],
                "url": "https://github.com/features/copilot",
                "rating": 4.7,
                "popularity": 15000,
                "last_updated": "2025-01-03"
            },
            {
                "id": "v0-vercel",
                "name": "v0 by Vercel",
                "category": "development",
                "subcategory": "web-dev",
                "description": "Generate UI components with AI",
                "features": [
                    "Text to UI",
                    "React/Vue/Svelte support",
                    "Responsive design",
                    "Tailwind CSS integration"
                ],
                "tech_stack": ["React", "Next.js", "Tailwind"],
                "pricing": {"free": True, "paid": True, "price_range": "$20/month"},
                "experience_level": ["beginner", "intermediate"],
                "url": "https://v0.dev",
                "rating": 4.9,
                "popularity": 8000,
                "last_updated": "2024-12-28"
            },
            {
                "id": "bolt-new",
                "name": "Bolt.new",
                "category": "development",
                "subcategory": "fullstack",
                "description": "Full-stack web app builder",
                "features": [
                    "Instant deployment",
                    "Full-stack generation",
                    "Database integration",
                    "API generation"
                ],
                "tech_stack": ["Node.js", "React", "Various DBs"],
                "pricing": {"free": True, "paid": True, "price_range": "$30/month"},
                "experience_level": ["beginner", "intermediate", "advanced"],
                "url": "https://bolt.new",
                "rating": 4.6,
                "popularity": 5000,
                "last_updated": "2025-01-02"
            },
            
            # 게임 개발
            {
                "id": "scenario",
                "name": "Scenario",
                "category": "development",
                "subcategory": "game-dev",
                "description": "AI-powered game asset generation",
                "features": [
                    "Character generation",
                    "Environment assets",
                    "Consistent art style",
                    "3D model support"
                ],
                "tech_stack": ["Stable Diffusion", "Custom Models"],
                "pricing": {"free": True, "paid": True, "price_range": "$30/month"},
                "experience_level": ["beginner", "intermediate", "advanced"],
                "url": "https://scenario.com",
                "rating": 4.7,
                "popularity": 3500,
                "last_updated": "2024-12-20"
            },
            {
                "id": "roblox-assistant",
                "name": "Roblox Assistant",
                "category": "development",
                "subcategory": "game-dev",
                "description": "AI coding assistant for Roblox Studio",
                "features": [
                    "Lua code generation",
                    "Game logic suggestions",
                    "Script optimization",
                    "Bug fixing"
                ],
                "tech_stack": ["Lua", "Roblox API"],
                "pricing": {"free": True, "paid": False},
                "experience_level": ["beginner", "intermediate"],
                "url": "https://create.roblox.com",
                "rating": 4.5,
                "popularity": 4000,
                "last_updated": "2024-12-15"
            },
            
            # 앱 개발
            {
                "id": "flutterflow-ai",
                "name": "FlutterFlow AI",
                "category": "development",
                "subcategory": "app-dev",
                "description": "No-code app builder with AI",
                "features": [
                    "Drag-and-drop UI",
                    "AI-powered code generation",
                    "Cross-platform support",
                    "Firebase integration"
                ],
                "tech_stack": ["Flutter", "Dart", "Firebase"],
                "pricing": {"free": True, "paid": True, "price_range": "$30/month"},
                "experience_level": ["beginner", "intermediate"],
                "url": "https://flutterflow.io",
                "rating": 4.6,
                "popularity": 6000,
                "last_updated": "2024-12-25"
            },
            
            # 연구 도구
            {
                "id": "elicit",
                "name": "Elicit",
                "category": "research",
                "subcategory": "literature-review",
                "description": "AI research assistant for papers",
                "features": [
                    "Paper summarization",
                    "Literature search",
                    "Citation extraction",
                    "Concept mapping"
                ],
                "tech_stack": ["LLM", "Semantic Scholar API"],
                "pricing": {"free": True, "paid": True, "price_range": "$10/month"},
                "experience_level": ["intermediate", "advanced"],
                "url": "https://elicit.org",
                "rating": 4.8,
                "popularity": 7000,
                "last_updated": "2025-01-01"
            },
            {
                "id": "consensus",
                "name": "Consensus",
                "category": "research",
                "subcategory": "literature-review",
                "description": "AI-powered research engine",
                "features": [
                    "Scientific paper search",
                    "Consensus analysis",
                    "Citation network",
                    "Study quality assessment"
                ],
                "tech_stack": ["LLM", "Research databases"],
                "pricing": {"free": True, "paid": True, "price_range": "$9/month"},
                "experience_level": ["beginner", "intermediate", "advanced"],
                "url": "https://consensus.app",
                "rating": 4.7,
                "popularity": 5500,
                "last_updated": "2024-12-30"
            },
            
            # 비즈니스
            {
                "id": "notion-ai",
                "name": "Notion AI",
                "category": "business",
                "subcategory": "productivity",
                "description": "AI-powered workspace",
                "features": [
                    "Writing assistant",
                    "Document generation",
                    "Data analysis",
                    "Task automation"
                ],
                "tech_stack": ["GPT-4"],
                "pricing": {"free": False, "paid": True, "price_range": "$10/month"},
                "experience_level": ["beginner", "intermediate"],
                "url": "https://notion.so",
                "rating": 4.6,
                "popularity": 12000,
                "last_updated": "2025-01-03"
            },
            
            # 크리에이티브
            {
                "id": "midjourney",
                "name": "Midjourney",
                "category": "creative",
                "subcategory": "image-generation",
                "description": "AI art generation platform",
                "features": [
                    "High-quality image generation",
                    "Style control",
                    "Variations",
                    "Upscaling"
                ],
                "tech_stack": ["Custom diffusion model"],
                "pricing": {"free": False, "paid": True, "price_range": "$10-60/month"},
                "experience_level": ["beginner", "intermediate", "advanced"],
                "url": "https://midjourney.com",
                "rating": 4.9,
                "popularity": 18000,
                "last_updated": "2025-01-02"
            },
            {
                "id": "jasper",
                "name": "Jasper AI",
                "category": "creative",
                "subcategory": "writing",
                "description": "AI content creation platform",
                "features": [
                    "Blog post generation",
                    "Marketing copy",
                    "SEO optimization",
                    "Multi-language support"
                ],
                "tech_stack": ["GPT-4"],
                "pricing": {"free": False, "paid": True, "price_range": "$39/month"},
                "experience_level": ["beginner", "intermediate"],
                "url": "https://jasper.ai",
                "rating": 4.5,
                "popularity": 9000,
                "last_updated": "2024-12-28"
            }
        ]
    
    def _load_categories(self) -> Dict[str, Any]:
        """카테고리 구조 로드"""
        return {
            "development": {
                "name": "개발 도구",
                "subcategories": {
                    "coding": "코딩 어시스턴트",
                    "web-dev": "웹 개발",
                    "app-dev": "앱 개발",
                    "game-dev": "게임 개발",
                    "fullstack": "풀스택 개발"
                }
            },
            "research": {
                "name": "연구 도구",
                "subcategories": {
                    "literature-review": "문헌 조사",
                    "data-analysis": "데이터 분석",
                    "experiment": "실험 설계"
                }
            },
            "business": {
                "name": "비즈니스",
                "subcategories": {
                    "productivity": "생산성",
                    "analytics": "분석",
                    "automation": "자동화"
                }
            },
            "creative": {
                "name": "크리에이티브",
                "subcategories": {
                    "image-generation": "이미지 생성",
                    "writing": "글쓰기",
                    "video": "비디오",
                    "music": "음악"
                }
            }
        }
    
    def list_agents(self, category: str = "all", subcategory: str = None) -> Dict[str, Any]:
        """Agent 목록 반환"""
        filtered = self.agents
        
        if category != "all":
            filtered = [a for a in filtered if a["category"] == category]
        
        if subcategory:
            filtered = [a for a in filtered if a["subcategory"] == subcategory]
        
        return {
            "category": category,
            "subcategory": subcategory,
            "count": len(filtered),
            "agents": filtered
        }
    
    def search_agents(self, query: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Agent 검색"""
        query_lower = query.lower()
        results = []
        
        for agent in self.agents:
            score = 0
            
            # 이름 매칭
            if query_lower in agent["name"].lower():
                score += 10
            
            # 설명 매칭
            if query_lower in agent["description"].lower():
                score += 5
            
            # 기능 매칭
            for feature in agent["features"]:
                if query_lower in feature.lower():
                    score += 3
            
            # 필터 적용
            if filters:
                if "language" in filters and filters["language"] not in agent.get("tech_stack", []):
                    continue
                if "framework" in filters and filters["framework"] not in agent.get("tech_stack", []):
                    continue
            
            if score > 0:
                results.append({
                    **agent,
                    "relevance_score": score
                })
        
        # 관련도순 정렬
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return {
            "query": query,
            "filters": filters,
            "count": len(results),
            "results": results
        }
    
    def recommend_for_task(self, task: str, experience_level: str, budget: str) -> Dict[str, Any]:
        """작업에 맞는 Agent 추천"""
        task_lower = task.lower()
        recommendations = []
        
        # 키워드 기반 매칭
        task_keywords = {
            "게임": ["game-dev"],
            "game": ["game-dev"],
            "앱": ["app-dev"],
            "app": ["app-dev"],
            "웹": ["web-dev"],
            "web": ["web-dev"],
            "코딩": ["coding"],
            "coding": ["coding"],
            "연구": ["literature-review", "data-analysis"],
            "research": ["literature-review", "data-analysis"],
            "이미지": ["image-generation"],
            "image": ["image-generation"],
            "글": ["writing"],
            "writing": ["writing"]
        }
        
        relevant_subcategories = []
        for keyword, subcats in task_keywords.items():
            if keyword in task_lower:
                relevant_subcategories.extend(subcats)
        
        for agent in self.agents:
            score = 0
            reasons = []
            
            # 서브카테고리 매칭
            if agent["subcategory"] in relevant_subcategories:
                score += 50
                reasons.append(f"{agent['subcategory']} 분야에 특화됨")
            
            # 경험 레벨 매칭
            if experience_level in agent["experience_level"]:
                score += 20
                reasons.append(f"{experience_level} 레벨에 적합")
            
            # 예산 매칭
            if budget == "free" and agent["pricing"]["free"]:
                score += 30
                reasons.append("무료 플랜 제공")
            elif budget == "paid" and agent["pricing"]["paid"]:
                score += 10
            
            # 설명에서 키워드 매칭
            if any(keyword in agent["description"].lower() for keyword in task_lower.split()):
                score += 15
                reasons.append("작업 설명과 일치")
            
            if score > 30:  # 최소 점수
                recommendations.append({
                    "agent": agent,
                    "match_score": score / 100,
                    "reasons": reasons
                })
        
        # 점수순 정렬
        recommendations.sort(key=lambda x: x["match_score"], reverse=True)
        
        return {
            "task": task,
            "experience_level": experience_level,
            "budget": budget,
            "recommendations": recommendations[:5],  # 상위 5개
            "total_found": len(recommendations)
        }