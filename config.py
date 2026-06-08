# config.py
import os
from dotenv import load_dotenv

# Load from .env file (for local development)
load_dotenv()

def get_zapier_token():
    """Get Zapier token from environment"""
    token = os.getenv("ZAPIER_TOKEN")
    if not token:
        raise ValueError("ZAPIER_TOKEN not set. Copy .env.example to .env and add your token")
    return token

def get_github_token():
    """Get GitHub token from environment"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN not set. Copy .env.example to .env and add your token")
    return token