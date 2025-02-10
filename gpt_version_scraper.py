import requests
import random
import time
from bs4 import BeautifulSoup


# 🚀 Rotating User-Agents
user_agents = [
    # 🖥️ Windows User-Agents
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/115.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:92.0) Gecko/20100101 Firefox/92.0",

    # 🍏 macOS User-Agents
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_5_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/115.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14) AppleWebKit/537.36 (KHTML, like Gecko) Safari/604.1.38",

    # 🐧 Linux User-Agents
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/109.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",

    # 📱 Mobile User-Agents (Less Bot Detection!)
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/537.36",
    "Mozilla/5.0 (Android 13; Mobile; rv:119.0) Gecko/119.0 Firefox/119.0",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; SM-A715F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
]


# ✅ Amazon Search URL
search_query = "laptop"
url = "https://www.amazon.com/dp/B0B38DLV5Z"

# 🚀 Headers to Bypass Detection
headers = {
    "User-Agent": random.choice(user_agents),
    "Referer": "https://www.amazon.com/",
    "Accept-Language": "en-US,en;q=0.9",
}

# 🚀 Using a Session for Persistence
session = requests.Session()
session.headers.update(headers)

# 🚀 Fetch Search Results
response = session.get(url)
print(f"HTTP Status Code: {response.status_code}")
soup = BeautifulSoup(response.text, "html.parser")
# print(soup.prettify()[:1000])  # Print the first 1000 characters of the HTML content

# Find the element again
price_div = soup.find(id="corePriceDisplay_desktop_feature_div")
# print(f"price div: {price_div}")


# The price can be located in different elements depending on the product page layout
price = soup.find(id="priceblock_ourprice") or soup.find(id="priceblock_dealprice")
print(f"Price found in priceblock: {price}")

if not price:
    price_div = soup.select_one("#corePriceDisplay_desktop_feature_div > div.a-section.a-spacing-none.aok-align-center.aok-relative")
    # print(f"Price div found: {price_div}")
    if price_div:
        price_span = price_div.find("span", class_="a-price-whole")
        print(f"Price span found: {price_span}")
        if price_span:
            price = price_span.get_text().strip()
            fraction_span = price_div.find("span", class_="a-price-fraction")
            print(f"Fraction span found: {fraction_span}")
            if fraction_span:
                price +=  fraction_span.get_text().strip()
                print(price_span.get_text().strip())
                print(fraction_span.get_text().strip())

if price:
    print(price)

# ✅ Random Delay to Avoid Detection
time.sleep(random.uniform(2, 5))


