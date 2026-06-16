"""
MySQL/MariaDB 연결 헬퍼.

.env 의 MYSQL_* 를 읽는다. --target prod 면 MYSQL_*_PROD 를 우선 사용(없으면 기본값).
LawQuery 본체·frc 와 동일한 자격증명 컨벤션.
"""
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()


def _conf(target: str = "dev") -> dict:
    sfx = "_PROD" if target == "prod" else ""
    g = lambda k, d=None: os.getenv(f"MYSQL_{k}{sfx}") or os.getenv(f"MYSQL_{k}", d)
    return {
        "host": g("HOST", "localhost"),
        "port": int(g("PORT", "3306")),
        "user": g("USER", "root"),
        "password": g("PASSWORD", "") or "",
        "charset": "utf8mb4",
        "autocommit": False,
    }


def get_connection(database: str | None = None, target: str = "dev"):
    """database=None 이면 서버 레벨 연결(CREATE DATABASE 용)."""
    conf = _conf(target)
    if database:
        conf["database"] = database
    return pymysql.connect(**conf)


def describe_target(target: str = "dev") -> str:
    c = _conf(target)
    return f"{c['user']}@{c['host']}:{c['port']}"
