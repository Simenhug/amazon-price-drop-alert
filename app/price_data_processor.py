from dataclasses import dataclass

from app.s3_data_handler import ProductDTO, S3DataHandler


@dataclass
class PriceDropDTO:
    product_name: str
    url: str
    product_id: str
    previous_price: str
    current_price: str


class PriceDataProcessor:
    def __init__(self):
        self.s3_data_handler = S3DataHandler()

    def check_price_drops(self) -> list[PriceDropDTO]:
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
