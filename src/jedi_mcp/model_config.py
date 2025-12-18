"""Model configuration and factory for switching between AI providers."""

import os
from typing import Literal
from strands.models.gemini import GeminiModel
from strands.models import BedrockModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ModelProvider = Literal["gemini", "bedrock"]


def get_model_provider() -> ModelProvider:
    """
    Get the configured model provider from environment variables.
    
    Returns:
        Model provider name (gemini or bedrock)
        
    Environment Variables:
        JEDI_MODEL_PROVIDER: Model provider to use (gemini or bedrock, default: gemini)
    """
    provider = os.environ.get("JEDI_MODEL_PROVIDER", "gemini").lower()
    if provider not in ["gemini", "bedrock"]:
        raise ValueError(f"Invalid model provider: {provider}. Must be 'gemini' or 'bedrock'")
    return provider


def create_navigation_model():
    """
    Create a model instance for navigation extraction.
    
    Uses environment variables to determine which provider and model to use.
    
    Environment Variables:
        JEDI_MODEL_PROVIDER: Provider to use (gemini or bedrock, default: gemini)
        JEDI_NAVIGATION_MODEL: Model ID to use (provider-specific)
        GOOGLE_API_KEY: Required for Gemini
        AWS credentials: Required for Bedrock (via boto3)
    
    Returns:
        Configured model instance
    """
    provider = get_model_provider()
    
    if provider == "gemini":
        model_id = os.environ.get("JEDI_NAVIGATION_MODEL", "gemini-2.0-flash-exp")
        return GeminiModel(
            client_args={
                "api_key": os.environ.get("GOOGLE_API_KEY"),
            },
            model_id=model_id,
            params={
                "temperature": 0.1,
                "max_output_tokens": 8192,
                "top_p": 0.95,
            }
        )
    else:  # bedrock
        model_id = os.environ.get("JEDI_NAVIGATION_MODEL", "qwen.qwen3-coder-30b-a3b-v1:0")
        return BedrockModel(
            model_id=model_id,
            temperature=0.1,
            max_output_tokens=8192,
            top_p=0.95,
        )


def create_content_processing_model():
    """
    Create a model instance for content processing and grouping.
    
    Uses environment variables to determine which provider and model to use.
    
    Environment Variables:
        JEDI_MODEL_PROVIDER: Provider to use (gemini or bedrock, default: gemini)
        JEDI_CONTENT_MODEL: Model ID to use (provider-specific)
        GOOGLE_API_KEY: Required for Gemini
        AWS credentials: Required for Bedrock (via boto3)
    
    Returns:
        Configured model instance
    """
    provider = get_model_provider()
    
    if provider == "gemini":
        model_id = os.environ.get("JEDI_CONTENT_MODEL", "gemini-2.0-flash-exp")
        return GeminiModel(
            client_args={
                "api_key": os.environ.get("GOOGLE_API_KEY"),
            },
            model_id=model_id,
            params={
                "temperature": 0.3,
                "max_output_tokens": 32768,
                "top_p": 0.9,
            }
        )
    else:  # bedrock
        model_id = os.environ.get("JEDI_CONTENT_MODEL", "qwen.qwen3-coder-30b-a3b-v1:0")
        return BedrockModel(
            model_id=model_id,
            temperature=0.3,
            max_output_tokens=32768,
            top_p=0.9,
        )
