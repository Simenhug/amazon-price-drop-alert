import time
from dataclasses import dataclass
from typing import Optional

import boto3
import matplotlib.pyplot as plt
import pandas as pd

from app.s3_data_handler import ProductDTO, S3DataHandler


@dataclass
class PriceDropDTO:
    product_name: str
    url: str
    product_id: str
    previous_price: str
    current_price: str
    price_chart_path: Optional[str] = None


@dataclass
class ProductSummaryDTO:
    product_name: str
    url: str
    product_id: str
    current_price: str
    price_chart_path: Optional[str] = None
    has_price_drop: bool = False
    previous_price: Optional[str] = None


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
        DEPRECATED: retrieves the two most recent price files from S3, check for any price drops, and returns a list of PriceDropDTOs
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

    def get_all_products_with_current_prices(self) -> list[ProductSummaryDTO]:
        """
        Get all registered products with their current prices
        """
        previous_prices, current_prices = (
            self.s3_data_handler.get_two_most_recent_prices()
        )
        all_products = self.s3_data_handler.list_registered_products()
        product_summaries = []

        for product in all_products:
            current_price = current_prices.get(product.product_id, "N/A")
            previous_price = previous_prices.get(product.product_id)
            has_price_drop = False

            if previous_price and current_price != "N/A":
                has_price_drop = float(current_price) < float(previous_price)

            product_summary = ProductSummaryDTO(
                product_name=product.product_name,
                url=product.url,
                product_id=product.product_id,
                current_price=current_price,
                has_price_drop=has_price_drop,
                previous_price=previous_price,
            )
            product_summaries.append(product_summary)

        return product_summaries

    def price_graph_for_past_year(self):
        """
        generate a price graph for the past year for all products and display them
        """
        products = self.s3_data_handler.list_registered_products()
        product_ids = [product.product_id for product in products]
        historical_prices = self.query_historical_prices(product_ids)
        graphs = self._plot_price_graphs(historical_prices, return_graph=True)

        # Import required modules outside the loop
        from io import BytesIO

        import matplotlib.image as mpimg
        import matplotlib.pyplot as plt

        # Display the graphs
        for product_id, png_data in graphs.items():
            # Create a figure to display the image
            plt.figure(figsize=(8, 4))
            img = mpimg.imread(BytesIO(png_data))
            plt.imshow(img)
            plt.axis("off")  # Hide axes
            plt.show()

    def query_historical_prices(self, product_ids) -> list[dict[str, str]]:
        """
        query all available historical prices for the given product_ids for the last 365 days

        :return: a list of dictionaries, each dict contains product_id, date, and price
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

    def plot_price_graphs(self, price_drops: list[PriceDropDTO]) -> list[PriceDropDTO]:
        """
        DEPRECATED: Takes in a list of PriceDropDTOs, generates pyplot figures for each product,
        and saves them as image files. Update the PriceDropDTO with the file path of the saved image.
        :param price_drops: list of PriceDropDTOs
        :return: PriceDropDTOs with updated price_chart_path (DEPRECATED)
        """
        product_ids = [price_drop.product_id for price_drop in price_drops]
        historical_prices = self.query_historical_prices(product_ids)
        graphs = self._plot_price_graphs(historical_prices)
        for price_drop in price_drops:
            price_drop.price_chart_path = graphs.get(price_drop.product_id)
        return price_drops

    def generate_price_graphs_for_products(
        self, products: list[ProductSummaryDTO]
    ) -> list[ProductSummaryDTO]:
        """
        Generate price graphs for any list of products
        :param products: list of ProductSummaryDTOs
        :return: ProductSummaryDTOs with updated price_chart_path
        """
        product_ids = [product.product_id for product in products]
        historical_prices = self.query_historical_prices(product_ids)
        graphs = self._plot_price_graphs(historical_prices)
        for product in products:
            product.price_chart_path = graphs.get(product.product_id)
        return products

    def create_product_summary(self) -> list[ProductSummaryDTO]:
        """
        Create summary data for email with price drops emphasized
        """
        all_products = self.get_all_products_with_current_prices()
        # Generate price graphs for all products
        all_products_with_graphs = self.generate_price_graphs_for_products(all_products)
        # Sort products with price drops first
        all_products_with_graphs.sort(
            key=lambda x: (not x.has_price_drop, x.product_name)
        )
        return all_products_with_graphs

    def _plot_price_graphs(
        self, data: list[dict[str, str]], return_graph: bool = False
    ) -> dict[str, str | bytes]:
        """
        Takes in a list of price data for multiple products, generates pyplot figures for each product,
        and saves them as image files.
        :param data: list of dictionaries like [{'product_id': '123abc', 'date': '2025-02-23 00:00:00.000', 'price': '149.99'}]
        :param return_graph: if True, returns the graph data in PNG format instead of saving to file
        :return: A dictionary mapping product IDs to file paths (str) or PNG data (bytes) if return_graph is True
        """
        # Convert input data to DataFrame
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])  # Ensure dates are in datetime format
        df["price"] = df["price"].astype(float)  # Ensure price is float

        # Group data by product_id
        product_groups = df.groupby("product_id")

        image_paths = {}

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

            # Create figure and plot price graph
            fig, ax = plt.subplots(
                figsize=(6, 3)
            )  # Adjusted figure size to make it smaller
            ax.plot(group["date"], group["price"], marker="o", linestyle="-")
            ax.set_xlabel("Date")
            ax.set_ylabel("Price")
            product = self.s3_data_handler.get_product_by_id(product_id)
            ax.set_title(f"Price Trend for {product.product_name}")
            ax.tick_params(axis="x", rotation=45)
            ax.grid(True)

            # Adjust layout to prevent x-axis labels from being cut off
            fig.tight_layout()

            if return_graph:
                # Return the graph as PNG data
                import io

                buf = io.BytesIO()
                fig.savefig(buf, format="png", dpi=150)
                buf.seek(0)
                image_paths[product_id] = buf.getvalue()
            else:
                # Save the figure as an image
                image_path = f"/tmp/{product_id}_price_trend.png"
                fig.savefig(
                    image_path, format="png", dpi=150
                )  # Adjusted DPI for smaller file size
                image_paths[product_id] = image_path

            plt.close(fig)  # Close the figure to free memory

        return image_paths


class PriceDataProcessorTestingTool:
    """
    A testing tool for PriceDataProcessor.
    """

    def __init__(self):
        self.data_processor = PriceDataProcessor()

    def test_plot_price_graphs(self):
        data = [
            {
                "product_id": "280e749b8ced667c",
                "date": "2025-02-23 00:00:00.000",
                "price": "149.99",
            },
            {
                "product_id": "280e749b8ced667c",
                "date": "2025-02-22 00:00:00.000",
                "price": "159.99",
            },
            {
                "product_id": "280e749b8ced667c",
                "date": "2025-02-21 00:00:00.000",
                "price": "169.99",
            },
            {
                "product_id": "280e749b8ced667c",
                "date": "2025-02-20 00:00:00.000",
                "price": "179.99",
            },
            {
                "product_id": "280e749b8ced667c",
                "date": "2025-02-19 00:00:00.000",
                "price": "189.99",
            },
            {
                "product_id": "5bc4c45f96482a43",
                "date": "2025-02-23 00:00:00.000",
                "price": "299.99",
            },
            {
                "product_id": "5bc4c45f96482a43",
                "date": "2025-02-22 00:00:00.000",
                "price": "309.99",
            },
            {
                "product_id": "5bc4c45f96482a43",
                "date": "2025-02-21 00:00:00.000",
                "price": "319.99",
            },
            {
                "product_id": "5bc4c45f96482a43",
                "date": "2025-02-20 00:00:00.000",
                "price": "329.99",
            },
            {
                "product_id": "5bc4c45f96482a43",
                "date": "2025-02-19 00:00:00.000",
                "price": "339.99",
            },
        ]
        graphs = self.data_processor._plot_price_graphs(data)
        print(graphs)

    def test_check_price_drops_and_plot_graphs(self):
        product_summaries = self.data_processor.create_product_summary()
        print(f"Found {len(product_summaries)} products in watchlist")
        price_drops = [p for p in product_summaries if p.has_price_drop]
        print(f"Found {len(price_drops)} products with price drops")
        for product in product_summaries:
            print(
                f"Product: {product.product_name}, Current Price: ${product.current_price}, Has Price Drop: {product.has_price_drop}"
            )

    def test_price_graph_for_past_year(self):
        self.data_processor.price_graph_for_past_year()


# just for testing
if __name__ == "__main__":
    test = PriceDataProcessorTestingTool()
    # test.test_check_price_drops_and_plot_graphs()
    # test.test_plot_price_graphs()
    test.test_price_graph_for_past_year()
