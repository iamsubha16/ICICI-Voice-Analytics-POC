import os
import uvicorn
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

if __name__ == "__main__":
    # Retrieve port from application config, falling back to environment or default
    try:
        from app.config import Config
        port = getattr(Config, "PORT", 8000)
    except ImportError:
        port = int(os.getenv("PORT", 8000))

    # Retrieve host and reload settings with sensible defaults
    host = os.getenv("HOST", "127.0.0.1")
    reload = os.getenv("RELOAD", "True").lower() in ("true", "1", "t", "y", "yes")

    print("=================================================")
    print("      Voice Analytics AI — Startup Script        ")
    print("=================================================")
    print(f"  Host:   {host}")
    print(f"  Port:   {port}")
    print(f"  Reload: {reload}")
    print("=================================================")
    
    # Run the uvicorn server targeting the FastAPI app
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)
