# tools/web_scraper.py
from typing import List, Dict, Union
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import time

def scrape_ebay(description: str) -> List[Dict]:
    """Scrape eBay for similar items"""
    query = "+".join(description.split())
    url = f"https://www.ebay.com/sch/i.html?_nkw={query}"

    items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        time.sleep(2)  # wait for JS to load

        html = page.content()
        soup = BeautifulSoup(html, "lxml")
        listings = soup.select(".s-item")[:10]

        for listing in listings:
            try:
                title_tag = listing.select_one(".s-item__title")
                price_tag = listing.select_one(".s-item__price")
                url_tag = listing.select_one(".s-item__link")

                title = title_tag.text.strip() if title_tag else "No title"
                price_text = price_tag.text.strip() if price_tag else "0"
                price = float(re.sub(r"[^\d.]", "", price_text)) if price_text else 0
                url = url_tag["href"] if url_tag else ""

                items.append({
                    "title": title,
                    "price": price,
                    "condition": "Unknown",
                    "url": url
                })
            except:
                continue

        browser.close()
    return items

def scrape_olx(description: str) -> List[Dict]:
    """Scrape OLX (France) for similar items"""
    query = "+".join(description.split())
    url = f"https://www.olx.fr/annonces/q-{query}/"

    items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        time.sleep(2)

        html = page.content()
        soup = BeautifulSoup(html, "lxml")
        listings = soup.select("li[data-cy='l-card']")[:10]

        for listing in listings:
            try:
                title_tag = listing.select_one("h6")
                price_tag = listing.select_one("p[data-testid='ad-price']")
                url_tag = listing.select_one("a")

                title = title_tag.text.strip() if title_tag else "No title"
                price_text = price_tag.text.strip() if price_tag else "0"
                price = float(re.sub(r"[^\d.]", "", price_text)) if price_text else 0
                url = url_tag["href"] if url_tag else ""

                items.append({
                    "title": title,
                    "price": price,
                    "condition": "Unknown",
                    "url": url
                })
            except:
                continue

        browser.close()
    return items

def search_similar_items(description: str, images: Union[List[str], None] = None) -> List[Dict]:
    """
    Scrape multiple famous marketplaces for similar items.
    """
    results = []
    results.extend(scrape_ebay(description))
    results.extend(scrape_olx(description))
    # You can add more sites here: Amazon, Leboncoin, etc.

    return results[:20]  # limit total items