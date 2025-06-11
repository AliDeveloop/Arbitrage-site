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

app = Flask(__name__)

# --- تنظیمات پایه ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
cache = TTLCache(maxsize=100, ttl=10)
LOG_FILE = "price_log.txt"
EXCHANGE_ORDER = ['nobitex', 'bitpin', 'ramzinex', 'tabdeal', 'okex', 'wallex']

# --- توابع اصلی ---

def format_price(price, unit='toman'):
    try:
        price = float(price)
        if unit == 'rial':
            price = price / 10
        return f"{int(price):,}" if price > 0 else None
    except (ValueError, TypeError):
        return None

def log_prices_to_file(prices):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"--- Log at {timestamp} ---\n")
            for exchange, price in prices.items():
                price_str = price if price else "N/A"
                f.write(f"Exchange: {exchange.capitalize():<10} | Price: {price_str}\n")
            f.write("---\n\n")
    except Exception as e:
        logger.error(f"Failed to write to log file: {e}")

# ... (توابع get_..._price بدون تغییر باقی می‌مانند) ...
def get_nobitex_price():
    try:
        url = 'https://api.nobitex.ir/v3/orderbook/USDTIRT'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('lastTradePrice')
        return format_price(price, unit='rial') if price else None
    except Exception as e:
        logger.error(f"Nobitex API error: {str(e)}")
        return None

def get_bitpin_price():
    try:
        url = 'https://api.bitpin.ir/api/v1/mth/orderbook/USDT_IRT/'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('asks', [[None]])[0][0]
        return format_price(price, unit='toman') if price else None
    except Exception as e:
        logger.error(f"Bitpin API error: {str(e)}")
        return None

def get_ramzinex_price():
    try:
        url = 'https://publicapi.ramzinex.com/exchange/api/v1.0/exchange/orderbooks/11/market_buy_price'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('data')
        return format_price(price, unit='rial') if price else None
    except Exception as e:
        logger.error(f"Ramzinex API error: {str(e)}")
        return None

def get_tabdeal_price():
    try:
        client = Spot()
        order_book = client.depth(symbol='USDTIRT', limit=1)
        price = order_book.get('asks', [[None]])[0][0]
        return format_price(price, unit='toman') if price else None
    except Exception as e:
        logger.error(f"Tabdeal API error: {str(e)}")
        return None

def get_okex_price():
    try:
        url = 'https://azapi.ok-ex.io/oapi/v1/market/ticker?symbol=USDT-IRT'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('ticker', {}).get('last')
        return format_price(price, unit='toman') if price else None
    except Exception as e:
        logger.error(f"OKEx API error: {str(e)}")
        return None

def get_wallex_price():
    try:
        url = 'https://api.wallex.ir/v1/depth?symbol=USDTTMN'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        price = data.get('result', {}).get('ask', [{}])[0].get('price')
        return format_price(price, unit='toman') if price else None
    except Exception as e:
        logger.error(f"Wallex API error: {str(e)}")
        return None

EXCHANGES = {
    'nobitex': get_nobitex_price, 'bitpin': get_bitpin_price, 'ramzinex': get_ramzinex_price,
    'tabdeal': get_tabdeal_price, 'okex': get_okex_price, 'wallex': get_wallex_price
}

def fetch_all_prices():
    cached_prices = cache.get('all_prices')
    if cached_prices: return cached_prices
    prices = {}
    with ThreadPoolExecutor(max_workers=len(EXCHANGES)) as executor:
        future_to_exchange = {executor.submit(func): name for name, func in EXCHANGES.items()}
        for future in future_to_exchange:
            exchange_name = future_to_exchange[future]
            try: prices[exchange_name] = future.result()
            except Exception as e:
                logger.error(f"Error fetching price for {exchange_name}: {e}")
                prices[exchange_name] = None
    log_prices_to_file(prices)
    cache['all_prices'] = prices
    return prices

def parse_log_file():
    if not os.path.exists(LOG_FILE):
        return []
    records = []
    current_timestamp = None
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith("--- Log at"):
                try:
                    ts_str = line.split("--- Log at")[1].strip().split("---")[0].strip()
                    current_timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                except (ValueError, IndexError): current_timestamp = None
            elif line.startswith("Exchange:") and current_timestamp:
                try:
                    parts = line.split('|')
                    exchange = parts[0].split(':')[1].strip().lower()
                    price_str = parts[1].split(':')[1].strip().replace(',', '')
                    if price_str != 'N/A':
                        records.append({"timestamp": current_timestamp, "exchange": exchange, "price": float(price_str)})
                except (IndexError, ValueError): continue
    return sorted(records, key=lambda x: x['timestamp'])

@app.route('/')
def home():
    prices = fetch_all_prices()
    template_prices = {f"{name}_price": price for name, price in prices.items()}
    return render_template('index.html', **template_prices, exchange_order=EXCHANGE_ORDER)

@app.route('/api/prices')
def get_prices_api():
    prices = fetch_all_prices()
    return jsonify(prices)

@app.route('/api/chart-data')
def get_chart_data():
    records = parse_log_file()
    if not records: return jsonify({})

    # Group prices by 4-hour slots for each exchange
    slots = defaultdict(lambda: defaultdict(list))
    all_time_labels = set()
    for rec in records:
        hour_slot = math.floor(rec['timestamp'].hour / 4) * 4
        label = rec['timestamp'].strftime(f"%Y-%m-%d {hour_slot:02d}:00")
        all_time_labels.add(label)
        slots[rec['exchange']][label].append(rec['price'])

    sorted_labels = sorted(list(all_time_labels))
    
    datasets = []
    for exchange in EXCHANGE_ORDER:
        data_points = []
        for label in sorted_labels:
            if label in slots[exchange]:
                prices_in_slot = slots[exchange][label]
                avg_price = sum(prices_in_slot) / len(prices_in_slot)
                data_points.append(round(avg_price))
            else:
                data_points.append(None) # Add null for gaps in the chart
        datasets.append({"label": exchange, "data": data_points})

    return jsonify({"labels": sorted_labels, "datasets": datasets})

@app.route('/api/historical-data')
def get_historical_data():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    records = parse_log_file()
    if not records: return jsonify({"data": [], "daily_stats": {}})
    
    # Group by date and get the last price for each exchange
    daily_prices = defaultdict(lambda: {ex: None for ex in EXCHANGE_ORDER})
    daily_stats = defaultdict(lambda: {'min': float('inf'), 'max': 0})
    
    for rec in records:
        date_str = rec['timestamp'].strftime("%Y-%m-%d")
        daily_prices[date_str][rec['exchange']] = rec['price']
        
        # Update daily stats (min/max for all exchanges on that day)
        daily_stats[date_str]['min'] = min(daily_stats[date_str]['min'], rec['price'])
        daily_stats[date_str]['max'] = max(daily_stats[date_str]['max'], rec['price'])

    # Format for table and sort by date descending
    formatted_data = [{"date": date, "prices": prices} for date, prices in daily_prices.items()]
    formatted_data = sorted(formatted_data, key=lambda x: x['date'], reverse=True)
    
    # Paginate
    start = (page - 1) * per_page
    end = start + per_page
    
    return jsonify({
        "data": formatted_data[start:end],
        "daily_stats": daily_stats
    })

if __name__ == '__main__':
    app.run(debug=True)
