import schedule
import time
import requests
import json
import smtplib
from tortoise import Tortoise, fields, models, run_async
current_BTC = 3 # текущее количество биткойнов у пользователя
key_json = {'binance':{}, 'bybit':{}, 'gateio':{}, 'kucoin':{}}

class Course(models.Model):
    id = fields.IntField(primary_key=True)
    title = fields.CharField(max_length=256)
    price = fields.FloatField()
    max_price = fields.FloatField()
    min_price = fields.FloatField()
    date = fields.DatetimeField(auto_now_add=True)
    difference = fields.FloatField()
    total_amount = fields.FloatField()

def reverse_course(x):
    return round(1/float(x) , 5)

def get_data(link):    # если актуальных данных по изменениям курса нет - запрашиваем у серевера последние 
    y = link.find('.') # имеющиеся и пишем, что изменений не происходило
    who = link.find('.', y+1)
    who = link[y+1:who] 
    x = requests.get(link).json()
    match who:
        case 'bybit':
            x = x['result']['list']
        case 'kucoin':
            x = x['data']
    if (x == []):
        nlink = link[0:link.rfind('&')]
        x = requests.get(nlink).json()
        match who:
            case 'binance':
                x = x[0]
                x[1] = x[4]
            case 'bybit':
                x = x['result']['list'][0]
                x[1] = x[4]
            case 'gateio':
                x = x[0]
                x[5] = x[2]
            case 'kucoin':
                x = x['data'][0]
                x[1] = x[2]
        return x
    else:
        x = x[0]
        return x

def count_diff(open, close): # Функция, обрбатывающая данные, полученные через API
    x1 = round(float(close)-float(open), 8) 
    x2 = round(x1/(float(open)/100), 2) 
    return [x1, x2, float(close)] 
    # 0 - разница между старой ценой и новой
    # 1 - рост/падение в процентах
    # 2 - актуальная цена валюты

async def record_courses(x):
    for c in x:
        for c2 in x[c]:
            name = c + ' (' + c2 + ')' 
            y = await Course.filter(title = name).order_by('-date').first()
            if (y == None): 
                mx = mn = x[c][c2][2]
            else:
                if (x[c][c2][2] > y.max_price): mx = x[c][c2][2]
                else: mx = y.max_price
                if (x[c][c2][2] < y.min_price): mn = x[c][c2][2]
                else: mn = y.min_price
            
            rec = await Course.create(
                title = name,
                price = x[c][c2][2],
                max_price = mx,
                min_price = mn,
                difference = x[c][c2][0],
                total_amount = x[c][c2][2] * current_BTC
            )
            await rec.save()
            global key_json
            key_json[c][c2] = { # я не понял что именно должно храниться в 'coins', поэтому не стал включать эту графу сюда
                'title': name,
                'kash': {
                    'price': x[c][c2][2],
                    'minmax': {
                        'max_price': mx,
                        'min_price': mn,
                    },
                    'difference': x[c][c2][0],
                    'total_amount': x[c][c2][2] * current_BTC
                },
                'date': rec.date.timestamp()
            }
    
def job(): 
    alldata = {'binance':{}, 'bybit':{}, 'gateio':{}, 'kucoin':{}}
    global key_json
    key_json = {'binance':{}, 'bybit':{}, 'gateio':{}, 'kucoin':{}}
    ctime = int(time.time()-61 ) # Фиксируем таймштамп, чтобы гарантировать что все запросы будут сделаны по одинаковому отрезку времени

    alldata['binance']['USDT'] = get_data(f'https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=1&startTime={ctime*1000}')
    alldata['binance']['ETH'] = get_data(f'https://api.binance.com/api/v3/klines?symbol=WBTCETH&interval=1m&limit=1&startTime={ctime*1000}')
    alldata['binance']['RUB'] = get_data(f'https://api.binance.com/api/v3/klines?symbol=BTCRUB&interval=1m&limit=1&startTime={ctime*1000}')
    alldata['binance']['DOGE'] = get_data(f'https://api.binance.com/api/v3/klines?symbol=DOGEBTC&interval=1m&limit=1&startTime={ctime*1000}')
    alldata['bybit']['USDT'] = get_data(f'https://api.bybit.com/v5/market/kline?symbol=BTCUSDT&interval=60&limit=1&start={ctime*1000}')
    alldata['gateio']['USDT'] = get_data(f'https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair=BTC_USDT&limit=1&interval=1m&from={ctime}')
    alldata['gateio']['ETH'] = get_data(f'https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair=ETH_BTC&limit=1&interval=1m&from={ctime}')
    alldata['gateio']['XMR'] = get_data(f'https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair=XMR_BTC&limit=1&interval=1m&from={ctime}')
    alldata['gateio']['DOGE'] = get_data(f'https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair=DOGE_BTC&limit=1&interval=1m&from={ctime}')
    alldata['kucoin']['USDT'] = get_data(f'https://api.kucoin.com/api/v1/market/candles?symbol=BTC-USDT&type=1min&start={ctime}')
    alldata['kucoin']['ETH'] = get_data(f'https://api.kucoin.com/api/v1/market/candles?symbol=ETH-BTC&type=1min&from={ctime}')
    alldata['kucoin']['XMR'] = get_data(f'https://api.kucoin.com/api/v1/market/candles?symbol=XMR-BTC&type=1min&from={ctime}')
    alldata['kucoin']['DOGE'] = get_data(f'https://api.kucoin.com/api/v1/market/candles?symbol=DOGE-BTC&type=1min&from={ctime}')

    # некоторые курсы даны не как BTC-X, а как X-BTC, исправляем
    alldata['binance']['DOGE'][1] = reverse_course(alldata['binance']['DOGE'][1])
    alldata['binance']['DOGE'][4] = reverse_course(alldata['binance']['DOGE'][4])
    alldata['gateio']['DOGE'][5] = reverse_course(alldata['gateio']['DOGE'][5])
    alldata['gateio']['DOGE'][2] = reverse_course(alldata['gateio']['DOGE'][2])
    alldata['kucoin']['DOGE'][1] = reverse_course(alldata['kucoin']['DOGE'][1])
    alldata['kucoin']['DOGE'][2] = reverse_course(alldata['kucoin']['DOGE'][2])
    alldata['gateio']['ETH'][5] = reverse_course(alldata['gateio']['ETH'][5])
    alldata['gateio']['ETH'][2] = reverse_course(alldata['gateio']['ETH'][2])
    alldata['gateio']['XMR'][5] = reverse_course(alldata['gateio']['XMR'][5])
    alldata['gateio']['XMR'][2] = reverse_course(alldata['gateio']['XMR'][2])
    alldata['kucoin']['ETH'][1] = reverse_course(alldata['kucoin']['ETH'][1])
    alldata['kucoin']['ETH'][2] = reverse_course(alldata['kucoin']['ETH'][2])
    alldata['kucoin']['XMR'][1] = reverse_course(alldata['kucoin']['XMR'][1])
    alldata['kucoin']['XMR'][2] = reverse_course(alldata['kucoin']['XMR'][2])

    alldata['binance']['USDT'] = count_diff(alldata['binance']['USDT'][1], alldata['binance']['USDT'][4]) 
    alldata['binance']['ETH'] = count_diff(alldata['binance']['ETH'][1], alldata['binance']['ETH'][4])
    alldata['binance']['RUB'] = count_diff(alldata['binance']['RUB'][1], alldata['binance']['RUB'][4])
    alldata['binance']['DOGE'] = count_diff(alldata['binance']['DOGE'][1], alldata['binance']['DOGE'][4])
    alldata['bybit']['USDT'] = count_diff(alldata['bybit']['USDT'][1], alldata['bybit']['USDT'][4])
    alldata['gateio']['USDT'] = count_diff(alldata['gateio']['USDT'][5], alldata['gateio']['USDT'][2])
    alldata['gateio']['ETH'] = count_diff(alldata['gateio']['ETH'][5], alldata['gateio']['ETH'][2])
    alldata['gateio']['XMR'] = count_diff(alldata['gateio']['XMR'][5], alldata['gateio']['XMR'][2])
    alldata['gateio']['DOGE'] = count_diff(alldata['gateio']['DOGE'][5], alldata['gateio']['DOGE'][2])
    alldata['kucoin']['USDT'] = count_diff(alldata['kucoin']['USDT'][1], alldata['kucoin']['USDT'][2])
    alldata['kucoin']['ETH'] = count_diff(alldata['kucoin']['ETH'][1], alldata['kucoin']['ETH'][2])
    alldata['kucoin']['XMR'] = count_diff(alldata['kucoin']['XMR'][1], alldata['kucoin']['XMR'][2])
    alldata['kucoin']['DOGE'] = count_diff(alldata['kucoin']['DOGE'][1], alldata['kucoin']['DOGE'][2])

    run_async(record_courses(alldata)) # записываем все курсы в базу данных и генерируем json
    key_json = json.dumps(key_json)
    print(key_json)

    print(f'''----------------{ctime}----------------
    --------Binance--------
    USDT | {alldata['binance']['USDT'][0]} | {alldata['binance']['USDT'][1]}%
    ETH | {alldata['binance']['ETH'][0]} | {alldata['binance']['ETH'][1]}%
    RUB | {alldata['binance']['RUB'][0]} | {alldata['binance']['RUB'][1]}%
    DOGE | {alldata['binance']['DOGE'][0]} | {alldata['binance']['DOGE'][1]}%
    --------ByBit--------
    USDT | {alldata['bybit']['USDT'][0]} | {alldata['bybit']['USDT'][1]}%
    --------Gate.io--------
    USDT | {alldata['gateio']['USDT'][0]} | {alldata['gateio']['USDT'][1]}%
    ETH | {alldata['gateio']['ETH'][0]} | {alldata['gateio']['ETH'][1]}%
    XMR | {alldata['gateio']['XMR'][0]} | {alldata['gateio']['XMR'][1]}%
    DOGE | {alldata['gateio']['DOGE'][0]} | {alldata['gateio']['DOGE'][1]}%
    --------Kucoin--------
    USDT | {alldata['kucoin']['USDT'][0]} | {alldata['kucoin']['USDT'][1]}%
    ETH | {alldata['kucoin']['ETH'][0]} | {alldata['kucoin']['ETH'][1]}%
    XMR | {alldata['kucoin']['XMR'][0]} | {alldata['kucoin']['XMR'][1]}%
    DOGE | {alldata['kucoin']['DOGE'][0]} | {alldata['kucoin']['DOGE'][1]}%
    ''')

async def createdb():
    await Tortoise.init(
        db_url="sqlite://db.sqlite3",
        modules={'models': ['__main__']},
    )
    await Tortoise.generate_schemas()

if __name__ == "__main__":
    run_async(createdb())
    job()
    schedule.every(1).minutes.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)
    