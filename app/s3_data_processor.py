import csv
import hashlib
from datetime import datetime

import boto3

from app.amazon_url_handler import AmazonURLProcessor

ID_SIZE = 16
S3_BUCKET_NAME = "amazon-product-price-history"
S3_PRICE_HISTORY_FILE_KEY = f"product_price_history/{datetime.today().strftime('%Y-%m-%d')}.csv"  # Organize by date
S3_PRODUCT_REGISTRY_FILE_KEY = "product_registry/product_registry.csv"  # Store the product ID, product name, and product URL


class ProductPriceProcessor:

    def store_prices(self, price_data: dict[tuple[str, str], str]) -> None:
        """
        :param price_data: A dictionary {(product_name, url): price}
        """

        converted_price_data = {
            self.hash_product_id(product_name, url): price
            for (product_name, url), price in price_data.items()
        }
        today_date = datetime.now().strftime("%Y-%m-%d")

        local_file_name = "temporary_price_data.csv"
        with open(local_file_name, mode="w", newline="") as file:
            fieldnames = ["product_id", "date", "price"]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for product_id, price in converted_price_data.items():
                writer.writerow(
                    {"product_id": product_id, "date": today_date, "price": price}
                )

        # Upload to S3
        s3_client = boto3.client("s3")
        s3_client.upload_file(
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

    def lookup_product_id(self, product_name: str, product_url: str) -> str | None:
        """
        retrieve the product registry csv file on S3 and lookup the product ID based on the product name and URL.
        The csv header is "product_id,product_name,product_url"

        :param product_name: The name of the product
        :param url: The URL of the product
        :return: The product ID if found, otherwise None
        """
        s3_client = boto3.client("s3")
        local_file_name = "temporary_product_registry.csv"
        s3_client.download_file(
            S3_BUCKET_NAME, S3_PRODUCT_REGISTRY_FILE_KEY, local_file_name
        )

        with open(local_file_name, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if (
                    row["product_name"] == product_name
                    and row["product_url"] == product_url
                ):
                    return row["product_id"]
        print(f"Product ID not found for {product_name} with URL {product_url}")
        return None

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
        s3_client = boto3.client("s3")
        local_file_name = "temporary_product_registry.csv"

        # Download the existing product registry file
        s3_client.download_file(
            S3_BUCKET_NAME, S3_PRODUCT_REGISTRY_FILE_KEY, local_file_name
        )

        # Check if the product already exists in the registry
        with open(local_file_name, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["product_name"] == product_name and row["product_url"] == url:
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
        s3_client.upload_file(
            local_file_name, S3_BUCKET_NAME, S3_PRODUCT_REGISTRY_FILE_KEY
        )

        print(
            f"Appended new product {product_name} to s3://{S3_BUCKET_NAME}/{S3_PRODUCT_REGISTRY_FILE_KEY}"
        )

    def list_registered_products(self) -> None:
        """
        print out all the registered products in the database
        """
        s3_client = boto3.client("s3")
        local_file_name = "temporary_product_registry.csv"
        s3_client.download_file(
            S3_BUCKET_NAME, S3_PRODUCT_REGISTRY_FILE_KEY, local_file_name
        )

        with open(local_file_name, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            next(reader)  # Skip the header line
            for row in reader:
                print(row)


# to register a new product to the watch list
if __name__ == "__main__":
    processor = ProductPriceProcessor()
    while True:
        register_new = (
            input("Would you like to register a new product to the watch list? (Y/n): ")
            .strip()
            .lower()
        )
        if register_new in ("", "y"):
            product_name = input("Enter the product name: ").strip()
            product_url = input("Enter the product URL: ").strip()
            processor.register_new_product(product_name, product_url)
        elif register_new == "n":
            print("Exiting the registration loop.")
            break
        else:
            print(
                "Invalid input. Please enter 'Y' to register a new product or 'n' to exit."
            )
