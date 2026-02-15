import pytest
import os
import subprocess
from unittest.mock import MagicMock, patch
from app.engines.turbo.engine import TurboEngine
from app.schemas.api_ir import APIIR
from app.schemas.turbo import TurboRunConfig, TurboMode, TurboTestStats

# --- Mock Data ---
SAMPLE_IR_CHAIN = [
    APIIR(method="POST", url="http://test.com/login", body={"u": "${user}"}),
    APIIR(method="GET", url="http://test.com/me", headers={"Auth": "${token}"})
]

@pytest.fixture
def mock_turbo_deps(tmp_path):
    """
    Setup mocks and sandbox environment.
    """
    # 1. Sandbox Engine
    engine = TurboEngine()
    # Point work dirs to tmp_path
    engine.synthesizer.work_dir = str(tmp_path / "data")
    engine.runner.work_dir = str(tmp_path / "runner")
    # Ensure dirs exist (Runner/Synthesizer init usually does this, but we changed the path after init)
    os.makedirs(engine.synthesizer.work_dir, exist_ok=True)
    os.makedirs(engine.runner.work_dir, exist_ok=True)
    
    # 2. Mock Synthesizer LLM (Bypass LangChain)
    # Patch _generate_batch to return fixed data
    with patch.object(engine.synthesizer, "_generate_batch") as mock_gen_batch:
        mock_gen_batch.return_value = [{"user": "u1", "token": "t1"}, {"user": "u2", "token": "t2"}]
        
        # 3. Mock Subprocess (Runner)
        # We patch subprocess.Popen in the runner module
        with patch("app.engines.turbo.runner.subprocess.Popen") as mock_popen:
            yield {
                "engine": engine,
                "mock_gen_batch": mock_gen_batch,
                "mock_popen": mock_popen,
                "tmp_path": tmp_path
            }

def test_flow5_happy_path_compilation_and_execution(mock_turbo_deps):
    """
    Flow 5 Scenario A: Happy Path
    1. Synthesize Data -> CSV created
    2. Compile Script -> locustfile.py created
    3. Start Runner -> subprocess.Popen called
    """
    deps = mock_turbo_deps
    engine = deps["engine"]
    mock_popen = deps["mock_popen"]
    tmp_path = deps["tmp_path"]
    
    # Setup Config
    config = TurboRunConfig(
        test_id="TEST_HAPPY",
        target_host="http://test.com",
        mode=TurboMode.LOCAL,
        users=10,
        spawn_rate=2,
        run_time="1m",
        api_ir_chain=SAMPLE_IR_CHAIN,
        data_count=5 # Request synthesis
    )
    
    # Setup Mock Process
    mock_process = MagicMock()
    mock_process.poll.return_value = None # Running
    mock_popen.return_value = mock_process
    
    # --- Execute ---
    test_id = asyncio_run_wrapper(engine.run_test(config))
    
    # Create Dummy CSV for Stats (Mocking Locust Output)
    # Locust --csv outputs: _stats.csv
    stats_csv = os.path.join(tmp_path, "runner", f"stats_{test_id}_stats.csv")
    with open(stats_csv, "w", encoding="utf-8") as f:
        f.write('Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,Minimum Response Time,Maximum Response Time,Average Content Size,Requests/s,Failures/s,50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%\n')
        f.write('GET,/,100,0,10,12,5,20,500,10.0,0.0,10,11,12,13,15,18,19,20,20,20,20\n')

    # --- Assertions ---
    
    # 1. Data Synthesis Verification
    # Check if CSV exists in synthesizer work dir
    data_dir = os.path.join(tmp_path, "data")
    files = os.listdir(data_dir)
    csv_files = [f for f in files if f.endswith(".csv")]
    assert len(csv_files) > 0, "Data CSV should be generated"
    
    # 2. Compilation Verification
    # Check if locustfile exists in runner work dir
    runner_dir = os.path.join(tmp_path, "runner")
    locust_file = os.path.join(runner_dir, f"locustfile_{test_id}.py")
    assert os.path.exists(locust_file), "Locustfile should be generated"
    
    # Check content of locustfile
    with open(locust_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert "class TurboUser(HttpUser):" in content
        assert "http://test.com/login" in content
        # Check if data file path is injected
        # The template uses implicit path or we pass it
        # Since we use sandbox, we want to confirm the path in python file is correct-ish
        # or at least the compilation didn't crash.
        
    # 3. Runner Verification
    assert mock_popen.called
    cmd_args = mock_popen.call_args[0][0]
    assert cmd_args[0] == "locust"
    assert "-f" in cmd_args
    assert locust_file in cmd_args
    
    # 4. Stats Check
    stats = engine.get_stats(test_id)
    assert stats is not None
    assert stats.state == "running"

def test_flow5_error_path_process_crash(mock_turbo_deps):
    """
    Flow 5 Scenario B: Error Path (Process Crash)
    Runner starts, but process exits with error code 1 immediately.
    Engine should detect this (via get_stats or similar logic).
    """
    deps = mock_turbo_deps
    engine = deps["engine"]
    mock_popen = deps["mock_popen"]
    
    # Setup Config
    config = TurboRunConfig(
        test_id="TEST_CRASH",
        target_host="http://test.com",
        api_ir_chain=SAMPLE_IR_CHAIN,
        data_count=0 
    )
    
    # Setup Mock Process that crashes
    mock_process = MagicMock()
    mock_process.poll.return_value = 1 # Crashed/Exited with Error
    mock_process.returncode = 1
    mock_popen.return_value = mock_process
    
    # Start Test
    test_id = asyncio_run_wrapper(engine.run_test(config))
    
    # Check Stats/State
    # Current implementation might return "running" if it only checks self.process
    # We want to verify if it handles the crash.
    stats = engine.get_stats(test_id)
    
    # Assertion: The state should reflect failure or stopped
    # If this fails, we need to fix engine.py
    assert stats.state in ["failed", "stopped", "error"], f"State was {stats.state}, expected failed/stopped"
    
# Helper for async running in sync tests
def asyncio_run_wrapper(coro):
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
