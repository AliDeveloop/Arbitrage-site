from flask import Flask, render_template, jsonify
import requests
from cachetools import TTLCache
import logging
from tabdeal.spot import Spot

app = Flask(__name__)

# تنظیم لاگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# تنظیم کش با TTL 10 ثانیه
cache = TTLCache(maxsize=100, ttl=10)

# فرمت استاندارد برای قیمت‌ها
def format_price(price, unit='toman'):
    try:
        price = float(price)
        # اگر قیمت به ریال باشه، به تومان تبدیل می‌کنیم
        if unit == 'rial':
            price = price / 10
        return f"{int(price):,}" if price > 0 else None
    except (ValueError, TypeError):
        return None

# دریافت قیمت از نوبیتکس
def get_nobitex_price():
    if "nobitex_price" in cache:
        return cache["nobitex_price"]
    
    try:
        url = 'https://api.nobitex.ir/v3/orderbook/USDTIRT'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('lastTradePrice')
        if price:
            formatted_price = format_price(price, unit='rial')  # تبدیل از ریال به تومان
            cache["nobitex_price"] = formatted_price
            return formatted_price
        logger.error("No lastTradePrice in Nobitex response")
    except Exception as e:
        logger.error(f"Nobitex API error: {str(e)}")
    return None

# دریافت قیمت از بیت پین
def get_bitpin_price():
    if "bitpin_price" in cache:
        return cache["bitpin_price"]
    
    try:
        url = 'https://api.bitpin.ir/api/v1/mth/orderbook/USDT_IRT/'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('asks', [[]])[0][0]
        if price:
            formatted_price = format_price(price, unit='toman')  # قیمت به تومان
            cache["bitpin_price"] = formatted_price
            return formatted_price
        logger.error("No valid ask price in Bitpin response")
    except Exception as e:
        logger.error(f"Bitpin API error: {str(e)}")
    return None

# دریافت قیمت از رمزینکس
def get_ramzinex_price():
    if "ramzinex_price" in cache:
        return cache["ramzinex_price"]
    
    try:
        url = 'https://publicapi.ramzinex.com/exchange/api/v1.0/exchange/orderbooks/11/market_buy_price'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('data')
        if price:
            formatted_price = format_price(price, unit='rial')  # تبدیل از ریال به تومان
            cache["ramzinex_price"] = formatted_price
            return formatted_price
        logger.error("No valid price in Ramzinex response")
    except Exception as e:
        logger.error(f"Ramzinex API error: {str(e)}")
    return None

# دریافت قیمت از تبدیل
def get_tabdeal_price():
    if "tabdeal_price" in cache:
        return cache["tabdeal_price"]
    
    try:
        client = Spot()
        order_book = client.depth(symbol='USDTIRT', limit=1)
        price = order_book.get('asks', [[]])[0][0]
        if price:
            formatted_price = format_price(price, unit='toman')  # قیمت به تومان
            cache["tabdeal_price"] = formatted_price
            return formatted_price
        logger.error("No valid ask price in Tabdeal response")
    except Exception as e:
        logger.error(f"Tabdeal API error: {str(e)}")
    return None

# دریافت قیمت از اوکی اکسچنج
def get_okex_price():
    if "okex_price" in cache:
        return cache["okex_price"]
    
    try:
        url = 'https://azapi.ok-ex.io/oapi/v1/market/ticker?symbol=USDT-IRT'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('ticker', {}).get('last')
        if price:
            formatted_price = format_price(price, unit='toman')  # قیمت به تومان
            cache["okex_price"] = formatted_price
            return formatted_price
        logger.error("No valid last price in OKEx response")
    except Exception as e:
        logger.error(f"OKEx API error: {str(e)}")
    return None

# دریافت قیمت از والکس
def get_wallex_price():
    if "wallex_price" in cache:
        return cache["wallex_price"]
    
    try:
        url = 'https://api.wallex.ir/v1/depth?symbol=USDTTMN'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('result', {}).get('ask', [{}])[0].get('price')
        if price:
            formatted_price = format_price(price, unit='toman')  # قیمت به تومان
            cache["wallex_price"] = formatted_price
            return formatted_price
        logger.error("No valid ask price in Wallex response")
    except Exception as e:
        logger.error(f"Wallex API error: {str(e)}")
    return None

@app.route('/')
def home():
    prices = {
        'nobitex_price': get_nobitex_price(),
        'bitpin_price': get_bitpin_price(),
        'ramzinex_price': get_ramzinex_price(),
        'tabdeal_price': get_tabdeal_price(),
        'okex_price': get_okex_price(),
        'wallex_price': get_wallex_price()
    }
    return render_template('index.html', **prices)

@app.route('/api/prices')
def get_prices():
    prices = {
        'nobitex': get_nobitex_price(),
        'bitpin': get_bitpin_price(),
        'ramzinex': get_ramzinex_price(),
        'tabdeal': get_tabdeal_price(),
        'okex': get_okex_price(),
        'wallex': get_wallex_price()
    }
    return jsonify(prices)

if __name__ == '__main__':
    app.run(debug=True)