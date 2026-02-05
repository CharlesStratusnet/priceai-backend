from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.parse
import os
import re

# Supabase credentials
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://apnwmtzgrtlzjbvxjdwc.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def scrape_woolworths(product_name):
    """Scrape price from Woolworths Australia"""
    try:
        search_term = urllib.parse.quote(product_name)
        url = f"https://www.woolworths.com.au/apis/ui/Search/products?searchTerm={search_term}&pageSize=1"
        
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        req.add_header("Accept", "application/json")
        
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            
            if data.get("Products") and len(data["Products"]) > 0:
                product = data["Products"][0]
                return {
                    "retailer": "woolworths",
                    "price": product.get("Price", 0),
                    "currency": "AUD",
                    "url": f"https://www.woolworths.com.au/shop/productdetails/{product.get('Stockcode', '')}"
                }
    except Exception as e:
        print(f"Woolworths scrape error: {e}")
    
    return None

def scrape_coles(product_name):
    """Scrape price from Coles Australia"""
    try:
        search_term = urllib.parse.quote(product_name)
        url = f"https://www.coles.com.au/api/search/v1/search?q={search_term}&page=1&ps=1"
        
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        req.add_header("Accept", "application/json")
        
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            
            results = data.get("results", [])
            if results and len(results) > 0:
                product = results[0]
                pricing = product.get("pricing", {})
                return {
                    "retailer": "coles",
                    "price": pricing.get("now", 0),
                    "currency": "AUD",
                    "url": f"https://www.coles.com.au/product/{product.get('id', '')}"
                }
    except Exception as e:
        print(f"Coles scrape error: {e}")
    
    return None

def save_price_to_db(product_id, price_data):
    """Save scraped price to Supabase"""
    if not SUPABASE_KEY or not price_data:
        return
    
    try:
        url = f"{SUPABASE_URL}/rest/v1/prices"
        data = json.dumps({
            "product_id": product_id,
            "retailer": price_data["retailer"],
            "price": price_data["price"],
            "currency": price_data["currency"],
            "url": price_data["url"]
        }).encode()
        
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("apikey", SUPABASE_KEY)
        req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Prefer", "return=minimal")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            pass
    except Exception as e:
        print(f"Save price error: {e}")

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse query parameters
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        product_name = params.get("product", [None])[0]
        product_id = params.get("product_id", [None])[0]
        
        if not product_name:
            self.send_response(400)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing product parameter"}).encode())
            return
        
        # Scrape prices from retailers
        prices = []
        
        woolworths_price = scrape_woolworths(product_name)
        if woolworths_price:
            prices.append(woolworths_price)
            if product_id:
                save_price_to_db(product_id, woolworths_price)
        
        coles_price = scrape_coles(product_name)
        if coles_price:
            prices.append(coles_price)
            if product_id:
                save_price_to_db(product_id, coles_price)
        
        # Build response
        response = {
            "product_name": product_name,
            "prices": prices,
            "retailers_checked": ["woolworths", "coles"]
        }
        
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())