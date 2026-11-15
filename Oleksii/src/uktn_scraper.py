import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import random
import csv
import re

# --- НАСТРОЙКИ ---
BASE_URL = "https://www.uktech.news/news/page/{}"
START_DATE = datetime(2026, 7, 1)  # Начало периода
END_DATE = datetime(2026, 8, 31)          # Парсим до сегодняшнего дня

# Генерируем сегодняшнюю дату в формате ГГГГ-ММ-ДД
TODAY_STR = datetime.now().strftime("%Y-%m-%d")
FILE_ALL = f"uktn_all_news_{TODAY_STR}.csv"
FILE_DEALS = f"uktn_deals_{TODAY_STR}.csv"

def parse_uktn_date(date_string):
    """Умный парсер дат: переводит '20 hours ago', 'May 27, 2026' или 'wed 25 mar 2026' в объект datetime"""
    if not date_string: return None
    # Очищаем от лишних пробелов и приводим к нижнему регистру
    date_string = date_string.lower().strip()
    now = datetime.now()

    try:
        # 1. Если дата относительная (содержит 'ago')
        if 'ago' in date_string:
            numbers = re.findall(r'\d+', date_string)
            if not numbers: return now # Если цифр нет, считаем что это сегодня
            
            val = int(numbers[0])
            if 'min' in date_string:
                return now - timedelta(minutes=val)
            elif 'hour' in date_string:
                return now - timedelta(hours=val)
            elif 'day' in date_string:
                return now - timedelta(days=val)
            elif 'week' in date_string:
                return now - timedelta(weeks=val)
            elif 'month' in date_string:
                return now - timedelta(days=val*30)
                
        # 2. Если дата абсолютная (на старых новостях)
        else:
            # Список всех возможных форматов, которые могут встретиться на сайте
            formats = [
                "%a %d %b %Y",  # wed 25 mar 2026 (Тот самый проблемный формат)
                "%B %d, %Y",    # may 27, 2026 (Полный месяц)
                "%d %B %Y",     # 27 may 2026
                "%b %d, %Y",    # mar 25, 2026 (Сокращенный месяц без дня недели)
                "%d %b %Y"      # 25 mar 2026
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_string, fmt)
                except ValueError:
                    continue # Если формат не подошел, пробуем следующий
            
            # Если вообще ни один формат из списка не подошел
            print(f"[!] Неизвестный формат даты: '{date_string}'")
            return None
                
    except Exception as e:
        print(f"[!] Системная ошибка парсинга даты: {date_string} -> {e}")
        return None
        
    return now

def is_deal(title):
    """Наша проверенная бронебойная функция поиска инвестиций"""
    text = title.lower()
    keywords = [
        'raises', 'secures', 'bags', 'lands', 'closes', 'receives', 
        'funding', 'investment', 'injects', 'backs', 'extends', 'nabs', 'gets', 'scores', 'boost'
    ]
    money_markers = ['£', '$', '€', 'million', 'billion', 'm', 'bn'] # Добавили £ и сокращения (m/bn)

    has_keyword = any(word in text for word in keywords)
    has_money = any(marker in text for marker in money_markers)
    has_big_money = any(m in text for m in ['million', 'billion', 'm', 'bn']) and any(c in text for c in ['£', '$', '€'])
    
    if (has_keyword and has_money) or has_big_money or ('fund' in text and has_money):
        return True
    return False

def main():
    page_number = 1
    count_total = 0
    count_deals = 0
    keep_going = True

    print(f"--- ЗАПУСК UKTN: собираем данные с {START_DATE.date()} ---")
    scraper = cloudscraper.create_scraper() # Обходим защиту

    with open(FILE_ALL, mode='w', newline='', encoding='utf-8-sig') as f_all, \
         open(FILE_DEALS, mode='w', newline='', encoding='utf-8-sig') as f_deals:
         
        writer_all = csv.writer(f_all, delimiter=';')
        writer_deals = csv.writer(f_deals, delimiter=';')
        
        # Записываем шапки (добавили колонку 'Категория')
        header = ['Дата', 'Область', 'Заголовок', 'Посилання']
        writer_all.writerow(header)
        writer_deals.writerow(header)

        while keep_going:
            url = BASE_URL.format(page_number)
            print(f"\n>> Сканирую страницу {page_number}...")

            try:
                response = scraper.get(url)
                if response.status_code != 200:
                    print(f"Ошибка доступа: {response.status_code}. Возможно, конец архива.")
                    break

                soup = BeautifulSoup(response.text, 'html.parser')
                
                # ИЩЕМ ВСЕ КАРТОЧКИ <article> (Идеальный подход благодаря твоему рентгену!)
                articles = soup.find_all('article')
                
                if not articles:
                    print("Карточки новостей не найдены.")
                    break
                
                items_on_page = 0
                
                for article in articles:
                    # 1. Ищем Заголовок и Ссылку
                    h_tag = article.find(['h2', 'h3'])
                    if not h_tag: continue
                    a_tag = h_tag.find('a')
                    if not a_tag: continue
                    
                    full_title = a_tag.text.strip()
                    link_url = a_tag.get('href')

                    # 2. Ищем Категорию (по классу text-teal)
                    cat_tag = article.find('span', class_=lambda c: c and 'text-teal' in c)
                    category = cat_tag.text.strip() if cat_tag else "News"

                    # 3. Ищем Дату (по классу text-gray-400)
                    date_tag = article.find('span', class_=lambda c: c and 'text-gray-400' in c)
                    if not date_tag: continue
                    
                    article_date = parse_uktn_date(date_tag.text)
                    if not article_date: continue

                    # 4. Проверка периода
                    if article_date > END_DATE: continue 
                    if article_date < START_DATE:
                        print(f"--- Дошли до старой даты ({article_date.date()}). Финиш. ---")
                        keep_going = False
                        break
                    
                    # Пишем в общий файл
                    writer_all.writerow([article_date.date(), category, full_title, link_url])
                    count_total += 1
                    items_on_page += 1

                    # Проверяем, сделка ли это
                    if is_deal(full_title) or category.lower() == 'funding':
                        writer_deals.writerow([article_date.date(), category, full_title, link_url])
                        count_deals += 1
                        print(f"[DEAL] {category}: {full_title[:60]}...")

                print(f"--> Страница {page_number}: добавлено {items_on_page} новостей.")

                if not keep_going: break
                
                # Пауза, чтобы не забанили
                time.sleep(random.uniform(4.2, 8.7))
                page_number += 1

            except Exception as e:
                print(f"Ошибка внутри цикла: {e}")
                break

    print("\n" + "=" * 30)
    print(f"ГОТОВО! UK Tech News собран.")
    print(f"Всего новостей: {count_total}")
    print(f"Из них Сделок (Deals): {count_deals}")

if __name__ == "__main__":
    main()