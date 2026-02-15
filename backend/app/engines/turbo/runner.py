import subprocess
import os
import signal
import logging
from typing import Optional, Dict, Any, List
from app.schemas.turbo import TurboRunConfig, TurboMode
from app.engines.turbo.compiler import LocustCompiler

logger = logging.getLogger(__name__)

class LocustRunner:
    """
    Locust 运行器
    管理 Locust 进程 (Local/Master/Worker)
    """
    
    def __init__(self, work_dir: str = "turbo_workspace"):
        self.work_dir = os.path.abspath(work_dir)
        os.makedirs(self.work_dir, exist_ok=True)
        self.compiler = LocustCompiler()
        self.process: Optional[subprocess.Popen] = None
        self.current_test_id: Optional[str] = None
        
    def start(self, config: TurboRunConfig) -> str:
        """
        启动压测
        """
        if self.process and self.process.poll() is None:
            raise RuntimeError("Locust is already running. Stop it first.")
            
        self.current_test_id = config.test_id
        
        # 1. Compile Script
        script_path = os.path.join(self.work_dir, f"locustfile_{config.test_id}.py")
        self.compiler.compile(config, output_path=script_path)
        
        # 2. Prepare Command
        cmd = [
            "locust",
            "-f", script_path,
            "--host", config.target_host,
        ]
        
        if config.mode == TurboMode.LOCAL:
            cmd.extend(["--headless", "-u", str(config.users), "-r", str(config.spawn_rate), "-t", config.run_time])
        elif config.mode == TurboMode.DISTRIBUTED:
            # Master node
            cmd.extend(["--master", "--expect-workers", str(config.worker_count)])
            cmd.extend(["--headless", "-u", str(config.users), "-r", str(config.spawn_rate), "-t", config.run_time])
            
            # TODO: Spawn workers? Or assume external workers?
            # For MVP/Day 1, we might want to spawn workers as sub-processes too if on same machine
            # But "Distributed" usually implies multiple machines.
            # We will implement a helper to spawn local workers for testing distributed mode.
            pass
            
        # CSV Output for stats
        csv_prefix = os.path.join(self.work_dir, f"stats_{config.test_id}")
        cmd.extend(["--csv", csv_prefix])
        
        logger.info(f"Starting Locust: {' '.join(cmd)}")
        
        # 3. Launch Process
        # We use a new session to ensure we can kill the process group
        if os.name == 'posix':
            self.process = subprocess.Popen(cmd, cwd=self.work_dir, preexec_fn=os.setsid)
        else:
            self.process = subprocess.Popen(cmd, cwd=self.work_dir, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            
        return config.test_id
        
    def stop(self):
        """
        停止压测
        """
        if self.process:
            logger.info("Stopping Locust...")
            if os.name == 'posix':
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            else:
                self.process.send_signal(signal.CTRL_BREAK_EVENT) # Windows specific
                
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                
            self.process = None
            logger.info("Locust stopped.")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取实时压测数据 (解析 CSV)
        """
        if not self.process or not self.current_test_id:
            return {}
            
        csv_path = os.path.join(self.work_dir, f"stats_{self.current_test_id}_stats.csv")
        if not os.path.exists(csv_path):
            return {}
            
        try:
            # Read last line of CSV efficiently
            import csv
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    return rows[-1] # Return latest aggregate input
        except Exception as e:
            logger.error(f"Failed to read stats: {e}")
            
        return {}
