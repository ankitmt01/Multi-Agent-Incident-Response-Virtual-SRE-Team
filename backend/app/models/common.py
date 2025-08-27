from enum import Enum

class Severity(str, Enum):
    low = "LOW"
    medium = "MEDIUM"
    high = "HIGH"
    critical = "CRITICAL"

class AgentName(str, Enum):
    detector = "detector"
    investigator = "investigator"
    remediator = "remediator"
    validator = "validator"
    reporter = "reporter"
