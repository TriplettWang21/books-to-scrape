from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests
import csv
import time
from dataclasses import dataclass
import re
import logging

BASE_URL = 'https://books.toscrape.com/catalogue/page-1.html'
MAX_RETRIES = 3
TIMEOUT = 10
DELAY = 1
SKIP_FIELDS = ['Number of reviews', 'Product Type','Tax', 'Price (incl. tax)']
CSV_HEADERS = [
    'Title',
    'UPC',
    'Category',
    'Price (excl. tax)',
    'Available Count',
    'Description'
]


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | %(message)s'
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = logging.FileHandler('scraper.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

@dataclass
class Book:
    title: str
    upc: str
    category: str
    price_excl_tax: float
    available_count: int
    description: str

    def to_csv_row(self):
        return [self.title, self.upc, self.category, self.price_excl_tax, self.available_count, self.description]


def fetch_page(url, session):
    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response

        except requests.RequestException as e:
            logger.warning(
                f'Request failed for {url} (attempt {attempt + 1}/{MAX_RETRIES}): {e}'
                )

            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

    return None


def get_book_links(soup, page_url):
    links = []

    books = soup.find_all('article', class_='product_pod')

    for item in books:
        h3 = item.h3

        if h3 is None:
            logger.warning(
            "Book card has no h3; skipping. Page: %s",
            page_url
            )
            continue

        link = h3.a

        if link is None:
            logger.warning(
            "Book card has no link; skipping. Page: %s",
            page_url
            )
            continue

        href = link.get("href")

        if href is None:
            logger.warning(
            "Book link has no href; skipping. Page: %s",
            page_url
            )
            continue

        links.append(urljoin(page_url, href))

    return links


def scrape_book(url, session):
    response = fetch_page(url, session)

    if response is None:
        logger.error(f'Skipping {url} - Request failed after {MAX_RETRIES} attempts')
        return None

    soup = BeautifulSoup(response.text, 'lxml')
    info = {}
    table = soup.find('table', class_='table table-striped')

    if table:
        for row in table.find_all('tr'):
            label = row.th.text
            if label in SKIP_FIELDS:
                continue
            info[label] = row.td.text

    title_block = soup.find('div', class_='col-sm-6 product_main')
    info['Title'] = title_block.h1.text.strip() if title_block else 'No Title Available'

    category_block = soup.find('ul', class_='breadcrumb')
    li_tags = category_block.find_all('li')
    info['Category'] = li_tags[2].text.strip()

    description_block = soup.find('div', id='product_description')
    description_tag = description_block.find_next_sibling('p') if description_block else None
    info['Description'] = description_tag.text if description_tag else 'No Description Available'

    info['Price (excl. tax)'] = float(info['Price (excl. tax)'].strip('£'))
    
    info['Available Count'] = int(re.search(r'\d+', info['Availability']).group())

    return Book(
        info['Title'], 
        info['UPC'], 
        info['Category'], 
        info['Price (excl. tax)'], 
        info['Available Count'], 
        info['Description']
        )


def main():
    current_url = BASE_URL
    books = []
    logger.info('Scraper started')

    with requests.Session() as session:
        while True:

            response = fetch_page(current_url, session)

            if response is None:
                logger.error(f'Failed to fetch catalogue page: {current_url} ')
                break

            soup = BeautifulSoup(response.text, 'lxml')

            links = get_book_links(soup, current_url)

            for link in links:
                info = scrape_book(link, session)
                if info:
                    books.append(info)

            next_button = soup.find('li', class_='next')

            if next_button is None:
                break

            next_href = next_button.a['href']
            current_url = urljoin(current_url, next_href)

            time.sleep(DELAY)

    with open('bookstore_all_books.csv', 'w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(CSV_HEADERS)
        for book in books:
            writer.writerow(book.to_csv_row())
    logger.info(f'Saved {len(books)} books to bookstore_all_books.csv')


if __name__ == '__main__':
    main()
