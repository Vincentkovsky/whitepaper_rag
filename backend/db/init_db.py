"""
Database initialization script.
Run this to create the database and tables.
"""
import asyncio
import os
from pathlib import Path

import asyncpg


async def init_database():
    """Initialize the PostgreSQL database"""
    # Parse DATABASE_URL
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/prism")
    
    # Convert SQLAlchemy URL to asyncpg URL
    if DATABASE_URL.startswith("postgresql+asyncpg://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    # Parse connection details
    # Format: postgresql://user:password@host:port/database
    parts = DATABASE_URL.replace("postgresql://", "").split("@")
    user_pass = parts[0].split(":")
    host_port_db = parts[1].split("/")
    host_port = host_port_db[0].split(":")
    
    user = user_pass[0]
    password = user_pass[1] if len(user_pass) > 1 else ""
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 5432
    database = host_port_db[1] if len(host_port_db)> 1 else "prism"
    
    print(f"Connecting to PostgreSQL at {host}:{port}")
    
    # Connect to postgres database to create our database
    conn = await asyncpg.connect(
        user=user,
        password=password,
        host=host,
        port=port,
        database="postgres",
    )
    
    try:
        # Check if database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            database
        )
        
        if not exists:
            print(f"Creating database: {database}")
            await conn.execute(f'CREATE DATABASE "{database}"')
        else:
            print(f"Database {database} already exists")
    finally:
        await conn.close()
    
    # Connect to our database and run schema
    conn = await asyncpg.connect(
        user=user,
        password=password,
        host=host,
        port=port,
        database=database,
    )
    
    try:
        # Read and execute schema
        schema_path = Path(__file__).parent / "schema.sql"
        print(f"Executing schema from: {schema_path}")
        
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        
        await conn.execute(schema_sql)
        print("Database schema created successfully!")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(init_database())
