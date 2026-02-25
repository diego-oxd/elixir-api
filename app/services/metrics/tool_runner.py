import logging
import subprocess

logger = logging.getLogger(__name__)


def run_tool(cmd: list[str], cwd: str, timeout: int = 120) -> tuple[str, str, int]:
    """Run a subprocess and return (stdout, stderr, returncode).

    Never raises — errors surface as non-zero returncode with stderr content.
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        logger.warning("[tool_runner] %s timed out after %ds", cmd[0], timeout)
        return "", f"Timed out after {timeout}s", 1
    except FileNotFoundError:
        logger.warning("[tool_runner] command not found: %s", cmd[0])
        return "", f"Command not found: {cmd[0]}", 1
    except Exception as e:
        logger.warning("[tool_runner] unexpected error running %s: %s", cmd[0], e)
        return "", str(e), 1
