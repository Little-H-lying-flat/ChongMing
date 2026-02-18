import asyncio
import sys
import os

# Set backend path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.engines.left_pupil.api_executor import APIExecutor
from app.schemas.api_ir import APIIR

async def run_test(scenario_name: str, api_ir: APIIR, expected_success: bool, description: str = ""):
    print(f"\n--- Running Scenario: {scenario_name} ---")
    
    # --- SIMULATE DISPATCHER RUNTIME PATCH ---
    # In the real app, Dispatcher._execute_step does this.
    # Here we manually invoke the logic to verify the LLM extraction works.
    if description and api_ir.expected_status_code is None:
        print(f"🔎 Simulating Runtime Patch for description: '{description}'")
        from app.core.ai_client import get_ai_manager
        from app.core.ai_models import AIModule
        import json
        
        try:
            ai_manager = get_ai_manager()
            # Initialize if needed (it might need config)
            # In script environment, settings are loaded.
            
            prompt = f"""
            Analyze the following test step description and extract the EXPECTED HTTP Status Code and any JSON Body assertions.
            
            Description: "{description}"
            
            Output strictly valid JSON with keys: "expected_status_code" (int or null), "json_assertions" (dict).
            If no status code is mentioned, return null.
            Example: {{"expected_status_code": 500, "json_assertions": {{"error": "Internal Server Error"}}}}
            """
            
            # Use Design Module or a fast model
            response = await ai_manager.simple_chat(
                prompt=prompt,
                module=AIModule.NEURAL_SCENARIO_GENERATOR, 
                temperature=0.0
            )
            
            content = response.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            data = json.loads(content)
            print(f"🤖 AI Extraction Result: {data}")
            
            if data.get("expected_status_code"):
                api_ir.expected_status_code = data.get("expected_status_code")
            if data.get("json_assertions"):
                api_ir.json_assertions = data.get("json_assertions")
                
        except Exception as e:
            print(f"❌ Runtime Patch Simulation Failed: {e}")

    async with APIExecutor() as executor:
        result = await executor.execute(api_ir)
        
    print(f"URL: {result.response.request_url if result.response else 'N/A'}")
    print(f"Status Code: {result.response.status_code if result.response else 'N/A'}")
    print(f"Success: {result.success}")
    if not result.success:
        print(f"Failures: {result.assertions_failed}")
    
    if result.success == expected_success:
        print("✅ VERIFICATION PASSED")
    else:
        print("❌ VERIFICATION FAILED")

async def main():
    # 7. Runtime Intent Patch (Simulated LLM Call)
    ir7 = APIIR(
        method="GET",
        url="https://jsonplaceholder.typicode.com/posts/99999", # 404
        expected_status_code=None, 
        json_assertions={}
    )
    # Natural language description
    desc_str_llm = "Send request to non-existent post. Verify that the status code is 404."
    await run_test("7. Runtime Intent Patch (LLM Recovery)", ir7, expected_success=True, description=desc_str_llm)

if __name__ == "__main__":
    asyncio.run(main())
