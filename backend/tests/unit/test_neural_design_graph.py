import pytest
import asyncio
from typing import Dict, Any

from app.services.neural_design.graph import build_neural_design_graph, GraphState

@pytest.fixture
def test_graph():
    return build_neural_design_graph()

# Mock functions to override the actual LLM calls during test
async def mock_node_scenarist(state: GraphState) -> Dict[str, Any]:
    # Simulate generating scenarios that are deliberately missing required fields
    return {
        "scenarios": [
            {
                "name": "[AutoGen] Test Login",
                "description": "User logs in",
                # Missing 'url' to trigger critic failure
                "steps": [{"action": "type", "target": "#user"}]
            }
        ],
        "extracted_points": ["Login"],
        "revision_count": state.get("revision_count", 0)
    }

async def mock_node_critic(state: GraphState) -> Dict[str, Any]:
    # Simulate a strict critic analyzing the scenarios
    scenarios = state.get("scenarios", [])
    if not scenarios:
        return {"feedback": "empty", "revision_count": state.get("revision_count", 0) + 1}
        
    for s in scenarios:
        for step in s.get("steps", []):
            if "url" not in step:
                print("Critic: Rejected. Missing URL in steps.")
                return {"feedback": "Missing 'url' property in steps", "revision_count": state.get("revision_count", 0) + 1}
                
    print("Critic: Approved.")
    return {"feedback": ""} # Approved

async def mock_node_editor(state: GraphState) -> Dict[str, Any]:
    # Simulate the editor fixing the issue
    print(f"Editor: Received feedback -> {state.get('feedback')}")
    scenarios = state.get("scenarios", [])
    for s in scenarios:
        for step in s.get("steps", []):
            if "url" not in step:
                step["url"] = "http://localhost:3000/login"
                
    return {"scenarios": scenarios, "editor_output": "fixed json string"}

@pytest.mark.asyncio
async def test_generate_review_modify_loop(test_graph, monkeypatch):
    """
    Test the flow: Router -> Scenarist -> Critic (Reject) -> Editor -> Critic (Approve) -> END
    """
    # Patch the graph nodes with our mocks
    # Note: langgraph compile returns a CompiledGraph, we can't easily monkeypatch its internal nodes 
    # if it's already compiled, but we can patch the underlying functions before compiling for a clean test.
    
    import app.services.neural_design.graph as nd_graph
    monkeypatch.setattr(nd_graph, "node_scenarist", mock_node_scenarist)
    monkeypatch.setattr(nd_graph, "node_critic", mock_node_critic)
    monkeypatch.setattr(nd_graph, "node_editor", mock_node_editor)
    
    # Recompile with mocked nodes
    mocked_graph = nd_graph.build_neural_design_graph()
    
    initial_state = {
        "requirement_text": "Need login test",
        "target_type": "UI",
        "revision_count": 0
    }
    
    # We can invoke the graph and trace the execution path
    events = []
    async for event in mocked_graph.astream(initial_state):
        for node_name, state_update in event.items():
            print(f"--- Node Executed: {node_name} ---")
            events.append(node_name)
            
    # Expected Flow:
    # 1. router (determines it's PRD)
    # 2. prd_extractor (which we didn't mock, but it runs fast)
    # 3. scenarist (mocked, outputs bad scenario)
    # 4. critic (mocked, rejects it)
    # 5. editor (mocked, fixes it)
    # 6. critic (mocked, approves it)
    # END
    
    # The actual order might vary depending on how astream yields, 
    # but we should definitely see 'scenarist', 'critic', 'editor', 'critic' in sequence
    
    assert "router" in events
    assert "scenarist" in events
    
    # Critic should run exactly twice
    critic_count = events.count("critic")
    assert critic_count == 2
    
    # Editor should run exactly once
    editor_count = events.count("editor")
    assert editor_count == 1
    
    # Scenarist should run ONLY ONCE (verifying the bug fix)
    scenarist_count = events.count("scenarist")
    assert scenarist_count == 1
