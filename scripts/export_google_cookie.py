#!/usr/bin/env python3
"""
Google NotebookLM 웹 자동화를 위한 로그인 세션(storage_state.json) 추출 도우미.
내 컴퓨터(로컬 PC)에서 실행하면 브라우저 창이 열리고, 구글 로그인 완료 후 Enter를 누르면
GitHub Secrets에 바로 붙여넣을 수 있는 Base64 문자열까지 자동 생성해 줍니다.

실행 방법:
  python scripts/export_google_cookie.py
"""
import asyncio
import base64
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "storage_state.json"
B64_FILE = BASE_DIR / "storage_state.b64.txt"


async def main():
    print("=" * 70)
    print("🌐 Google NotebookLM 세션 쿠키 추출 도우미")
    print("=" * 70)
    print("잠시 후 크롬 브라우저 창이 열리면 구글 계정으로 로그인해 주세요.")
    print("로그인이 완료되어 NotebookLM 메인 화면(내 노트북 목록)이 보이면")
    print("이 터미널 창으로 돌아와 [Enter] 키를 눌러주세요!\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(locale="ko-KR", timezone_id="Asia/Seoul")
        page = await context.new_page()
        await page.goto("https://notebooklm.google.com/")

        input(">>> NotebookLM 로그인이 완료되었으면 [Enter] 키를 누르세요... ")

        await context.storage_state(path=str(STATE_FILE))
        await browser.close()

    raw_bytes = STATE_FILE.read_bytes()
    b64_str = base64.b64encode(raw_bytes).decode("ascii")
    B64_FILE.write_text(b64_str, encoding="utf-8")

    print("\n✅ 구글 세션 추출 완료!")
    print(f"1) 로컬 파일 저장됨: {STATE_FILE}")
    print(f"2) GitHub Secrets 등록용 Base64 파일 저장됨: {B64_FILE}")
    print("\n👉 GitHub 저장소의 [Settings -> Secrets and variables -> Actions]에서")
    print("   'GOOGLE_STORAGE_STATE_B64' 시크릿 이름으로 storage_state.b64.txt 파일 안의 내용을 붙여넣으세요.")


if __name__ == "__main__":
    asyncio.run(main())
