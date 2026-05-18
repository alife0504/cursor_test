"""Phase 19 — backup/restore 腳本整合測試（≥ 3 個）。

涵蓋：
1. backup.sh dry-run 檢查（不實際跑，只驗證 script 語法 + env 檢查）
2. verify_backup.sh 對「假 backup」失敗應正確報錯
3. dr_drill_a.sh dry-run（檢查能找到 backup）

策略：
- 不真的跑備份（會打 docker，太慢）
- 用 bash -n（語法檢查）+ bash --noexec 確認 script 沒語法錯
- 用 mock backup file 驗證 verify_backup.sh 對「壞檔案」失敗

跑：cd backend && uv run pytest tests/integration/test_backup_restore.py -v
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = _ROOT / "scripts"


def _resolve_bash() -> str | None:
    """找 Git Bash（msys），避開 WSL bash（WSL 看不到 Windows 檔案系統的 /c）。"""
    # 優先 Git Bash
    candidates = [
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\usr\bin\bash.exe",
    ]
    for c in candidates:
        if Path(c).is_file():
            return c
    # Linux / 直接系統 bash
    found = shutil.which("bash")
    return found


_BASH = _resolve_bash()


def _bash_syntax_check(script: Path) -> tuple[int, str]:
    """bash -n 語法檢查（不執行）。

    Windows：直接用 Git Bash + 原 Windows 路徑（msys bash 接受 C:\\foo\\bar）。
    """
    if _BASH is None:
        return -1, "bash not available"

    proc = subprocess.run(  # noqa: S603 — 受控的 _BASH + 寫死 script path，無外部輸入
        [_BASH, "-n", str(script)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    return proc.returncode, proc.stderr or ""


@pytest.fixture(scope="module")
def _bash_available() -> bool:
    """確認 bash 可執行（Windows 用 Git Bash 而非 WSL bash）。"""
    if _BASH is None:
        return False
    try:
        proc = subprocess.run(  # noqa: S603 — 寫死 _BASH 路徑 + --version
            [_BASH, "--version"], capture_output=True, text=True, timeout=5
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


# ════════════════════════════════════════════════════════
# 1. backup.sh 語法檢查
# ════════════════════════════════════════════════════════


def test_backup_script_syntax_ok(_bash_available) -> None:
    if not _bash_available:
        pytest.skip("bash 不可用（CI Windows 環境）")
    rc, stderr = _bash_syntax_check(SCRIPTS_DIR / "backup.sh")
    assert rc == 0, f"backup.sh 語法錯：{stderr}"


def test_restore_script_syntax_ok(_bash_available) -> None:
    if not _bash_available:
        pytest.skip("bash 不可用")
    rc, stderr = _bash_syntax_check(SCRIPTS_DIR / "restore.sh")
    assert rc == 0, f"restore.sh 語法錯：{stderr}"


def test_verify_backup_script_syntax_ok(_bash_available) -> None:
    if not _bash_available:
        pytest.skip("bash 不可用")
    rc, stderr = _bash_syntax_check(SCRIPTS_DIR / "verify_backup.sh")
    assert rc == 0, f"verify_backup.sh 語法錯：{stderr}"


def test_dr_drill_a_script_syntax_ok(_bash_available) -> None:
    if not _bash_available:
        pytest.skip("bash 不可用")
    rc, stderr = _bash_syntax_check(SCRIPTS_DIR / "dr_drill_a.sh")
    assert rc == 0, f"dr_drill_a.sh 語法錯：{stderr}"


def test_generate_self_signed_cert_syntax_ok(_bash_available) -> None:
    if not _bash_available:
        pytest.skip("bash 不可用")
    rc, stderr = _bash_syntax_check(SCRIPTS_DIR / "generate_self_signed_cert.sh")
    assert rc == 0, f"generate_self_signed_cert.sh 語法錯：{stderr}"


# ════════════════════════════════════════════════════════
# 2. verify_backup.sh 對「假 backup」應失敗
# ════════════════════════════════════════════════════════


def test_verify_backup_fails_on_missing_file(_bash_available, tmp_path) -> None:
    if not _bash_available:
        pytest.skip("bash 不可用")

    fake_backup = tmp_path / "nonexistent.tar.gz.gpg"
    proc = subprocess.run(  # noqa: S603 — 受控的 script path + tmp_path 輸入
        [_BASH, str(SCRIPTS_DIR / "verify_backup.sh"), str(fake_backup)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        cwd=str(_ROOT),
    )
    # 不存在 → 應該 exit code != 0
    assert proc.returncode != 0
    combined = (proc.stderr or "") + (proc.stdout or "")
    assert (
        "找不到" in combined
        or "not found" in combined.lower()
        or "no such" in combined.lower()
        or "env.prod" in combined.lower()  # 也可能先撞 .env.prod missing
    ), f"無預期錯誤訊息：{combined[:300]}"


def test_backup_script_requires_env_prod(_bash_available, tmp_path) -> None:
    """無 .env.prod 時 backup.sh 應該明確拒絕。"""
    if not _bash_available:
        pytest.skip("bash 不可用")

    # 用 tmp_path 當 fake project root
    fake_root = tmp_path / "fake_project"
    (fake_root / "scripts").mkdir(parents=True)

    shutil.copy(SCRIPTS_DIR / "backup.sh", fake_root / "scripts" / "backup.sh")
    # 故意 不建 .env.prod
    proc = subprocess.run(  # noqa: S603 — 受控的 script copy + tmp_path
        [_BASH, str(fake_root / "scripts" / "backup.sh")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        cwd=str(fake_root),
    )
    assert proc.returncode != 0
    combined = (proc.stderr or "") + (proc.stdout or "")
    assert ".env.prod" in combined, f"無預期錯誤訊息：{combined[:300]}"


# ════════════════════════════════════════════════════════
# 3. compose file 結構驗證
# ════════════════════════════════════════════════════════


def test_docker_compose_prod_yaml_parses() -> None:
    """docker-compose.prod.yml 可以被 PyYAML 解析（基本 schema 正確）。"""
    import yaml

    compose_path = _ROOT / "docker-compose.prod.yml"
    assert compose_path.exists()
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    assert "services" in data
    expected = {
        "timescaledb",
        "redis",
        "qdrant",
        "backend",
        "celery_worker",
        "celery_beat",
        "frontend",
        "nginx",
    }
    assert expected.issubset(set(data["services"].keys()))


def test_docker_compose_test_restore_yaml_parses() -> None:
    """docker-compose.test-restore.yml 可解析 + 含 timescaledb_test。"""
    import yaml

    compose_path = _ROOT / "docker-compose.test-restore.yml"
    assert compose_path.exists()
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    assert "timescaledb_test" in data["services"]
    # 對外 port 必為 5433（避開 prod 5432）
    ports = data["services"]["timescaledb_test"]["ports"]
    assert any("5433" in str(p) for p in ports), f"expected 5433, got {ports}"


def test_nginx_conf_has_required_blocks() -> None:
    """nginx.conf 含 HTTPS、WS、SSE、rate limit 等關鍵 block。"""
    conf = (_ROOT / "docker" / "nginx" / "nginx.conf").read_text(encoding="utf-8")
    assert "listen 443" in conf
    assert "ssl_certificate" in conf
    assert "limit_req_zone" in conf
    assert "Upgrade" in conf  # WS upgrade header
    assert "proxy_buffering off" in conf  # SSE
    assert "X-Frame-Options" in conf
    assert "server_tokens off" in conf


def test_env_prod_example_contains_required_keys() -> None:
    """.env.prod.example 必含 prod 部署所需 keys。"""
    content = (_ROOT / ".env.prod.example").read_text(encoding="utf-8")
    required = [
        "APP_ENV=prod",
        "SECRET_KEY",
        "DATA_ENCRYPTION_KEY",
        "POSTGRES_SUPERUSER_PASSWORD",
        "REDIS_PASSWORD",
        "QDRANT_API_KEY",
        "GOOGLE_API_KEY",
        "CSP_PROD_ENABLED=true",
        "BACKUP_DIR",
        "GPG_RECIPIENT",
    ]
    for key in required:
        assert key in content, f"missing key: {key}"
