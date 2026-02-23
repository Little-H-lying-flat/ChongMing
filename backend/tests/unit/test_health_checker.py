"""
健康检查单元测试

测试 HealthChecker 的 URL 检查和环境健康状态功能
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.environment_manager import HealthChecker, CheckResult, HealthReport


class TestHealthChecker:
    """测试健康检查功能"""

    @pytest.fixture
    def checker(self):
        """创建 HealthChecker 实例"""
        return HealthChecker(timeout=5.0)

    @pytest.fixture
    def mock_env(self):
        """模拟环境对象"""
        env = MagicMock()
        env.id = "env-test123"
        env.name = "测试环境"
        env.base_url = "https://example.com"
        return env

    @pytest.mark.asyncio
    async def test_check_url_success(self, checker):
        """测试成功的 URL 检查"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            mock_context = AsyncMock()
            mock_context.get = AsyncMock(return_value=mock_response)
            mock_context.__aenter__ = AsyncMock(return_value=mock_context)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_context

            result = await checker._check_url(mock_context, "https://example.com")

            assert result.status == "healthy"
            assert result.latency_ms is not None
            assert result.error is None

    @pytest.mark.asyncio
    async def test_check_url_unhealthy(self, checker):
        """测试失败的 URL 检查（HTTP 错误）"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            
            mock_context = AsyncMock()
            mock_context.get = AsyncMock(return_value=mock_response)
            mock_context.__aenter__ = AsyncMock(return_value=mock_context)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_context

            result = await checker._check_url(mock_context, "https://example.com")

            assert result.status == "unhealthy"
            assert "HTTP 500" in result.error

    @pytest.mark.asyncio
    async def test_check_url_timeout(self, checker):
        """测试超时的 URL 检查"""
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_context.__aenter__ = AsyncMock(return_value=mock_context)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_context

            result = await checker._check_url(mock_context, "https://example.com")

            assert result.status == "unhealthy"
            assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_check_url_connection_error(self, checker):
        """测试连接失败的 URL 检查"""
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_context.__aenter__ = AsyncMock(return_value=mock_context)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_context

            result = await checker._check_url(mock_context, "https://example.com")

            assert result.status == "unhealthy"
            assert "Connection" in result.error

    def test_calculate_overall_status_all_healthy(self, checker):
        """测试全部健康的总体状态"""
        details = {
            "base_url": {"status": "healthy"},
            "health_endpoint": {"status": "healthy"},
        }
        status = checker._calculate_overall_status(details)
        assert status == "healthy"

    def test_calculate_overall_status_some_unhealthy(self, checker):
        """测试部分不健康的总体状态"""
        details = {
            "base_url": {"status": "healthy"},
            "health_endpoint": {"status": "unhealthy"},
        }
        status = checker._calculate_overall_status(details)
        assert status == "degraded"

    def test_calculate_overall_status_error(self, checker):
        """测试有错误的总体状态"""
        details = {
            "base_url": {"status": "error"},
        }
        status = checker._calculate_overall_status(details)
        assert status == "unhealthy"

    @pytest.mark.asyncio
    async def test_check_environment(self, checker, mock_env):
        """测试环境健康检查"""
        with patch.object(checker, "_check_url") as mock_check:
            mock_check.return_value = CheckResult(status="healthy", latency_ms=100.0)

            report = await checker.check_environment(mock_env)

            assert isinstance(report, HealthReport)
            assert report.environment == "env-test123"
            assert report.environment_name == "测试环境"
            assert report.overall_status in ["healthy", "degraded", "unhealthy", "unknown"]
            assert "base_url" in report.details

    @pytest.mark.asyncio
    async def test_quick_check_success(self, checker):
        """测试快速检查成功"""
        with patch.object(checker, "_check_url") as mock_check:
            mock_check.return_value = CheckResult(status="healthy", latency_ms=50.0)

            result = await checker.quick_check("https://example.com")

            assert result is True

    @pytest.mark.asyncio
    async def test_quick_check_failure(self, checker):
        """测试快速检查失败"""
        with patch.object(checker, "_check_url") as mock_check:
            mock_check.return_value = CheckResult(status="unhealthy", error="timeout")

            result = await checker.quick_check("https://example.com")

            assert result is False


class TestCheckResult:
    """测试 CheckResult 数据类"""

    def test_create_healthy_result(self):
        """测试创建健康结果"""
        result = CheckResult(status="healthy", latency_ms=100.5)
        assert result.status == "healthy"
        assert result.latency_ms == 100.5
        assert result.error is None

    def test_create_error_result(self):
        """测试创建错误结果"""
        result = CheckResult(status="error", error="Connection failed")
        assert result.status == "error"
        assert result.latency_ms is None
        assert result.error == "Connection failed"


class TestHealthReport:
    """测试 HealthReport 数据类"""

    def test_create_report(self):
        """测试创建健康报告"""
        report = HealthReport(
            environment="env-123",
            environment_name="Test Env",
            timestamp="2026-02-09T10:00:00Z",
            overall_status="healthy",
            details={"base_url": {"status": "healthy"}},
        )
        assert report.environment == "env-123"
        assert report.environment_name == "Test Env"
        assert report.overall_status == "healthy"
        assert "base_url" in report.details
