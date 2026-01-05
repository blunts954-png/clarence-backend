from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import time
import json
import random
import os
import re
import openai
from dotenv import load_dotenv

# Initialize App
app = FastAPI()
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- DATA MODELS ---
class ScrapeRequest(BaseModel):
    city: str
    job_niche: str
    category: str = "jobs" # jobs, gigs, for_sale
    proxy_mode: bool = True

# --- CORE LOGIC ---
def get_proxy():
    # In production, this would load from a secure env var or file
    try:
        if os.path.exists("proxies.txt"):
            with open("proxies.txt", "r") as f:
                proxies = [line.strip() for line in f if line.strip()]
            return random.choice(proxies) if proxies else None
    except:
        pass
    return None

def setup_driver(use_proxy=False):
    chrome_options = Options()
    # Core Headless Options
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # Point to the installed Chromium (The fix for Error 127)
    chrome_options.binary_location = "/usr/bin/chromium"

    if use_proxy:
        proxy = get_proxy()
        if proxy:
            chrome_options.add_argument(f'--proxy-server={proxy}')

    # Use the pre-installed system driver
    service = Service("/usr/bin/chromedriver")
    
    return webdriver.Chrome(service=service, options=chrome_options)

def smart_scroll(driver):
    # Scroll down to trigger lazy-loaded items
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(3): # Short scroll for speed in API mode
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

def extract_data(html, job_niche):
    soup = BeautifulSoup(html, 'html.parser')
    
    # Simple extraction logic to verify the scraper works
    # In the future, this is where you connect the AI extraction
    text_content = soup.get_text()
    clean_text = re.sub(r'\s+', ' ', text_content).strip()
    
    return {
        "status": "success", 
        "data_length": len(clean_text), 
        "preview": clean_text[:200]
    }

# --- ENDPOINT ---
@app.get("/")
def home():
    return {"status": "Clarence Backend Online", "version": "6.0"}

@app.post("/scrape")
async def run_scraper(request: ScrapeRequest):
    print(f"Received mission: {request.city} - {request.job_niche}")
    
    # URL Construction for Craigslist
    base = f"https://{request.city}.craigslist.org/search/"
    cat_map = {"jobs": "jjj", "gigs": "ggg", "for_sale": "sss"}
    cat_code = cat_map.get(request.category, "jjj")
    
    url = f"{base}{cat_code}?query={request.job_niche.replace(' ', '+')}"
    
    driver = None
    try:
        driver = setup_driver(request.proxy_mode)
        driver.get(url)
        smart_scroll(driver)
        html = driver.page_source
        
        # Extract data
        data = extract_data(html, request.job_niche)
        
        return {"success": True, "target": url, "result": data}
        
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if driver:
            driver.quit()