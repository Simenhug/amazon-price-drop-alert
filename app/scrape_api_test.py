import requests


def test_scraper():
    proxy = {
        "https": "http://scraperapi.render=true.device_type=mobile.country_code=us:9a7e51a7bc21ee366e3f38dd27a2b703@proxy-server.scraperapi.com:8001"
    }

    test_url = (
        "https://httpbin.org/ip"  # A simple service that returns the IP of the request
    )

    response = requests.get(test_url, proxies=proxy, verify=False)

    print(f"HTTP Status Code: {response.status_code}")
    print(f"Response Content: {response.text}")


def test_scraper_api_can_access_amazon():
    proxy = {
        "https": "http://scraperapi.render=true.device_type=mobile.country_code=us:9a7e51a7bc21ee366e3f38dd27a2b703@proxy-server.scraperapi.com:8001"
    }
    test_url = "https://www.amazon.com/dp/B0DPLYGYXV"  # Product URL

    response = requests.get(test_url, proxies=proxy, verify=False)

    print(f"HTTP Status Code: {response.status_code}")
    print(f"Response Content (First 500 chars): {response.text[:500]}")
