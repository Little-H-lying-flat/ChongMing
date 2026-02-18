import asyncio
import sys
import os
import traceback

# Ensure backend path is in sys.path
sys.path.append(os.getcwd())

from app.services.neural_design.service import DesignService
from app.services.neural_design.models import DesignRequest
from app.core.ai_client import init_ai_manager
from app.services.smart_ops.ai_config_provider_impl import AIConfigProviderImpl

async def debug_design():
    print("🚀 Debugging DesignService...")
    
    try:
        import nest_asyncio
        nest_asyncio.apply()
        
        # Initialize dependencies
        init_ai_manager(AIConfigProviderImpl())
        service = DesignService()
        
        req = DesignRequest(
            project_id="debug_proj",
            requirement_text="Test login page",
            target_type="API"
        )
        
        print("Calling analyze_requirement...")
        scenarios = await service.analyze_requirement(req)
        print(f"✅ Success! Generated {len(scenarios)} scenarios.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(debug_design())
