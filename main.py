from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
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
    # In production, load this from a secure environment variable or mounted secret
    # For now, we assume the file is copied into the container
    try:
        with open("proxies.txt", "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
        return random.choice(proxies) if proxies else None
    except:
        return None

def setup_driver(use_proxy=False):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    if use_proxy:
        proxy = get_proxy()
        if proxy:
            chrome_options.add_argument(f'--proxy-server={proxy}')

    # Render-specific binary location (handled by Dockerfile later)
    chrome_options.binary_location = "/usr/bin/google-chrome"
    
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def smart_scroll(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(3): # Reduced for speed in API mode
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

def extract_data(html, job_niche):
    soup = BeautifulSoup(html, 'html.parser')
    # Simplified extraction logic for the API demo
    results = []
    # Logic to target specific Craigslist list items would go here
    # For the MVP, we just return raw text length to prove it worked
    text = soup.get_text()
    return {"status": "scraped", "data_length": len(text), "sample": text[:200]}

# --- ENDPOINT ---
@app.post("/scrape")
async def run_scraper(request: ScrapeRequest):
    print(f"Received mission: {request.city} - {request.job_niche}")
    
    # URL Construction
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
        
        # In a real run, you'd pass 'html' to your OpenAI function here
        # data = universal_extract(html) 
        
        data = extract_data(html, request.job_niche)
        
        return {"success": True, "target": url, "result": data}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if driver:
            driver.quit()