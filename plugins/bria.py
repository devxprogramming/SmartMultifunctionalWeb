import asyncio
import aiohttp
import json
from typing import Dict, List
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import base64
from fastapi import APIRouter, HTTPException
from io import BytesIO
from urllib.parse import urlparse, parse_qs

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import NEW_IMAGE_GEN_API_KEY
from utils import LOGGER

class AsyncBriaClient:
    def __init__(self, api_token: str, base_url: str):
        self.api_token = api_token
        self.base_url = base_url.rstrip()  # Remove trailing spaces
        self.supported_model_versions: Dict[str, List[str]] = {
            "DEFAULT": ["3.2"],
            "HD": ["2.2"],
            "BASE": ["3.2", "2.3"],
            "FAST": ["3.1"],
        }
        if not self.api_token:
            LOGGER.error("No API token provided.")

    def _log_response(self, data: dict, filename: str) -> str:
        """
        Logs the API response to a file.
        Appends the response data to the specified log file.
        """
        try:
            with open(filename, "a") as f:
                json.dump(data, f, indent=4)
                f.write("\n")
            return "Log response file saved"
        except Exception as e:
            error_msg = f"Failed to log response: {e}"
            print(error_msg)
            return error_msg

    def auto_model_selector(self, mode: str, rms: bool = True) -> str:
        """
        Automatically selects a model version based on mode and rms settings.
        """
        if not mode:
            error_msg = "No mode set. Please set a mode."
            LOGGER.error(error_msg)
            raise ValueError(error_msg)

        if mode not in self.supported_model_versions:
            error_msg = f"Unsupported mode: {mode}"
            LOGGER.error(error_msg)
            raise ValueError(error_msg)
        
        supported_models = self.supported_model_versions[mode]
        if not rms:
            return supported_models[0]
        
        return random.choice(supported_models)

    async def request_handler(self, endpoint: str, payload: dict) -> dict:
        """
        Handles API requests to the Bria API.
        """
        if not self.api_token:
            error_msg = "No API token provided."
            LOGGER.error(error_msg)
            return {"error": error_msg}

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Content-Type": "application/json",
            "api_token": self.api_token
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    response_data = await response.json()

                    if response.status == 200:
                        return response_data
                    else:
                        return {
                            "error": f"HTTP {response.status}",
                            "message": response_data.get("message", ""),
                            "status_code": response.status
                        }
                        
        except aiohttp.ClientError as e:
            error_msg = f"Request failed: {str(e)}"
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            return {"error": error_msg}

    async def _default_mode(self, payload: dict) -> dict:
        """
        Handles DEFAULT mode image generation.
        """
        if not payload:
            raise ValueError("Payload cannot be empty")

        merged_payload = {
            "prompt": payload.get("prompt", "a book"),
            "sync": False,
            "num_results": 1,
        }
        merged_payload.update(payload)

        model_version = self.auto_model_selector("DEFAULT", rms=True)
        endpoint = f"text-to-image/base/{model_version}"
        return await self.request_handler(endpoint, merged_payload)

    async def _hd_mode(self, payload: dict) -> dict:
        """
        Handles HD mode image generation.
        """
        if not payload:
            raise ValueError("Payload cannot be empty")

        merged_payload = {
            "prompt": payload.get("prompt", "a book"),
            "sync": False,
            "num_results": 1,
            "aspect_ratio": "1:1",
            "prompt_enhancement": True
        }
        merged_payload.update(payload)
        
        model_version = self.auto_model_selector("HD", rms=True)
        endpoint = f"text-to-image/hd/{model_version}"
        return await self.request_handler(endpoint, merged_payload)

    def _extract_image_metadata(self, image_url: str) -> tuple:
        """
        Extracts clean image URL and metadata from a signed URL.
        Returns tuple of (clean_url, metadata_dict)
        """
        if not image_url:
            return image_url, {}
        
        # Parse URL parameters
        parsed_url = urlparse(image_url)
        clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        
        # Extract metadata from query parameters
        metadata = {}
        if parsed_url.query:
            query_params = parse_qs(parsed_url.query)
            # Convert lists to single values
            metadata = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}
        
        return clean_url, metadata

async def generate_image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Telegram command handler for generating images.
    """
    if not context.args:
        await update.message.reply_text("Please provide a prompt. Usage: /generate <prompt>")
        return
    
    prompt = " ".join(context.args)
    await update.message.reply_text("Generating image, please wait...")
    
    try:
        # Prepare payload
        payload = {
            "prompt": prompt,
        }

        # Generate image using HD mode
        bria_client = AsyncBriaClient(api_token=NEW_IMAGE_GEN_API_KEY, base_url="https://engine.prod.bria-api.com/v1")
        result = await bria_client._hd_mode(payload)
        
        # Handle response
        if "error" in result:
            await update.message.reply_text(f"Error: {result['error']}")
        elif "result" in result:
            # Handle multiple images response - send actual images
            for idx, image_data in enumerate(result["result"]):
                image_url = image_data["urls"][0]
                seed = image_data["seed"]
                uuid = image_data["uuid"]
                
                # Extract clean URL and metadata
                clean_url, metadata = bria_client._extract_image_metadata(image_url)
                
                print(f"Clean URL: {clean_url}")
                print(f"Metadata: {metadata}")
                
                try:
                    # Download image and send as photo
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url) as img_response:
                            if img_response.status == 200:
                                image_byte = await img_response.read()
                                image_stream = BytesIO(image_byte)
                                image_stream.seek(0)
                                await update.message.reply_photo(
                                    photo=image_stream, 
                                    caption=f"Generated Image {idx + 1}\nSeed: {seed}\nUUID: {uuid}"
                                )
                            else:
                                await update.message.reply_text(
                                    f"Failed to download image {idx + 1}\n"
                                    f"URL: {clean_url}\n"
                                    f"Seed: {seed}"
                                )
                except aiohttp.ClientError as e:
                    error_msg = f"Failed to download image: {str(e)}"
                    print(error_msg)
                    await update.message.reply_text(error_msg)
                except Exception as e:
                    error_msg = f"Error sending image: {str(e)}"
                    print(error_msg)
                    await update.message.reply_text(error_msg)
        else:
            await update.message.reply_text("Unexpected response format received.")
                
    except Exception as e:
        error_msg = f"An error occurred: {str(e)}"
        await update.message.reply_text(error_msg)
        print(f"Error in generate_image_command: {e}")

###################### App Testing ######################

async def main():
    base_url = "https://engine.prod.bria-api.com/v1"
    client = AsyncBriaClient(api_token=NEW_IMAGE_GEN_API_KEY, base_url=base_url)
    req = await client._hd_mode(
        {
            "prompt": "Realistic product photo of a basketball sneakers, surrounded by attributable objects reflecting the brand’s mood and the type of brand. Use only the two primary brand colors.  Logo should be integrated elegantly into the scene. Style: minimal, artistic, surreal. High detail.",
        }
    )
    print(req)
    return req

if __name__ == "__main__":
    asyncio.run(main())