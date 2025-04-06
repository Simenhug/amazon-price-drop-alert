import os
import sys

# Check if running in AWS Lambda (AWS_LAMBDA_FUNCTION_NAME is set in Lambda runtime)
if "AWS_LAMBDA_FUNCTION_NAME" in os.environ:
    sys.path.append("/opt/python")

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import boto3

from app.amazon_url_handler import AmazonURLProcessor

ID_SIZE = 16
S3_BUCKET_NAME = "amazon-product-price-history"
S3_PRICE_HISTORY_DIRECTORY = "product_price_history"
S3_PRICE_HISTORY_FILE_KEY = f"product_price_history/{datetime.today().strftime('%Y-%m-%d')}.csv"  # Organize by date
S3_PRODUCT_REGISTRY_FILE_KEY = "product_registry/product_registry.csv"  # Store the product ID, product name, and product URL

# product registry csv file header: "product_id,product_name,product_url"
PRODUCT_NAME_HEADER = "product_name"
PRODUCT_URL_HEADER = "product_url"
PRODUCT_ID_HEADER = "product_id"

# product price history csv file header: "product_id,date,price"
DATE_HEADER = "date"
PRICE_HEADER = "price"


@dataclass
class ProductDTO:
    product_name: str
    url: str
    product_id: str
    price: Optional[str] = None

    def __hash__(self):
        return hash(self.product_id)


class S3DataHandler:
    """
    A singleton class to:
    * upload and download product data to and from S3
    * look up product data by product ID
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(S3DataHandler, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.s3_client = boto3.client("s3")
        self.product_cache = set()

    def get_two_most_recent_prices(self) -> tuple[dict, dict]:

        response = self.s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME, Prefix=S3_PRICE_HISTORY_DIRECTORY
        )
        if "Contents" not in response:
            return []
        # Filter out "directory" keys (ending with '/')
        files_only = [
            obj for obj in response["Contents"] if not obj["Key"].endswith("/")
        ]

        # Sort objects by last modified date, descending
        sorted_files = sorted(
            files_only, key=lambda obj: obj["LastModified"], reverse=True
        )

        previous_price_file_key, current_price_file_key = [
            obj["Key"] for obj in sorted_files[:2]
        ]
        return (
            self.get_prices_from_file(previous_price_file_key),
            self._get_prices_from_file(current_price_file_key),
        )

    def get_prices_from_file(self, file_key: str) -> dict:
        """
        Download the file from S3 and parse the prices
        :return: A dictionary of prices {product_id: price}
        """
        local_file_name = "/tmp/temporary_price_data.csv"
        self.s3_client.download_file(S3_BUCKET_NAME, file_key, local_file_name)

        prices = {}
        with open(local_file_name, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                prices[row[PRODUCT_ID_HEADER]] = row[PRICE_HEADER]

        return prices

    def store_prices(self, products: list[ProductDTO]) -> None:
        """
        :param price_data: A dictionary {(product_name, url): price}
        """
        today_date = datetime.now().strftime("%Y-%m-%d")

        local_file_name = "/tmp/temporary_price_data.csv"
        with open(local_file_name, mode="w", newline="") as file:
            fieldnames = [PRODUCT_ID_HEADER, DATE_HEADER, PRICE_HEADER]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for product in products:
                if product.price:
                    writer.writerow(
                        {
                            PRODUCT_ID_HEADER: product.product_id,
                            DATE_HEADER: today_date,
                            PRICE_HEADER: product.price,
                        }
                    )

        # Upload to S3
        self.s3_client.upload_file(
            local_file_name, S3_BUCKET_NAME, S3_PRICE_HISTORY_FILE_KEY
        )

        print(
            f"Uploaded {local_file_name} to s3://{S3_BUCKET_NAME}/{S3_PRICE_HISTORY_FILE_KEY}"
        )

    def hash_product_id(self, product_name: str, url: str) -> str:
        """
        create or get an unique product ID based on the product name and URL.
        the product ID will be used to store and lookup prices.
        :param product_name: The name of the product
        :param url: The URL of the product
        :return: The product ID
        """
        product_id = hashlib.sha256(f"{product_name}{url}".encode()).hexdigest()[
            :ID_SIZE
        ]
        return product_id

    def get_products_with_ids(self, product_ids: list[str]) -> dict[str, ProductDTO]:
        """
        :param product_ids: A list of product IDs
        :return: A dictionary of product IDs to ProductDTOs (without price)
        """
        product_ids = set(product_ids)
        products = {}
        for product_id in list(product_ids):
            cached_product = self._get_product_from_cache(product_id)
            if cached_product:
                products[product_id] = cached_product
                product_ids.remove(product_id)

        local_file_name = "/tmp/temporary_product_registry.csv"
        self.s3_client.download_file(
            S3_BUCKET_NAME, S3_PRODUCT_REGISTRY_FILE_KEY, local_file_name
        )

        with open(local_file_name, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row[PRODUCT_ID_HEADER] in product_ids:
                    product = ProductDTO(
                        product_name=row[PRODUCT_NAME_HEADER],
                        url=row[PRODUCT_URL_HEADER],
                        product_id=row[PRODUCT_ID_HEADER],
                    )
                    products[row[PRODUCT_ID_HEADER]] = product
                    self.product_cache.add(product)
                    product_ids.remove(row[PRODUCT_ID_HEADER])
        if product_ids:
            raise KeyError(f"Product IDs not found in the registry: {product_ids}")
        return products

    def register_new_product(self, product_name: str, url: str) -> str:
        """
        Register a new product in the database
        :param product_name: The name of the product
        :param url: The URL of the product
        :return: The product ID
        """
        # Simplify the URL and confirm with the user
        url_processor = AmazonURLProcessor()
        simplified_url = url_processor.get_simplified_amazon_url(url)
        print(f"Product {product_name} will be stored with URL {simplified_url}")
        while True:
            proceed = input("Do you want to proceed? (Y/n): ").strip().lower()
            if proceed in ("", "y"):
                break
            elif proceed == "n":
                print("Operation cancelled.")
                return None
            else:
                print("Invalid input. Please enter 'Y' to proceed or 'n' to cancel.")

        url = simplified_url
        local_file_name = "/tmp/temporary_product_registry.csv"

        # Download the existing product registry file
        self.s3_client.download_file(
            S3_BUCKET_NAME, S3_PRODUCT_REGISTRY_FILE_KEY, local_file_name
        )

        # Check if the product already exists in the registry
        with open(local_file_name, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if (
                    row[PRODUCT_NAME_HEADER] == product_name
                    and row[PRODUCT_URL_HEADER] == url
                ):
                    print(
                        f"Product {product_name} with URL {url} already exists in the registry."
                    )
                    return None

        # Generate a new product ID
        product_id = self.hash_product_id(product_name, url)

        # Append the new product to the local file
        with open(local_file_name, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([product_name, url, product_id])

        # Upload the updated file back to S3
        self.s3_client.upload_file(
            local_file_name, S3_BUCKET_NAME, S3_PRODUCT_REGISTRY_FILE_KEY
        )

        self.product_cache.add(ProductDTO(product_name, url, product_id))

        print(
            f"Appended new product {product_name} to s3://{S3_BUCKET_NAME}/{S3_PRODUCT_REGISTRY_FILE_KEY}"
        )

    def list_registered_products(self) -> list[ProductDTO]:
        """
        print out all the registered products in the database
        """
        local_file_name = "/tmp/temporary_product_registry.csv"
        self.s3_client.download_file(
            S3_BUCKET_NAME, S3_PRODUCT_REGISTRY_FILE_KEY, local_file_name
        )
        products = []
        with open(local_file_name, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                product = ProductDTO(
                    product_name=row[PRODUCT_NAME_HEADER],
                    url=row[PRODUCT_URL_HEADER],
                    product_id=row[PRODUCT_ID_HEADER],
                )
                products.append(product)
                self.product_cache.add(product)
        return products

    def get_two_most_recent_price_files(self):
        """
        Get the two most recent price files from S3
        """
        files = self.s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME)
        files = files["Contents"]
        files.sort(key=lambda x: x["LastModified"], reverse=True)
        recent_files = files[:2]
        return recent_files

    def _get_product_from_cache(self, product_id: str) -> Optional[ProductDTO]:
        for product in self.product_cache:
            if product.product_id == product_id:
                return product
        return None

    def get_product_by_id(self, product_id: str) -> ProductDTO:
        product = self._get_product_from_cache(product_id)
        if product:
            return product
        return self.get_products_with_ids([product_id])[product_id]
