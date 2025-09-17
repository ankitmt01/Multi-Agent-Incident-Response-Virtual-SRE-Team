# from dotenv import load_dotenv
# import os

# load_dotenv()

# PORT = int(os.getenv("PORT", "8000"))
# VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", ".chroma")
# KB_MIN_DOCS = int(os.getenv("KB_MIN_DOCS", "8"))
# ENV_NAME = os.getenv("ENV_NAME", "staging")

# POLICY_ENV_ALLOWLIST = set([s.strip() for s in os.getenv("POLICY_ENV_ALLOWLIST", "staging,dev").split(",") if s.strip()])
# POLICY_REQUIRE_APPROVAL_FOR = set([s.strip() for s in os.getenv("POLICY_REQUIRE_APPROVAL_FOR", "write,config_change").split(",") if s.strip()])

# ALLOWED_ORIGINS = [s.strip() for s in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
# LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

# # Chroma collection name (must be 3–63 chars)
# COLLECTION_NAME = os.getenv("COLLECTION_NAME", "knowledge_base")

# # 🔐 Simple API key for write endpoints (set in .env)
# API_KEY = os.getenv("API_KEY", "").strip()

# # 💾 On-disk persistence (mounted volume-friendly)
# STATE_DIR = os.getenv("STATE_DIR", "state")
# os.makedirs(STATE_DIR, exist_ok=True)

# # Notifications (stubs; wire later)
# SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()
# SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "").strip() 
# JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").strip()
# JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "").strip()
# JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "").strip()

# AUTH_MODE = os.getenv("AUTH_MODE", "api_key").strip()  # api_key | scoped_jwt
# DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in ("1","true","yes")

# # JWT (only used if AUTH_MODE=scoped_jwt)
# JWT_SECRET   = os.getenv("JWT_SECRET", "please-change").strip()
# JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "incident-copilot").strip()
# JWT_ISSUER   = os.getenv("JWT_ISSUER", "").strip()



from dotenv import load_dotenv
import os

load_dotenv()

# -------- Core --------
PORT = int(os.getenv("PORT", "8000"))
VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", ".chroma")
KB_MIN_DOCS = int(os.getenv("KB_MIN_DOCS", "8"))
ENV_NAME = os.getenv("ENV_NAME", "staging")

POLICY_ENV_ALLOWLIST = set([s.strip() for s in os.getenv("POLICY_ENV_ALLOWLIST", "staging,dev").split(",") if s.strip()])
POLICY_REQUIRE_APPROVAL_FOR = set([s.strip() for s in os.getenv("POLICY_REQUIRE_APPROVAL_FOR", "write,config_change").split(",") if s.strip()])

ALLOWED_ORIGINS = [s.strip() for s in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

# Chroma collection name (must be 3–63 chars)
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "knowledge_base")

# 🔐 Base API key (full-access / ops)
API_KEY = os.getenv("API_KEY", "").strip()

# 💾 On-disk persistence (mounted volume-friendly)
STATE_DIR = os.getenv("STATE_DIR", "state")
os.makedirs(STATE_DIR, exist_ok=True)

# Notifications (stubs; wire later)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "").strip()
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").strip()
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "").strip()
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "").strip()

# -------- Auth switches (NEW) --------
AUTH_MODE = os.getenv("AUTH_MODE", "api_key").strip()          # api_key | scoped_jwt
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in ("1", "true", "yes")

# JWT (used if AUTH_MODE=scoped_jwt)
JWT_SECRET   = os.getenv("JWT_SECRET", "please-change").strip()
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "incident-copilot").strip()
JWT_ISSUER   = os.getenv("JWT_ISSUER", "").strip()
