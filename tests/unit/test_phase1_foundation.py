"""Smoke tests for Phase 1 service skeleton health contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICES = [
    ("detection-engine", 8001),
    ("recommendation-engine", 8002),
    ("jira-integration", 8003),
    ("mcp-layer", 8004),
    ("memory-service", 8005),
    ("predictive-analytics", 8006),
]


def test_service_skeletons_exist() -> None:
    for name, _port in SERVICES:
        service_dir = ROOT / "src" / name
        assert (service_dir / "main.py").is_file()
        assert (service_dir / "Dockerfile").is_file()
        assert (service_dir / "requirements.txt").is_file()


def test_foundation_files_exist() -> None:
    assert (ROOT / "docker-compose.yml").is_file()
    assert (ROOT / "package.json").is_file()
    assert (ROOT / "pyproject.toml").is_file()
    assert (ROOT / ".env.example").is_file()
    assert (ROOT / ".gitignore").is_file()
    assert (ROOT / "src" / "copilot-ui" / "package.json").is_file()
    assert (ROOT / "src" / "copilot-ui" / "src" / "app" / "layout.tsx").is_file()
    assert (ROOT / "src" / "copilot-ui" / "src" / "app" / "health" / "route.ts").is_file()
