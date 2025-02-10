import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By

def get_amazon_price_with_soup(url):
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.amazon.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    }
    session = requests.Session()
    session.headers.update(headers)

    print(f"Fetching URL: {url}")
    search_response = session.get(url)
    print(f"HTTP Status Code: {search_response.status_code}")
    soup = BeautifulSoup(search_response.text, 'html.parser')

    
    # Print the HTML content for debugging
    # print(soup.prettify()[:1000])  # Print the first 1000 characters of the HTML content
    
    # The price can be located in different elements depending on the product page layout
    price = soup.find(id="priceblock_ourprice") or soup.find(id="priceblock_dealprice")
    print(f"Price found in priceblock: {price}")
    
    if not price:
        price_div = soup.select_one("#corePriceDisplay_desktop_feature_div > div.a-section.a-spacing-none.aok-align-center.aok-relative")
        print(f"Price div found: {price_div}")
        if price_div:
            price_span = price_div.find("span", class_="a-price-whole")
            print(f"Price span found: {price_span}")
            if price_span:
                price = price_span.get_text().strip()
                fraction_span = price_div.find("span", class_="a-price-fraction")
                print(f"Fraction span found: {fraction_span}")
                if fraction_span:
                    price += "." + fraction_span.get_text().strip()
    
    if price:
        return price
    else:
        return "Price not found"

def get_amazon_price_with_selenium(url):
    # Set up Selenium WebDriver
    driver = webdriver.Chrome()
    driver.get(url)

    # Wait for the price element to load (if needed)
    driver.implicitly_wait(10)

    # Extract HTML after JavaScript execution
    page_source = driver.page_source

    # Use BeautifulSoup to parse
    soup = BeautifulSoup(page_source, "html.parser")

    # Find the element again
    price_div = soup.find(id="corePriceDisplay_desktop_feature_div")
    print(price_div)
    driver.quit()
    
    # Print the HTML content for debugging
    # print(soup.prettify()[:1000])  # Print the first 1000 characters of the HTML content
    
    # The price can be located in different elements depending on the product page layout
    price = soup.find(id="priceblock_ourprice") or soup.find(id="priceblock_dealprice")
    print(f"Price found in priceblock: {price}")
    
    if not price:
        price_div = soup.select_one("#corePriceDisplay_desktop_feature_div > div.a-section.a-spacing-none.aok-align-center.aok-relative")
        print(f"Price div found: {price_div}")
        if price_div:
            price_span = price_div.find("span", class_="a-price-whole")
            print(f"Price span found: {price_span}")
            if price_span:
                price = price_span.get_text().strip()
                fraction_span = price_div.find("span", class_="a-price-fraction")
                print(f"Fraction span found: {fraction_span}")
                if fraction_span:
                    price += "." + fraction_span.get_text().strip()
    
    if price:
        return price
    else:
        return "Price not found"

if __name__ == "__main__":
    url = "https://www.amazon.com/dp/B0B38DLV5Z"
    while True:
        # price = get_amazon_price_with_selenium(url)
        price = get_amazon_price_with_soup(url)
        print(f"The price of the product is: {price}")
        input("Press Enter to check the price again...")
