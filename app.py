from flask import Flask, render_template
import requests

app = Flask(__name__)

# دریافت قیمت از نوبیتکس
def get_nobitex_price():
    url = 'https://api.nobitex.ir/v3/orderbook/USDTIRT'
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        last_trade_price = data['lastTradePrice']
        if last_trade_price:
            # حذف آخرین رقم و فرمت گذاری
            formatted_price = f"{int(str(last_trade_price)[:-1]):,}"
            return formatted_price
    return None

# دریافت قیمت از بیت پین
def get_bitpin_price():
    url = 'https://api.bitpin.ir/api/v1/mth/orderbook/USDT_IRT/'
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        try:
            last_ask_price = int(data['asks'][0][0])
            return f"{last_ask_price:,}"
        except (KeyError, IndexError, ValueError):
            return None
    return None

# دریافت قیمت از رمزینکس
def get_ramzinex_price():
    url = 'https://publicapi.ramzinex.com/exchange/api/v1.0/exchange/orderbooks/11/market_buy_price'
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        price = data['data']
        if price:
            # حذف آخرین رقم و فرمت گذاری
            formatted_price = f"{int(str(price)[:-1]):,}"
            return formatted_price
    return None

@app.route('/')
def home():
    nobitex_price = get_nobitex_price()
    bitpin_price = get_bitpin_price()
    ramzinex_price = get_ramzinex_price()
    return render_template('index.html', nobitex_price=nobitex_price, bitpin_price=bitpin_price, ramzinex_price=ramzinex_price)

if __name__ == '__main__':
    app.run(debug=True)
