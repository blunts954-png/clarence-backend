from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import os

app = FastAPI()

# --- SETUP ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Templates (for the UI)
templates = Jinja2Templates(directory="templates")

# --- BLUEPRINTS (From your PDF) ---
BLUEPRINTS = {
    "Cars & Trucks": ["date", "title", "price", "dist", "link"],
    "Housing": ["date", "title", "price", "housing", "link"],
    "Jobs": ["date", "title", "link"],
    "Services": ["date", "title", "link"]
}

class ScrapeRequest(BaseModel):
    target_url: str
    blueprint: str
    max_pages: int = 3

def setup_driver():
    options = Options()
    options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
    
    # Auto-install ChromeDriver
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

@app.get("/")
def home(request: Request):
    # Serves the Dark Mode UI
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/scrape")
def run_scraper(request: ScrapeRequest):
    print(f"--- INITIALIZING SIGNAL: {request.blueprint} ---")
    print(f"Target: {request.target_url}")
    
    driver = None
    all_data = []
    
    try:
        driver = setup_driver()
        driver.get(request.target_url)
        
        current_page = 1
        
        while current_page <= request.max_pages:
            print(f"Scanning Page {current_page}...")
            
            # Wait for results to load
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "result-info"))
                )
            except:
                print("No results found on this page.")
                break

            # SCRAPE ITEMS (CSS Selectors are faster and more reliable than AI here)
            items = driver.find_elements(By.CLASS_NAME, "result-info")
            print(f"Found {len(items)} items on page {current_page}.")
            
            for item in items:
                try:
                    # Universal Extraction based on Craigslist structure
                    data = {}
                    
                    # Title & Link
                    try:
                        title_el = item.find_element(By.CLASS_NAME, "posting-title")
                        data['title'] = title_el.text
                        data['link'] = title_el.find_element(By.TAG_NAME, "a").get_attribute("href")
                    except: continue

                    # Price
                    try:
                        data['price'] = item.find_element(By.CLASS_NAME, "price").text
                    except: data['price'] = "N/A"

                    # Meta (Location/Odometer)
                    try:
                        data['meta'] = item.find_element(By.CLASS_NAME, "meta").text
                    except: data['meta'] = ""

                    all_data.append(data)
                except:
                    continue
            
            # PAGINATION LOGIC
            if current_page < request.max_pages:
                try:
                    # Look for the 'next' button
                    next_button = driver.find_element(By.CLASS_NAME, "next")
                    
                    # Craigslist keeps the 'next' button but adds a "disabled" class if no pages left? 
                    # Actually usually it just stops linking. We check standard behavior.
                    if "disabled" in next_button.get_attribute("class"): 
                        print("End of list reached.")
                        break

                    print("Clicking NEXT page...")
                    driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(3) # Wait for load
                    current_page += 1
                except:
                    print("Next button not found. Stopping.")
                    break
            else:
                break
                
        print(f"--- MISSION COMPLETE. Collected {len(all_data)} items. ---")
        return {"status": "success", "count": len(all_data), "data": all_data}

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return {"status": "error", "message": str(e)}
    
    finally:
        if driver:
            driver.quit()