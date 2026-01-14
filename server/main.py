import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
from starlette.responses import JSONResponse, Response

# 1. 경로 보정
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# 2. 필수 모듈 임포트
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport

# =========================
# 3. 기존 주가 분석 툴 임포트
# =========================
try:
    from tools.quant_engine import analyzer
except ImportError:
    try:
        from server.tools.quant_engine import analyzer
    except ImportError:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from tools.quant_engine import analyzer

# 4. FastMCP 초기화
mcp = FastMCP("Stock-Pattern-Analyzer")

# =========================
# 5. 주식 분석 툴 등록 (실전 투자자용 고급 분석)
# =========================

@mcp.tool()
async def find_historical_pattern(ticker: str, window_days: int = 30) -> str:
    """
    현재 차트 패턴과 가장 유사한 과거 시점을 찾아 당시 이후 주가 흐름을 제시합니다.
    Z-Score 정규화와 피어슨 상관계수를 사용한 시계열 데이터마이닝 기법입니다.
    
    Args:
        ticker: 종목 코드 (예: AAPL, TSLA, 005930.KS)
        window_days: 분석 기간 (기본 30일)
    """
    try:
        result = await analyzer.find_similar_patterns(ticker, window_size=window_days)
        if "error" in result:
            return f"❌ {result['error']}"
        
        matches = result.get("top_matches", [])
        if not matches:
            return f"📊 [{ticker}] 현재 패턴과 80% 이상 유사한 과거 사례를 찾을 수 없습니다."
        
        period = result.get('current_period', {})
        response = f"""📈 [{ticker}] 차트 패턴 분석 (최근 {window_days}일)
📅 분석기간: {period.get('start', '?')} ~ {period.get('end', '?')}
🔬 알고리즘: Pearson Correlation (Z-Score Normalized)

🎯 유사 패턴 발견 ({len(matches)}건):
"""
        for i, m in enumerate(matches, 1):
            arrow = "📈" if m['after_5days_return'] > 0 else "📉"
            response += f"\n{i}. {m['start_date']} ~ {m['end_date']} (유사도 {m['similarity']}%)\n"
            response += f"   {arrow} 5일 후 수익률: {m['after_5days_return']:+.2f}%\n"
        
        response += "\n💡 [추천 행동] 위 기간들의 당시 뉴스·이슈를 검색하여 현재와 비교하세요."
        return response
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def calculate_volatility_regime(ticker: str, lookback_days: int = 252) -> str:
    """
    주식의 변동성 체제(Volatility Regime)를 분석합니다.
    현재가 저변동성/정상/고변동성 중 어느 구간인지 판단하여 매매 전략 수립에 활용합니다.
    
    Args:
        ticker: 종목 코드
        lookback_days: 과거 비교 기간 (기본 252일=1년)
    """
    try:
        import yfinance as yf
        import numpy as np
        
        stock = yf.Ticker(ticker)
        df = stock.history(period=f"{lookback_days}d")
        
        if len(df) < 30:
            return "❌ 데이터 부족"
        
        # 일별 수익률 계산
        returns = df['Close'].pct_change().dropna()
        
        # 현재 20일 변동성
        recent_vol = returns.tail(20).std() * np.sqrt(252) * 100
        
        # 과거 252일 변동성 분포
        historical_vols = []
        for i in range(20, len(returns)):
            vol = returns.iloc[i-20:i].std() * np.sqrt(252) * 100
            historical_vols.append(vol)
        
        percentile = np.percentile(historical_vols, [25, 50, 75])
        
        if recent_vol < percentile[0]:
            regime = "🟢 저변동성"
            advice = "돌파 매매, 레버리지 전략 고려 가능"
        elif recent_vol < percentile[2]:
            regime = "🟡 정상 변동성"
            advice = "일반적인 추세 추종 전략"
        else:
            regime = "🔴 고변동성"
            advice = "리스크 관리 강화, 포지션 축소 권장"
        
        return f"""📊 [{ticker}] 변동성 분석 ({lookback_days}일 기준)

📈 현재 변동성: {recent_vol:.2f}% (연환산)
📉 과거 25%ile: {percentile[0]:.2f}%
📊 과거 중앙값: {percentile[1]:.2f}%
📈 과거 75%ile: {percentile[2]:.2f}%

🎯 현재 체제: {regime}
💡 전략 제안: {advice}

⚠️ 변동성은 급격히 변할 수 있으므로 지속적인 모니터링이 필요합니다."""
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def detect_support_resistance(ticker: str, period: str = "6mo") -> str:
    """
    주요 지지선/저항선을 자동으로 탐지합니다.
    과거 가격에서 여러 번 반등/저항한 수평선 레벨을 클러스터링 기법으로 찾습니다.
    
    Args:
        ticker: 종목 코드
        period: 분석 기간 (1mo, 3mo, 6mo, 1y, 2y)
    """
    try:
        import yfinance as yf
        import numpy as np
        from scipy.signal import find_peaks
        
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        
        if len(df) < 50:
            return "❌ 데이터 부족"
        
        closes = df['Close'].values
        current_price = closes[-1]
        
        # 고점/저점 탐지
        peaks, _ = find_peaks(closes, distance=5)
        troughs, _ = find_peaks(-closes, distance=5)
        
        # 레벨 클러스터링 (±2% 범위 내 그룹화)
        def cluster_levels(prices, tolerance=0.02):
            if len(prices) == 0:
                return []
            sorted_prices = np.sort(prices)
            clusters = []
            current_cluster = [sorted_prices[0]]
            
            for price in sorted_prices[1:]:
                if price <= current_cluster[-1] * (1 + tolerance):
                    current_cluster.append(price)
                else:
                    clusters.append(np.mean(current_cluster))
                    current_cluster = [price]
            clusters.append(np.mean(current_cluster))
            return clusters
        
        resistance_levels = cluster_levels(closes[peaks])
        support_levels = cluster_levels(closes[troughs])
        
        # 현재가 기준 필터링
        nearby_resistance = [r for r in resistance_levels if r > current_price][:3]
        nearby_support = [s for s in support_levels if s < current_price][-3:]
        
        response = f"""📊 [{ticker}] 지지/저항 분석 ({period})
💵 현재가: ${current_price:.2f}

"""
        
        if nearby_resistance:
            response += "🔴 저항선 (상방):\n"
            for i, r in enumerate(nearby_resistance, 1):
                dist = ((r / current_price) - 1) * 100
                response += f"  {i}. ${r:.2f} (+{dist:.1f}%)\n"
        
        if nearby_support:
            response += "\n🟢 지지선 (하방):\n"
            for i, s in enumerate(reversed(nearby_support), 1):
                dist = ((s / current_price) - 1) * 100
                response += f"  {i}. ${s:.2f} ({dist:.1f}%)\n"
        
        response += "\n💡 매매 전략: 지지선 근처 매수, 저항선 돌파시 추격 매수 고려"
        return response
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def compare_relative_strength(ticker: str, benchmark: str = "SPY", period: str = "1y") -> str:
    """
    특정 종목의 상대 강도를 벤치마크와 비교합니다.
    시장 대비 초과 수익률을 분석하여 강세/약세를 판단합니다.
    
    Args:
        ticker: 분석할 종목 코드
        benchmark: 비교 기준 (기본 SPY=S&P500)
        period: 분석 기간 (3mo, 6mo, 1y, 2y)
    """
    try:
        import yfinance as yf
        import numpy as np
        
        stock_data = yf.Ticker(ticker).history(period=period)
        bench_data = yf.Ticker(benchmark).history(period=period)
        
        if len(stock_data) < 20 or len(bench_data) < 20:
            return "❌ 데이터 부족"
        
        # 공통 날짜 정렬
        common_dates = stock_data.index.intersection(bench_data.index)
        stock_close = stock_data.loc[common_dates, 'Close']
        bench_close = bench_data.loc[common_dates, 'Close']
        
        # 정규화 (시작점=100)
        stock_norm = (stock_close / stock_close.iloc[0]) * 100
        bench_norm = (bench_close / bench_close.iloc[0]) * 100
        
        # 상대 강도 = 종목/벤치마크
        relative_strength = stock_norm / bench_norm * 100
        
        # 최근 추세 (20일 이동평균 기울기)
        recent_rs = relative_strength.tail(20)
        trend = "📈 상승" if recent_rs.iloc[-1] > recent_rs.iloc[0] else "📉 하락"
        
        stock_return = ((stock_close.iloc[-1] / stock_close.iloc[0]) - 1) * 100
        bench_return = ((bench_close.iloc[-1] / bench_close.iloc[0]) - 1) * 100
        alpha = stock_return - bench_return
        
        status = "🔥 강세" if alpha > 5 else "❄️ 약세" if alpha < -5 else "⚖️ 중립"
        
        return f"""📊 [{ticker}] vs [{benchmark}] 상대 강도 ({period})

📈 {ticker} 수익률: {stock_return:+.2f}%
📊 {benchmark} 수익률: {bench_return:+.2f}%
🎯 알파(초과수익): {alpha:+.2f}%

📊 상대강도 현재값: {relative_strength.iloc[-1]:.2f}
📈 최근 20일 추세: {trend}

🏆 판정: {status}

💡 전략:
- 강세: 지속 보유 또는 추가 매수 고려
- 약세: 비중 축소 또는 벤치마크 교체 검토
- 중립: 시장 수익률 추종 중, 대기 전략"""
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def scan_technical_signals(ticker: str) -> str:
    """
    여러 기술적 지표를 종합하여 매수/매도 신호를 스캔합니다.
    RSI, MACD, 볼린저밴드, 이동평균선 등을 자동으로 분석합니다.
    
    Args:
        ticker: 종목 코드
    """
    try:
        import yfinance as yf
        import numpy as np
        
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo")
        
        if len(df) < 50:
            return "❌ 데이터 부족"
        
        closes = df['Close'].values
        current = closes[-1]
        
        # RSI 계산
        def calc_rsi(prices, period=14):
            deltas = np.diff(prices)
            gain = np.where(deltas > 0, deltas, 0)
            loss = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gain[-period:])
            avg_loss = np.mean(loss[-period:])
            rs = avg_gain / (avg_loss + 1e-10)
            return 100 - (100 / (1 + rs))
        
        rsi = calc_rsi(closes)
        rsi_signal = "🔴 과매수" if rsi > 70 else "🟢 과매도" if rsi < 30 else "⚪ 중립"
        
        # 이동평균선
        ma20 = np.mean(closes[-20:])
        ma50 = np.mean(closes[-50:]) if len(closes) >= 50 else ma20
        
        ma_signal = "🟢 골든크로스" if ma20 > ma50 and current > ma20 else \
                   "🔴 데드크로스" if ma20 < ma50 and current < ma20 else "⚪ 중립"
        
        # 볼린저 밴드
        ma20_full = np.mean(closes[-20:])
        std20 = np.std(closes[-20:])
        upper_band = ma20_full + 2 * std20
        lower_band = ma20_full - 2 * std20
        
        bb_signal = "🔴 상단밴드" if current > upper_band else \
                   "🟢 하단밴드" if current < lower_band else "⚪ 중립"
        
        # 종합 판단
        signals = [rsi < 30, ma20 > ma50, current < lower_band]
        buy_score = sum(signals)
        
        recommendation = "🟢 매수 고려" if buy_score >= 2 else \
                        "🔴 매도 고려" if buy_score == 0 else "⚪ 관망"
        
        return f"""📊 [{ticker}] 기술적 지표 종합 스캔
💵 현재가: ${current:.2f}

📈 지표 분석:
1️⃣ RSI(14): {rsi:.1f} → {rsi_signal}
2️⃣ 이동평균: MA20=${ma20:.2f}, MA50=${ma50:.2f} → {ma_signal}
3️⃣ 볼린저밴드: ${lower_band:.2f} ~ ${upper_band:.2f} → {bb_signal}

🎯 종합 판단: {recommendation}
📊 매수 신호 점수: {buy_score}/3

⚠️ 이는 참고용이며, 반드시 추가 분석과 함께 사용하세요."""
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"

# =========================
# 6. Starlette 앱 구성 (Streamable HTTP 완전 지원)
# =========================

sse_transport = SseServerTransport("/")

async def handle_root(request: Request):
    if request.method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
    
    if request.method == "GET":
        accept = request.headers.get("accept", "")
        if "text/event-stream" in accept:
            async with sse_transport.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await mcp._mcp_server.run(
                    streams[0], streams[1], 
                    mcp._mcp_server.create_initialization_options()
                )
            return Response()
        
        return JSONResponse({
            "status": "online",
            "service": "Stock-Pattern-Analyzer"
        })

    elif request.method == "POST":
        # ⭐ 핵심 수정: JSON-RPC 직접 처리
        body = await request.json()
        
        # 세션 생성
        from mcp.server.session import ServerSession
        from mcp.server.stdio import stdio_server
        
        read_stream, write_stream = stdio_server()
        
        async with mcp._mcp_server.run(read_stream, write_stream, mcp._mcp_server.create_initialization_options()):
            # 요청 처리
            response_data = await mcp._mcp_server.handle_request(body)
        
        return JSONResponse(response_data)

    return Response(status_code=405)

# CORS 미들웨어 설정 (모든 도메인 허용)
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
]

app = Starlette(
    debug=True,
    routes=[
        Route("/", handle_root, methods=["GET", "POST", "OPTIONS"]),
    ],
    middleware=middleware
)

# =========================
# 7. 서버 실행
# =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Stock Pattern Analyzer MCP Server", file=sys.stderr)
    print(f"📡 Listening on 0.0.0.0:{port}", file=sys.stderr)
    print(f"✅ Transport: SSE + Streamable HTTP", file=sys.stderr)
    
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1, reload=False)