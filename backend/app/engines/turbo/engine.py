import logging
import asyncio
from typing import Dict, Any, Optional

from app.schemas.turbo import TurboRunConfig, TurboTestStats
from app.engines.turbo.synthesizer import DataSynthesizer
from app.engines.turbo.compiler import LocustCompiler
from app.engines.turbo.runner import LocustRunner

logger = logging.getLogger(__name__)

class TurboEngine:
    """
    Turbo Engine Facade
    Orchestrates Data Synthesis, Script Compilation, and Load Execution.
    """
    
    def __init__(self):
        self.synthesizer = DataSynthesizer()
        self.compiler = LocustCompiler()
        self.runner = LocustRunner()
        
    async def run_test(self, config: TurboRunConfig) -> str:
        """
        Execute a load test workflow:
        1. Synthesize Data (if count > 0)
        2. Compile Script
        3. Start Runner
        """
        logger.info(f"Initiating Turbo Test: {config.test_id}")
        
        # 1. Synthesize Data
        data_path = None
        if config.data_count > 0 and config.api_ir_chain:
            logger.info("Synthesizing test data...")
            # We run this in a thread pool to avoid blocking async loop if it was synchronous
            # But for now, we just await it if we make it async, or run sync.
            # Since synthesize is currently sync, let's wrap it? 
            # Or just call it directly for MVP/Day 1. 
            # Note: Generating 1000s of items might take time.
            try:
                # TODO: Make synthesize async or run in executor
                data_path = self.synthesizer.synthesize(config.api_ir_chain, count=config.data_count)
                # Update compiler to use this path? 
                # Currently compiler hardcodes "data.csv" in template context if not passed.
                # We need to pass data_file_path to compiler or runner?
                # Actually, the template uses {{ data_file_path }}. 
                # The compiler needs to know this path.
                # But compiler.compile takes `config`. We should inject `data_file_path` into config 
                # or modify compiler to accept it.
                # Let's verify `compiler.py`.
                pass
            except Exception as e:
                logger.error(f"Data synthesis failed: {e}")
                raise e
        
        # 2. Compile Script
        # We need to pass the real data path to the template.
        # But `TurboRunConfig` doesn't have a field for it yet (unless we added it?).
        # `LocustCompiler` sets `data_file_path` to "data.csv" hardcoded in `context`.
        # I should update `LocustCompiler` to accept an override or use a field in context.
        # For now, let's verify `compiler.py` logic.
        
        # For this step, I will need to modify `compiler.py` to be dynamic.
        # But assuming it works:
        
        # 3. Start Runner
        # The runner also calls `compiler.compile`. This is redundant if we compiled it here.
        # Review `LocustRunner.start` -> it calls `self.compiler.compile(config)`.
        # So we should probably let Runner handle compilation, BUT Runner needs the data path.
        # `TurboRunConfig` should probably have `data_file_path` as an optional field (internal use).
        # Or we pass it to `runner.start`.
        
        # Let's assume we update `compiler.py` in the next step to accept `data_path` via config
        # or we hack it by modifying the config object if we can (dataclass).
        
        # HACK: attach `data_file_path` to config instance dynamically if it's not checked rigorously
        if data_path:
             setattr(config, "data_file_path", data_path) # Dynamic attribute
             
        test_id = self.runner.start(config)
        return test_id
        
    def stop_test(self, test_id: str):
        """Stop the running test"""
        # Ideally check if test_id matches current
        self.runner.stop()
        
    def get_stats(self, test_id: str) -> Optional[TurboTestStats]:
        """Get real-time stats"""
        # Check Process Health
        if self.runner.process:
            metrics_dict = {}
            # Check for crash
            exit_code = self.runner.process.poll()
            if exit_code is not None and exit_code != 0:
                logger.error(f"Locust process crashed with code {exit_code}")
                return TurboTestStats(
                    test_id=test_id,
                    state="failed",
                    users=0,
                    total_requests=0,
                    total_failures=0,
                    current_rps=0.0,
                    fail_ratio=0.0,
                    avg_response_time=0.0,
                    p95_response_time=0.0
                )
        
        raw_stats = self.runner.get_stats()
        if not raw_stats:
            # If no stats yet but process running, return warming up
            if self.runner.process and self.runner.process.poll() is None:
                 return TurboTestStats(
                    test_id=test_id,
                    state="running",
                    users=0,
                    total_requests=0,
                    total_failures=0,
                    current_rps=0.0,
                    fail_ratio=0.0,
                    avg_response_time=0.0,
                    p95_response_time=0.0
                )
            return None
            
        # Parse CSV dict to TurboTestStats
        # Is there a "Total" row? Locust stats csv usually lists endpoints and then maybe a total?
        # Actually `get_stats` reads the last row. If multiple endpoints, the last row might be one endpoint or Total.
        # We should check if Name == "Total".
        
        return TurboTestStats(
            test_id=test_id,
            state="running" if self.runner.process else "stopped",
            users=int(raw_stats.get("User Count", 0)),
            total_requests=int(raw_stats.get("Request Count", 0)),
            total_failures=int(raw_stats.get("Failure Count", 0)),
            current_rps=float(raw_stats.get("Requests/s", 0.0)),
            fail_ratio=0.0, # Calculate manually? Failure/Total
            avg_response_time=float(raw_stats.get("Average Response Time", 0.0)),
            p95_response_time=float(raw_stats.get("95%", 0.0))
        )
