import os

# log settings
ER_DATA_LOG_FILE = os.environ.get("ER_DATA_LOG_FILE", "./logs/er_data_collector.log")

# API settings
API_URL_V1 = os.environ.get("API_URL_V1", "https://open-api.bser.io/v1")
API_URL_V2 = os.environ.get("API_URL_V2", "https://open-api.bser.io/v2")
API_KEY = os.environ.get("API_KEY")

# MongoDB settings
DB_URL = os.environ["MONGO_URI"]

# report settings
N_TARGET = int(os.environ.get("REPORT_N_TARGET", "50"))
N_MIN = int(os.environ.get("REPORT_N_MIN", "30"))
MAX_VERSIONS_BACK = int(os.environ.get("REPORT_MAX_VERSIONS_BACK", "2"))
TTL_DAYS = int(os.environ.get("REPORT_TTL_DAYS", "21"))
WINDOW_RULE_VERSION = os.environ.get("REPORT_WINDOW_RULE_VERSION", "v1")
SEASON_CAP = os.environ.get("REPORT_SEASON_CAP", "current_season_only")

POLL_INTERVAL_SEC = int(os.environ.get("REPORT_POLL_INTERVAL_SEC", "5"))
WORKER_LOCK_ID = os.environ.get("REPORT_WORKER_LOCK_ID", "")

# matchingMode default is 3
MATCHING_MODE = int(os.environ.get("REPORT_MATCHING_MODE", "3"))

# lease/retry settings
REPORT_JOB_LEASE_SEC = int(os.environ.get("REPORT_JOB_LEASE_SEC", "600"))
REPORT_JOB_MAX_RETRY = int(os.environ.get("REPORT_JOB_MAX_RETRY", "3"))
