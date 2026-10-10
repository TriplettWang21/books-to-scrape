# Books to Scrape — Python Web Scraper

A Python web scraper that collects book information from [Books to Scrape](https://books.toscrape.com/), a website designed for web scraping practice. The scraper navigates catalogue pages, extracts book details, handles request failures, and exports the collected data to a CSV file.

## Features

* **Catalogue pagination:** Automatically follows pagination links to visit multiple catalogue pages.
* **Book data extraction:** Collects book titles, UPCs, categories, prices, availability counts, and descriptions.
* **HTTP session management:** Reuses a `requests.Session` for HTTP requests.
* **Retry logic:** Retries failed requests with increasing delays between attempts.
* **Data validation and normalization:** Converts prices and availability counts into appropriate data types.
* **Error handling:** Handles request failures, malformed HTML, missing fields, and invalid data.
* **Logging:** Records scraping progress and relevant warnings or errors to the console and log file.
* **CSV export:** Saves collected book data to `bookstore_all_books.csv`.
* **Automated testing:** Includes tests for normal operation, malformed HTML, request retries, data extraction, pagination, and failure scenarios.

## Technologies Used

* Python
* Requests
* Beautiful Soup 4
* lxml
* pytest
* Python standard libraries, including `csv`, `logging`, `dataclasses`, and `time`

## Project Structure

```text
books-to-scrape/
├── books_to_scrape.py       # Main scraper
├── test_scraper.py          # Automated tests
├── .gitignore               # Git ignore rules
├── README.md                # Project documentation
└── bookstore_all_books.csv  # Generated output (after running)
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/TriplettWang21/books-to-scrape.git
cd books-to-scrape
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

Install the required packages:

```bash
python -m pip install requests beautifulsoup4 lxml pytest
```

## Usage

Run the scraper from the project directory:

```bash
python books_to_scrape.py
```

By default, the scraper saves the collected book information to:

```text
bookstore_all_books.csv
```

The CSV contains the following columns:

* Title
* UPC
* Category
* Price (excl. tax)
* Availability
* Description

The scraper follows catalogue pagination automatically and uses retries to handle temporary request failures.

## Running Tests

Run the complete test suite from the project directory:

```bash
pytest -v
```

The current test suite contains **22 tests**, covering:

* Catalogue link extraction and malformed catalogue entries
* HTTP requests and retry behavior
* Book detail extraction and missing HTML elements
* Invalid prices and availability values
* Pagination and CSV generation
* Initial and mid-scrape request failures

All 22 tests passed in the latest run.

## Purpose

This project was built as a practical Python learning project to develop skills in web scraping, data processing, error handling, automated testing, and Git-based version control.

It demonstrates how to organize a scraper into reusable functions and test its behavior under both normal and failure conditions.
