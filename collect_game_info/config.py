import os

# log 관련 설정
ER_DATA_LOG_FILE = os.environ.get("ER_DATA_LOG_FILE", "./logs/collect_game_info.log")

# API 관련 설정
API_URL_V1 = os.environ.get("API_URL_V1", "https://open-api.bser.io/v1")
API_URL_V2 = os.environ.get("API_URL_V2", "https://open-api.bser.io/v2")
API_KEY = os.environ.get("API_KEY")

# MongoDB settings
DB_URL = os.environ["MONGO_INTERNAL_URI"]
