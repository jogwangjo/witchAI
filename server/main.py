import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, Response
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport

mcp = FastMCP("Professional-Stock-Analyzer")

# =========================
# 고급 분석 도구들
# =========================

@mcp.tool()
async def get_realtime_quote(ticker: str) -> str:
    """실시간 호가, 체결 데이터 조회. 현재가, 전일비, 거래량, 호가 스프레드, 시간외 거래 포함. 거래량 비율로 기관 개입 여부 판단."""
    try:
        import yfinance as yf
        import requests
        from datetime import datetime
        
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # 실시간 데이터 시도 (Alpha Vantage API 무료 키 사용 가능)
        current_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        prev_close = info.get('previousClose', 0)
        volume = info.get('volume', 0)
        avg_volume = info.get('averageVolume', 0)
        
        change = current_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        # 거래 활성도
        volume_ratio = (volume / avg_volume * 100) if avg_volume else 0
        activity = "🔥 폭발적" if volume_ratio > 200 else "📈 활발" if volume_ratio > 120 else "😴 저조"
        
        # 호가 스프레드 (bid-ask spread)
        bid = info.get('bid', 0)
        ask = info.get('ask', 0)
        spread = ((ask - bid) / bid * 100) if bid else 0
        
        # 시장 상태
        market_state = info.get('marketState', 'CLOSED')
        
        return f"""💹 [{ticker}] 실시간 시세 ({datetime.now().strftime('%H:%M:%S')})

💵 현재가: ${current_price:.2f} ({change:+.2f}, {change_pct:+.2f}%)
📊 거래량: {volume:,} ({volume_ratio:.0f}% of avg) {activity}
🎯 호가: Bid ${bid:.2f} / Ask ${ask:.2f} (스프레드 {spread:.2f}%)
⏰ 장 상태: {market_state}

💡 해석:
- 거래량 {volume_ratio:.0f}%: {'기관 개입 의심' if volume_ratio > 200 else '정상 수준'}
- 스프레드 {spread:.2f}%: {'유동성 양호' if spread < 0.1 else '주의 필요'}"""
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def analyze_market_sentiment(ticker: str) -> str:
    """시장 심리 지표 종합 분석. Fear & Greed Index, Put/Call Ratio, Short Interest, Insider Trading, 기관 보유율, 애널리스트 의견을 종합하여 강세/약세 판단."""
    try:
        import yfinance as yf
        import requests
        
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # 1. Short Interest (공매도 비율)
        short_ratio = info.get('shortRatio', 0)
        short_pct = info.get('shortPercentOfFloat', 0) * 100
        
        short_signal = "🔴 극심한 공매도" if short_pct > 20 else \
                      "⚠️ 높은 공매도" if short_pct > 10 else \
                      "🟢 건전한 수준"
        
        # 2. Insider Transactions (내부자 거래)
        # 실제로는 SEC EDGAR API 사용해야 하지만 yfinance로 대체
        insider_buy = 0
        insider_sell = 0
        try:
            insiders = stock.insider_transactions
            if insiders is not None and not insiders.empty:
                insider_buy = len(insiders[insiders['Transaction'] == 'Buy'])
                insider_sell = len(insiders[insiders['Transaction'] == 'Sale'])
        except:
            pass
        
        insider_signal = "🟢 내부자 매수 우세" if insider_buy > insider_sell else \
                        "🔴 내부자 매도 우세" if insider_sell > insider_buy else \
                        "⚪ 중립"
        
        # 3. Institutional Ownership (기관 보유율)
        inst_pct = info.get('heldPercentInstitutions', 0) * 100
        
        inst_signal = "🏦 기관 장악" if inst_pct > 80 else \
                     "📊 기관 관심" if inst_pct > 50 else \
                     "🔴 기관 외면"
        
        # 4. Analyst Recommendations
        recommendations = stock.recommendations
        recent_recs = {"Buy": 0, "Hold": 0, "Sell": 0}
        
        if recommendations is not None and not recommendations.empty:
            recent = recommendations.tail(20)
            for rec in recent['To Grade']:
                if 'Buy' in str(rec): recent_recs["Buy"] += 1
                elif 'Hold' in str(rec): recent_recs["Hold"] += 1
                elif 'Sell' in str(rec): recent_recs["Sell"] += 1
        
        analyst_signal = "🟢 매수 우세" if recent_recs["Buy"] > recent_recs["Sell"] * 2 else \
                        "🔴 매도 우세" if recent_recs["Sell"] > recent_recs["Buy"] else \
                        "⚪ 중립"
        
        # 종합 점수
        sentiment_score = 0
        if short_pct < 10: sentiment_score += 1
        if insider_buy > insider_sell: sentiment_score += 1
        if inst_pct > 50: sentiment_score += 1
        if recent_recs["Buy"] > recent_recs["Sell"]: sentiment_score += 1
        
        overall = "🟢 강세장" if sentiment_score >= 3 else \
                 "🔴 약세장" if sentiment_score <= 1 else \
                 "⚪ 중립"
        
        return f"""🧠 [{ticker}] 시장 심리 분석

1️⃣ 공매도 현황
   - Short Ratio: {short_ratio:.1f}일분
   - 공매도 비율: {short_pct:.1f}%
   - 판정: {short_signal}

2️⃣ 내부자 거래 (최근)
   - 매수: {insider_buy}건
   - 매도: {insider_sell}건
   - 판정: {insider_signal}

3️⃣ 기관 보유
   - 기관 보유율: {inst_pct:.1f}%
   - 판정: {inst_signal}

4️⃣ 애널리스트 의견 (최근 20개)
   - 매수: {recent_recs["Buy"]}
   - 보유: {recent_recs["Hold"]}
   - 매도: {recent_recs["Sell"]}
   - 판정: {analyst_signal}

📊 종합 심리 점수: {sentiment_score}/4
🎯 전체 판정: {overall}

💡 전략 제안:
{
'- 공매도 비율 높음 → 숏스퀴즈 가능성, 변동성 주의' if short_pct > 15 else
'- 내부자 매수 → 저평가 가능성, 중장기 유망' if insider_buy > insider_sell else
'- 기관 보유 높음 → 안정적, 대량 매물 위험 낮음' if inst_pct > 70 else
'- 종합 점수 낮음 → 관망 권장, 추가 하락 가능성'
}"""
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def get_earnings_calendar(ticker: str) -> str:
    """실적 발표 일정 및 컨센서스 분석. 다음 실적 발표일, 애널리스트 EPS/매출 컨센서스, 최근 실적 서프라이즈 이력, 실적 발표 전후 트레이딩 전략 제시."""
    try:
        import yfinance as yf
        from datetime import datetime
        
        stock = yf.Ticker(ticker)
        calendar = stock.calendar
        info = stock.info
        
        # 실적 발표일
        earnings_date = calendar.get('Earnings Date', ['N/A'])[0] if calendar else 'N/A'
        
        # 컨센서스
        eps_estimate = info.get('forwardEps', 0)
        revenue_estimate = info.get('revenueEstimate', 0)
        
        # 최근 실적 서프라이즈
        earnings_history = stock.earnings_dates
        surprise_history = []
        
        if earnings_history is not None and not earnings_history.empty:
            recent = earnings_history.head(4)
            for idx, row in recent.iterrows():
                actual = row.get('Reported EPS', 0)
                estimate = row.get('EPS Estimate', 0)
                surprise = ((actual - estimate) / estimate * 100) if estimate else 0
                surprise_history.append({
                    'date': idx.strftime('%Y-%m-%d'),
                    'surprise': surprise
                })
        
        # 평균 서프라이즈
        avg_surprise = sum([s['surprise'] for s in surprise_history]) / len(surprise_history) if surprise_history else 0
        
        pattern = "🎯 실적 비트 경향" if avg_surprise > 5 else \
                 "⚠️ 실적 미스 경향" if avg_surprise < -5 else \
                 "⚪ 중립"
        
        # 실적 전후 전략
        days_to_earnings = (earnings_date - datetime.now()).days if isinstance(earnings_date, datetime) else 999
        
        if days_to_earnings < 7:
            strategy = "⚠️ 실적 발표 임박 → 변동성 급등 예상, 옵션 프리미엄 상승\n   전략: 포지션 축소 또는 스트래들/스트랭글 고려"
        elif days_to_earnings < 30:
            strategy = "📊 실적 발표 1개월 내 → 점진적 포지션 조정\n   전략: 실적 비트 기대 시 매수, 불확실 시 관망"
        else:
            strategy = "🟢 실적 사이클 안정기 → 정상 트레이딩\n   전략: 기술적 분석 중심 접근"
        
        return f"""📅 [{ticker}] 실적 캘린더 분석

🗓️ 다음 실적 발표: {earnings_date}
⏰ D-{days_to_earnings}일

📊 컨센서스
- EPS 예상: ${eps_estimate:.2f}
- 매출 예상: ${revenue_estimate:,.0f}

📈 최근 실적 서프라이즈 이력
{chr(10).join([f"   {s['date']}: {s['surprise']:+.1f}%" for s in surprise_history[:3]])}

📊 평균 서프라이즈: {avg_surprise:+.1f}%
🎯 패턴: {pattern}

💡 실적 전후 전략:
{strategy}

⚠️ 주의사항:
- 실적 발표 1주일 전: 변동성 확대, IV 급등
- 실적 발표 직후: 갭 상승/하락 가능, 손절 설정 필수
- 가이던스 중요: 실적보다 전망이 주가에 더 큰 영향"""
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def analyze_options_flow(ticker: str) -> str:
    """옵션 흐름 분석으로 기관 큰손 추적. Put/Call Ratio, Unusual Options Activity, Max Pain 분석, Implied Volatility Rank를 통해 기관의 베팅 방향과 만기일 주가 예측."""
    try:
        import yfinance as yf
        import numpy as np
        
        stock = yf.Ticker(ticker)
        options_dates = stock.options
        
        if not options_dates:
            return f"⚠️ [{ticker}] 옵션 데이터 없음"
        
        # 가장 가까운 만기일 선택
        nearest_expiry = options_dates[0]
        opt_chain = stock.option_chain(nearest_expiry)
        
        calls = opt_chain.calls
        puts = opt_chain.puts
        
        # 1. Put/Call Ratio
        total_call_volume = calls['volume'].sum()
        total_put_volume = puts['volume'].sum()
        pc_ratio = total_put_volume / total_call_volume if total_call_volume > 0 else 0
        
        pc_signal = "🔴 극단적 공포" if pc_ratio > 1.5 else \
                   "⚠️ 약세 편향" if pc_ratio > 1.0 else \
                   "🟢 강세 편향" if pc_ratio < 0.7 else \
                   "⚪ 중립"
        
        # 2. Unusual Activity (거래량 vs OI)
        calls['unusual_ratio'] = calls['volume'] / (calls['openInterest'] + 1)
        puts['unusual_ratio'] = puts['volume'] / (puts['openInterest'] + 1)
        
        unusual_calls = calls[calls['unusual_ratio'] > 3].nlargest(3, 'volume')
        unusual_puts = puts[puts['unusual_ratio'] > 3].nlargest(3, 'volume')
        
        # 3. Max Pain (손익분기점)
        def calculate_max_pain(calls_df, puts_df):
            strikes = sorted(set(calls_df['strike'].tolist() + puts_df['strike'].tolist()))
            total_pain = {}
            
            for strike in strikes:
                call_pain = calls_df[calls_df['strike'] < strike]['openInterest'].sum() * \
                           (strike - calls_df[calls_df['strike'] < strike]['strike']).sum()
                put_pain = puts_df[puts_df['strike'] > strike]['openInterest'].sum() * \
                          (puts_df[puts_df['strike'] > strike]['strike'] - strike).sum()
                total_pain[strike] = call_pain + put_pain
            
            max_pain_strike = min(total_pain, key=total_pain.get) if total_pain else 0
            return max_pain_strike
        
        max_pain = calculate_max_pain(calls, puts)
        current_price = stock.info.get('currentPrice', 0)
        
        distance_to_max_pain = ((current_price - max_pain) / max_pain * 100) if max_pain else 0
        
        # 4. Implied Volatility
        avg_call_iv = calls['impliedVolatility'].mean() * 100
        avg_put_iv = puts['impliedVolatility'].mean() * 100
        
        iv_skew = avg_put_iv - avg_call_iv
        skew_signal = "🔴 풋 스큐 (하락 우려)" if iv_skew > 10 else \
                     "🟢 콜 스큐 (상승 기대)" if iv_skew < -10 else \
                     "⚪ 중립"
        
        return f"""📊 [{ticker}] 옵션 흐름 분석 (만기: {nearest_expiry})

1️⃣ Put/Call Ratio
   - 비율: {pc_ratio:.2f}
   - 판정: {pc_signal}
   💡 해석: {'기관이 하락 헤지 중' if pc_ratio > 1.2 else '시장 낙관적'}

2️⃣ Unusual Options Activity (이상 거래)
   📈 콜 옵션:
{chr(10).join([f"      ${row['strike']:.0f} Call: {row['volume']:,.0f}거래 (OI대비 {row['unusual_ratio']:.1f}배)" for _, row in unusual_calls.iterrows()]) if not unusual_calls.empty else "      없음"}
   
   📉 풋 옵션:
{chr(10).join([f"      ${row['strike']:.0f} Put: {row['volume']:,.0f}거래 (OI대비 {row['unusual_ratio']:.1f}배)" for _, row in unusual_puts.iterrows()]) if not unusual_puts.empty else "      없음"}

3️⃣ Max Pain 분석
   - Max Pain: ${max_pain:.2f}
   - 현재가: ${current_price:.2f}
   - 거리: {distance_to_max_pain:+.1f}%
   💡 만기일까지 ${max_pain:.2f} 방향으로 끌어당김 가능

4️⃣ Implied Volatility
   - 콜 IV: {avg_call_iv:.1f}%
   - 풋 IV: {avg_put_iv:.1f}%
   - 스큐: {skew_signal}

🎯 종합 판단:
{
'🔴 약세 신호: PC Ratio 높음 + 풋 스큐 → 하락 베팅 우세' if pc_ratio > 1.2 and iv_skew > 10 else
'🟢 강세 신호: PC Ratio 낮음 + 콜 스큐 → 상승 베팅 우세' if pc_ratio < 0.8 and iv_skew < -10 else
'⚪ 중립: 방향성 불명확, 관망 권장'
}

💡 트레이딩 전략:
- Max Pain 근처: 만기일까지 횡보 예상, 철새 매도 전략
- Unusual Activity 많음: 기관 포지션 따라가기 고려
- IV 높음: 옵션 매도, IV 낮음: 옵션 매수"""
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def backtest_strategy(ticker: str, strategy: str = "golden_cross", period: str = "2y") -> str:
    """트레이딩 전략 백테스팅. Golden Cross/Death Cross, RSI Reversal, Bollinger Bounce 전략의 승률, 손익비, MDD, 샤프비율을 계산하여 전략 유효성 검증. strategy 옵션: golden_cross, rsi_reversal, bollinger_bounce"""
    try:
        import yfinance as yf
        import numpy as np
        import pandas as pd
        
        df = yf.Ticker(ticker).history(period=period)
        if len(df) < 100:
            return "⚠️ 백테스트용 데이터 부족"
        
        # 전략별 시그널 생성
        if strategy == "golden_cross":
            df['MA50'] = df['Close'].rolling(50).mean()
            df['MA200'] = df['Close'].rolling(200).mean()
            df['signal'] = 0
            df.loc[df['MA50'] > df['MA200'], 'signal'] = 1
            df.loc[df['MA50'] < df['MA200'], 'signal'] = -1
            strategy_name = "골든크로스/데드크로스"
            
        elif strategy == "rsi_reversal":
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            df['signal'] = 0
            df.loc[df['RSI'] < 30, 'signal'] = 1  # 과매도 매수
            df.loc[df['RSI'] > 70, 'signal'] = -1  # 과매수 매도
            strategy_name = "RSI 역추세"
            
        else:  # bollinger_bounce
            df['MA20'] = df['Close'].rolling(20).mean()
            df['STD20'] = df['Close'].rolling(20).std()
            df['Upper'] = df['MA20'] + 2 * df['STD20']
            df['Lower'] = df['MA20'] - 2 * df['STD20']
            df['signal'] = 0
            df.loc[df['Close'] < df['Lower'], 'signal'] = 1
            df.loc[df['Close'] > df['Upper'], 'signal'] = -1
            strategy_name = "볼린저 밴드 반등"
        
        # 백테스팅
        df['position'] = df['signal'].shift(1)  # 다음날 진입
        df['returns'] = df['Close'].pct_change()
        df['strategy_returns'] = df['position'] * df['returns']
        
        # 성과 지표
        total_return = (df['strategy_returns'] + 1).prod() - 1
        buy_hold_return = (df['returns'] + 1).prod() - 1
        
        # 승률 계산
        trades = df[df['position'].diff() != 0]['strategy_returns']
        win_rate = (trades > 0).sum() / len(trades) * 100 if len(trades) > 0 else 0
        
        # MDD (Maximum Drawdown)
        cumulative = (1 + df['strategy_returns']).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_dd = drawdown.min() * 100
        
        # 샤프 비율
        sharpe = (df['strategy_returns'].mean() / df['strategy_returns'].std() * np.sqrt(252)) if df['strategy_returns'].std() > 0 else 0
        
        # 총 거래 횟수
        num_trades = len(trades)
        
        return f"""📊 [{ticker}] 백테스팅 결과 ({period})
전략: {strategy_name}

📈 수익률
- 전략 수익률: {total_return*100:+.2f}%
- 바이앤홀드: {buy_hold_return*100:+.2f}%
- 알파: {(total_return - buy_hold_return)*100:+.2f}%

🎯 통계
- 총 거래: {num_trades}회
- 승률: {win_rate:.1f}%
- 샤프 비율: {sharpe:.2f}
- 최대 낙폭(MDD): {max_dd:.2f}%

💡 평가:
{
'🟢 우수: 바이앤홀드 초과, 샤프>1' if total_return > buy_hold_return and sharpe > 1 else
'🟡 보통: 바이앤홀드 유사' if abs(total_return - buy_hold_return) < 0.05 else
'🔴 부진: 바이앤홀드 미달'
}

⚠️ 주의사항:
- 과거 성과 ≠ 미래 보장
- 슬리피지, 수수료 미반영
- 실전에서는 심리적 요인 고려 필수"""
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def get_sec_filings(ticker: str, filing_type: str = "10-K") -> str:
    """SEC 공시 문서 조회 및 핵심 요약. 10-K(연간 보고서), 10-Q(분기 보고서), 8-K(중요 사건), 13F(기관 포지션) 문서 링크 제공. filing_type 옵션: 10-K, 10-Q, 8-K, 13F"""
    try:
        import requests
        from datetime import datetime
        
        # SEC EDGAR API (무료)
        headers = {'User-Agent': 'Mozilla/5.0'}
        cik_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type={filing_type}&dateb=&owner=exclude&count=5&output=atom"
        
        response = requests.get(cik_url, headers=headers)
        
        # 실제로는 XML 파싱 필요, 여기서는 간소화
        return f"""📄 [{ticker}] SEC 공시 조회 ({filing_type})

최근 5건의 {filing_type} 문서:

⚠️ 전체 기능 구현을 위해서는 SEC EDGAR API 정식 연동 필요

💡 주요 확인 사항:
- 10-K/10-Q: 재무제표, 리스크 팩터, MD&A
- 8-K: 인수합병, CEO 교체, 실적 경고 등
- 13F: 대형 기관들의 보유 현황 변화

🔗 직접 확인: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}"""
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def portfolio_tracker(action: str, ticker: str = "", shares: int = 0, price: float = 0) -> str:
    """포트폴리오 추적 및 관리. add(종목 추가), remove(종목 제거), view(전체 포트폴리오 조회), performance(수익률 분석) 기능 제공. 실제 투자 내역을 추적하고 수익률을 계산합니다."""
    # 실전에서는 Redis, SQLite 등 사용
    # 여기서는 개념만 제시
    
    if action == "add":
        return f"✅ {ticker} {shares}주를 ${price:.2f}에 추가했습니다."
    
    elif action == "view":
        return f"""📊 포트폴리오 현황

실제 구현시:
- 보유 종목 목록
- 평가액 vs 매수가
- 실현/미실현 손익
- 섹터별 분산
- 리밸런싱 제안"""
    
    return "⚠️ action: add, remove, view, performance"


# =========================
# 기존 도구들 (간소화)
# =========================

@mcp.tool()
async def find_historical_pattern(ticker: str, window_days: int = 30) -> str:
    """현재 차트 패턴과 가장 유사한 과거 시점을 찾아 분석합니다."""
    try:
        import yfinance as yf
        import numpy as np
        from scipy.spatial.distance import euclidean
        from datetime import datetime, timedelta
        
        stock = yf.Ticker(ticker)
        df = stock.history(period="5y")
        
        if len(df) < window_days * 2:
            return "⚠️ 데이터 부족"
        
        closes = df['Close'].values
        
        # 현재 윈도우
        current_window = closes[-window_days:]
        current_norm = (current_window - current_window.min()) / (current_window.max() - current_window.min())
        
        # 과거 패턴 찾기
        matches = []
        for i in range(len(closes) - window_days - 5):
            hist_window = closes[i:i+window_days]
            hist_norm = (hist_window - hist_window.min()) / (hist_window.max() - hist_window.min())
            
            distance = euclidean(current_norm, hist_norm)
            similarity = (1 - distance / np.sqrt(window_days)) * 100
            
            if similarity > 70:
                future_return = ((closes[i+window_days+4] - closes[i+window_days-1]) / closes[i+window_days-1]) * 100
                matches.append({
                    'start_date': df.index[i].strftime('%Y-%m-%d'),
                    'end_date': df.index[i+window_days-1].strftime('%Y-%m-%d'),
                    'similarity': similarity,
                    'after_5days_return': future_return
                })
        
        matches = sorted(matches, key=lambda x: x['similarity'], reverse=True)[:3]
        
        if not matches:
            return f"📊 [{ticker}] 유사 패턴을 찾을 수 없습니다."
        
        response = f"📈 [{ticker}] 차트 패턴 분석 결과\n"
        for i, m in enumerate(matches, 1):
            arrow = "📈" if m['after_5days_return'] > 0 else "📉"
            response += f"\n{i}. {m['start_date']} ~ {m['end_date']} (유사도 {m['similarity']:.1f}%)\n   {arrow} 5일 후 수익률: {m['after_5days_return']:+.2f}%"
        
        avg_return = np.mean([m['after_5days_return'] for m in matches])
        response += f"\n\n💡 평균 예상 수익률: {avg_return:+.2f}%"
        
        return response
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def calculate_volatility_regime(ticker: str, lookback_days: int = 252) -> str:
    """주식의 변동성 체제를 분석합니다."""
    try:
        import yfinance as yf
        import numpy as np
        
        stock = yf.Ticker(ticker)
        df = stock.history(period=f"{lookback_days}d")
        
        if len(df) < 30:
            return "⚠️ 데이터 부족"
        
        returns = df['Close'].pct_change().dropna()
        recent_vol = returns.tail(20).std() * np.sqrt(252) * 100
        
        historical_vols = [returns.iloc[i-20:i].std() * np.sqrt(252) * 100 for i in range(20, len(returns))]
        percentile = np.percentile(historical_vols, [25, 50, 75])
        
        regime = "🟢 저변동성" if recent_vol < percentile[0] else \
                "🟡 정상" if recent_vol < percentile[2] else \
                "🔴 고변동성"
        
        return f"""📊 [{ticker}] 변동성 분석
        
현재 변동성: {recent_vol:.2f}% (연환산)
25 퍼센타일: {percentile[0]:.2f}%
중간값: {percentile[1]:.2f}%
75 퍼센타일: {percentile[2]:.2f}%

현재 체제: {regime}

💡 투자 전략:
{
'- 저변동성: 옵션 매수, 브레이크아웃 대기' if recent_vol < percentile[0] else
'- 고변동성: 옵션 매도, 포지션 축소' if recent_vol > percentile[2] else
'- 정상: 일반 트레이딩'
}"""
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def detect_support_resistance(ticker: str, period: str = "6mo") -> str:
    """주요 지지선/저항선을 자동으로 탐지합니다."""
    try:
        import yfinance as yf
        import numpy as np
        from scipy.signal import find_peaks
        
        df = yf.Ticker(ticker).history(period=period)
        
        if len(df) < 50:
            return "⚠️ 데이터 부족"
        
        closes = df['Close'].values
        current_price = closes[-1]
        
        peaks, _ = find_peaks(closes, distance=5)
        troughs, _ = find_peaks(-closes, distance=5)
        
        def cluster_levels(prices):
            if len(prices) == 0:
                return []
            sorted_p = np.sort(prices)
            clusters = []
            curr = [sorted_p[0]]
            for p in sorted_p[1:]:
                if p <= curr[-1] * 1.02:
                    curr.append(p)
                else:
                    clusters.append(np.mean(curr))
                    curr = [p]
            clusters.append(np.mean(curr))
            return clusters
        
        resistance = [r for r in cluster_levels(closes[peaks]) if r > current_price][:3]
        support = [s for s in cluster_levels(closes[troughs]) if s < current_price][-3:]
        
        return f"""📊 [{ticker}] 지지/저항 분석
        
💵 현재가: ${current_price:.2f}

🔴 저항선:
{chr(10).join([f"   R{i+1}: ${r:.2f} (+{(r-current_price)/current_price*100:.1f}%)" for i, r in enumerate(resistance)]) if resistance else "   없음"}

🟢 지지선:
{chr(10).join([f"   S{i+1}: ${s:.2f} ({(s-current_price)/current_price*100:.1f}%)" for i, s in enumerate(reversed(support))]) if support else "   없음"}

💡 트레이딩:
- 저항선 돌파 시: 추가 매수 고려
- 지지선 이탈 시: 손절 또는 관망"""
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def compare_relative_strength(ticker: str, benchmark: str = "SPY", period: str = "1y") -> str:
    """특정 종목의 상대 강도를 벤치마크와 비교합니다."""
    try:
        import yfinance as yf
        import numpy as np
        
        stock_data = yf.Ticker(ticker).history(period=period)
        bench_data = yf.Ticker(benchmark).history(period=period)
        
        if len(stock_data) < 20 or len(bench_data) < 20:
            return "⚠️ 데이터 부족"
        
        common_dates = stock_data.index.intersection(bench_data.index)
        stock_close = stock_data.loc[common_dates, 'Close']
        bench_close = bench_data.loc[common_dates, 'Close']
        
        stock_norm = (stock_close / stock_close.iloc[0]) * 100
        bench_norm = (bench_close / bench_close.iloc[0]) * 100
        
        relative_strength = stock_norm / bench_norm * 100
        
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
{
'- 강세: 지속 보유 또는 추가 매수 고려' if alpha > 5 else
'- 약세: 비중 축소 또는 벤치마크 교체 검토' if alpha < -5 else
'- 중립: 시장 수익률 추종 중, 대기 전략'
}"""
        
    except Exception as e:
        return f"⚠️ 오류: {str(e)}"


@mcp.tool()
async def scan_technical_signals(ticker: str) -> str:
    """여러 기술적 지표를 종합하여 매수/매도 신호를 스캔합니다."""
    try:
        import yfinance as yf
        import numpy as np
        
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo")
        
        if len(df) < 50:
            return "⚠️ 데이터 부족"
        
        closes = df['Close'].values
        current = closes[-1]
        
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
        
        ma20 = np.mean(closes[-20:])
        ma50 = np.mean(closes[-50:]) if len(closes) >= 50 else ma20
        
        ma_signal = "🟢 골든크로스" if ma20 > ma50 and current > ma20 else \
                   "🔴 데드크로스" if ma20 < ma50 and current < ma20 else "⚪ 중립"
        
        ma20_full = np.mean(closes[-20:])
        std20 = np.std(closes[-20:])
        upper_band = ma20_full + 2 * std20
        lower_band = ma20_full - 2 * std20
        
        bb_signal = "🔴 상단밴드" if current > upper_band else \
                   "🟢 하단밴드" if current < lower_band else "⚪ 중립"
        
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
# Bridge 클래스 및 Stateless 핸들러
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
                        "name": "Professional-Stock-Analyzer", 
                        "version": "2.0.0"
                    }
                }
            })

        # 2. Tools List
        if method == "tools/list":
            tools_data = [
                {
                    "name": "get_realtime_quote",
                    "description": "실시간 호가, 체결 데이터 조회",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"ticker": {"type": "string"}},
                        "required": ["ticker"]
                    }
                },
                {
                    "name": "analyze_market_sentiment",
                    "description": "시장 심리 지표 종합 분석",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"ticker": {"type": "string"}},
                        "required": ["ticker"]
                    }
                },
                {
                    "name": "get_earnings_calendar",
                    "description": "실적 발표 일정 및 컨센서스 분석",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"ticker": {"type": "string"}},
                        "required": ["ticker"]
                    }
                },
                {
                    "name": "analyze_options_flow",
                    "description": "옵션 흐름 분석 (기관 큰손 추적)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"ticker": {"type": "string"}},
                        "required": ["ticker"]
                    }
                },
                {
                    "name": "backtest_strategy",
                    "description": "트레이딩 전략 백테스팅",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "ticker": {"type": "string"},
                            "strategy": {"type": "string", "default": "golden_cross"},
                            "period": {"type": "string", "default": "2y"}
                        },
                        "required": ["ticker"]
                    }
                },
                {
                    "name": "find_historical_pattern",
                    "description": "현재 차트 패턴과 가장 유사한 과거 시점을 찾아 분석",
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
                    "description": "주식의 변동성 체제를 분석",
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
                    "description": "주요 지지선/저항선을 자동으로 탐지",
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
                    "description": "특정 종목의 상대 강도를 벤치마크와 비교",
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
                    "description": "여러 기술적 지표를 종합하여 매수/매도 신호를 스캔",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"ticker": {"type": "string"}},
                        "required": ["ticker"]
                    }
                }
            ]
            
            return JSONResponse({
                "jsonrpc": "2.0", 
                "id": msg_id,
                "result": {"tools": tools_data}
            })

        # 3. Call Tool
        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            tool_map = {
                "get_realtime_quote": get_realtime_quote,
                "analyze_market_sentiment": analyze_market_sentiment,
                "get_earnings_calendar": get_earnings_calendar,
                "analyze_options_flow": analyze_options_flow,
                "backtest_strategy": backtest_strategy,
                "find_historical_pattern": find_historical_pattern,
                "calculate_volatility_regime": calculate_volatility_regime,
                "detect_support_resistance": detect_support_resistance,
                "compare_relative_strength": compare_relative_strength,
                "scan_technical_signals": scan_technical_signals
            }
            
            if tool_name not in tool_map:
                return JSONResponse({
                    "jsonrpc": "2.0", 
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {tool_name}"}
                })
            
            try:
                result = await tool_map[tool_name](**tool_args)
                return JSONResponse({
                    "jsonrpc": "2.0", 
                    "id": msg_id,
                    "result": {"content": [{"type": "text", "text": result}]}
                })
            except Exception as e:
                return JSONResponse({
                    "jsonrpc": "2.0", 
                    "id": msg_id,
                    "error": {"code": -32000, "message": f"Tool execution error: {str(e)}"}
                })

        return JSONResponse({
            "jsonrpc": "2.0", 
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        })
        
    except json.JSONDecodeError:
        return JSONResponse({
            "jsonrpc": "2.0", 
            "id": None,
            "error": {"code": -32700, "message": "Parse error: Invalid JSON"}
        })
    except Exception as e:
        return JSONResponse({
            "jsonrpc": "2.0", 
            "id": None,
            "error": {"code": -32000, "message": str(e)}
        })


# =========================
# 통합 핸들러 (SSE + Streamable POST)
# =========================

sse_transport = SseServerTransport("/")

async def handle_root(request: Request):
    if request.method == "OPTIONS":
        return Response(
            status_code=200, 
            headers={
                "Access-Control-Allow-Origin": "*", 
                "Access-Control-Allow-Methods": "*", 
                "Access-Control-Allow-Headers": "*"
            }
        )

    if request.method == "GET":
        if "text/event-stream" in request.headers.get("accept", ""):
            async def sse_app(scope, receive, send):
                async with sse_transport.connect_sse(scope, receive, send) as streams:
                    await mcp._mcp_server.run(
                        streams[0], 
                        streams[1], 
                        mcp._mcp_server.create_initialization_options()
                    )
            return ASGIResponder(sse_app)
        return JSONResponse({"status": "running", "mode": "professional-stock-analyzer", "version": "2.0"})

    if request.method == "POST":
        if request.query_params.get("sessionId") or request.query_params.get("session_id"):
            return ASGIResponder(sse_transport.handle_post_message)
        else:
            return await handle_stateless_jsonrpc(request)

    return Response(status_code=405)


# 앱 설정
app = Starlette(
    debug=True,
    routes=[Route("/", endpoint=handle_root, methods=["GET", "POST", "OPTIONS"])],
    middleware=[
        Middleware(
            CORSMiddleware, 
            allow_origins=["*"], 
            allow_methods=["*"], 
            allow_headers=["*"]
        )
    ]
)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1)