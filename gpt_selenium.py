from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc

# 🚀 Configure Selenium to Evade Detection
options = Options()
options.add_argument("--headless")  # Run in background (optional)
options.add_argument("--disable-blink-features=AutomationControlled")  # Prevent bot detection
options.add_argument("start-maximized")

# 🚀 Start WebDriver
driver = uc.Chrome(service=Service(ChromeDriverManager().install()), options=options)

url = "https://www.amazon.com/dp/B0B38DLV5Z"
# 🚀 Load Amazon Page
driver.get(url)
time.sleep(5)  # Let the page load

# Find the element again
price_div = soup.find(id="corePriceDisplay_desktop_feature_div")
print(f"price div: {price_div}")


# The price can be located in different elements depending on the product page layout
price = soup.find(id="priceblock_ourprice") or soup.find(id="priceblock_dealprice")
print(f"Price found in priceblock: {price}")

if not price:
    price_div = soup.select_one("#corePriceDisplay_desktop_feature_div > div.a-section.a-spacing-none.aok-align-center.aok-relative")
    print(f"Price div found: {price_div}")
    if price_div:
        price_span = price_div.find("span", class_="a-price-whole")
        print(f"Price span found: {price_span}")
        if price_span:
            price = price_span.get_text().strip()
            fraction_span = price_div.find("span", class_="a-price-fraction")
            print(f"Fraction span found: {fraction_span}")
            if fraction_span:
                price += "." + fraction_span.get_text().strip()

if price:
    print(price)

# ✅ Close WebDriver
driver.quit()
