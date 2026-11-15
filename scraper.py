import argparse
import json
import re
import time
from urllib.parse import urljoin

import requests
import schedule
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def get_book_data(
    book_url: str, session: requests.Session | None = None
) -> dict:
    """Получить данные о книге со страницы Books to Scrape.

    Args:
        book_url (str): Полный URL страницы книги.
        session (requests.Session | None): Общая HTTP-сессия или None
            для отдельного запроса.

    Returns:
        dict: Название (title, str), цена в фунтах (price, float),
            рейтинг от 1 до 5 (rating, int), остаток (stock, int),
            описание (description, str) и все характеристики
            Product Information (product_info, dict).
    """
    client = session if session is not None else requests
    response = client.get(book_url, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")
    main = soup.select_one(".product_main")
    if main is None:
        raise ValueError(f"Не найдены данные книги: {book_url}")

    title = main.find("h1").get_text(strip=True)
    price_text = main.select_one(".price_color").get_text(strip=True)
    price = float(price_text.replace("£", ""))

    rating_map = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
    rating_classes = main.select_one(".star-rating")["class"]
    rating = next(
        rating_map[name]
        for name in rating_classes
        if name in rating_map
    )

    availability = main.select_one(".availability").get_text(
        " ", strip=True
    )
    stock_match = re.search(r"\d+", availability)
    stock = int(stock_match.group()) if stock_match else 0

    description_tag = soup.select_one("#product_description + p")
    description = (
        description_tag.get_text(" ", strip=True)
        if description_tag is not None
        else ""
    )

    product_info = {}
    for row in soup.select("table.table-striped tr"):
        key = row.find("th").get_text(strip=True)
        value = row.find("td").get_text(" ", strip=True)
        product_info[key] = value

    return {
        "title": title,
        "price": price,
        "rating": rating,
        "stock": stock,
        "description": description,
        "product_info": product_info,
    }


def scrape_books(is_save: bool = False) -> list[dict]:
    """Собрать данные обо всех книгах каталога Books to Scrape.

    Args:
        is_save (bool): Если True, сохранить результат в books_data.txt
            в текущей рабочей папке. По умолчанию False.

    Returns:
        list[dict]: Список словарей с данными всех книг каталога.
    """
    books = []
    page_url = "https://books.toscrape.com/catalogue/page-1.html"
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )

    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=retries))
        while True:
            response = session.get(page_url, timeout=30)
            response.raise_for_status()
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")
            book_links = soup.select("article.product_pod h3 a")

            if not book_links:
                raise ValueError(f"Нет ссылок на книги: {page_url}")

            for link in book_links:
                book_url = urljoin(response.url, link["href"])
                books.append(get_book_data(book_url, session=session))
                time.sleep(0.2)

            print(f"Собрано книг: {len(books)}", flush=True)
            next_page = soup.select_one("li.next a")
            if next_page is None:
                break
            page_url = urljoin(response.url, next_page["href"])

    if is_save:
        with open("books_data.txt", "w", encoding="utf-8") as file:
            json.dump(books, file, ensure_ascii=False, indent=4)

    return books


def run_schedule(run_time: str = "19:00", once: bool = False) -> None:
    """Запускать сбор с сохранением файла ежедневно в указанное время.

    Args:
        run_time (str): Локальное время запуска в формате ЧЧ:ММ.
        once (bool): Если True, завершиться после первой выгрузки.
            Используется для проверки расписания в ноутбуке.

    Returns:
        None: Результаты сохраняются в books_data.txt.
    """
    scheduler = schedule.Scheduler()
    job = scheduler.every().day.at(run_time).do(
        scrape_books, is_save=True
    )
    print(f"Следующий запуск: {job.next_run}", flush=True)

    try:
        while True:
            scheduler.run_pending()
            if once and job.last_run is not None:
                print("Выгрузка по расписанию завершена.", flush=True)
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("Планировщик остановлен.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Сбор данных о книгах")
    parser.add_argument("--schedule", action="store_true")
    args = parser.parse_args()
    if args.schedule:
        run_schedule()
    else:
        scrape_books(is_save=True)
