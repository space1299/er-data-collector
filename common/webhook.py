import os
import json
import requests

from common.logger import setup_logger

logger = setup_logger("discord_webhook")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


def send_discord_webhook(content: str, username: str = "ER-Collector", embeds=None):
    """
    Discord 웹훅으로 메시지 전송.

    :param content: 기본 텍스트 메시지
    :param username: 웹훅에 표시될 이름
    :param embeds: 디스코드 embed 리스트 (옵션, dict 리스트)
    """
    if not DISCORD_WEBHOOK_URL:
        logger.error("DISCORD_WEBHOOK_URL 이 설정되지 않았습니다.")
        return

    payload = {
        "username": username,
        "content": content,
    }

    if embeds:
        payload["embeds"] = embeds

    try:
        resp = requests.post(
            DISCORD_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        if resp.status_code >= 400:
            logger.error(f"Discord webhook 실패: {resp.status_code} {resp.text}")
        else:
            logger.info("Discord webhook 전송 완료")
    except Exception as e:
        logger.exception(f"Discord webhook 전송 중 예외 발생: {e}")

if __name__ == "__main__":
    message = "배경이 다른 인용 메시지는 '''text'''로 사용하며 보기에는 이렇게 표시됩니다. 적절한 자동 줄바꿈이 되며 최대 1800자까지 지원합니다."
    embeds = [
        {
            "title": "title은 이렇게 표시됩니다.",
            "description": (
                "descriptions은 이렇게 표시되며\n"
                f"```text\n{message[:1800]}\n```"
            ),
            "color": 0x5555FF,
            "fields": [
                {"name": "fields_name1", "value": "fields_value1", "inline": True},
                {"name": "fields_name2", "value": "fields_value2", "inline": True},
                {"name": "inline 옵션을 끈 경우", "value": "이렇게 줄바꿈되어 표시됩니다.", "inline": False},
                {"name": "inline 옵션을 켠 경우", "value": "이렇게 한 줄에 표시됩니다.", "inline": True},
                {"name": "inline 옵션을 켠 경우", "value": "이렇게 한 줄에 표시됩니다.", "inline": True},
                {"name": "inline 옵션을 켠 경우", "value": "이렇게 한 줄에 표시됩니다.", "inline": True},
                {"name": "field의 한계는", "value": "테스트 필요합니다.", "inline": False},
                {"name": "field의 한계는", "value": "테스트 필요합니다.", "inline": False},
                {"name": "field의 한계는", "value": "테스트 필요합니다.", "inline": False},
            ],
        }
    ]

    send_discord_webhook("", embeds=embeds)
