import os
import requests, time
try:
    from config import API_URL_V1, API_URL_V2, API_KEY
except Exception:
    API_URL_V1 = os.environ.get("API_URL_V1", "https://open-api.bser.io/v1")
    API_URL_V2 = os.environ.get("API_URL_V2", "https://open-api.bser.io/v2")
    API_KEY = os.environ.get("API_KEY")
from common.logger import setup_logger
from urllib.parse import quote_plus

logger = setup_logger("er_api")

def api_request(url) -> dict:
    start = time.time()

    headers = {"accept": "application/json", "x-api-key": API_KEY}
    response = requests.get(url, headers=headers)

    elapsed = time.time() - start
    wait = max(0.0, 1.1 - elapsed)
    time.sleep(wait)

    try:
        body = response.json()
    except Exception:
        body = None

    if response.status_code == 200 and isinstance(body, dict):
        body["_http_status"] = 200
        return body

    return {
        "error": "Failed to fetch data",
        "status_code": response.status_code,
        "url": url,
        "body_type": type(body).__name__,
    }

# Userid 조회
def get_user_id(nickname):
    q = quote_plus(str(nickname))
    url = f"{API_URL_V1}/user/nickname?query={q}"
    res = api_request(url)

    if not isinstance(res, dict):
        return None

    user = res.get("user")
    if not isinstance(user, dict):
        return None

    user_id = user.get("userId")
    return user_id

# 게임 경기 정보 획득
def get_game_data_raw(game_id):
    url = f"{API_URL_V1}/games/{game_id}"

    return api_request(url)

def get_user_game_data(user_id, next_game_id=None):
    url = f"{API_URL_V1}/user/games/uid/{user_id}"
    if next_game_id:
        url += f"?next={next_game_id}"

    data = api_request(url)

    if "error" in data:
        logger.warning(
            f"[er_api] get_user_game_data 실패: user_id={user_id}, next={next_game_id}, "
            f"status={data.get('status_code')}"
        )
        return {}

    return data


def get_l10n_url(save_path):
    url = f"{API_URL_V1}/l10n/Korean"
    response = api_request(url)

    with requests.get(response.get("data",{}).get("l10Path"), stream=True) as r:
        r.raise_for_status()  # 오류 발생 시 예외 처리
        with open(save_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):  # 8KB씩 저장
                f.write(chunk)

    logger.info(f"l10n.txt 파일이 저장되었습니다: {save_path}")

# 게임 정보 획득
def get_game_info(metatype="hash"):
    url = f"{API_URL_V2}/data/{metatype}"

    return api_request(url)


# User season stats (reference-only)
def get_user_stats(user_id, season_id, matching_mode):
    url = f"{API_URL_V2}/user/stats/uid/{user_id}/{season_id}/{matching_mode}"
    return api_request(url)

if __name__ == "__main__":
    test_game_code = 52268066
    test_user_num = 1051341
    # user_data = get_all_user_game_data(test_user_num, 5, 0)
    # print(get_game_data_raw(test_game_code))
    # print(user_data)
    print(get_user_id("simspace"))
