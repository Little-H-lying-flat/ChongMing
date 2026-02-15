
import pytest
import os
import csv
from unittest.mock import MagicMock, patch

from app.engines.turbo.synthesizer import DataSynthesizer, GeneratedDataBatch
from app.schemas.api_ir import APIIR

@pytest.fixture
def mock_llm_chain():
    with patch("app.engines.turbo.synthesizer.ChatOpenAI") as MockChat:
        mock_instance = MockChat.return_value
        # Mock invoking the chain
        # The chain is prompt | llm | parser.
        # We need to mock the chain execution or the components.
        # Since we use LCEL, it is easier to mock the `invoke` method of the constructed chain.
        # However, constructing the chain happens inside the method.
        # So we can mock `ChatOpenAI` to return a mock that produces expected output when invoked.
        yield mock_instance

def test_synthesizer_generates_csv(tmp_path):
    # Setup
    synthesizer = DataSynthesizer(work_dir=str(tmp_path))
    
    # Mock the chain invocation
    mock_batch = GeneratedDataBatch(items=[
        {"user_id": "u1", "email": "test1@example.com"},
        {"user_id": "u2", "email": "test2@example.com"}
    ])
    
    # We need to patch the invoke method of the chain.
    # A simplified way is to subclass or patch the _generate_batch method directly
    # to avoid complex LangChain internals mocking.
    with patch.object(synthesizer, '_generate_batch', return_value=mock_batch.items) as mock_gen:
        api_ir_chain = [
            APIIR(method="POST", url="/users", body={"id": "${user_id}", "email": "${email}"})
        ]
        
        # Act
        csv_path = synthesizer.synthesize(api_ir_chain, count=2)
        
        # Assert
        assert os.path.exists(csv_path)
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert rows[0]['user_id'] == 'u1'
            assert rows[0]['email'] == 'test1@example.com'
            
        # Verify schema extraction
        # The _generate_batch should be called 
        mock_gen.assert_called()
        args = mock_gen.call_args
        schema = args[0][0] # First arg is schema_summary
        assert "user_id" in schema['fields']
        assert "email" in schema['fields']
