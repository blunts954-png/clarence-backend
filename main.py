from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

app = FastAPI()

# --- CORS & TEMPLATES ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

# --- CHROME SETUP ---
def setup_driver():
    options = Options()
    options.add_argument("--headless=new") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

# --- ROUTES ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/scrape")
async def run_scraper(request: ScrapeRequest):
    print(f"--- SIGNAL INITIATED: {request.target_url} ---")
    
    driver = None
    all_items = []
    
    try:
        driver = setup_driver()
        driver.get(request.target_url)
        
        current_page = 1
        
        while current_page <= request.max_pages:
            print(f"Scanning Sector {current_page}...")
            
            # Wait for content
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "result-info"))
                )
            except:
                print("Signal weak/lost on this page.")
                break

            listings = driver.find_elements(By.CLASS_NAME, "result-info")
            
            for item in listings:
                try:
                    data = {}
                    
                    # 1. Universal Title/Link (Used for all blueprints)
                    try:
                        title_el = item.find_element(By.CLASS_NAME, "posting-title")
                        data['Title'] = title_el.text
                        data['Link'] = title_el.find_element(By.TAG_NAME, "a").get_attribute("href")
                    except: 
                        data['Title'] = "Unknown"
                        data['Link'] = "#"

                    # 2. Universal Price
                    try:
                        data['Price'] = item.find_element(By.CLASS_NAME, "price").text
                    except: 
                        data['Price'] = "N/A"

                    # 3. Contextual Data (Based on Blueprint)
                    meta_text = ""
                    try:
                        meta_text = item.find_element(By.CLASS_NAME, "meta").text
                    except: pass

                    if request.data_blueprint == "cars":
                        data['Details'] = meta_text # Odometer/Location
                    elif request.data_blueprint == "housing":
                        data['Specs'] = meta_text # SqFt/Bedrooms
                    elif request.data_blueprint == "jobs":
                        data['Location'] = meta_text
                    else:
                        data['Info'] = meta_text

                    all_items.append(data)
                except:
                    continue
            
            # PAGINATION
            if current_page < request.max_pages:
                try:
                    next_button = driver.find_element(By.CLASS_NAME, "next")
                    if "disabled" in next_button.get_attribute("class"): 
                        break
                    
                    driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(2)
                    current_page += 1
                except:
                    break
            else:
                break
                
        return {
            "success": True, 
            "pages_processed": current_page,
            "result": { "items": all_items } 
        }

    except Exception as e:
        print(f"SYSTEM FAILURE: {e}")
        return {"success": False, "error": str(e)}
    
    finally:
        if driver:
            driver.quit()