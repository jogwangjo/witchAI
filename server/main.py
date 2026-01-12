import sys
import os
from pathlib import Path
import uvicorn 

# 1. 경로 보정
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# 2. 필요한 모듈 임포트
from mcp.server.fastmcp import FastMCP

# tools 가져오기
try:
    from tools.quant_engine import analyzer
except ImportError:
    try:
        from server.tools.quant_engine import analyzer
    except ImportError:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from tools.quant_engine import analyzer

# 3. [핵심 수정 부분 A] 포트를 먼저 정의하고, FastMCP 생성자 안에서 host/port를 설정합니다.
port = int(os.getenv("PORT", 8000))

# 여기서 host='0.0.0.0'과 port=port를 설정해야 합니다.
mcp = FastMCP("Stock-Pattern-Analyzer", host="0.0.0.0", port=port)

# 4. 툴 등록
@mcp.tool()
async def analyze_stock_pattern(ticker: str, window_days: int = 30) -> str:
    """
    주식의 현재 차트 패턴을 분석하고, 과거 10년 치 데이터 중 가장 유사했던 시점을 찾아줍니다.
    """
    result = await analyzer.find_similar_patterns(ticker, window_size=window_days)
    
    if "error" in result:
        return f"분석 중 오류 발생: {result['error']}"
    
    matches = result["top_matches"]
    if not matches:
        return f"'{ticker}'의 현재 패턴과 유사도 80% 이상인 과거 패턴을 찾을 수 없습니다."
    
    response = f"""
📊 **[{ticker}] 주가 패턴 정밀 분석 결과**
- 분석 알고리즘: Z-Score Normalization + Pearson Correlation
- 분석 기간: 최근 {window_days}일 ({result['current_period']['start']} ~ {result['current_period']['end']})

발견된 가장 유사한 과거 사례 (Top {len(matches)}):
"""
    for i, match in enumerate(matches, 1):
        trend = "상승" if match['after_5days_return'] > 0 else "하락"
        response += f"""
{i}. **{match['start_date']} ~ {match['end_date']}** (유사도: {match['similarity']}%)
   - 당시 패턴 종료 후 5일간 주가: {match['after_5days_return']}% {trend}
   - [LLM 요청 사항]: 위 기간({match['start_date']}~{match['end_date']}) 동안 {ticker}와 관련된 주요 뉴스와 시장 이슈를 검색해서, 현재 상황과 비교 설명해주세요.
"""
    response += "\n⚠️ 이 분석은 과거의 통계적 유사성만을 보여주며, 미래의 수익을 보장하지 않습니다."
    return response

if __name__ == "__main__":
    print(f"🚀 Starting MCP Server on 0.0.0.0:{port}", file=sys.stderr)

    # 5. [핵심 수정 부분 B] run() 안에는 transport만 남깁니다. (이미 위에서 설정했으므로)
    mcp.run(transport='sse')