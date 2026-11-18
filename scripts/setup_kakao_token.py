#!/usr/bin/env python3
"""
카카오톡 '나에게 보내기' 최초 1회 토큰 발급 도우미 스크립트.
실행 방법:
  python scripts/setup_kakao_token.py
"""
import urllib.parse
import requests

REDIRECT_URI = "https://localhost:3000"


def main():
    print("=" * 68)
    print("🔑 카카오톡 '나에게 보내기' Refresh Token 발급 도우미")
    print("=" * 68)
    rest_api_key = input("\n1) Kakao Developers의 [REST API 키]를 입력해 주세요: ").strip()
    if not rest_api_key:
        print("❌ REST API 키가 비어 있습니다.")
        return

    client_secret = input(
        "2) [선택] Client Secret을 설정하셨다면 입력해 주세요 (없으면 그냥 Enter): "
    ).strip()

    auth_url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={rest_api_key}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&response_type=code"
        f"&scope=talk_message"
    )

    print("\n" + "-" * 68)
    print("아래 URL을 인터넷 브라우저 주소창에 붙여넣고 카카오 로그인을 진행해 주세요.")
    print("(동의 항목에서 '카카오톡 메시지 전송'에 반드시 체크해 주세요!)")
    print("-" * 68)
    print(f"\n{auth_url}\n")
    print("-" * 68)
    print("로그인 후 브라우저가 '사이트에 연결할 수 없음(localhost:3000)' 화면으로 바뀌면 정상입니다!")
    print("그 상태의 브라우저 주소창 전체 URL(또는 code= 뒤의 값)을 복사해 아래에 붙여넣어 주세요.")

    raw_input_val = input("\n3) 주소창 URL 전체 또는 code 값을 붙여넣으세요: ").strip()
    code = raw_input_val
    if "code=" in raw_input_val:
        parsed = urllib.parse.urlparse(raw_input_val)
        qs = urllib.parse.parse_qs(parsed.query)
        code = qs.get("code", [raw_input_val])[0]

    payload = {
        "grant_type": "authorization_code",
        "client_id": rest_api_key,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }
    if client_secret:
        payload["client_secret"] = client_secret

    resp = requests.post("https://kauth.kakao.com/oauth/token", data=payload, timeout=15)
    if resp.status_code != 200:
        print(f"\n❌ 토큰 발급 실패 ({resp.status_code}): {resp.text}")
        return

    data = resp.json()
    refresh_token = data.get("refresh_token", "")
    access_token = data.get("access_token", "")

    print("\n✅ 토큰 발급 성공! 아래 값들을 .env 파일 또는 GitHub Secrets에 등록해 주세요.")
    print("=" * 68)
    print(f"KAKAO_REST_API_KEY={rest_api_key}")
    if client_secret:
        print(f"KAKAO_CLIENT_SECRET={client_secret}")
    print(f"KAKAO_REFRESH_TOKEN={refresh_token}")
    print("=" * 68)

    test_yn = input("\n지금 바로 내 카카오톡으로 테스트 메시지를 보내볼까요? (y/n): ").strip().lower()
    if test_yn == "y" and access_token:
        import json

        r = requests.post(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            headers={"Authorization": f"Bearer {access_token}"},
            data={
                "template_object": json.dumps(
                    {
                        "object_type": "text",
                        "text": "🎉 [연동 성공] 월·수·금 07:30 경제·경영 2인 팟캐스트 브리핑 알림이 정상 연결되었습니다!",
                        "link": {
                            "web_url": "https://notebooklm.google.com",
                            "mobile_web_url": "https://notebooklm.google.com",
                        },
                    },
                    ensure_ascii=False,
                )
            },
            timeout=10,
        )
        print("카카오톡 발송 결과:", r.json())


if __name__ == "__main__":
    main()
