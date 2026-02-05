from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.parse
import os

# Supabase credentials
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://apnwmtzgrtlzjbvxjdwc.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def get_product_info(barcode):
    """Get product info from UPCitemdb (free trial endpoint)"""
    url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={barcode}"
    
    try:
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
            if data.get("items") and len(data["items"]) > 0:
                item = data["items"][0]
                return {
                    "name": item.get("title", "Unknown Product"),
                    "brand": item.get("brand", ""),
                    "image": item.get("images", [""])[0] if item.get("images") else "",
                    "description": item.get("description", "")
                }
    except Exception as e:
        print(f"UPCitemdb error: {e}")
    
    return None

def get_cached_prices(barcode):
    """Check Supabase for cached prices"""
    if not SUPABASE_KEY:
        return None
    
    try:
        # First get product_id from barcode
        url = f"{SUPABASE_URL}/rest/v1/products?barcode=eq.{barcode}&select=id"
        req = urllib.request.Request(url)
        req.add_header("apikey", SUPABASE_KEY)
        req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            products = json.loads(response.read().decode())
            
            if products and len(products) > 0:
                product_id = products[0]["id"]
                
                # Get prices for this product
                prices_url = f"{SUPABASE_URL}/rest/v1/prices?product_id=eq.{product_id}&select=*&order=created_at.desc&limit=10"
                req2 = urllib.request.Request(prices_url)
                req2.add_header("apikey", SUPABASE_KEY)
                req2.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
                
                with urllib.request.urlopen(req2, timeout=5) as response2:
                    return json.loads(response2.read().decode())
    except Exception as e:
        print(f"Supabase error: {e}")
    
    return None

def calculate_verdict(prices):
    """Calculate if this is a good deal"""
    if not prices or len(prices) == 0:
        return {"verdict": "UNKNOWN", "message": "No price data available"}
    
    current_price = prices[0]["price"]
    all_prices = [p["price"] for p in prices if p["price"]]
    
    if len(all_prices) < 2:
        return {"verdict": "FAIR", "message": "Not enough price history"}
    
    avg_price = sum(all_prices) / len(all_prices)
    min_price = min(all_prices)
    max_price = max(all_prices)
    
    if current_price <= min_price * 1.05:
        return {"verdict": "GOOD_DEAL", "message": f"This is near the lowest price! (Avg: ${avg_price:.2f})"}
    elif current_price >= max_price * 0.95:
        return {"verdict": "BAD_DEAL", "message": f"This is near the highest price. Wait for a sale. (Avg: ${avg_price:.2f})"}
    elif current_price < avg_price:
        return {"verdict": "FAIR", "message": f"Below average price. (Avg: ${avg_price:.2f})"}
    else:
        return {"verdict": "WAIT", "message": f"Above average price. Consider waiting. (Avg: ${avg_price:.2f})"}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse query parameters
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        barcode = params.get("barcode", [None])[0]
        
        if not barcode:
            self.send_response(400)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Missing barcode parameter"}).encode())
            return
        
        # Get product info
        product = get_product_info(barcode)
        
        # Get cached prices
        prices = get_cached_prices(barcode)
        
        # Calculate verdict
        verdict = calculate_verdict(prices) if prices else {"verdict": "UNKNOWN", "message": "Scan again to fetch prices"}
        
        # Build response
        response = {
            "barcode": barcode,
            "product": product,
            "prices": prices,
            "verdict": verdict
        }
        
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())