from app.amazon_price_checker import AmazonPriceExtractor

# from app.scrape_api_test import *


# This is the entry point for the AWS Lambda
def lambda_handler(event, context):
    url = "https://www.amazon.com/dp/B0838DLV5Z"
    extractor = AmazonPriceExtractor()

    price = extractor.get_amazon_price_with_soup(url)
    return {"price": price}
