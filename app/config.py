import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Sarvam AI ASR
    SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "mock_key_for_demo")
    
    # Azure OpenAI
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "mock_key_for_demo")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://mock-audatec.openai.azure.com/")
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5.4-nano")
    
    # Static Credentials
    LOGIN_EMAIL = os.getenv("LOGIN_EMAIL", "admin@audatec.in")
    # Default bcrypt hash for "admin123"
    LOGIN_PASSWORD_HASH = os.getenv("LOGIN_PASSWORD_HASH", "$2b$12$jlBiHRzApNBl1BZiPiQsAObTcNjr0rrxsY9zCPVn42DWL9WWmWP0e")
    
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "audatec_super_secret_session_key_123456")
    PORT = int(os.getenv("PORT", 8000))
    
    # Folders
    UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")

# Ensure upload directory exists
os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
