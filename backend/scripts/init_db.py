import asyncio
import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import init_db
# Import all models to ensure they are registered with Base.metadata
from app.models import base
from app.models import ai_config
from app.models import api_ir
from app.models import data_record
from app.models import environment
from app.models import execution
from app.models import test_case

async def main():
    print("Initializing database...")
    await init_db()
    print("Database initialized successfully.")

if __name__ == "__main__":
    asyncio.run(main())
