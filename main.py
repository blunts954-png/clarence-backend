from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import re
import os

app = FastAPI()

# --- PRODUCTION CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for now to prevent handshake errors
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# --- DATA MODELS ---
class ScrapeRequest(BaseModel):
    target_url: str
    data_blueprint: str 
    max_pages: int = 1

# --- CHROME SETUP (HEADLESS SERVER MODE) ---
def setup_driver():
    options = Options()
    options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # Masking as a real user to avoid immediate blocking
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

# --- UNIVERSAL PARSER ---
def extract_universal(element, blueprint_key):
    text = element.text
    data = {}
    
    # 1. Title Heuristics
    try:
        title_el = element.find_element(By.CSS_SELECTOR, "h1, h2, h3, h4, .title, .name, a.posting-title")
        data['Title'] = title_el.text.strip()
    except:
        data['Title'] = text.split('\n')[0] if text else "Unknown"

    # 2. Link Extraction
    try:
        link_el = element.find_element(By.TAG_NAME, "a")
        data['Link'] = link_el.get_attribute("href")
    except:
        data['Link'] = "#"

    # 3. Price Regex
    price_match = re.search(r'\$[\d,]+', text)
    data['Price'] = price_match.group(0) if price_match else "N/A"

    # 4. Blueprint Specifics (From PDF Source 1)
    if blueprint_key == "cars":
        miles = re.search(r'(\d{1,3}(?:,\d{3})*)\s*(?:mi|miles)', text, re.IGNORECASE)
        data['Odometer'] = miles.group(0) if miles else "N/A"
        
    elif blueprint_key == "housing":
        beds = re.search(r'(\d+)\s*(?:br|bed)', text, re.IGNORECASE)
        sqft = re.search(r'(\d{3,5})\s*(?:sq|ft)', text, re.IGNORECASE)
        data['Specs'] = f"{beds.group(0) if beds else ''} {sqft.group(0) if sqft else ''}".strip()

    elif blueprint_key == "jobs":
        # Look for pay rates
        comp = re.search(r'\$[\d,]+(?:\.\d+)?\s*(?:hr|hour|yr)', text, re.IGNORECASE)
        data['Comp'] = comp.group(0) if comp else "N/A"

    return data

# --- ENDPOINTS ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/scrape")
async def run_scraper(request: ScrapeRequest):
    print(f"--- SIGNAL LOCKED: {request.target_url} ---")
    
    driver = None
    all_items = []
    
    try:
        driver = setup_driver()
        driver.get(request.target_url)
        time.sleep(3) # Cloud latency buffer
        
        current_page = 1
        
        while current_page <= request.max_pages:
            print(f"Scanning Page {current_page}...")
            
            # UNIVERSAL SELECTOR STRATEGY
            # 1. Try exact Craigslist class
            candidates = driver.find_elements(By.CLASS_NAME, "result-info")
            
            # 2. If empty, try generic card classes
            if not candidates:
                for selector in [".card", ".item", "article", ".listing", ".result-item", "li.cl-static-search-result"]:
                    found = driver.find_elements(By.CSS_SELECTOR, selector)
                    if len(found) > 2:
                        candidates = found
                        break
            
            # 3. Last Resort: Divs with Links
            if not candidates:
                 # Find divs that contain "Price" or "$" and a Link
                 candidates = driver.find_elements(By.XPATH, "//div[.//a and contains(., '$')]")[:40]

            for item in candidates:
                try:
                    # Skip invisible/tiny elements
                    if item.size['height'] < 20: continue
                    
                    extracted = extract_universal(item, request.data_blueprint)
                    if len(extracted.get('Title', '')) > 2:
                        all_items.append(extracted)
                except:
                    continue
            
            # PAGINATION
            if current_page < request.max_pages:
                try:
                    # Generic "Next" button hunter
                    next_btn = driver.find_element(By.XPATH, "//a[contains(translate(., 'NEXT', 'next'), 'next') or contains(., '>')]")
                    driver.execute_script("arguments[0].click();", next_btn)
                    time.sleep(3)
                    current_page += 1
                except:
                    print("Pagination end reached.")
                    break
            else:
                break

        return JSONResponse(content={
            "success": True, 
            "count": len(all_items), 
            "result": { "items": all_items } 
        })

    except Exception as e:
        print(f"CRITICAL FAILURE: {e}")
        # Return JSON error to prevent frontend crash
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=200)
    
    finally:
        if driver:
            driver.quit()