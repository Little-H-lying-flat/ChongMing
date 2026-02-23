import asyncio
from app.core.ai_client import get_ai_manager, Message
from app.core.ai_models import AIModule

async def main():
    manager = get_ai_manager()
    messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Hello, tell me a short joke.")
    ]
    try:
        resp = await manager.invoke(AIModule.DEFECT_ROOT_CAUSE, messages)
        print("Success!", resp.content)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
