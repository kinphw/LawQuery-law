"""개발 ldb_<code> → 운영 **정확 복제** (mysqldump → mysql 파이프, SSH 터널 경유).

운영 MySQL은 localhost 바인딩이라 3306 직접 미도달 → SSH 터널(paramiko/sshtunnel)로
포워딩 후 `mysqldump(dev) | mysql(prod)`. 스키마·데이터·콜레이션(uca1400)·PK 그대로.
파이프라인 재실행이 아니라 **세션·GUI로 다듬은 개발 DB를 그대로** 옮긴다.

.env 필요:
  MYSQL_*(dev)               개발 자격
  MYSQL_*_PROD               운영 자격(서버 로컬 MySQL)
  SSH_HOST/SSH_USER/SSH_PASSWORD[/SSH_PORT/SSH_BIND_PORT]   운영 SSH(터널)
SSH_HOST 미설정 시 직접 연결 시도(운영 3306 직접 닿을 때만).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _bin(name: str) -> str:
    p = shutil.which(name) or shutil.which(name.replace("mysql", "mariadb"))
    if not p:
        raise RuntimeError(f"'{name}' 실행파일을 PATH에서 찾을 수 없습니다(MariaDB/MySQL bin).")
    return p


def _open_tunnel(log):
    """SSH_HOST 있으면 터널 열고 (tunnel, local_port) 반환. 없으면 (None, None)."""
    host = os.getenv("SSH_HOST")
    if not host:
        return None, None
    try:
        import paramiko
        if not hasattr(paramiko, "DSSKey"):          # 신버전 paramiko 호환 shim
            paramiko.DSSKey = type("DSSKey", (), {})
        from sshtunnel import SSHTunnelForwarder
    except ImportError as e:
        raise RuntimeError(f"SSH 터널에 paramiko/sshtunnel 필요: pip install paramiko sshtunnel ({e})")

    prod_port = int(os.getenv("MYSQL_PORT_PROD") or os.getenv("MYSQL_PORT") or 3306)
    tunnel = SSHTunnelForwarder(
        (host, int(os.getenv("SSH_PORT", "22"))),
        ssh_username=os.getenv("SSH_USER"),
        ssh_password=os.getenv("SSH_PASSWORD"),
        remote_bind_address=("127.0.0.1", prod_port),
        local_bind_address=("127.0.0.1", int(os.getenv("SSH_BIND_PORT", "13306"))),
        set_keepalive=10.0,
    )
    tunnel.start()
    log(f"[deploy] SSH 터널 {host} → 127.0.0.1:{tunnel.local_bind_port}")
    return tunnel, tunnel.local_bind_port


def replicate_db(code: str, log=print) -> None:
    """개발 ldb_<code> 를 운영 ldb_<code> 로 정확 복제(DROP+CREATE 포함)."""
    db = f"ldb_{code}"
    dump_bin, mysql_bin = _bin("mysqldump"), _bin("mysql")

    dev = {"h": os.getenv("MYSQL_HOST", "localhost"), "P": os.getenv("MYSQL_PORT", "3306"),
           "u": os.getenv("MYSQL_USER", "root"), "pw": os.getenv("MYSQL_PASSWORD", "") or ""}
    prod_pw = os.getenv("MYSQL_PASSWORD_PROD") or ""
    prod_u = os.getenv("MYSQL_USER_PROD") or dev["u"]

    tunnel, port = _open_tunnel(log)
    try:
        if tunnel:
            prod_h, prod_p = "127.0.0.1", str(port)
        else:
            prod_h = os.getenv("MYSQL_HOST_PROD") or dev["h"]
            prod_p = os.getenv("MYSQL_PORT_PROD") or "3306"

        log(f"[deploy] {db}: dev({dev['h']}:{dev['P']}) → prod({prod_h}:{prod_p}) 정확복제 시작")
        dump_cmd = [dump_bin, f"-h{dev['h']}", f"-P{dev['P']}", f"-u{dev['u']}",
                    "--databases", db, "--add-drop-database", "--single-transaction",
                    "--default-character-set=utf8mb4"]
        load_cmd = [mysql_bin, f"-h{prod_h}", f"-P{prod_p}", f"-u{prod_u}",
                    "--default-character-set=utf8mb4"]
        # 비번은 MYSQL_PWD 환경변수로(명령행 노출·경고 방지). dump/load 각각 다른 비번.
        p1 = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env={**os.environ, "MYSQL_PWD": dev["pw"]})
        p2 = subprocess.Popen(load_cmd, stdin=p1.stdout, stderr=subprocess.PIPE,
                              env={**os.environ, "MYSQL_PWD": prod_pw})
        p1.stdout.close()
        _, e2 = p2.communicate()
        _, e1 = p1.communicate()
        if p1.returncode:
            raise RuntimeError(f"mysqldump 실패: {e1.decode('utf-8', 'replace')[:400]}")
        if p2.returncode:
            raise RuntimeError(f"mysql(load) 실패: {e2.decode('utf-8', 'replace')[:400]}")
        log(f"[deploy] ✅ {db} 운영 복제 완료(개발 asis 그대로).")
    finally:
        if tunnel:
            tunnel.stop()
            log("[deploy] SSH 터널 닫힘")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print("사용법: python -m common.replicate <code>   (예: g)"); sys.exit(1)
    replicate_db(sys.argv[1])
