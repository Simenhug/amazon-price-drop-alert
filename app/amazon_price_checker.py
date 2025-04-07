import os
import random
import time

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from app.amazon_url_handler import AmazonURLProcessor
from app.email_sender import send_email
from app.price_data_processor import PriceDataProcessor
from app.s3_data_handler import ProductDTO, S3DataHandler
from app.utils import InsuffcientScraperAPIQuotaException

PRICE_ELEMENT_SELECTOR = "#corePriceDisplay_mobile_feature_div"
PRICE_WHOLE_SPAN_CLASS = ".a-price-whole"
PRICE_FRACTION_SPAN_CLASS = ".a-price-fraction"


class AmazonPriceExtractor:
    def __init__(self, scraper_api_key_name: str = None):
        load_dotenv()
        if not scraper_api_key_name:
            scraper_api_key_name = "SCRAPER_API_KEY"
        self.scraper_api_key = os.getenv(scraper_api_key_name)
        if not self.scraper_api_key:
            raise ValueError("Scraper API Key not found in environment variables")
        self.s3_data_handler = S3DataHandler()
        self.url_handler = AmazonURLProcessor()
        self.price_data_processor = PriceDataProcessor()

    def extract_price_from_soup(self, soup, debug: bool = False) -> str:

        price_whole = soup.select_one(
            f"{PRICE_ELEMENT_SELECTOR} {PRICE_WHOLE_SPAN_CLASS}"
        ).text.strip()
        if debug:
            print(f"Price Whole: {price_whole}\n")
        price_fraction = soup.select_one(
            f"{PRICE_ELEMENT_SELECTOR} {PRICE_FRACTION_SPAN_CLASS}"
        ).text.strip()
        if debug:
            print(f"Price Fraction: {price_fraction}\n")
        return price_whole + price_fraction

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

    def get_amazon_price_with_soup(self, url: str, debug: bool = False) -> str:

        proxy = self.scraper_api_proxy_builder()
        print(f"Proxy: {proxy}\n")
        response = requests.get(url, proxies=proxy, verify=False)
        print(f"HTTP Status Code: {response.status_code}\n")
        self._check_insufficient_scraper_api_quota(response)

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

        price = self.extract_price_from_soup(soup, debug=debug)
        print(f"Price: {price}\n")
        return price

    def _check_insufficient_scraper_api_quota(self, response: requests.Response):
        if response.status_code == 403:
            if all(
                keyword in response.text.lower()
                for keyword in ["exhausted", "api credits", "scraperapi"]
            ):
                print("Current Scraper API likely reached its monthly limit.")
                print(f"response text: {response.text}")
                raise InsuffcientScraperAPIQuotaException()

    def extract_price_for_all_registered_products(
        self, debug: bool = False
    ) -> list[ProductDTO]:
        products = self.s3_data_handler.list_registered_products()
        if debug:
            print("\ngoing to extract prices for the following products:")
            for product in products:
                print(product.product_name)
        for product in products:
            try:
                if debug:
                    print(
                        f"\nExtracting price for {product.product_name} with {product.url}"
                    )
                # Random Delay to Avoid Detection
                time.sleep(random.uniform(6, 10))
                human_like_url = self.url_handler.generate_human_like_amazon_url(
                    product.url, product.product_name
                )
                if debug:
                    print(f"\nHuman-like URL: {human_like_url}\n")
                price = self.get_amazon_price_with_soup(human_like_url, debug=debug)
                product.price = price
            except InsuffcientScraperAPIQuotaException:
                self._retry_with_secondary_scraper_api_key(debug=debug)
                return
            except Exception as e:
                print(
                    f"Failed to extract price for {product.product_name} with {product.url}: {e}"
                )

        return products

    def _retry_with_secondary_scraper_api_key(self, debug: bool = False):
        """retry with the secondary scraper API key"""
        if self.scraper_api_key_name == "SCRAPER_API_KEY":
            print(
                "Insufficient Scraper API Quota. Restarting the extraction process with secondary Scraper API key."
            )
            extractor = AmazonPriceExtractor(
                scraper_api_key_name="SECONDARY_SCRAPER_API_KEY"
            )
            extractor.run(debug=debug)

    def store_product_prices(self, products: list[ProductDTO]) -> None:
        self.s3_data_handler.store_prices(products)

    def check_and_process_price_drops(self):
        """
        check for any price drops
        generate price charts for any products with price drops
        send email alerts with price chart images
        """
        price_drops = self.price_data_processor.check_price_drops()
        if not price_drops:
            print("\nNo price drops detected.")
            return
        price_drops = self.price_data_processor.plot_price_graphs(price_drops)

        email = os.getenv("EMAIL")
        send_email(
            sender=email,
            recipient=email,
            subject="Price Drop Alert!",
            price_drops=price_drops,
        )

    def run(self, debug: bool = False):
        # scrape latest price for all watched products
        products = self.extract_price_for_all_registered_products(debug=debug)
        self.store_product_prices(products)
        # check for any price drops and send email alerts if any
        self.check_and_process_price_drops()


# this is only for testing locally, not how workflow is triggered in production
if __name__ == "__main__":
    extractor = AmazonPriceExtractor()
    extractor.run(debug=True)
