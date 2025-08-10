# Copyright @ISmartCoder
# Updates Channel: https://t.me/TheSmartDev

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import os
import importlib
import socket
from utils import LOGGER

app = FastAPI(title="A360API")

def load_index_html():
    try:
        with open("templates/index.html", "r") as file:
            return file.read()
    except FileNotFoundError:
        LOGGER.error("index.html not found in templates directory")
        return "<h1>Welcome to AbirAPI</h1><p>Index page not found.</p>"

def get_server_address():
    hostname = socket.gethostname()
    try:
        ip_address = socket.gethostbyname(hostname)
    except socket.gaierror:
        ip_address = "localhost"
    return f"http://{ip_address}:8000"

@app.get("/", response_class=HTMLResponse)
async def root():
    return load_index_html()

def load_plugins():
    plugins_dir = "plugins"
    for filename in os.listdir(plugins_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = filename[:-3]
            try:
                module = importlib.import_module(f"plugins.{module_name}")
                if hasattr(module, "router"):
                    app.include_router(module.router)
                    LOGGER.info(f"Successfully loaded plugin: {module_name}")
                else:
                    LOGGER.warning(f"Plugin {module_name} does not have a router")
            except Exception as e:
                LOGGER.error(f"Failed to load plugin {module_name}: {str(e)}")

load_plugins()

if __name__ == "__main__":
    import uvicorn
    host = "0.0.0.0"
    port = 8000
    LOGGER.info(f"Starting server at {get_server_address()}")
    uvicorn.run(app, host=host, port=port)
