import pytest
import time
import asyncio
from unittest.mock import AsyncMock, patch

from app.engines.master_dispatcher.router import MasterRouter, routing_cache

@pytest.fixture
def master_router():
    router = MasterRouter()
    # Mock the AI agent for deterministic tests
    router.ai_agent.analyze = AsyncMock(return_value={"engine_type": "LEFT_PUPIL", "reasoning": "Mocked AI Decision"})
    return router

@pytest.fixture(autouse=True)
def clean_cache():
    # Setup: clear the cache before each test
    routing_cache.cache.clear()
    yield

@pytest.mark.asyncio
async def test_fast_path_api(master_router):
    """L1 - Pure Rule Test (API Fast Path)"""
    start = time.time()
    decision = await master_router.route({"step_type": "API"})
    end = time.time()
    
    assert decision == "LEFT_PUPIL"
    assert (end - start) < 0.05 # Should be extremely fast (<50ms)
    master_router.ai_agent.analyze.assert_not_called()

@pytest.mark.asyncio
async def test_fast_path_ui(master_router):
    """L1 - Pure Rule Test (UI Fast Path)"""
    start = time.time()
    decision = await master_router.route({"action": "click", "selector": "#btn-submit"})
    end = time.time()
    
    assert decision == "RIGHT_PUPIL"
    assert (end - start) < 0.05
    master_router.ai_agent.analyze.assert_not_called()

@pytest.mark.asyncio
async def test_ambiguous_routing(master_router):
    """L2 - Ambiguous Routing (LLM Slow Path)"""
    step = {"description": "Check if user is logged in"}
    
    decision = await master_router.route(step)
    
    assert decision == "LEFT_PUPIL"
    master_router.ai_agent.analyze.assert_called_once_with(step)
    
    # Assert cache is populated
    assert len(routing_cache.cache) == 1

@pytest.mark.asyncio
async def test_latency_and_caching(master_router):
    """L3 - Cache hit and latency benchmark test"""
    async def slow_ai(step):
        await asyncio.sleep(0.1) # Simulate network call
        return {"engine_type": "RIGHT_PUPIL", "reasoning": "Mocked Slow AI Decision"}
        
    master_router.ai_agent.analyze = AsyncMock(side_effect=slow_ai)
    
    step = {"description": "ambiguous step for cache test"}
    
    # First call (Cache Miss -> Slow Path L2)
    start1 = time.time()
    decision1 = await master_router.route(step)
    end1 = time.time()
    
    assert decision1 == "RIGHT_PUPIL"
    assert (end1 - start1) >= 0.1 # Should take at least 100ms
    master_router.ai_agent.analyze.assert_called_once()
    
    # Second call (Cache Hit -> Fast Path L3)
    start2 = time.time()
    decision2 = await master_router.route(step)
    end2 = time.time()
    
    assert decision2 == "RIGHT_PUPIL"
    assert (end2 - start2) < 0.05 # Should hit cache instantly
    # Confirm AI was NOT called a second time
    master_router.ai_agent.analyze.assert_called_once()
