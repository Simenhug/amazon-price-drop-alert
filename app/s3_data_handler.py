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

# product registry csv file header: "product_id,product_name,product_url,archived"
PRODUCT_NAME_HEADER = "product_name"
PRODUCT_URL_HEADER = "product_url"
PRODUCT_ID_HEADER = "product_id"
ARCHIVED_HEADER = "archived"  # this stores the date when the product was archived in YYYY-MM-DD format

# product price history csv file header: "product_id,date,price"
DATE_HEADER = "date"
PRICE_HEADER = "price"


@dataclass
class ProductDTO:
    product_name: str
    url: str
    product_id: str
    price: Optional[str] = None
    archived: Optional[str] = None

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

    def _filter_active_products(self, products: list[ProductDTO]) -> list[ProductDTO]:
        """
        Filter out products that have been archived
        :param products: List of ProductDTO objects
        :return: List of active ProductDTO objects (archived field is None or empty)
        """
        return [product for product in products if not product.archived]

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

        current_price_file_key, previous_price_file_key = [
            obj["Key"] for obj in sorted_files[:2]
        ]
        print("Previous price file:", previous_price_file_key)
        print("Current price file:", current_price_file_key)
        return (
            self.get_prices_from_file(previous_price_file_key),
            self.get_prices_from_file(current_price_file_key),
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
                        archived=row.get(ARCHIVED_HEADER, None),
                    )
                    products[row[PRODUCT_ID_HEADER]] = product
                    self.product_cache.add(product)
                    product_ids.remove(row[PRODUCT_ID_HEADER])
        if product_ids:
            raise KeyError(f"Product IDs not found in the registry: {product_ids}")
        # Filter out archived products and return as dictionary
        active_products = self._filter_active_products(list(products.values()))
        return {product.product_id: product for product in active_products}

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
                    row[PRODUCT_NAME_HEADER].lower() == product_name.lower()
                    or row[PRODUCT_URL_HEADER] == url
                ):
                    print(
                        f"Product {product_name} with URL {url} already exists in the registry."
                    )
                    return None

        # Generate a new product ID
        product_id = self.hash_product_id(product_name, url)

        # Append the new product to the local file
        with open(local_file_name, mode="a", newline="") as file:
            fieldnames = [
                PRODUCT_NAME_HEADER,
                PRODUCT_URL_HEADER,
                PRODUCT_ID_HEADER,
                ARCHIVED_HEADER,
            ]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writerow(
                {
                    PRODUCT_NAME_HEADER: product_name,
                    PRODUCT_URL_HEADER: url,
                    PRODUCT_ID_HEADER: product_id,
                    ARCHIVED_HEADER: "",
                }
            )

        # Upload the updated file back to S3
        self.s3_client.upload_file(
            local_file_name, S3_BUCKET_NAME, S3_PRODUCT_REGISTRY_FILE_KEY
        )

        self.product_cache.add(ProductDTO(product_name, url, product_id, archived=""))

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
                    archived=row.get(ARCHIVED_HEADER, None),
                )
                products.append(product)
                self.product_cache.add(product)
        return self._filter_active_products(products)

    def get_two_most_recent_price_files(self):
        """
        DEPRECATED: Get the two most recent price files from S3
        """
        files = self.s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME)
        files = files["Contents"]
        files.sort(key=lambda x: x["LastModified"], reverse=True)
        recent_files = files[:2]
        return recent_files

    def _get_product_from_cache(self, product_id: str) -> Optional[ProductDTO]:
        for product in self.product_cache:
            if product.product_id == product_id and not product.archived:
                return product
        return None

    def get_product_by_id(self, product_id: str) -> ProductDTO:
        product = self._get_product_from_cache(product_id)
        if product:
            return product
        return self.get_products_with_ids([product_id])[product_id]

    def interactive_product_registration(self):
        """
        Interactive method to register products or archive existing products.
        This method provides a menu-driven interface for product management.
        """
        while True:
            print("\n=== Product Management Menu ===")
            print("1. Register New Product")
            print("2. Archive Product")
            print("3. Exit")

            choice = input("\nPlease select an option (1-3): ").strip()

            if choice == "1":
                self._handle_register_new_product()
            elif choice == "2":
                self._handle_archive_product()
            elif choice == "3":
                print("Exiting the product management system.")
                break
            else:
                print("Invalid input. Please enter a number between 1 and 3.")

    def _handle_register_new_product(self):
        """
        Handle the register new product flow
        """
        # Read all products to get existing names
        local_file_name = "/tmp/temporary_product_registry.csv"
        try:
            self.s3_client.download_file(
                S3_BUCKET_NAME, S3_PRODUCT_REGISTRY_FILE_KEY, local_file_name
            )
        except Exception as e:
            print(f"Error reading product registry: {e}")
            return

        # Extract all product names and separate active/archived
        all_names = set()
        active_products = []
        archived_products = []

        with open(local_file_name, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                product_name = row[PRODUCT_NAME_HEADER]
                all_names.add(product_name.lower())  # Store lowercase for comparison

                product = ProductDTO(
                    product_name=product_name,
                    url=row[PRODUCT_URL_HEADER],
                    product_id=row[PRODUCT_ID_HEADER],
                    archived=row.get(ARCHIVED_HEADER, None),
                )

                if product.archived:
                    archived_products.append(product)
                else:
                    active_products.append(product)

        # Display existing products for reference
        print("\n=== Existing Products ===")
        if active_products:
            print("Active Products:")
            for product in active_products:
                print(f" - {product.product_name}")
        else:
            print("No active products.")

        if archived_products:
            print("Archived Products:")
            for product in archived_products:
                print(f" - {product.product_name}")
        else:
            print("No archived products.")

        # Get new product details
        print("\n=== Register New Product ===")
        product_name = input("Enter the product name: ").strip()
        if not product_name:
            print("Product name cannot be empty.")
            return

        # Check for duplicate name
        if product_name.lower() in all_names:
            print(f"Product name '{product_name}' already exists in the registry.")
            return

        product_url = input("Enter the product URL (full URL): ").strip()
        if not product_url:
            print("Product URL cannot be empty.")
            return

        # Register the product
        result = self.register_new_product(product_name, product_url)
        if result:
            print(f"Product '{product_name}' registered successfully!")

    def _handle_archive_product(self):
        """
        Handle the archive product flow
        """
        # Get active products
        active_products = self.list_registered_products()

        if not active_products:
            print("No active products to archive.")
            return

        while True:
            # Display numbered list of active products
            print("\n=== Active Products ===")
            for i, product in enumerate(active_products, 1):
                print(f"{i}. {product.product_name}")

            # Get user selection
            selection = input(
                f"\nSelect a product to archive (1-{len(active_products)}): "
            ).strip()
            selected_number = self._validate_number_input(
                selection, len(active_products)
            )

            if selected_number is None:
                print("Invalid selection. Please enter a valid number.")
                continue

            # Get the selected product
            selected_product = active_products[selected_number - 1]

            # Show confirmation
            print(f"\nSelected product: {selected_product.product_name}")
            print(f"Product URL: {selected_product.url}")

            if self._get_confirmation(
                f"Do you want to archive '{selected_product.product_name}'?"
            ):
                # Archive the product
                if self.archive_product(selected_product.product_id):
                    print(
                        f"Product '{selected_product.product_name}' has been archived successfully!"
                    )
                else:
                    print("Failed to archive the product.")
                break
            else:
                print("Archive cancelled. Returning to product list.")
                # Continue the loop to show the list again

    def archive_product(self, product_id: str) -> bool:
        """
        Archive a product by setting the archived field to the current date
        archived products will be ignored by all tasks
        :param product_id: The product ID to archive
        :return: True if successful, False if product not found
        """
        local_file_name = "/tmp/temporary_product_registry.csv"

        # Download the existing product registry file
        self.s3_client.download_file(
            S3_BUCKET_NAME, S3_PRODUCT_REGISTRY_FILE_KEY, local_file_name
        )

        # Read all products and find the one to archive
        products = []
        product_found = False
        with open(local_file_name, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row[PRODUCT_ID_HEADER] == product_id:
                    row[ARCHIVED_HEADER] = datetime.now().strftime("%Y-%m-%d")
                    product_found = True
                products.append(row)

        if not product_found:
            return False

        # Write back all products with the updated archived field
        with open(local_file_name, mode="w", newline="") as file:
            fieldnames = [
                PRODUCT_NAME_HEADER,
                PRODUCT_URL_HEADER,
                PRODUCT_ID_HEADER,
                ARCHIVED_HEADER,
            ]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(products)

        # Upload the updated file back to S3
        self.s3_client.upload_file(
            local_file_name, S3_BUCKET_NAME, S3_PRODUCT_REGISTRY_FILE_KEY
        )

        # Clear cache to force refresh
        self.product_cache.clear()

        print(f"Product {product_id} has been archived.")
        return True

    def _validate_number_input(self, user_input: str, max_number: int) -> Optional[int]:
        """
        Validate user input for numbered selection
        :param user_input: The user's input string
        :param max_number: The maximum valid number
        :return: The valid number as int, or None if invalid
        """
        try:
            number = int(user_input.strip())
            if 1 <= number <= max_number:
                return number
            else:
                return None
        except ValueError:
            return None

    def _get_confirmation(self, message: str) -> bool:
        """
        Get yes/no confirmation from user
        :param message: The confirmation message to display
        :return: True for 'y'/'yes', False for 'n'/'no'
        """
        while True:
            response = input(f"{message} (y/n): ").strip().lower()
            if response in ("y", "yes"):
                return True
            elif response in ("n", "no"):
                return False
            else:
                print("Invalid input. Please enter 'y' or 'n'.")


# to register a new product to the watch list
if __name__ == "__main__":
    processor = S3DataHandler()
    processor.interactive_product_registration()
