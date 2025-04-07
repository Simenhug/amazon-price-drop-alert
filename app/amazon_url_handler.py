import random
import re
import time
from urllib.parse import quote, urlparse


class AmazonURLProcessor:
    def _extract_product_name(self, url: str) -> str:
        """
        Extracts product name from the Amazon URL if available.
        :param url: Full Amazon product URL
        :return: Product name in a formatted string
        """
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split("/")

        try:
            dp_index = path_parts.index("dp")
            product_name = path_parts[dp_index - 1].replace("-", " ")
            return product_name
        except (ValueError, IndexError):
            return "Amazon Product"

    def generate_human_like_amazon_url(self, url: str, search_keyword: str) -> str:
        """
        Transforms a simplified Amazon product URL into a more human-like version
        by adding tracking parameters and varying the structure.
        :param url: Simplified Amazon product URL (https://www.amazon.com/<product-name>/dp/<asin-number>)
        :param search_keywords: keywords used to search for the product, this will be used to construct the URL
        :return: Human-like Amazon product URL
        """
        parsed_url = urlparse(url)
        match = re.search(
            r"/dp/([A-Z0-9]{10})|/gp/product/([A-Z0-9]{10})", parsed_url.path
        )

        if match:
            asin = match.group(1) or match.group(2)
            product_name = self._extract_product_name(url).replace(" ", "-")
            encoded_keywords = quote(search_keyword)

            # Random tracking parameters
            qid = str(
                int(time.time())
            )  # Simulated search timestamp in Unix epoch format
            ref_options = [
                "sr_1_2",
                "sr_1_4",
                "sr_1_5",
                "sr_1_6",
                "sr_1_7",
                "sr_1_8",
                "sr_1_9",
                "sr_1_10",
                "sr_1_11",
                "sr_1_12",
                "sr_1_13",
                "sr_1_14",
                "nb_sb_noss_2",
                "nb_sb_noss_3",
                "nb_sb_ss_i_1_4",
                "sspa_dk_detail_0",
                "sspa_dk_detail_1",
                "sspa_cps_detail_2",
                "sponsored_products_auto",
                "sponsored_products_related",
                "srsr_1_1",
                "srsr_2_2",
                "ppx_yo_dt_b_search_asin_title",
            ]
            ref = random.choice(ref_options)

            url_format = f"https://www.amazon.com/{product_name}/dp/{asin}/?th=1&psc=1&ref_={ref}&qid={qid}&keywords={encoded_keywords}"

            return url_format

        return f"Invalid Amazon product URL: {url}"

    def get_simplified_amazon_url(self, url: str) -> str:
        """
        Simplifies an Amazon URL by removing tracking parameters and encoding.
        The simplified URL will be in the form of https://www.amazon.com/<product-name>/dp/<asin-number>
        The simplifed URL will be stored in the S3 databased.
        """
        parsed_url = urlparse(url)
        match = re.search(
            r"/dp/([A-Z0-9]{10})|/gp/product/([A-Z0-9]{10})", parsed_url.path
        )

        if match:
            asin = match.group(1) or match.group(2)
            product_name = self._extract_product_name(url).replace(" ", "-")
            return f"https://www.amazon.com/{product_name}/dp/{asin}"

        return f"Invalid Amazon product URL: {url}"
