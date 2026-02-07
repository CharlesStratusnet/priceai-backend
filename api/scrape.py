import os
import json
import requests
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


def handler(request):
    """Scrape prices from Amazon using Real-Time Amazon Data API on RapidAPI."""

    query_params = parse_qs(urlparse(request.path).query)
    product_name = query_params.get("product", [None])[0]

    if not product_name:
        request.send_response(400)
        request.send_header("Content-type", "application/json")
        request.end_headers()
        request.wfile.write(json.dumps({"error": "Product name is required. Use ?product=YourProduct"}).encode("utf-8"))
        return

    rapidapi_key = os.environ.get("RAPIDAPI_KEY")
    if not rapidapi_key:
        request.send_response(500)
        request.send_header("Content-type", "application/json")
        request.end_headers()
        request.wfile.write(json.dumps({"error": "RAPIDAPI_KEY not configured"}).encode("utf-8"))
        return

    # Search Amazon for the product
    url = "https://real-time-amazon-data.p.rapidapi.com/search"
    querystring = {"query": product_name, "country": "AU"}
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "real-time-amazon-data.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=15)
        data = response.json()

        prices = []
        if data.get("status") == "OK" and data.get("data") and data["data"].get("products"):
            for product in data["data"]["products"][:5]:  # Top 5 results
                price_info = {
                    "retailer": "amazon_au",
                    "name": product.get("product_title", "Unknown"),
                    "price": product.get("product_price", "N/A"),
                    "original_price": product.get("product_original_price", "N/A"),
                    "rating": product.get("product_star_rating", "N/A"),
                    "reviews": product.get("product_num_ratings", 0),
                    "is_prime": product.get("is_prime", False),
                    "url": product.get("product_url", ""),
                    "image": product.get("product_photo", "")
                }
                prices.append(price_info)

        result = {
            "product_name": product_name,
            "prices": prices,
            "retailers_checked": ["amazon_au"],
            "total_results": len(prices)
        }

        request.send_response(200)
        request.send_header("Content-type", "application/json")
        request.end_headers()
        request.wfile.write(json.dumps(result).encode("utf-8"))

    except Exception as e:
        request.send_response(500)
        request.send_header("Content-type", "application/json")
        request.end_headers()
        request.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    return