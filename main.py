from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
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

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATA MODELS ---
class ScrapeRequest(BaseModel):
    target_url: str
    data_blueprint: str
    proxy_mode: bool = True
    max_pages: int = 1 # New Parameter

# --- CORE LOGIC ---
def get_proxy():
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
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.binary_location = "/usr/bin/chromium"

    if use_proxy:
        proxy = get_proxy()
        if proxy:
            chrome_options.add_argument(f'--proxy-server={proxy}')

    service = Service("/usr/bin/chromedriver")
    return webdriver.Chrome(service=service, options=chrome_options)

def smart_scroll(driver):
    # Aggressive Scroll to trigger all lazy loads
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(5): 
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)

def ai_analyze_page(html, blueprint):
    """
    Extracts Data AND the 'Next Page' link in one pass.
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Cleaning noise
    for script in soup(["script", "style", "nav", "footer", "iframe"]):
        script.decompose()
        
    # MASTER MODE: Increased limit to 50,000 chars to catch all 68 cars
    text_content = soup.get_text(separator=' ', strip=True)[:50000]

    prompt = f"""
    Task 1: Extract a list of items based on: {blueprint}.
    Task 2: Find the "Next Page" or "Load More" URL if it exists.
    
    Return JSON format only:
    {{
        "items": [ {{...}}, {{...}} ],
        "next_page_url": "FULL_URL_HERE_OR_NULL"
    }}
    
    Text Source: {text_content}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"items": [], "next_page_url": None, "error": str(e)}

# --- ENDPOINTS ---
@app.get("/")
def home():
    return {"status": "Clarence 6.0 | Master Backend Online"}

@app.post("/scrape")
async def run_scraper(request: ScrapeRequest):
    print(f"Mission: {request.target_url} | Pages: {request.max_pages}")
    
    driver = None
    all_items = []
    current_url = request.target_url
    pages_scraped = 0
    
    try:
        driver = setup_driver(request.proxy_mode)
        
        while pages_scraped < request.max_pages and current_url:
            print(f"Scraping Page {pages_scraped + 1}: {current_url}")
            
            driver.get(current_url)
            smart_scroll(driver)
            html = driver.page_source
            
            # AI Extraction
            analysis = ai_analyze_page(html, request.data_blueprint)
            
            # Collect Items
            if "items" in analysis:
                all_items.extend(analysis["items"])
            
            # Logic for Next Page
            next_url = analysis.get("next_page_url")
            
            # Simple validation to ensure AI isn't hallucinating bad links
            if next_url and next_url.startswith("http") and next_url != current_url:
                current_url = next_url
            else:
                current_url = None # Stop loop if no valid link
                
            pages_scraped += 1
            time.sleep(1) # Be polite
        
        return {
            "success": True, 
            "pages_processed": pages_scraped,
            "total_items": len(all_items),
            "result": {"items": all_items}
        }
        
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if driver:
            driver.quit()