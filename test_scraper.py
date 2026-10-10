from pathlib import Path
from typing import Literal
from unittest.mock import Mock, patch, call

import pytest
import requests
from bs4 import BeautifulSoup
import csv

from books_to_scrape import (
    get_book_links,
    fetch_page,
    scrape_book,
    Book,
    main,
    MAX_RETRIES,
    CSV_HEADERS
)


@pytest.fixture
def mock_session():
    session = Mock()

    response = Mock()
    session.get.return_value = response

    return session, response


@pytest.fixture
def valid_book_html():
    return """
    <table class="table table-striped">
        <tr>
            <th>UPC</th>
            <td>test-upc-123</td>
        </tr>
        <tr>
            <th>Price (excl. tax)</th>
            <td>£12.99</td>
        </tr>
        <tr>
            <th>Availability</th>
            <td>In stock (7 available)</td>
        </tr>
    </table>

    <div class="col-sm-6 product_main">
        <h1>Test Book</h1>
    </div>

    <ul class="breadcrumb">
        <li>Home</li>
        <li>Books</li>
        <li>Fiction</li>
    </ul>

    <div id="product_description"></div>
    <p>This is a test book description.</p>
    """


@pytest.fixture
def valid_book_soup(valid_book_html: str):
    return BeautifulSoup(valid_book_html, "lxml")


def test_get_book_links():
    html = """
    <article class="product_pod">
        <h3>
            <a href="book1/index.html">Book One</a>
        </h3>
    </article>

    <article class="product_pod">
        <h3>
            <a href="book2/index.html">Book Two</a>
        </h3>
    </article>
    """

    soup = BeautifulSoup(html, "lxml")

    links = get_book_links(
        soup,
        "https://example.com/catalogue/page-1.html"
    )

    assert links == [
        "https://example.com/catalogue/book1/index.html",
        "https://example.com/catalogue/book2/index.html"
    ]


def test_get_book_links_malformed(caplog: pytest.LogCaptureFixture):
    html = """
    <article class="product_pod">
    <p>Book with broken HTML</p>
    </article>
    """
    soup = BeautifulSoup(html, "lxml")

    links = get_book_links(
        soup,
        "https://example.com/catalogue/page-1.html"
    )

    assert links == []
    assert "Book card has no h3; skipping." in caplog.text


def test_get_book_links_missing_link(caplog: pytest.LogCaptureFixture):
    html = """
    <article class="product_pod">
        <h3>
            <span>Book Without Link</span>
        </h3>
    </article>
    """

    soup = BeautifulSoup(html, "lxml")

    links = get_book_links(
        soup,
        "https://example.com/catalogue/page-1.html"
    )

    assert links == []
    assert "Book card has no link; skipping." in caplog.text


def test_get_book_links_missing_href(caplog: pytest.LogCaptureFixture):
    html = """
    <article class="product_pod">
        <h3>
            <a>Book Without Href</a>
        </h3>
    </article>
    """

    soup = BeautifulSoup(html, "lxml")

    links = get_book_links(
        soup,
        "https://example.com/catalogue/page-1.html"
    )

    assert links == []
    assert "Book link has no href; skipping." in caplog.text


def test_fetch_page(mock_session: tuple[Mock, Mock]):
    session, response = mock_session

    response.status_code = 200

    result = fetch_page(
        "https://example.com",
        session
    )

    session.get.assert_called_once_with(
        "https://example.com",
        timeout=10,
    )

    assert result.status_code == 200


def test_fetch_page_retry_success(mock_session: tuple[Mock, Mock]):
    session, response = mock_session

    response.status_code = 200

    session.get.side_effect = [
        requests.RequestException("Connection Failed"),    
        response
    ]

    result = fetch_page(
        "http://example.com",
        session
    )

    assert result.status_code == 200
    assert session.get.call_count == 2


def test_fetch_page_retry_failure(mock_session: tuple[Mock, Mock], caplog: pytest.LogCaptureFixture):
    session, response = mock_session

    session.get.side_effect = [
        requests.RequestException("Connection Failed"),
        requests.RequestException("Connection Failed"),
        requests.RequestException("Connection Failed")        
    ]
    with patch("books_to_scrape.time.sleep") as mock_sleep:
        result = fetch_page(
            "http://example.com",
            session
        )

    assert result is None
    assert session.get.call_count == 3
    assert "Request failed for http://example.com" in caplog.text
    assert mock_sleep.call_count == 2
    assert mock_sleep.call_args_list == [
        call(1),
        call(2)
    ]

def test_scrape_book_success(mock_session: tuple[Mock, Mock], valid_book_html: str):
    session, response = mock_session

    response.text = valid_book_html

    result = scrape_book(
        "http://example.com/test_book",
        session
    )

    expected_book = Book(
        'Test Book',
        'test-upc-123',
        'Fiction',
        12.99,
        7,
        'This is a test book description.'
    )

    assert result == expected_book


def test_scrape_book_request_failure(mock_session: tuple[Mock, Mock], caplog: pytest.LogCaptureFixture):
    session, response = mock_session

    url = "http://example.com/test_book"

    session.get.side_effect = requests.RequestException("Request Failed")
    
    with patch("books_to_scrape.time.sleep"):
        result = scrape_book(url, session)

    assert result is None
    assert f"Skipping {url} - Request failed after {MAX_RETRIES} attempts" in caplog.text


def test_scrape_book_missing_title_block(mock_session: tuple[Mock, Mock], valid_book_soup: BeautifulSoup):
    session, response = mock_session

    title_block = valid_book_soup.find(
    'div',
    class_='col-sm-6 product_main'
    )

    title_block.decompose()

    response.text = str(valid_book_soup)

    expected_book = Book(
        'No Title Available',
        'test-upc-123',
        'Fiction',
        12.99,
        7,
        'This is a test book description.'
    )

    result = scrape_book("http://example.com/test_book", session)

    assert result == expected_book


def test_scrape_book_missing_description_marker(mock_session: tuple[Mock, Mock], valid_book_soup: BeautifulSoup):
    session, response = mock_session

    description_block = valid_book_soup.find(
        'div',
        id='product_description'
    )

    description_block.decompose()

    response.text = str(valid_book_soup)

    expected_book = Book(
        'Test Book',
        'test-upc-123',
        'Fiction',
        12.99,
        7,
        'No Description Available'
    )

    result = scrape_book("http://example.com/test_book", session)

    assert result == expected_book


def test_scrape_book_missing_breadcrumb(
        mock_session: tuple[Mock, Mock], 
        valid_book_soup: BeautifulSoup,
        caplog: pytest.LogCaptureFixture
    ):
    session, response = mock_session

    breadcrumb = valid_book_soup.find(
        'ul',
        class_='breadcrumb'
    )

    breadcrumb.decompose()

    response.text = str(valid_book_soup)

    expected_book = Book(
        'Test Book',
        'test-upc-123',
        'Unknown',
        12.99,
        7,
        'This is a test book description.'
    )

    result = scrape_book("http://example.com/test_book", session)

    assert result == expected_book
    assert 'No category available: http://example.com/test_book' in caplog.text


def test_scrape_book_description_missing_next_sibling(mock_session: tuple[Mock, Mock], valid_book_soup: BeautifulSoup):
    session, response = mock_session

    description_block = valid_book_soup.find(
        'div',
        id='product_description'
    )

    description_paragraph = description_block.find_next_sibling('p')
    description_paragraph.decompose()

    response.text = str(valid_book_soup)

    expected_book = Book(
    'Test Book',
    'test-upc-123',
    'Fiction',
    12.99,
    7,
    'No Description Available'
    )

    result = scrape_book("http://example.com/test_book", session)

    assert result == expected_book


def test_scrape_book_invalid_price(mock_session: tuple[Mock, Mock], valid_book_soup: BeautifulSoup):
    session, response = mock_session

    price_cell = valid_book_soup.find(
        'th',
        string='Price (excl. tax)'
    ).find_next_sibling('td')

    price_cell.string = 'Not a price'

    response.text = str(valid_book_soup)

    with pytest.raises(ValueError):
        scrape_book("http://example.com/test_book", session)


def test_scrape_book_invalid_availability(mock_session: tuple[Mock, Mock], valid_book_soup: BeautifulSoup):
    session, response = mock_session

    availability_cell = valid_book_soup.find(
        'th',
        string='Availability'
    ).find_next_sibling('td')

    availability_cell.string = 'Out of stock'

    response.text = str(valid_book_soup)

    with pytest.raises(AttributeError):
        scrape_book("http://example.com/test_book", session)


@pytest.mark.parametrize(
    'availability, expected_count',
    [
        ('In stock (0 available)', 0),
        ('In stock (347 available)', 347)
    ]
)

def test_scrape_book_availability_edge_cases(
    mock_session: tuple[Mock, Mock],
    valid_book_soup: BeautifulSoup,
    availability: Literal['In stock (0 available)'] | Literal['In stock (347 available)'], 
    expected_count: Literal[0] | Literal[347]
):
    session, response = mock_session

    availability_cell = valid_book_soup.find(
        'th',
        string='Availability'
    ).find_next_sibling('td')

    availability_cell.string = availability

    response.text = str(valid_book_soup)

    expected_book = Book(
        'Test Book',
        'test-upc-123',
        'Fiction',
        12.99,
        expected_count,
        'This is a test book description.'
    )

    result = scrape_book("http://example.com/test_book", session)

    assert result == expected_book


def test_main_writes_books_to_csv(tmp_path: Path):
    test_book_1 = Book(
        'Test Book 1',
        'test-upc-347',
        'Fiction',
        19.99,
        21,
        'This is the testing description for book 1.'
    )

    test_book_2 = Book(
        'Test Book 2',
        'test-upc-443',
        'Travel',
        29.99,
        10,
        'This is the testing description for book 2.'
    )

    mock_response = Mock()
    mock_response.text = '<html></html>'

    output_file = tmp_path / 'test_books.csv'

    with patch('books_to_scrape.fetch_page', return_value=mock_response):
        with patch('books_to_scrape.get_book_links', return_value=[
         'http://example.com/test-book-1',
         'http://example.com/test-book-2'
        ]):
           with patch('books_to_scrape.scrape_book', side_effect=[
               test_book_1,
               test_book_2
           ]):
               main(output_file)

    assert output_file.exists() 

    with open (output_file) as csv_file:
        rows = list(csv.reader(csv_file))

    assert rows[0] == CSV_HEADERS
    assert rows[1] == list(map(str, test_book_1.to_csv_row()))
    assert rows[2] == list(map(str, test_book_2.to_csv_row()))


def test_main_fetch_page_fail(tmp_path: Path):
    output_file = tmp_path / 'test_books.csv'

    with patch('books_to_scrape.fetch_page', return_value=None):
        with patch('books_to_scrape.get_book_links') as mock_get_book_links:
            with patch('books_to_scrape.scrape_book') as mock_scrape_book:
                main(output_file)

    mock_get_book_links.assert_not_called()
    mock_scrape_book.assert_not_called()


def test_main_no_next_button(tmp_path: Path):
    output_file = tmp_path / 'test_books.csv'

    mock_response = Mock()
    mock_response.text = """
    <html>
        <body>
            <article class="product_pod">
                <h3>
                    <a href="test-book.html">Test Book</a>
                </h3>
            </article>
        </body>
    </html>
    """
    test_book = Book(
        'Test Book',
        'test-upc-347',
        'Fiction',
        19.99,
        21,
        'This is the testing description.'
    )

    with patch('books_to_scrape.fetch_page', return_value=mock_response):
        with patch('books_to_scrape.get_book_links', return_value=["test-book.html"]):
            with patch(
                'books_to_scrape.scrape_book', 
                return_value=test_book
                ) as mock_scrape_book:
                main(output_file)

    assert output_file.exists()

    with open (output_file) as csv_file:
        rows = list(csv.reader(csv_file))

    assert rows[0] == CSV_HEADERS
    assert rows[1] == list(map(str, test_book.to_csv_row()))

    mock_scrape_book.assert_called_once()


def test_main_follows_next_page(tmp_path: Path):
    output_file = tmp_path / 'test_books.csv'

    mock_response_page_1 = Mock()
    mock_response_page_1.text = """
    <html>
        <body>
            <article class="product_pod">
                <h3>
                    <a href="test-book-1.html">Test Book 1</a>
                </h3>
            </article>

            <ul class="pager">
                <li class="next">
                    <a href="page-2.html">next</a>
                </li>
            </ul>
        </body>
    </html>
    """

    mock_response_page_2 = Mock()
    mock_response_page_2.text = """
    <html>
        <body>
            <article class="product_pod">
                <h3>
                    <a href="test-book-2.html">Test Book 2</a>
                </h3>
            </article>
        </body>
    </html>
    """

    test_book_1 = Book(
        'Test Book 1',
        'test-upc-347',
        'Fiction',
        19.99,
        21,
        'This is the testing description for book 1.'
    )

    test_book_2 = Book(
        'Test Book 2',
        'test-upc-443',
        'Travel',
        29.99,
        10,
        'This is the testing description for book 2.'
    )

    with patch(
        'books_to_scrape.fetch_page',
        side_effect=[
            mock_response_page_1, 
            mock_response_page_2
        ]) as mock_fetch_page:
        with patch(
            'books_to_scrape.get_book_links',
            side_effect=[
                ['test-book-1.html'],
                ['test-book-2.html']
        ]) as mock_get_book_links:
            with patch(
            'books_to_scrape.scrape_book',
            side_effect=[
                test_book_1,
                test_book_2
            ]) as mock_scrape_book:
                main(output_file)

    assert output_file.exists()

    with open (output_file) as csv_file:
        rows = list(csv.reader(csv_file))

    assert rows[0] == CSV_HEADERS
    assert rows[1] == list(map(str, test_book_1.to_csv_row()))
    assert rows[2] == list(map(str, test_book_2.to_csv_row()))

    assert mock_fetch_page.call_count == 2
    assert mock_get_book_links.call_count == 2
    assert mock_scrape_book.call_count == 2


def test_main_mid_scrape_fetch_failure(tmp_path: Path):
    output_file = tmp_path / 'test_books.csv'

    mock_response_page_1 = Mock()
    mock_response_page_1.text = """
    <html>
        <body>
            <article class="product_pod">
                <h3>
                    <a href="test-book-1.html">Test Book 1</a>
                </h3>
            </article>

            <ul class="pager">
                <li class="next">
                    <a href="page-2.html">next</a>
                </li>
            </ul>
        </body>
    </html>
    """

    test_book_1 = Book(
        'Test Book 1',
        'test-upc-347',
        'Fiction',
        19.99,
        21,
        'This is the testing description for book 1'        
    )

    with patch(
        'books_to_scrape.fetch_page',
        side_effect=[
            mock_response_page_1,
            None
        ]) as mock_fetch_page:
        with patch(
            'books_to_scrape.get_book_links',
            return_value=['test-book-1.html']
        ) as mock_get_book_links:
            with patch(
            'books_to_scrape.scrape_book',
            return_value=test_book_1
            ) as mock_scrape_book:
                main(output_file)

    assert output_file.exists()

    with open(output_file) as csv_file:
        rows = list(csv.reader(csv_file))

    assert rows[0] == CSV_HEADERS
    assert rows[1] == list(map(str, test_book_1.to_csv_row()))

    assert mock_fetch_page.call_count == 2
    assert mock_get_book_links.call_count == 1
    assert mock_scrape_book.call_count == 1