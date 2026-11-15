import json
from unittest.mock import Mock

import pytest

import scraper

BASE_URL = "https://books.toscrape.com/catalogue/"

BOOK_HTML = """
<div class="product_main">
    <h1>Test Book</h1>
    <p class="price_color">£10.50</p>
    <p class="star-rating Three"></p>
    <p class="availability">In stock (7 available)</p>
</div>
<div id="product_description"></div>
<p>Test description.</p>
<table class="table table-striped">
    <tr><th>UPC</th><td>book-1</td></tr>
    <tr><th>Product Type</th><td>Books</td></tr>
</table>
"""

PAGE_ONE_HTML = """
<article class="product_pod">
    <h3><a href="book-1/index.html">Test Book</a></h3>
</article>
<li class="next"><a href="page-2.html">next</a></li>
"""

PAGE_TWO_HTML = """
<article class="product_pod">
    <h3><a href="book-2/index.html">Second Book</a></h3>
</article>
"""


@pytest.fixture(autouse=True)
def fake_site(monkeypatch, tmp_path):
    """Подготовить тестовые страницы и временную рабочую папку."""
    second_book_html = BOOK_HTML.replace("Test Book", "Second Book").replace(
        "book-1", "book-2"
    )

    pages = {
        BASE_URL + "page-1.html": PAGE_ONE_HTML,
        BASE_URL + "page-2.html": PAGE_TWO_HTML,
        BASE_URL + "book-1/index.html": BOOK_HTML,
        BASE_URL + "book-2/index.html": second_book_html,
    }

    def fake_get(url, timeout=None):
        """Вернуть подготовленную HTML-страницу по её адресу."""
        response = Mock(text=pages[url], url=url)
        response.raise_for_status.return_value = None
        return response

    def fake_session_get(self, url, timeout=None):
        """Вернуть тестовую страницу при использовании HTTP-сессии."""
        return fake_get(url, timeout=timeout)

    monkeypatch.setattr(scraper.requests, "get", fake_get)
    monkeypatch.setattr(scraper.requests.Session, "get", fake_session_get)
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)
    monkeypatch.chdir(tmp_path)


def test_get_book_data():
    """Проверить структуру и значения данных одной книги."""
    book = scraper.get_book_data(BASE_URL + "book-1/index.html")

    assert isinstance(book, dict)
    assert book == {
        "title": "Test Book",
        "price": 10.5,
        "rating": 3,
        "stock": 7,
        "description": "Test description.",
        "product_info": {
            "UPC": "book-1",
            "Product Type": "Books",
        },
    }


def test_scrape_books_without_saving(tmp_path):
    """Проверить обход двух страниц и отсутствие записи файла."""
    books = scraper.scrape_books(is_save=False)

    assert isinstance(books, list)
    assert len(books) == 2
    assert [book["title"] for book in books] == [
        "Test Book",
        "Second Book",
    ]
    assert not (tmp_path / "books_data.txt").exists()


def test_scrape_books_with_saving(tmp_path):
    """Проверить сохранение собранных данных в файл."""
    books = scraper.scrape_books(is_save=True)

    file_path = tmp_path / "books_data.txt"
    assert file_path.is_file()

    with file_path.open(encoding="utf-8") as file:
        saved_books = json.load(file)

    assert len(saved_books) == 2
    assert saved_books == books
