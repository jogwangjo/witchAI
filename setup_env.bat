@echo off
echo ================================
echo AI Recommender MCP 환경 설정
echo ================================
echo.

cd /d %~dp0

REM .env.example 생성
echo # GitHub Token (선택사항)> .env.example
echo # GITHUB_TOKEN=your_token_here>> .env.example
echo.>> .env.example
echo # Hugging Face Token (선택사항)>> .env.example
echo # HUGGINGFACE_TOKEN=your_token_here>> .env.example
echo.>> .env.example
echo PORT=8000>> .env.example
echo HOST=0.0.0.0>> .env.example
echo .env.example 생성 완료!

REM .env 생성 (빈 파일)
if not exist .env (
    echo # 환경변수 설정> .env
    echo # 토큰은 선택사항입니다>> .env
    echo.>> .env
    echo PORT=8000>> .env
    echo HOST=0.0.0.0>> .env
    echo .env 생성 완료!
) else (
    echo .env 파일이 이미 존재합니다.
)

REM .gitignore 생성
echo # Python> .gitignore
echo __pycache__/>> .gitignore
echo *.pyc>> .gitignore
echo .Python>> .gitignore
echo.>> .gitignore
echo # Virtual Environment>> .gitignore
echo venv/>> .gitignore
echo env/>> .gitignore
echo.>> .gitignore
echo # Environment variables>> .gitignore
echo .env>> .gitignore
echo.>> .gitignore
echo # IDE>> .gitignore
echo .vscode/>> .gitignore
echo .idea/>> .gitignore
echo.>> .gitignore
echo # OS>> .gitignore
echo .DS_Store>> .gitignore
echo Thumbs.db>> .gitignore
echo .gitignore 생성 완료!

REM tools 폴더 확인
if not exist "server\tools" (
    mkdir "server\tools"
    echo. > "server\tools\__init__.py"
    echo server\tools 폴더 생성 완료!
)

REM __init__.py 파일 생성
if not exist "server\__init__.py" (
    echo. > "server\__init__.py"
    echo server\__init__.py 생성 완료!
)

echo.
echo ================================
echo 설정 완료!
echo ================================
echo.
echo 다음 단계:
echo 1. .env 파일을 열어서 토큰 입력 (선택사항)
echo 2. python-dotenv 설치: pip install python-dotenv
echo 3. 서버 실행: python server/main.py
echo.
pause