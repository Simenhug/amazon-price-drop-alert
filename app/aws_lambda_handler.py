import os
import sys

# Check if running in AWS Lambda (AWS_LAMBDA_FUNCTION_NAME is set in Lambda runtime)
if "AWS_LAMBDA_FUNCTION_NAME" in os.environ:
    sys.path.append("/opt/python")

from app.amazon_price_checker import AmazonPriceExtractor

# from app.scrape_api_test import *


# This is the entry point for the AWS Lambda
def lambda_handler(event, context):
    extractor = AmazonPriceExtractor()
    extractor.run()
