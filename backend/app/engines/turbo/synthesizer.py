import json
import csv
import os
import uuid
import logging
from typing import List, Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.api_ir import APIIR

logger = logging.getLogger(__name__)

class GeneratedDataBatch(BaseModel):
    items: List[Dict[str, Any]] = Field(description="List of generated data items")

class DataSynthesizer:
    """
    Intelligent Data Synthesizer using LLM (Qwen)
    """
    
    def __init__(self, work_dir: str = "turbo_data"):
        self.work_dir = os.path.abspath(work_dir)
        os.makedirs(self.work_dir, exist_ok=True)
        
        self.llm = ChatOpenAI(
            model=settings.MODEL_GENERAL_LONG, # Use qwen-long for large context
            api_key=settings.QWEN_API_KEY,
            base_url=settings.QWEN_BASE_URL,
            temperature=0.7
        )
        
        self.parser = PydanticOutputParser(pydantic_object=GeneratedDataBatch)
        
    def synthesize(self, api_ir_chain: List[APIIR], count: int = 100) -> str:
        """
        Synthesize test data based on API-IR Schema.
        Returns the path to the generated CSV file.
        """
        # 1. Analyze Schema from API-IR
        schema_summary = self._extract_schema_summary(api_ir_chain)
        
        # 2. Generate Data via LLM
        # For simplicity in this phase, we generate in one go or small batches.
        # Ideally, we should loop for large counts.
        batch_size = min(count, 50) # Limit batch size for reliability
        total_items = []
        
        logger.info(f"Synthesizing {count} rows of data based on schema: {schema_summary['fields']}")
        
        generated_count = 0
        while generated_count < count:
            current_batch_size = min(batch_size, count - generated_count)
            try:
                items = self._generate_batch(schema_summary, current_batch_size)
                total_items.extend(items)
                generated_count += len(items)
                logger.info(f"Generated {generated_count}/{count} items...")
            except Exception as e:
                logger.error(f"Generation failed for batch: {e}")
                break
                
        # 3. Save to CSV
        if not total_items:
            raise RuntimeError("No data generated")
            
        filename = f"data_{uuid.uuid4().hex[:8]}.csv"
        filepath = os.path.join(self.work_dir, filename)
        
        self._save_to_csv(total_items, filepath)
        return filepath

    def _extract_schema_summary(self, api_ir_chain: List[APIIR]) -> Dict[str, Any]:
        """
        Extract variable requirements from API-IR chain.
        We look for ${var} placeholders in URL, params, and body.
        """
        variables = set()
        
        for ir in api_ir_chain:
            # Check variable in URL
            # Simple regex for ${var}
            import re
            vars_in_url = re.findall(r'\$\{(\w+)\}', ir.url)
            variables.update(vars_in_url)
            
            # Check variables in Body (if dict)
            if isinstance(ir.body, dict):
                # Simple recursive search could be better, here we flat string search
                body_str = json.dumps(ir.body)
                vars_in_body = re.findall(r'\$\{(\w+)\}', body_str)
                variables.update(vars_in_body)
                
        # TODO: infer types from Usage context if possible. 
        # For now, we list field names.
        return {
            "fields": list(variables)
        }

    def _generate_batch(self, schema: Dict, count: int) -> List[Dict[str, Any]]:
        """Generate a single batch of data"""
        
        prompt = PromptTemplate(
            template="""You are a Test Data Generator. 
Generate {count} items of test data (JSON format) for the following fields:
{fields}

Requirements:
1. Ensure data is realistic and varied.
2. Follow standard formats (e.g. UUID for ids, Email for emails).
3. Output MUST be a valid JSON object with a single key 'items' containing the list.
{format_instructions}
""",
            input_variables=["count", "fields"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        chain = prompt | self.llm | self.parser
        
        result = chain.invoke({
            "count": count, 
            "fields": ", ".join(schema["fields"])
        })
        
        return result.items

    def _save_to_csv(self, items: List[Dict], filepath: str):
        if not items:
            return
            
        keys = items[0].keys()
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(items)
        logger.info(f"Saved generated data to {filepath}")

    def generate_value(self, field_name: str, context: str = "") -> str:
        """
        Generate a single value for a specific field (Data Healing).
        """
        try:
            # Simple prompt for single value
            prompt = f"Generate a valid, realistic value for the field '{field_name}'. {context} Return ONLY the value, no quotes or explanation."
            
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            logger.error(f"Data Generation failed: {e}")
            return "test_value" # Fallback
