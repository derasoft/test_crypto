from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
from tortoise import Tortoise, fields, models, run_async
browser = ''
all_goods = ['копьё', 'дуршлаг', 'красные носки', 'леска для спиннинга']

class Goods(models.Model):
    id = fields.IntField(primary_key=True)
    shop_name = fields.CharField(max_length=256)
    keyword = fields.CharField(max_length=256)
    link = fields.CharField(max_length=1000)
    price = fields.FloatField()
    date = fields.DatetimeField(auto_now_add=True)

async def record(x):
    rec = await Goods.create(
        shop_name = x[0],
        keyword = x[1],
        link = x[2],
        price = x[3]
    )
    await rec.save()

def wb_collector(query):
    def link_cutter(text):
        x = text.find('href=')
        y = text.find('"', x+6)
        return text[x+6:y]

    def price_cutter(text):
        if 'red-price' in text: x = text.find('red-price')
        elif 'wallet-price' in text: x = text.find('wallet-price') 
        elif 'price__lower-price' in text: x = text.find('price__lower-price') 
        x = text.find('>', x)
        y = text.find('&', x)
        return text[x+1:y]
    
    global browser
    page = browser.new_page()
    page.goto(f'https://www.wildberries.ru/catalog/0/search.aspx?page=1&sort=priceup&search={query}')
    # time.sleep(2)
    card = page.locator('.product-card__wrapper').nth(0).inner_html()
    page.screenshot(path=f'./screenshots/demo(wb_{query}).png')
    page.close()
    return ['Wildberies', query, link_cutter(card), price_cutter(card)]

def ozon_collector(query): 
    def link_cutter(text):
        x = text.find('href=')
        y = text.find('?', x+6)
        return 'https://www.ozon.ru' + text[x+6:y]

    def price_cutter(text):
        x = text.find('c3015-a1')
        x = text.find('>', x)
        y = text.find(' ', x)
        return text[x+1:y]

    def anti_bot(page):
        page.locator('.rb').click(timeout=10)

    global browser
    page = browser.new_page()
    page.goto(f'https://www.ozon.ru/search/?from_global=true&sorting=price&text={query}')
    # time.sleep(3)
    try:  
        b = page.locator('.rb')
        b.click()
    except PlaywrightTimeoutError:
        print('timeout')
    finally:
        card = page.locator('.qj0_23').nth(0).inner_html()
        page.screenshot(path=f'./screenshots/demo(ozon_{query}).png')
        page.close()
        return ['Ozon', query, link_cutter(card), price_cutter(card)]

def yandex_collector(query): 
    def link_cutter(text):
        x = text.find('href=')
        y = text.find('?', x+6)
        return 'https://market.yandex.ru/' + text[x+6:y]

    def price_cutter(text):
        x = text.find('ds-text_color_price-term')
        x = text.find('>', x)
        y = text.find('<', x)
        return text[x+1:y]

    global browser
    page = browser.new_page()
    page.goto(f'https://market.yandex.ru/search?how=aprice&text={query}')
    # time.sleep(3)
    card = page.locator('._1H-VK').nth(0).inner_html()
    page.screenshot(path=f'./screenshots/demo(yandex_{query}).png')
    page.close()
    return ['Yandex Market', query, link_cutter(card), price_cutter(card)]

async def createdb():
    await Tortoise.init(
        db_url="sqlite://db.sqlite3",
        modules={'models': ['__main__']},
    )
    await Tortoise.generate_schemas()

if __name__ == "__main__":
    run_async(createdb())
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # пришлось оставить отображение окон браузера - если их скрыть,
        time.sleep(3)                               # сервис видит подвох и включает защиту от ботов
        goodlist = []
        for c in all_goods:                         # ищем товары и собираем данные о них
            print(f'Ищем {c} на Wildberies')
            goodlist.append(wb_collector(c))
            print(f'Ищем {c} на Ozon')
            goodlist.append(ozon_collector(c))
            print(f'Ищем {c} на Яндекс Маркете')
            goodlist.append(yandex_collector(c))
    for c in goodlist:                             # записываем их в БД
        run_async(record(c))