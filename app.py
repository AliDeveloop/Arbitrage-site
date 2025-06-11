from flask import Flask, render_template, jsonify, request
import requests
from cachetools import TTLCache
import logging
from tabdeal.spot import Spot
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import os
from collections import defaultdict
import math
import jdatetime

app = Flask(__name__)

# --- تنظیمات جدید ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
cache = TTLCache(maxsize=100, ttl=10)
EXCHANGE_ORDER = ['nobitex', 'bitpin', 'ramzinex', 'tabdeal', 'okex', 'wallex']

# آدرس اسکریپت‌های PHP روی هاست دیگرتان
# !!! این آدرس‌ها را با آدرس واقعی هاست خود جایگزین کنید !!!
PHP_API_URL_SAVE = "https://your-php-host.com/save_log.php"
PHP_API_URL_GET = "https://your-php-host.com/get_log.php"
# !!! این کلید باید با کلیدی که در save_log.php گذاشتید یکسان باشد !!!
SECRET_KEY = "YOUR_SUPER_SECRET_KEY" 

# --- توابع اصلی (با تغییرات) ---

def log_prices_to_api(prices):
    """قیمت‌ها را از طریق API به هاست PHP ارسال می‌کند."""
    try:
        # برای جلوگیری از خطای SSL، می‌توانید verify=False را اضافه کنید، اما امن نیست
        # راه بهتر، اطمینان از معتبر بودن گواهی SSL هاست PHP است
        headers = {'Authorization': f'Bearer {SECRET_KEY}', 'Content-Type': 'application/json'}
        response = requests.post(PHP_API_URL_SAVE, json=prices, headers=headers, timeout=10)
        response.raise_for_status() # اگر خطا بود، exception ایجاد می‌کند
        logger.info("Successfully logged prices to remote API.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to log prices to remote API: {e}")

def parse_log_from_api():
    """لاگ‌ها را از هاست PHP دریافت و پردازش می‌کند."""
    try:
        response = requests.get(PHP_API_URL_GET, timeout=10)
        response.raise_for_status()
        log_content = response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch logs from remote API: {e}")
        return []

    records = []
    current_timestamp = None
    for line in log_content.splitlines():
        if line.startswith("--- Log at"):
            try:
                ts_str = line.split("--- Log at")[1].strip().split("---")[0].strip()
                current_timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except (ValueError, IndexError):
                current_timestamp = None
        elif line.startswith("Exchange:") and current_timestamp:
            try:
                parts = line.split('|')
                exchange = parts[0].split(':')[1].strip().lower()
                price_str = parts[1].split(':')[1].strip().replace(',', '')
                if price_str != 'N/A':
                    records.append({"timestamp": current_timestamp, "exchange": exchange, "price": float(price_str)})
            except (IndexError, ValueError):
                continue
    return sorted(records, key=lambda x: x['timestamp'])

# ... (توابع get_..._price و format_price بدون تغییر) ...
def format_price(price, unit='toman'):
    try:
        price = float(price)
        if unit == 'rial':
            price = price / 10
        return f"{int(price):,}" if price > 0 else None
    except (ValueError, TypeError):
        return None

def get_nobitex_price():
    try:
        url = 'https://api.nobitex.ir/v3/orderbook/USDTIRT'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('lastTradePrice')
        return format_price(price, unit='rial') if price else None
    except Exception as e: return None
def get_bitpin_price():
    try:
        url = 'https://api.bitpin.ir/api/v1/mth/orderbook/USDT_IRT/'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('asks', [[None]])[0][0]
        return format_price(price, unit='toman') if price else None
    except Exception as e: return None
def get_ramzinex_price():
    try:
        url = 'https://publicapi.ramzinex.com/exchange/api/v1.0/exchange/orderbooks/11/market_buy_price'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('data')
        return format_price(price, unit='rial') if price else None
    except Exception as e: return None
def get_tabdeal_price():
    try:
        client = Spot()
        order_book = client.depth(symbol='USDTIRT', limit=1)
        price = order_book.get('asks', [[None]])[0][0]
        return format_price(price, unit='toman') if price else None
    except Exception as e: return None
def get_okex_price():
    try:
        url = 'https://azapi.ok-ex.io/oapi/v1/market/ticker?symbol=USDT-IRT'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('ticker', {}).get('last')
        return format_price(price, unit='toman') if price else None
    except Exception as e: return None
def get_wallex_price():
    try:
        url = 'https://api.wallex.ir/v1/depth?symbol=USDTTMN'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('result', {}).get('ask', [{}])[0].get('price')
        return format_price(price, unit='toman') if price else None
    except Exception as e: return None

EXCHANGES = { 'nobitex': get_nobitex_price, 'bitpin': get_bitpin_price, 'ramzinex': get_ramzinex_price, 'tabdeal': get_tabdeal_price, 'okex': get_okex_price, 'wallex': get_wallex_price }

def fetch_all_prices():
    cached_prices = cache.get('all_prices')
    if cached_prices: return cached_prices
    prices = {}
    with ThreadPoolExecutor(max_workers=len(EXCHANGES)) as executor:
        future_to_exchange = {executor.submit(func): name for name, func in EXCHANGES.items()}
        for future in future_to_exchange:
            exchange_name = future_to_exchange[future]
            try: prices[exchange_name] = future.result()
            except Exception as e: prices[exchange_name] = None
    
    # تابع جدید برای ارسال به API جایگزین می‌شود
    log_prices_to_api(prices) 
    
    cache['all_prices'] = prices
    return prices

# --- روت‌ها و APIها ---
# این بخش‌ها از parse_log_from_api استفاده می‌کنند و نیازی به تغییر ندارند

@app.route('/')
def home():
    prices = fetch_all_prices()
    template_prices = {f"{name}_price": price for name, price in prices.items()}
    return render_template('index.html', **template_prices)

@app.route('/api/prices')
def get_prices_api():
    prices = fetch_all_prices()
    return jsonify(prices)

@app.route('/api/chart-data')
def get_chart_data():
    records = parse_log_from_api() # استفاده از تابع جدید
    if not records: return jsonify({})
    slots = defaultdict(lambda: defaultdict(list))
    all_time_labels = set()
    for rec in records:
        hour_slot = math.floor(rec['timestamp'].hour / 4) * 4
        label = rec['timestamp'].replace(hour=hour_slot, minute=0, second=0, microsecond=0)
        all_time_labels.add(label)
        slots[rec['exchange']][label].append(rec['price'])
    sorted_labels = sorted(list(all_time_labels))
    jalali_labels = [jdatetime.datetime.fromgregorian(dt=d).strftime("%Y/%m/%d - %H:%M") for d in sorted_labels]
    datasets = []
    for exchange in EXCHANGE_ORDER:
        data_points = []
        for label_dt in sorted_labels:
            if label_dt in slots[exchange]:
                avg_price = sum(slots[exchange][label_dt]) / len(slots[exchange][label_dt])
                data_points.append(round(avg_price))
            else:
                data_points.append(None)
        datasets.append({"label": exchange, "data": data_points})
    return jsonify({"labels": jalali_labels, "datasets": datasets})


@app.route('/api/historical-data')
def get_historical_data():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    records = parse_log_from_api() # استفاده از تابع جدید
    if not records: return jsonify({"data": [], "daily_stats": {}})
    daily_prices = defaultdict(lambda: {ex: None for ex in EXCHANGE_ORDER})
    daily_stats = defaultdict(lambda: {'min': float('inf'), 'max': 0})
    for rec in records:
        jalali_date = jdatetime.date.fromgregorian(date=rec['timestamp'].date())
        date_str = jalali_date.strftime("%Y/%m/%d")
        daily_prices[date_str][rec['exchange']] = rec['price']
        daily_stats[date_str]['min'] = min(daily_stats[date_str]['min'], rec['price'])
        daily_stats[date_str]['max'] = max(daily_stats[date_str]['max'], rec['price'])
    formatted_data = [{"date": date, "prices": prices} for date, prices in daily_prices.items()]
    formatted_data = sorted(formatted_data, key=lambda x: x['date'], reverse=True)
    start = (page - 1) * per_page
    end = start + per_page
    return jsonify({ "data": formatted_data[start:end], "daily_stats": daily_stats })


if __name__ == '__main__':
    app.run(debug=True)
