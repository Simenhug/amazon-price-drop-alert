import requests
import random
import time
from bs4 import BeautifulSoup
from app.utils import RetryOnException


PRICE_ELEMENT_SELECTOR = "#corePriceDisplay_desktop_feature_div > div.a-section.a-spacing-none.aok-align-center.aok-relative"
USER_AGENTS = [
        # 🖥️ Windows User-Agents
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/115.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:92.0) Gecko/20100101 Firefox/92.0",

        # 🍏 macOS User-Agents
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_5_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/115.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14) AppleWebKit/537.36 (KHTML, like Gecko) Safari/604.1.38",

        # 🐧 Linux User-Agents
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/109.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",

        # 📱 Mobile User-Agents (Less Bot Detection!)
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/537.36",
        "Mozilla/5.0 (Android 13; Mobile; rv:119.0) Gecko/119.0 Firefox/119.0",
        "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 11; SM-A715F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    ]

class PriceNotFoundException(Exception):
    pass

class AmazonPriceExtractor:
    
    def extract_price_from_soup(self, soup) -> str:
        price_div = soup.select_one(PRICE_ELEMENT_SELECTOR)
        price = None

        if price_div:
            price_span = price_div.find("span", class_="a-price-whole")
            # print(f"Price span found: {price_span}")
            if price_span:
                price = price_span.get_text().strip()
                fraction_span = price_div.find("span", class_="a-price-fraction")
                # print(f"Fraction span found: {fraction_span}")
                if fraction_span:
                    price +=  fraction_span.get_text().strip()
                    return price
                
        raise PriceNotFoundException()

    def get_random_user_agent(self):
        agent = random.choice(USER_AGENTS)
        print(f"User-Agent: {agent}")
        return agent

    @RetryOnException(exception=PriceNotFoundException)
    def get_amazon_price_with_soup(self, url: str) -> str:

        agent = self.get_random_user_agent()

        # 🚀 Headers to Bypass Detection
        headers = {
            "User-Agent": agent,
            "Referer": "https://www.amazon.com/",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # 🚀 Using a Session for Persistence
        session = requests.Session()
        session.headers.update(headers)

        # 🚀 Fetch Search Results
        response = session.get(url)
        print(f"HTTP Status Code: {response.status_code}")
        soup = BeautifulSoup(response.text, "html.parser")

        price_div = soup.select_one(PRICE_ELEMENT_SELECTOR)

        return self.extract_price_from_soup(soup)
    

# this is only for testing locally, not how workflow is triggered in production
if __name__ == "__main__":
    url = "https://www.amazon.com/dp/B0DPLYGYXV"
    extractor = AmazonPriceExtractor()
    while True:
        price = extractor.get_amazon_price_with_soup(url)
        print(f"The price of the product is: {price}")
        input("Press Enter to check the price again...")
        # ✅ Random Delay to Avoid Detection
        time.sleep(random.uniform(2, 5))
