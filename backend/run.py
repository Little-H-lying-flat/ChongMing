"""
重明 (ChongMing) — 启动脚本

修复 Windows 下 Playwright subprocess 崩溃:
  uvicorn 0.40.0 在 Windows + reload 模式下使用 SelectorEventLoop,
  该 Loop 不支持 asyncio.create_subprocess_exec (Playwright 依赖此功能).
  
  本脚本在 uvicorn 启动前 monkey-patch asyncio_loop_factory,
  确保 Windows 下始终使用 ProactorEventLoop.

使用方式:
  python run.py              (开发模式, 自动 reload)
  python run.py --no-reload  (生产模式)
"""

import sys
import os
import asyncio
import atexit
import shutil
import subprocess
import urllib.request
from pathlib import Path

import uvicorn

def start_services():
    """Start dependent services via Docker Compose"""
    print("\n[run.py] Starting infrastructure services (Postgres, Redis, etc.)...")

    # Resolve paths
    backend_dir = Path(__file__).parent
    project_root = backend_dir.parent
    compose_file = project_root / "deploy" / "docker-compose.yml"
    
    if not compose_file.exists():
        print(f"WARNING:[run.py] Docker Compose file not found at: {compose_file}")
        return

    try:
        # Check if docker-compose is installed
        subprocess.run(["docker-compose", "--version"], check=True, capture_output=True)
        
        # Start services detached
        # We ONLY start infrastructure services, not the app services (api-gateway, workers)
        # because we are running the app locally.
        infra_services = [
            "postgres", "redis", "chromadb", "milvus", "minio", "etcd"
        ]
        
        cmd = ["docker-compose", "-p", "chongming", "-f", str(compose_file), "up", "-d"] + infra_services
        
        print(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, cwd=str(project_root))
        print("[run.py] Services started successfully.\n")
        
    except FileNotFoundError:
        print("ERROR:[run.py] 'docker-compose' not found. Please install Docker Desktop.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR:[run.py] Failed to start services: {e}")
    except Exception as e:
        print(f"ERROR:[run.py] Unexpected error starting services: {e}")


def _resolve_node_bin() -> str | None:
    node_bin = os.environ.get("NODE_BIN")
    if node_bin:
        return node_bin

    node_bin = shutil.which("node")
    if node_bin:
        return node_bin

    if sys.platform == "win32":
        default_node = Path("C:/Program Files/nodejs/node.exe")
        if default_node.exists():
            return str(default_node)

    return None


def _midscene_runner_is_up() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8787/health", timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


def start_midscene_runner() -> subprocess.Popen | None:
    """Start local Midscene Runner without shell wrappers."""
    if _midscene_runner_is_up():
        print("[run.py] Midscene Runner already listening on http://127.0.0.1:8787")
        return None

    backend_dir = Path(__file__).parent
    project_root = backend_dir.parent
    server_js = project_root / "midscene-runner" / "src" / "server.js"

    if not server_js.exists():
        print(f"WARNING:[run.py] Midscene Runner entry not found at: {server_js}")
        return None

    node_bin = _resolve_node_bin()
    if not node_bin:
        print("WARNING:[run.py] Node.js not found. Set NODE_BIN or install Node.js to start Midscene Runner.")
        return None

    env = os.environ.copy()
    env.setdefault("PORT", "8787")
    env.setdefault("HOST", "127.0.0.1")
    env.setdefault("MIDSCENE_ENV_FILE", str(backend_dir / ".env"))
    env.setdefault("MIDSCENE_DRY_RUN", "1")

    print(f"[run.py] Starting Midscene Runner with Node: {node_bin}")
    try:
        process = subprocess.Popen(
            [node_bin, str(server_js), "--dry-run"],
            cwd=str(project_root),
            env=env,
        )
    except Exception as e:
        print(f"ERROR:[run.py] Failed to start Midscene Runner: {e}")
        return None

    def cleanup_midscene_runner():
        if process.poll() is None:
            print("[run.py] Stopping Midscene Runner...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    atexit.register(cleanup_midscene_runner)
    return process


def patch_windows_loop():
    """Patch uvicorn to use ProactorEventLoop on Windows"""
    if sys.platform == "win32":
        try:
            import uvicorn.loops.asyncio as _uvicorn_asyncio
            _original_factory = _uvicorn_asyncio.asyncio_loop_factory
            
            def _patched_loop_factory(use_subprocess: bool = False):
                return asyncio.ProactorEventLoop
            
            _uvicorn_asyncio.asyncio_loop_factory = _patched_loop_factory
            print("[run.py] Patched uvicorn loop factory to ProactorEventLoop")
        except Exception as e:
            print(f"WARNING:[run.py] Failed to patch uvicorn: {e}")
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def start_app_process():
    """
    Worker process entry point.
    Patches the loop and starts uvicorn WITHOUT internal reload.
    """
    patch_windows_loop()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable internal reload
        log_level="info",
    )

if __name__ == "__main__":
    start_services()
    midscene_runner_process = start_midscene_runner()

    reload_requested = "--reload" in sys.argv
    
    if sys.platform == "win32" and reload_requested:
        print("[run.py] Windows detected: Using 'watchfiles' for Proactor-compatible hot reload...")
        try:
            from watchfiles import run_process
            # Watch 'app' directory and restart 'start_app_process' on changes
            run_process("./app", target=start_app_process)
        except ImportError:
            print("ERROR:[run.py] 'watchfiles' not found. Install it (pip install watchfiles) for hot reload.")
            print("WARNING:Running without reload.")
            start_app_process()
    else:
        # Non-Windows OR No-Reload requested
        # If on Windows (no-reload), we still need to patch
        if sys.platform == "win32":
             patch_windows_loop()
             
        # Determine strict reload flag for uvicorn
        # If non-windows, we trust uvicorn's reload
        use_reload = reload_requested and sys.platform != "win32"
        
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=use_reload,
            log_level="info",
        )
