import requests
import random
import time
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

# ✅ Configurations
EMAIL_ADDRESS = "your_email@gmail.com"
EMAIL_PASSWORD = "your_email_password"
TO_EMAIL = "receiver_email@gmail.com"
PRICE_THRESHOLD = 500
PRODUCT_URL = "https://www.amazon.com/dp/B09BG6GZDD"

# ✅ Rotating User-Agents
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

headers = {
    "User-Agent": random.choice(user_agents),
    "Referer": "https://www.amazon.com/",
    "Accept-Language": "en-US,en;q=0.9",
}

def get_amazon_price(url):
    """Scrape product price and title from Amazon"""
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    title = soup.find("span", id="productTitle")
    title = title.text.strip() if title else "No Title Found"

    price = soup.select_one(".a-price-whole")
    price = price.text.strip() if price else "Price Unavailable"

    availability = soup.select_one("#availability span")
    availability = availability.text.strip() if availability else "No Availability Info"

    return {"Title": title, "Price": price, "Availability": availability}

def save_price_to_csv(data, filename="amazon_prices.csv"):
    """Save price tracking data to CSV"""
    try:
        df = pd.read_csv(filename)
    except FileNotFoundError:
        df = pd.DataFrame(columns=["Title", "Price", "Availability", "Date"])

    data["Date"] = pd.Timestamp.now()
    df = df.append(data, ignore_index=True)

    df.to_csv(filename, index=False)

def send_email_alert(product, price):
    """Send an email alert when the price drops"""
    subject = f"🔥 Amazon Price Drop Alert: {product}!"
    body = f"The price of {product} has dropped to {price}!\nCheck it here: {PRODUCT_URL}"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, TO_EMAIL, msg.as_string())

# ✅ Run the tracker
product_data = get_amazon_price(PRODUCT_URL)
save_price_to_csv(product_data)

if int(product_data["Price"].replace(",", "")) <= PRICE_THRESHOLD:
    send_email_alert(product_data["Title"], product_data["Price"])
