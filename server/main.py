import sys
import os
from pathlib import Path
import uvicorn # 실행 제어를 위해 필수

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

# 3. MCP 서버 초기화
mcp = FastMCP("Stock-Pattern-Analyzer")

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

# 5. 서버 실행 (이 부분이 핵심입니다!)
if __name__ == "__main__":
    # Koyeb이 제공하는 포트 번호 가져오기 (없으면 8000)
    port = int(os.getenv("PORT", 8000))
    host = "0.0.0.0"

    print(f"🚀 Starting MCP Server on {host}:{port}", file=sys.stderr)
    
    # [핵심] uvicorn.run을 패치하여 host와 port를 강제로 설정
    # FastMCP.run()이 내부적으로 uvicorn.run을 부를 때 이 설정을 쓰게 만듭니다.
    original_run = uvicorn.run

    def patched_run(app, **kwargs):
        kwargs['host'] = host
        kwargs['port'] = port
        print(f"🔧 Applied patch: host={host}, port={port}", file=sys.stderr)
        return original_run(app, **kwargs)

    uvicorn.run = patched_run

    # 이제 실행 (인자 없이 실행해도 위 패치가 적용됨)
    mcp.run(transport='sse')