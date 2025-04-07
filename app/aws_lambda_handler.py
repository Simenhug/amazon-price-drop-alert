from app.amazon_price_checker import AmazonPriceExtractor

# from app.scrape_api_test import *


# This is the entry point for the AWS Lambda
def lambda_handler(event, context):
    extractor = AmazonPriceExtractor()
    extractor.run()
