import sys
import os

# [중요] 경로 문제 해결: 현재 파일의 위치를 시스템 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP
import asyncio

# 모듈 가져오기 (경로 유동성 확보)
try:
    from tools.quant_engine import analyzer
except ImportError:
    # 실행 위치에 따라 server.tools로 인식될 수도 있음
    from server.tools.quant_engine import analyzer

# 서버 초기화
mcp = FastMCP("Stock-Pattern-Analyzer")

@mcp.tool()
async def analyze_stock_pattern(ticker: str, window_days: int = 30) -> str:
    """
    주식의 현재 차트 패턴을 분석하고, 과거 10년 치 데이터 중 가장 유사했던 시점을 찾아줍니다.
    이 도구는 단순 가격 비교가 아닌, 'Z-Score 정규화'와 '피어슨 상관계수'를 사용하여 
    가격 레벨이 다르더라도 '추세와 모양'이 비슷한 시점을 수학적으로 찾아냅니다.
    
    Args:
        ticker: 종목 코드 (예: 한국 주식 '005930.KS', 미국 주식 'AAPL', 'TSLA')
        window_days: 분석할 패턴의 기간 (기본값 30일)
    """
    
    # 1. 분석 엔진 실행
    result = await analyzer.find_similar_patterns(ticker, window_size=window_days)
    
    if "error" in result:
        return f"분석 중 오류 발생: {result['error']}"
    
    # 2. 결과 포맷팅 (LLM이 읽기 좋게)
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

    response += "\n⚠️ 이 분석은 과거의 통계적 유사성만을 보여주며, 미래의 수익을 보장하지 않습니다. 투자의 참고 지표로만 활용하세요."
    
    return response

# Koyeb 등에서 ASGI 앱으로 인식하기 위한 변수 노출
app = mcp._get_server_app() 

if __name__ == "__main__":
    # 반드시 'sse'로 설정해야 HTTP 엔드포인트가 생성됩니다.
    mcp.run(transport='sse')