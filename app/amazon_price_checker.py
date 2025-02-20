import os
import random
import time

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from app.utils import RetryOnException

PRICE_ELEMENT_SELECTOR = "#corePrice_feature_div"
PRICE_WHOLE_SPAN_CLASS = ".a-price-whole"
PRICE_FRACTION_SPAN_CLASS = ".a-price-fraction"


class PriceNotFoundException(Exception):
    def __init__(self, original_exception=None):
        self.original_exception = original_exception
        super().__init__(f"Price not found. Original exception: {original_exception}")


class AmazonPriceExtractor:
    def __init__(self):
        load_dotenv()
        self.scraper_api_key = os.getenv("SCRAPER_API_KEY")
        if not self.scraper_api_key:
            raise ValueError("Scraper API Key not found in environment variables")

    def extract_price_from_soup(self, soup) -> str:

        try:
            price_whole = soup.select_one(
                f"{PRICE_ELEMENT_SELECTOR} {PRICE_WHOLE_SPAN_CLASS}"
            ).text.strip()
            price_fraction = soup.select_one(
                f"{PRICE_ELEMENT_SELECTOR} {PRICE_FRACTION_SPAN_CLASS}"
            ).text.strip()
            return price_whole + price_fraction
        except Exception as e:
            raise PriceNotFoundException(e)

    def scraper_api_proxy_builder(
        self,
        javascript_render: bool = True,  # if the targeted URLs require rendering javascript
        device_type: str = "mobile",  # either "desktop" or "mobile", the current PRICE_ELEMENT_SELECTOR only works for mobile
        disable_follow_redirect: bool = False,
        country_code: str = "us",
        binary_target: bool = False,  # helpful when trying to scrape files or images.
        retry_404: bool = False,
    ):
        """
        remember all of these options can be optional, and the proxy would simply be
        "scraperapi:<my-scraper-api-key>@proxy-server.scraperapi.com:8001"
        """

        # this http:// prefix is necessary for this script to work on AWS Lambda, although not necessary for local testing
        proxy = "http://"
        if javascript_render:
            proxy += "scraperapi.render=true."
        if disable_follow_redirect:
            proxy += "follow_redirect=false."
        if binary_target:
            proxy += "binary_target=true."
        if retry_404:
            proxy += "retry_404=true."
        # by default we're scraping a mobile page, because amazon has less strict anti-scraping measures for mobile
        proxy += f"device_type={device_type}."
        proxy += f"country_code={country_code}"  # notice not adding a period here

        proxy += f":{self.scraper_api_key}"
        proxy += "@proxy-server.scraperapi.com:8001"
        return {"https": proxy}

    @RetryOnException(exception=PriceNotFoundException, retries=1)
    def get_amazon_price_with_soup(self, url: str, debug: bool = False) -> str:

        proxy = self.scraper_api_proxy_builder()
        print(f"Proxy: {proxy}\n")
        response = requests.get(url, proxies=proxy, verify=False)
        print(f"HTTP Status Code: {response.status_code}\n")

        if debug:
            # Save the response content to an HTML file
            file_path = "webpage.html"
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(response.text)

            # Open the saved HTML file in the default web browser
            # this only works on macOS
            # should not be run on AWS Lambda, which is a headless Linux environment
            os.system(f"open {file_path}")

        soup = BeautifulSoup(response.text, "html.parser")

        price = self.extract_price_from_soup(soup)
        print(f"Price: {price}\n")
        return price


# this is only for testing locally, not how workflow is triggered in production
# IMPORTANT: If the code is working fine but suddenly starts getting 404s, try a different amazon product
if __name__ == "__main__":
    url = "https://www.amazon.com/dp/B0DPLYGYXV"
    extractor = AmazonPriceExtractor()
    price = extractor.get_amazon_price_with_soup(url, debug=True)
    print(f"The price of the product is: {price}\n")
    # ✅ Random Delay to Avoid Detection
    time.sleep(random.uniform(6, 10))
