import time
from dataclasses import dataclass

import boto3

from app.s3_data_handler import ProductDTO, S3DataHandler


@dataclass
class PriceDropDTO:
    product_name: str
    url: str
    product_id: str
    previous_price: str
    current_price: str


# Athena constants
DATABASE = "amazon_products_historical_prices"
PRICE_TABLE_NAME = "amazon_products_historical_prices"
WORKGROUP = "amazon-product-price-drop-alert-app"
LOOKBACK_DAYS = 365


class PriceDataProcessor:
    def __init__(self):
        self.s3_data_handler = S3DataHandler()
        self.athena_client = boto3.client("athena")

    def check_price_drops(self) -> list[PriceDropDTO]:
        """
        retrieves the two most recent price files from S3, check for any price drops, and returns a list of PriceDropDTOs
        """
        previous_prices, current_prices = (
            self.s3_data_handler.get_two_most_recent_prices()
        )
        price_drops = []
        product_ids_with_drops = [
            product_id
            for product_id, previous_price in previous_prices.items()
            if float(current_prices.get(product_id, float("inf")))
            < float(previous_price)
        ]
        products_info = self.s3_data_handler.get_products_with_ids(
            product_ids_with_drops
        )

        for product_id in product_ids_with_drops:
            previous_price = previous_prices[product_id]
            current_price = current_prices[product_id]
            product_info: ProductDTO = products_info[product_id]
            price_drop_dto = PriceDropDTO(
                product_name=product_info.product_name,
                url=product_info.url,
                product_id=product_id,
                previous_price=previous_price,
                current_price=current_price,
            )
            price_drops.append(price_drop_dto)

        return price_drops

    def query_historical_prices(self, product_ids):
        # Format product_ids for SQL query
        formatted_ids = ", ".join(f"'{pid}'" for pid in product_ids)

        query = f"""
        SELECT
            product_id,
            date_parse(date, '%Y-%m-%d') AS date,
            price
        FROM {PRICE_TABLE_NAME}
        WHERE
            product_id IN ({formatted_ids})
            AND date_parse(date, '%Y-%m-%d') >= date_add('day', -{LOOKBACK_DAYS}, current_date)
        ORDER BY date DESC;
        """

        response = self.athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": DATABASE},
            WorkGroup=WORKGROUP,
        )

        query_execution_id = response["QueryExecutionId"]

        # Wait for query completion
        while True:
            status = self.athena_client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            state = status["QueryExecution"]["Status"]["State"]

            if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
                break
            time.sleep(1)

        if state != "SUCCEEDED":
            raise Exception(f"Athena query failed or cancelled: {state}")

        # Fetch results
        results_paginator = self.athena_client.get_paginator("get_query_results")
        results_iter = results_paginator.paginate(QueryExecutionId=query_execution_id)

        # Parse results
        rows = []
        column_info = None

        for results_page in results_iter:
            if column_info is None:
                column_info = [
                    col["Label"]
                    for col in results_page["ResultSet"]["ResultSetMetadata"][
                        "ColumnInfo"
                    ]
                ]

            for row in results_page["ResultSet"]["Rows"][1:]:  # Skip header row
                rows.append(
                    {
                        column_info[i]: col.get("VarCharValue", None)
                        for i, col in enumerate(row["Data"])
                    }
                )

        return rows


# just for testing
if __name__ == "__main__":
    processor = PriceDataProcessor()
    product_ids = ["280e749b8ced667c", "5bc4c45f96482a43"]
    print(processor.query_historical_prices(product_ids))
