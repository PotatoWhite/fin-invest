"""Git-based deploy and rollback operations."""

import logging
import subprocess
from datetime import datetime

from db import Database

logger = logging.getLogger(__name__)


def get_current_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10)
        return result.stdout.strip()[:12]
    except Exception:
        return "unknown"


def deploy_from_merge(db: Database) -> bool:
    """Deploy after a PR merge: restart service + healthcheck."""
    commit = get_current_commit()
    logger.info("Deploying commit %s...", commit)

    try:
        # Docker-based deploy
        result = subprocess.run(
            ["docker", "compose", "up", "-d", "--build"],
            capture_output=True, text=True, timeout=300,
            cwd="/home/bravopotato/Spaces/finspace/invest")

        if result.returncode != 0:
            logger.error("Docker build failed: %s", result.stderr[:500])
            _record_deploy(db, commit, "failed", result.stderr[:500])
            return False

        # Healthcheck (wait 30 seconds, then check)
        import time
        time.sleep(30)

        health_result = subprocess.run(
            ["docker", "compose", "exec", "invest",
             "python", "-c", "from db import check_health; check_health()"],
            capture_output=True, text=True, timeout=30,
            cwd="/home/bravopotato/Spaces/finspace/invest")

        if health_result.returncode != 0:
            logger.error("Health check failed after deploy!")
            rollback(db, commit)
            return False

        _record_deploy(db, commit, "success", "Deployed and healthy")
        logger.info("Deploy successful: %s", commit)
        return True

    except subprocess.TimeoutExpired:
        logger.error("Deploy timed out")
        _record_deploy(db, commit, "failed", "Timeout")
        return False
    except Exception as e:
        logger.error("Deploy error: %s", e)
        _record_deploy(db, commit, "failed", str(e))
        return False


def rollback(db: Database, failed_commit: str) -> bool:
    """Rollback to previous commit."""
    logger.warning("Rolling back from %s...", failed_commit)
    try:
        subprocess.run(
            ["git", "revert", "HEAD", "--no-edit"],
            capture_output=True, text=True, timeout=30,
            cwd="/home/bravopotato/Spaces/finspace/invest")

        subprocess.run(
            ["docker", "compose", "up", "-d", "--build"],
            capture_output=True, text=True, timeout=300,
            cwd="/home/bravopotato/Spaces/finspace/invest")

        new_commit = get_current_commit()
        _record_deploy(db, new_commit, "rolled_back",
                       f"Rolled back from {failed_commit}")
        logger.info("Rollback complete: %s → %s", failed_commit, new_commit)
        return True

    except Exception as e:
        logger.error("Rollback failed: %s", e)
        _record_deploy(db, failed_commit, "rollback_failed", str(e))
        return False


def _record_deploy(db: Database, commit: str, status: str, details: str):
    db.insert("deploy_history",
              timestamp=datetime.now().isoformat(),
              commit_hash=commit,
              status=status,
              changes_summary=details)
