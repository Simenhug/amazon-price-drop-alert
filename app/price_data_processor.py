import base64
import os
import sys

# Check if running in AWS Lambda (AWS_LAMBDA_FUNCTION_NAME is set in Lambda runtime)
if "AWS_LAMBDA_FUNCTION_NAME" in os.environ:
    sys.path.append("/opt/python")

import time
from dataclasses import dataclass

import boto3
import pandas as pd
import plotly.express as px

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
        """
        query all available historical prices for the given product_ids for the last 365 days
        returns a list of dictionaries, each dict contains product_id, date, and price
        like [{'product_id': '123abc', 'date': '2025-02-23 00:00:00.000', 'price': '149.99'}]
        """
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

    def plot_price_graphs(self, data: list[dict[str, str]]) -> dict[str, str]:
        """
        takes in list of price data, returns base64 encoded PNG images for each product
        :param data: list of dictionaries like [{'product_id': '123abc', 'date': '2025-02-23 00:00:00.000', 'price': '149.99'}]
        :return: dictionary mapping product_id to base64 encoded PNG image string
        """
        # Convert input data to DataFrame
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])  # Ensure dates are in datetime format
        df["price"] = df["price"].astype(float)  # Ensure price is float

        # Group data by product_id
        product_groups = df.groupby("product_id")

        graphs = {}

        for product_id, group in product_groups:
            # Sort by date
            group = group.sort_values(by="date")

            # Create a date range from min to max date
            full_date_range = pd.date_range(
                start=group["date"].min(), end=group["date"].max(), freq="D"
            )

            # Reindex with full date range and forward fill missing prices
            group = (
                group.set_index("date").reindex(full_date_range).ffill().reset_index()
            )
            group.rename(columns={"index": "date"}, inplace=True)

            # Get product info for title
            product = self.s3_data_handler.get_product_by_id(product_id)

            # Create plotly figure
            fig = px.line(
                group,
                x="date",
                y="price",
                title=f"Price Trend for {product.product_name}",
                markers=True,
            )

            # Customize the layout
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="Price",
                xaxis=dict(
                    tickangle=45,
                    tickformat="%Y-%m-%d",
                ),
                showlegend=False,
                template="plotly_white",
                margin=dict(l=50, r=50, t=50, b=50),
            )

            # Convert to base64 encoded PNG
            img_bytes = fig.to_image(format="png", width=800, height=400)
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")
            graphs[product_id] = img_base64

        return graphs


# just for testing
if __name__ == "__main__":
    processor = PriceDataProcessor()
    product_ids = ["280e749b8ced667c", "5bc4c45f96482a43"]
    # print(processor.query_historical_prices(product_ids))
    data = [
        {
            "product_id": "280e749b8ced667c",
            "date": "2024-01-01 00:00:00.000",
            "price": "149.99",
        },
        {
            "product_id": "280e749b8ced667c",
            "date": "2024-02-01 00:00:00.000",
            "price": "139.99",
        },
        {
            "product_id": "280e749b8ced667c",
            "date": "2024-03-01 00:00:00.000",
            "price": "129.99",
        },
        {
            "product_id": "5bc4c45f96482a43",
            "date": "2024-01-01 00:00:00.000",
            "price": "299.99",
        },
        {
            "product_id": "5bc4c45f96482a43",
            "date": "2024-02-01 00:00:00.000",
            "price": "279.99",
        },
        {
            "product_id": "5bc4c45f96482a43",
            "date": "2024-03-01 00:00:00.000",
            "price": "259.99",
        },
    ]
    graphs = processor.plot_price_graphs(data)
    print(f"Generated {len(graphs)} graphs")

    # Save graphs as files
    for product_id, graph_data in graphs.items():
        # Decode base64 to bytes
        img_bytes = base64.b64decode(graph_data)
        # Save to file
        filename = f"price_graph_{product_id}.png"
        with open(filename, "wb") as f:
            f.write(img_bytes)
        print(f"Saved graph for product {product_id} to {filename}")
