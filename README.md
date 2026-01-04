# AI Recommender MCP Server

PlayMCP 공모전을 위한 AI 추천 MCP 서버 - AI 동향, 순위, Agent 추천을 제공하는 종합 플랫폼

## 🌟 주요 기능

### 1. AI 뉴스 및 동향 (`get_ai_news`)
- arXiv 최신 논문 자동 수집
- Hugging Face 신규 모델 트래킹
- GitHub AI 프로젝트 트렌드
- 카테고리별 필터링 (연구/산업/제품)

### 2. AI 모델 순위 (`get_ai_rankings`)
- Chatbot Arena 리더보드
- Open LLM 벤치마크
- MMLU, HellaSwag 등 다양한 벤치마크
- 오픈소스/상용 모델 구분

### 3. AI Agent 카탈로그 (`list_ai_agents`)
- 80+ AI 에이전트 데이터베이스
- 카테고리별 분류 (개발/연구/비즈니스/크리에이티브)
- 세부 분류 (코딩/웹개발/앱개발/게임개발 등)

### 4. 맞춤형 추천 (`recommend_ai_tools`)
- 작업 목적 기반 AI 도구 추천
- 경험 수준별 필터링 (초급/중급/고급)
- 예산 범위 고려 (무료/유료/엔터프라이즈)
- 매칭 점수 및 추천 이유 제공

### 5. AI Agent 검색 (`search_ai_agents`)
- 키워드 기반 검색
- 프레임워크/언어/라이선스 필터
- 관련도 점수 계산

## 🚀 빠른 시작

### 로컬 개발

```bash
# 저장소 클론
git clone https://github.com/your-repo/ai-recommender-mcp.git
cd ai-recommender-mcp

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 서버 실행
uvicorn server.main:app --reload --port 8000
```

### Docker 사용

```bash
# 이미지 빌드
docker build -t ai-recommender-mcp .

# 컨테이너 실행
docker run -p 8000:8000 ai-recommender-mcp
```

### 클라우드 배포

**Railway**
```bash
railway login
railway init
railway up
```

**Render**
1. GitHub 저장소 연결
2. Docker 배포 선택
3. 환경변수 설정
4. 배포

**Fly.io**
```bash
fly launch
fly deploy
```

## 📡 MCP 클라이언트 설정

### Claude Desktop 설정

`claude_desktop_config.json`에 추가:

```json
{
  "mcpServers": {
    "ai-recommender": {
      "url": "https://your-server.com/mcp/v1/messages",
      "transport": {
        "type": "streamable-http"
      },
      "headers": {
        "X-API-Key": "your-api-key-here"
      }
    }
  }
}
```

### VS Code MCP Extension 설정

```json
{
  "mcp.servers": [
    {
      "name": "AI Recommender",
      "url": "https://your-server.com/mcp/v1/messages",
      "type": "streamable-http"
    }
  ]
}
```

## 🔧 API 사용 예시

### 1. AI 뉴스 가져오기

```python
{
  "method": "tools/call",
  "params": {
    "name": "get_ai_news",
    "arguments": {
      "category": "research",
      "limit": 5
    }
  }
}
```

**응답:**
```json
{
  "category": "research",
  "count": 5,
  "news": [
    {
      "title": "Attention Is All You Need v2",
      "source": "arXiv",
      "date": "2025-01-03",
      "summary": "...",
      "url": "..."
    }
  ]
}
```

### 2. 게임 개발용 AI 도구 추천

```python
{
  "method": "tools/call",
  "params": {
    "name": "recommend_ai_tools",
    "arguments": {
      "task": "게임 개발 - 2D 아트 에셋 생성",
      "experience_level": "beginner",
      "budget": "free"
    }
  }
}
```

**응답:**
```json
{
  "recommendations": [
    {
      "agent": {
        "name": "Scenario",
        "description": "AI-powered game asset generation",
        "pricing": {"free": true, "paid": true}
      },
      "match_score": 0.95,
      "reasons": [
        "game-dev 분야에 특화됨",
        "beginner 레벨에 적합",
        "무료 플랜 제공"
      ]
    }
  ]
}
```

## 🏆 PlayMCP 공모전 준수사항

### ✅ 필수 요구사항
- [x] MCP 버전: 2025-03-26 이상
- [x] Streamable HTTP 전송 방식
- [x] Remote MCP 서버 (공개 URL)
- [x] Stateless 아키텍처
- [x] OAuth/커스텀 헤더 인증 지원

### 📊 평가 기준 대응

#### 1. 기능성 (30점)
- **완성도**: 5개 핵심 기능 완벽 구현
- **활용성**: 실제 AI 개발/연구에 즉시 활용 가능
- **독창성**: AI 추천이라는 메타적 접근

#### 2. 기술적 우수성 (30점)
- **MCP 표준**: 2025-03-26 스펙 완벽 준수
- **성능**: 비동기 처리, 캐싱으로 최적화
- **안정성**: 에러 핸들링, Health check

#### 3. 실용성 (20점)
- **문제 해결**: AI 도구 선택의 어려움 해결
- **사용자 경험**: 직관적인 인터페이스
- **확장성**: 새로운 AI Agent 쉽게 추가 가능

#### 4. 창의성 (20점)
- **차별화**: AI를 추천하는 AI - 메타적 접근
- **혁신성**: 실시간 동향 + 큐레이션 결합
- **참신성**: AI 에코시스템 전체를 다루는 첫 MCP

## 🧪 테스트

### MCP Inspector로 검증

```bash
# MCP Inspector 설치
npm install -g @anthropic-ai/mcp-inspector

# 서버 검증
mcp-inspector http://localhost:8000/mcp/v1/messages
```

### 단위 테스트

```bash
pytest tests/ -v
```

### 통합 테스트

```bash
pytest tests/integration/ -v
```

## 📈 로드맵

### Phase 1 (현재)
- [x] 핵심 기능 구현
- [x] MCP 표준 준수
- [x] 기본 데이터베이스

### Phase 2
- [ ] 실시간 데이터 수집 자동화
- [ ] 벡터 DB 기반 검색 개선
- [ ] 사용자 피드백 시스템

### Phase 3
- [ ] 개인화된 추천 알고리즘
- [ ] AI Agent 자동 테스트
- [ ] 커뮤니티 리뷰 통합

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 라이선스

MIT License - 자유롭게 사용, 수정, 배포 가능

## 📧 연락처

- GitHub Issues: [링크]
- Email: your-email@example.com

## 🙏 감사의 말

- Anthropic MCP 표준
- 오픈소스 AI 커뮤니티
- PlayMCP 공모전 주최측

---

**Made with ❤️ for PlayMCP Contest**