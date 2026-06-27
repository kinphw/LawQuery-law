"""개발 ldb_<code> → 운영 **정확 복제** (mysqldump → mysql 파이프, SSH 터널 경유).

운영 MySQL은 localhost 바인딩이라 3306 직접 미도달 → SSH 터널(paramiko/sshtunnel)로
포워딩 후 `mysqldump(dev) | mysql(prod)`. 스키마·데이터·콜레이션(uca1400)·PK 그대로.
파이프라인 재실행이 아니라 **세션·GUI로 다듬은 개발 DB를 그대로** 옮긴다.

.env 필요:
  MYSQL_*(dev)               개발 자격
  MYSQL_*_PROD               운영 자격(서버 로컬 MySQL)
  SSH_HOST/SSH_USER[/SSH_PORT]              운영 SSH(터널)
    인증: SSH_KEY_PATH[/SSH_KEY_PASSPHRASE]  또는  SSH_PASSWORD
    SSH_BIND_PORT 미설정 시 빈 로컬포트 자동 선택(수동 터널 13306 과 충돌 방지).
SSH_HOST 미설정 시 직접 연결 시도(운영 3306 직접 닿을 때만).
"""
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _bin(name: str) -> str:
    p = shutil.which(name) or shutil.which(name.replace("mysql", "mariadb"))
    if not p:
        raise RuntimeError(f"'{name}' 실행파일을 PATH에서 찾을 수 없습니다(MariaDB/MySQL bin).")
    return p


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait_port(proc, port, timeout=12) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:       # ssh 가 먼저 죽음(인증·호스트키 등)
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


class _CliTunnel:
    """시스템 ssh -L 서브프로세스를 sshtunnel 과 같은 인터페이스로 감싼다."""
    def __init__(self, proc, port):
        self._proc = proc
        self.local_bind_port = port

    def stop(self):
        try:
            self._proc.terminate()
        except Exception:
            pass


def _open_tunnel_cli(host, remote_port, bind_port, log):
    """시스템 ssh 클라이언트로 터널(= ~/.ssh/config·키·agent·known_hosts 그대로 사용)."""
    ssh = shutil.which("ssh")
    port = bind_port or _free_port()
    user = os.getenv("SSH_USER")
    target = f"{user}@{host}" if user else host          # 미지정 시 config 의 User
    cmd = [ssh, "-N",
           "-o", "ExitOnForwardFailure=yes",
           "-o", "ConnectTimeout=10",
           "-o", "BatchMode=yes"]                          # 비대화(프롬프트로 멈춤 방지)
    sp = os.getenv("SSH_PORT")
    if sp:
        cmd += ["-p", sp]
    cmd += ["-L", f"127.0.0.1:{port}:127.0.0.1:{remote_port}", target]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    log(f"[deploy] ssh 터널(CLI) {target} → 127.0.0.1:{port}")
    if not _wait_port(proc, port):
        err = ""
        if proc.poll() is not None:
            try:
                err = (proc.stderr.read() or "").strip()[:400]
            except Exception:
                pass
        else:
            proc.terminate()
        raise RuntimeError(f"ssh 터널 실패: {err or '포트 대기 시간 초과'} "
                           "(키 암호는 ssh-agent 에 로드하거나 SSH_KEY_PATH/SSH_PASSWORD 사용)")
    return _CliTunnel(proc, port)


def _open_tunnel(log):
    """SSH_HOST 있으면 터널 열고 (tunnel, local_port) 반환. 없으면 (None, None).

    인증 우선순위:
      1) SSH_KEY_PATH / SSH_PASSWORD 명시 → paramiko(sshtunnel)
      2) 그 외 + 시스템 ssh 존재 → ssh -L (~/.ssh/config·agent 그대로)  ← 'ssh 그냥 됨' 케이스
    """
    host = os.getenv("SSH_HOST")
    if not host:
        return None, None

    remote_port = int(os.getenv("MYSQL_PORT_PROD") or os.getenv("MYSQL_PORT") or 3306)
    bind_port = int(os.getenv("SSH_BIND_PORT", "0"))      # 0 = 빈 포트 자동
    explicit = os.getenv("SSH_KEY_PATH") or os.getenv("SSH_PASSWORD")

    if not explicit and shutil.which("ssh"):
        t = _open_tunnel_cli(host, remote_port, bind_port, log)
        return t, t.local_bind_port

    # 명시적 키/비번 경로 — paramiko
    try:
        import paramiko
        if not hasattr(paramiko, "DSSKey"):              # 신버전 paramiko 호환 shim
            paramiko.DSSKey = type("DSSKey", (), {})
        from sshtunnel import SSHTunnelForwarder
    except ImportError as e:
        raise RuntimeError(f"SSH 터널에 paramiko/sshtunnel 필요: pip install paramiko sshtunnel ({e})")

    key_path = os.getenv("SSH_KEY_PATH")
    if key_path:
        key_path = os.path.expanduser(key_path.strip())
    tunnel = SSHTunnelForwarder(
        (host, int(os.getenv("SSH_PORT", "22"))),
        ssh_username=os.getenv("SSH_USER"),
        ssh_password=os.getenv("SSH_PASSWORD") or None,
        ssh_pkey=key_path or None,
        ssh_private_key_password=os.getenv("SSH_KEY_PASSPHRASE") or None,
        remote_bind_address=("127.0.0.1", remote_port),
        local_bind_address=("127.0.0.1", bind_port),
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
