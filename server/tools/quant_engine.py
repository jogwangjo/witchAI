import yfinance as yf
import numpy as np
import pandas as pd
from datetime import timedelta
from typing import List, Dict, Any, Tuple

class StockPatternAnalyzer:
    """
    시계열 데이터 마이닝 기법을 활용한 주가 패턴 분석 엔진
    Algorithm: Z-Score Normalization + Pearson Correlation (Moving Window)
    """

    def __init__(self):
        pass

    def _z_score_normalize(self, series: np.ndarray) -> np.ndarray:
        """데이터를 평균 0, 표준편차 1로 정규화 (스케일링 보정)"""
        return (series - np.mean(series)) / np.std(series)

    def calculate_similarity(self, target_sequence: np.ndarray, candidate_sequence: np.ndarray) -> float:
        """
        두 시계열 데이터 간의 피어슨 상관계수 계산
        Return: -1.0 (정반대) ~ 1.0 (완전 일치)
        """
        if len(target_sequence) != len(candidate_sequence):
            return 0.0
        
        # 상관계수 계산 (속도를 위해 numpy corrcoef 사용)
        return np.corrcoef(target_sequence, candidate_sequence)[0, 1]

    async def find_similar_patterns(self, ticker: str, window_size: int = 30, top_k: int = 3) -> Dict[str, Any]:
        """
        특정 종목의 최근 패턴과 가장 유사한 과거 패턴을 탐색
        """
        # 1. 데이터 수집 (최대 기간)
        try:
            stock = yf.Ticker(ticker)
            # 10년치 데이터 로드 (충분한 탐색 공간 확보)
            df = stock.history(period="10y")
            
            if len(df) < window_size * 2:
                return {"error": "데이터가 부족하여 분석할 수 없습니다."}
            
            # 종가(Close) 데이터만 추출
            closes = df['Close'].values
            dates = df.index
            
        except Exception as e:
            return {"error": f"데이터 수집 중 오류 발생: {str(e)}"}

        # 2. 타겟 패턴 설정 (최근 N일)
        target_seq = closes[-window_size:]
        target_norm = self._z_score_normalize(target_seq)
        
        # 3. 슬라이딩 윈도우 탐색 (Search Space)
        # 최근 패턴과 겹치지 않도록 탐색 범위 제한
        search_space_limit = len(closes) - window_size - 1
        
        results = []
        
        # 벡터화 연산을 하면 더 빠르지만, 명시적인 이해를 위해 루프 사용 (Numpy 최적화 적용 가능)
        for i in range(search_space_limit):
            candidate_seq = closes[i : i + window_size]
            
            # 윈도우 내 변동성이 너무 없으면(거래 정지 등) 스킵
            if np.std(candidate_seq) == 0:
                continue
                
            candidate_norm = self._z_score_normalize(candidate_seq)
            
            # 상관계수 계산
            similarity = self.calculate_similarity(target_norm, candidate_norm)
            
            # 유사도가 0.8 이상인 경우만 기록 (노이즈 필터링)
            if similarity > 0.8:
                start_date = dates[i].strftime("%Y-%m-%d")
                end_date = dates[i + window_size - 1].strftime("%Y-%m-%d")
                
                # 유사 구간 이후의 미래 데이터 (Next 5 days) 확인
                future_return = 0.0
                if i + window_size + 5 < len(closes):
                    current_price = closes[i + window_size - 1]
                    future_price = closes[i + window_size + 5]
                    future_return = ((future_price - current_price) / current_price) * 100
                
                results.append({
                    "start_date": start_date,
                    "end_date": end_date,
                    "similarity": round(similarity * 100, 2), # 퍼센트
                    "after_5days_return": round(future_return, 2)
                })
        
        # 4. 결과 정렬 (유사도 높은 순)
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
        # 상위 K개 추출 (기간이 겹치는 중복 제거 로직은 간단하게 생략)
        final_results = results[:top_k]
        
        return {
            "ticker": ticker,
            "current_period": {
                "start": dates[-window_size].strftime("%Y-%m-%d"),
                "end": dates[-1].strftime("%Y-%m-%d")
            },
            "analysis_algorithm": "Pearson Correlation with Z-Score Normalization",
            "top_matches": final_results
        }

# 인스턴스 생성
analyzer = StockPatternAnalyzer()