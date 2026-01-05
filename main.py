from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import os
import random
import re

# --- CONFIG ---
app = FastAPI()

# --- MODELS ---
class ScrapeRequest(BaseModel):
    city: str
    job_niche: str
    category: str = "jobs"
    proxy_mode: bool = False

# --- UTILS ---
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # This path is specific to Render's Docker environment
    chrome_options.binary_location = "/usr/bin/google-chrome" 
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def clean_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    # Remove junk
    for x in soup(["script", "style", "nav", "footer", "noscript", "header"]):
        x.decompose()
    # Get text
    text = soup.get_text(separator=' ', strip=True)
    return text[:5000] # Limit to 5000 chars to save tokens/bandwidth

# --- ENDPOINTS ---
@app.get("/")
def home():
    return {"status": "Signal Backend Operational"}

@app.post("/scrape")
async def run_scraper(request: ScrapeRequest):
    driver = None
    try:
        # 1. URL Construction
        cat_map = {"jobs": "jjj", "gigs": "ggg", "for_sale": "sss"}
        cat_code = cat_map.get(request.category, "jjj")
        url = f"https://{request.city}.craigslist.org/search/{cat_code}?query={request.job_niche.replace(' ', '+')}"
        
        # 2. Scrape
        driver = setup_driver()
        driver.get(url)
        
        # Simple scroll
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # 3. Extract
        raw_html = driver.page_source
        clean_text = clean_html(raw_html)
        
        # 4. Return
        return {
            "success": True,
            "target_url": url,
            "result": clean_text  # Sending clean text to frontend
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
    
    finally:
        if driver:
            driver.quit()