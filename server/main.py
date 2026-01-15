import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

# 1. 경로 보정
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# 2. 필수 모듈 임포트
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, Response
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
# 5. 주식 분석 툴 등록 (사용자님 400줄 로직 그대로 유지)
# =========================

@mcp.tool()
async def find_historical_pattern(ticker: str, window_days: int = 30) -> str:
    """현재 차트 패턴과 가장 유사한 과거 시점을 찾아 분석합니다."""
    try:
        result = await analyzer.find_similar_patterns(ticker, window_size=window_days)
        if "error" in result: return f"❌ {result['error']}"
        matches = result.get("top_matches", [])
        if not matches: return f"📊 [{ticker}] 유사 패턴을 찾을 수 없습니다."
        period = result.get('current_period', {})
        response = f"📈 [{ticker}] 차트 패턴 분석 결과\n📅 {period.get('start')} ~ {period.get('end')}\n"
        for i, m in enumerate(matches, 1):
            arrow = "📈" if m['after_5days_return'] > 0 else "📉"
            response += f"\n{i}. {m['start_date']} ~ {m['end_date']} (유사도 {m['similarity']}%)\n   {arrow} 5일 후 수익률: {m['after_5days_return']:+.2f}%"
        return response
    except Exception as e: return f"⚠️ 오류: {str(e)}"

@mcp.tool()
async def calculate_volatility_regime(ticker: str, lookback_days: int = 252) -> str:
    """주식의 변동성 체제를 분석합니다."""
    try:
        import yfinance as yf
        import numpy as np
        stock = yf.Ticker(ticker)
        df = stock.history(period=f"{lookback_days}d")
        if len(df) < 30: return "❌ 데이터 부족"
        returns = df['Close'].pct_change().dropna()
        recent_vol = returns.tail(20).std() * np.sqrt(252) * 100
        historical_vols = [returns.iloc[i-20:i].std() * np.sqrt(252) * 100 for i in range(20, len(returns))]
        percentile = np.percentile(historical_vols, [25, 50, 75])
        regime = "🟢 저변동성" if recent_vol < percentile[0] else "🟡 정상" if recent_vol < percentile[2] else "🔴 고변동성"
        return f"📊 [{ticker}] 변동성: {recent_vol:.2f}% (연환산)\n현재 체제: {regime}"
    except Exception as e: return f"⚠️ 오류: {str(e)}"

@mcp.tool()
async def detect_support_resistance(ticker: str, period: str = "6mo") -> str:
    """주요 지지선/저항선을 자동으로 탐지합니다."""
    try:
        import yfinance as yf
        import numpy as np
        from scipy.signal import find_peaks
        df = yf.Ticker(ticker).history(period=period)
        if len(df) < 50: return "❌ 데이터 부족"
        closes = df['Close'].values
        current_price = closes[-1]
        peaks, _ = find_peaks(closes, distance=5)
        troughs, _ = find_peaks(-closes, distance=5)
        def cluster_levels(prices):
            if len(prices) == 0: return []
            sorted_p = np.sort(prices)
            clusters = []
            curr = [sorted_p[0]]
            for p in sorted_p[1:]:
                if p <= curr[-1] * 1.02: curr.append(p)
                else: clusters.append(np.mean(curr)); curr = [p]
            clusters.append(np.mean(curr))
            return clusters
        resistance = [r for r in cluster_levels(closes[peaks]) if r > current_price][:3]
        support = [s for s in cluster_levels(closes[troughs]) if s < current_price][-3:]
        return f"📊 [{ticker}] 현재가: ${current_price:.2f}\n🔴 저항: {[f'${r:.2f}' for r in resistance]}\n🟢 지지: {[f'${s:.2f}' for s in reversed(support)]}"
    except Exception as e: return f"⚠️ 오류: {str(e)}"

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
# 6. Bridge 클래스 및 Stateless 핸들러 (옛날 설정 복구)
# =========================

class ASGIResponder(Response):
    """Starlette와 MCP ASGI 핸들러 사이의 가교 역할"""
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)

async def handle_stateless_jsonrpc(request: Request):
    """Session ID가 없는 일반 POST 요청(Streamable HTTP)을 수동으로 처리"""
    try:
        body = await request.json()
        method = body.get("method")
        msg_id = body.get("id")
        params = body.get("params", {})

        # 1. Initialize
        if method == "initialize":
            return JSONResponse({
                "jsonrpc": "2.0", 
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "prompts": {},
                        "resources": {}
                    },
                    "serverInfo": {
                        "name": "Stock-Analyzer", 
                        "version": "1.0.0"
                    }
                }
            })

        # 2. Tools List
        if method == "tools/list":
            tools_data = []
            # FastMCP에서 등록된 도구 목록 가져오기
            try:
                # 방법 1: FastMCP의 _tools 딕셔너리에서 직접 가져오기
                for tool_name, tool_info in mcp._tools.items():
                    tools_data.append({
                        "name": tool_name,
                        "description": tool_info.get("description", ""),
                        "inputSchema": {
                            "type": "object",
                            "properties": tool_info.get("input_schema", {}),
                            "required": []
                        }
                    })
            except:
                # 방법 2: 하드코딩된 도구 목록
                tools_data = [
                    {
                        "name": "find_historical_pattern",
                        "description": "현재 차트 패턴과 가장 유사한 과거 시점을 찾아 분석합니다.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "ticker": {"type": "string"},
                                "window_days": {"type": "integer", "default": 30}
                            },
                            "required": ["ticker"]
                        }
                    },
                    {
                        "name": "calculate_volatility_regime",
                        "description": "주식의 변동성 체제를 분석합니다.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "ticker": {"type": "string"},
                                "lookback_days": {"type": "integer", "default": 252}
                            },
                            "required": ["ticker"]
                        }
                    },
                    {
                        "name": "detect_support_resistance",
                        "description": "주요 지지선/저항선을 자동으로 탐지합니다.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "ticker": {"type": "string"},
                                "period": {"type": "string", "default": "6mo"}
                            },
                            "required": ["ticker"]
                        }
                    },
                    {
                        "name": "compare_relative_strength",
                        "description": "특정 종목의 상대 강도를 벤치마크와 비교합니다.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "ticker": {"type": "string"},
                                "benchmark": {"type": "string", "default": "SPY"},
                                "period": {"type": "string", "default": "1y"}
                            },
                            "required": ["ticker"]
                        }
                    },
                    {
                        "name": "scan_technical_signals",
                        "description": "여러 기술적 지표를 종합하여 매수/매도 신호를 스캔합니다.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "ticker": {"type": "string"}
                            },
                            "required": ["ticker"]
                        }
                    }
                ]
            
            return JSONResponse({
                "jsonrpc": "2.0", 
                "id": msg_id,
                "result": {
                    "tools": tools_data
                }
            })

        # 3. Call Tool
        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            # 도구 실행
            try:
                if tool_name == "find_historical_pattern":
                    result = await find_historical_pattern(
                        ticker=tool_args.get("ticker"),
                        window_days=tool_args.get("window_days", 30)
                    )
                elif tool_name == "calculate_volatility_regime":
                    result = await calculate_volatility_regime(
                        ticker=tool_args.get("ticker"),
                        lookback_days=tool_args.get("lookback_days", 252)
                    )
                elif tool_name == "detect_support_resistance":
                    result = await detect_support_resistance(
                        ticker=tool_args.get("ticker"),
                        period=tool_args.get("period", "6mo")
                    )
                elif tool_name == "compare_relative_strength":
                    result = await compare_relative_strength(
                        ticker=tool_args.get("ticker"),
                        benchmark=tool_args.get("benchmark", "SPY"),
                        period=tool_args.get("period", "1y")
                    )
                elif tool_name == "scan_technical_signals":
                    result = await scan_technical_signals(
                        ticker=tool_args.get("ticker")
                    )
                else:
                    return JSONResponse({
                        "jsonrpc": "2.0", 
                        "id": msg_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {tool_name}"
                        }
                    })
                
                # 결과 형식 맞추기
                return JSONResponse({
                    "jsonrpc": "2.0", 
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result
                            }
                        ]
                    }
                })
                
            except Exception as e:
                return JSONResponse({
                    "jsonrpc": "2.0", 
                    "id": msg_id,
                    "error": {
                        "code": -32000,
                        "message": f"Tool execution error: {str(e)}"
                    }
                })

        return JSONResponse({
            "jsonrpc": "2.0", 
            "id": msg_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        })
        
    except json.JSONDecodeError:
        return JSONResponse({
            "jsonrpc": "2.0", 
            "id": None,
            "error": {
                "code": -32700,
                "message": "Parse error: Invalid JSON"
            }
        })
    except Exception as e:
        return JSONResponse({
            "jsonrpc": "2.0", 
            "id": None,
            "error": {
                "code": -32000,
                "message": str(e)
            }
        })
# =========================
# 7. 통합 핸들러 (SSE + Streamable POST)
# =========================

sse_transport = SseServerTransport("/")

async def handle_root(request: Request):
    # 1. OPTIONS (CORS)
    if request.method == "OPTIONS":
        return Response(status_code=200, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "*", "Access-Control-Allow-Headers": "*"})

    # 2. GET (SSE 연결)
    if request.method == "GET":
        if "text/event-stream" in request.headers.get("accept", ""):
            async def sse_app(scope, receive, send):
                async with sse_transport.connect_sse(scope, receive, send) as streams:
                    await mcp._mcp_server.run(streams[0], streams[1], mcp._mcp_server.create_initialization_options())
            return ASGIResponder(sse_app)
        return JSONResponse({"status": "running", "mode": "hybrid-streamable"})

    # 3. POST (메시지 전송)
    if request.method == "POST":
        # 세션 ID가 있으면 SDK의 SSE 핸들러에 위임
        if request.query_params.get("sessionId") or request.query_params.get("session_id"):
            return ASGIResponder(sse_transport.handle_post_message)
        # 세션 ID가 없으면 수동 JSON-RPC 핸들러로 처리 (Streamable HTTP 호환)
        else:
            return await handle_stateless_jsonrpc(request)

    return Response(status_code=405)

# 앱 설정
app = Starlette(
    debug=True,
    routes=[Route("/", endpoint=handle_root, methods=["GET", "POST", "OPTIONS"])],
    middleware=[Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])]
)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1)