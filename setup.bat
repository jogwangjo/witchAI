@echo off
echo ================================
echo AI Recommender MCP 설치 시작
echo ================================
echo.

REM 가상환경 생성
echo [1/4] 가상환경 생성 중...
python -m venv venv
if %errorlevel% neq 0 (
    echo 오류: Python이 설치되어 있지 않거나 경로가 설정되지 않았습니다.
    pause
    exit /b 1
)

REM 가상환경 활성화
echo [2/4] 가상환경 활성화 중...
call venv\Scripts\activate.bat

REM 패키지 설치
echo [3/4] 패키지 설치 중...
pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo 오류: 패키지 설치에 실패했습니다.
    pause
    exit /b 1
)

REM 폴더 구조 확인
echo [4/4] 프로젝트 구조 확인 중...
if not exist "server" mkdir server
if not exist "server\tools" mkdir server\tools
if not exist "data" mkdir data

echo.
echo ================================
echo 설치 완료!
echo ================================
echo.
echo 서버를 실행하려면 다음 명령어를 입력하세요:
echo.
echo   venv\Scripts\activate
echo   python run_server.py
echo.
echo 또는 run_server.bat을 더블클릭하세요.
echo.
pause