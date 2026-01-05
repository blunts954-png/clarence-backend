from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import os
import logging

# --- LOGGING SETUP ---
# This ensures errors show up in your Render logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    
    # SAFETY FIX: Removed hardcoded binary_location. 
    # We let Selenium find Chrome automatically.
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize Chrome Driver: {e}")
        raise e

def clean_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    for x in soup(["script", "style", "nav", "footer", "noscript", "header"]):
        x.decompose()
    text = soup.get_text(separator=' ', strip=True)
    return text[:5000]

# --- ENDPOINTS ---
@app.get("/")
def home():
    return {"status": "Signal Backend Operational", "version": "Safe-Mode-1.0"}

@app.post("/scrape")
async def run_scraper(request: ScrapeRequest):
    driver = None
    logger.info(f"Received scrape request for: {request.city} / {request.job_niche}")
    
    try:
        # 1. URL Construction
        cat_map = {"jobs": "jjj", "gigs": "ggg", "for_sale": "sss"}
        cat_code = cat_map.get(request.category, "jjj")
        url = f"https://{request.city}.craigslist.org/search/{cat_code}?query={request.job_niche.replace(' ', '+')}"
        
        # 2. Scrape
        logger.info("Initializing Driver...")
        driver = setup_driver()
        
        logger.info(f"Navigating to {url}...")
        driver.get(url)
        
        # Simple scroll
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # 3. Extract
        raw_html = driver.page_source
        clean_text = clean_html(raw_html)
        logger.info("Scrape successful.")
        
        # 4. Return
        return {
            "success": True,
            "target_url": url,
            "result": clean_text
        }

    except Exception as e:
        logger.error(f"Scrape Error: {str(e)}")
        # This will return the actual error to your frontend instead of just crashing
        return {"success": False, "error": str(e)}
    
    finally:
        if driver:
            driver.quit()