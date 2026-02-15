
import pytest
import os
import shutil
from unittest.mock import MagicMock, patch

from app.schemas.turbo import TurboRunConfig, TurboMode
from app.schemas.api_ir import APIIR
from app.engines.turbo.compiler import LocustCompiler
from app.engines.turbo.runner import LocustRunner

@pytest.fixture
def turbo_config():
    return TurboRunConfig(
        test_id="test_001",
        target_host="https://httpbin.org",
        users=10,
        spawn_rate=2.0,
        run_time="30s",
        mode=TurboMode.LOCAL,
        api_ir_chain=[
            APIIR(method="GET", url="/get", weight=3),
            APIIR(method="POST", url="/post", body={"foo": "bar"}, weight=1)
        ]
    )

def test_compiler_generates_file(turbo_config, tmp_path):
    # Setup
    compiler = LocustCompiler()
    output_path = tmp_path / "locustfile_test.py"
    
    # Act
    generated_path = compiler.compile(turbo_config, output_path=str(output_path))
    
    # Assert
    assert os.path.exists(generated_path)
    with open(generated_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "class TurboUser(HttpUser):" in content
        assert 'host = "https://httpbin.org"' in content
        assert '@task(3)' in content
        assert 'method="GET"' in content
        assert 'url = "/get"' in content
        assert '@task(1)' in content
        assert 'method="POST"' in content

@patch("subprocess.Popen")
def test_runner_starts_process(mock_popen, turbo_config, tmp_path):
    # Setup
    runner = LocustRunner(work_dir=str(tmp_path))
    
    # Act
    test_id = runner.start(turbo_config)
    
    # Assert
    assert test_id == "test_001"
    assert runner.process is not None
    mock_popen.assert_called_once()
    
    # Verify command args
    args, kwargs = mock_popen.call_args
    cmd = args[0]
    assert cmd[0] == "locust"
    assert "--host" in cmd
    assert "https://httpbin.org" in cmd
    assert "--headless" in cmd
    assert "--csv" in cmd
    
    # Cleanup
    runner.stop()
