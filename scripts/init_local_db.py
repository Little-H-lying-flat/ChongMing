
import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

from app.core.database import init_db

if __name__ == "__main__":
    print("Initializing Database...")
    asyncio.run(init_db())
    print("Database Initialized!")
