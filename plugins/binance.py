# Copyright @ISmartCoder
# Updates Channel: https://t.me/TheSmartDev
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import aiohttp
import requests
from utils import LOGGER

router = APIRouter(prefix="/binance")
BASE_URL_ALL = "https://api.binance.com/api/v3/ticker/24hr"
BASE_URL_SYMBOL = "https://api.binance.com/api/v3/ticker/24hr?symbol={token}USDT"
BASE_URL_PRICE = "https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

@router.get("/24h")
async def get_24h_ticker():
    try:
        response = requests.get(BASE_URL_ALL, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        return JSONResponse(
            content={
                "success": True,
                "data": data,
                "count": len(data) if isinstance(data, list) else 1,
                "api_owner": "@ISmartCoder",
                "api_updates": "t.me/TheSmartDev"
            }
        )
    except requests.exceptions.RequestException as e:
        LOGGER.error(f"Failed to fetch 24h ticker data: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Failed to fetch data: {str(e)}",
                "api_owner": "@ISmartCoder",
                "api_updates": "t.me/TheSmartDev"
            }
        )

@router.get("/price")
async def get_price(token: str = ""):
    if not token:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Missing 'token' parameter",
                "api_owner": "@ISmartCoder",
                "api_updates": "t.me/TheSmartDev"
            }
        )
    
    try:
        url = BASE_URL_SYMBOL.format(token=token.upper())
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "code" in data and "msg" in data:
            LOGGER.error(f"Invalid token {token}: {data['msg']}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": f"Invalid token: {data['msg']}",
                    "api_owner": "@ISmartCoder",
                    "api_updates": "t.me/TheSmartDev"
                }
            )
        return JSONResponse(
            content={
                "success": True,
                "data": data,
                "api_owner": "@ISmartCoder",
                "api_updates": "t.me/TheSmartDev"
            }
        )
    except requests.exceptions.RequestException as e:
        LOGGER.error(f"Failed to fetch price for token {token}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Failed to fetch data: {str(e)}",
                "api_owner": "@ISmartCoder",
                "api_updates": "t.me/TheSmartDev"
            }
        )

async def get_spot_price(symbol: str) -> float | None:
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        try:
            async with session.get(BASE_URL_PRICE.format(symbol=symbol.upper()), timeout=10) as response:
                if response.status != 200:
                    LOGGER.error(f"API request failed with status {response.status} for symbol {symbol}")
                    return None
                data = await response.json()
                return float(data.get("price")) if "price" in data else None
        except Exception as e:
            LOGGER.error(f"Failed to fetch spot price for {symbol}: {str(e)}")
            return None

@router.get("/cx")
async def convert_currency(base: str = "", target: str = "", amount: float = 1.0):
    if not base or not target:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Missing 'base' or 'target' parameter",
                "api_owner": "@ISmartCoder",
                "api_updates": "t.me/TheSmartDev"
            }
        )
    if amount <= 0:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Amount must be greater than 0",
                "api_owner": "@ISmartCoder",
                "api_updates": "t.me/TheSmartDev"
            }
        )

    try:
        direct_symbol = base.upper() + target.upper()
        inverse_symbol = target.upper() + base.upper()
        
        price = await get_spot_price(direct_symbol)
        inverted = False
        if price is None:
            price = await get_spot_price(inverse_symbol)
            if price is None:
                LOGGER.error(f"No valid trading pair found for {base} to {target}")
                return JSONResponse(
                    status_code=404,
                    content={
                        "success": False,
                        "error": "Invalid token pair: not found on Binance",
                        "api_owner": "@ISmartCoder",
                        "api_updates": "t.me/TheSmartDev"
                    }
                )
            inverted = True

        base_usdt_price = await get_spot_price(base.upper() + "USDT") or 0.0
        target_usdt_price = await get_spot_price(target.upper() + "USDT") or 0.0

        if inverted:
            converted_amount = amount / price
        else:
            converted_amount = amount * price

        total_in_usdt = amount * base_usdt_price

        data = {
            "base_coin": base.upper(),
            "target_coin": target.upper(),
            "amount": amount,
            "converted_amount": converted_amount,
            "total_in_usdt": total_in_usdt,
            "base_usdt_price": base_usdt_price,
            "target_usdt_price": target_usdt_price
        }

        return JSONResponse(
            content={
                "success": True,
                "data": data,
                "api_owner": "@ISmartCoder",
                "api_updates": "t.me/TheSmartDev"
            }
        )
    except Exception as e:
        LOGGER.error(f"Failed to convert {base} to {target}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Failed to convert: {str(e)}",
                "api_owner": "@ISmartCoder",
                "api_updates": "t.me/TheSmartDev"
            }
        )
