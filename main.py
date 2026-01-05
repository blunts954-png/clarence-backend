from fastapi import FastAPI
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from bs4 import BeautifulSoup
import time
import logging
import shutil
from fastapi.middleware.cors import CORSMiddleware

# --- LOGGING & APP SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ENABLE CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REQUEST MODELS ---
class UniversalRequest(BaseModel):
    url: str

# --- CORE LOGIC ---
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled") 
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # CRITICAL FIX: Point to the 'chromium' binary found in your error log
    # We use shutil to find it dynamically so it works on Render and Local
    binary_path = shutil.which("chromium") or shutil.which("google-chrome")
    if binary_path:
        chrome_options.binary_location = binary_path
        logger.info(f"Binary found at: {binary_path}")

    try:
        # CRITICAL FIX: Tell the manager to install the driver for CHROMIUM, not Chrome.
        # This fixes the v114 vs v143 mismatch.
        logger.info("Installing compatible driver for Chromium...")
        service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        logger.error(f"Primary Driver Init Failed: {e}")
        # Last Resort Fallback
        try:
             logger.info("Attempting fallback to standard Chrome...")
             service = Service(ChromeDriverManager().install())
             driver = webdriver.Chrome(service=service, options=chrome_options)
             return driver
        except Exception as e2:
            logger.error(f"Fallback Driver Init Failed: {e2}")
            raise e

def clean_html_content(html):
    soup = BeautifulSoup(html, 'html.parser')
    for element in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
        element.decompose()
    text = soup.get_text(separator=' ', strip=True)
    return text[:10000]

# --- ENDPOINTS ---
@app.get("/")
def home():
    return {"status": "Signal Universal Engine Online"}

@app.post("/scrape_universal")
async def universal_scraper(request: UniversalRequest):
    driver = None
    logger.info(f"Targeting: {request.url}")
    
    try:
        driver = setup_driver()
        driver.get(request.url)
        
        # Smart Scroll
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        raw_html = driver.page_source
        clean_text = clean_html_content(raw_html)
        
        return {
            "success": True,
            "target": request.url,
            "data_length": len(clean_text),
            "result": clean_text
        }

    except Exception as e:
        logger.error(f"Scrape Failed: {e}")
        return {"success": False, "error": str(e)}
    
    finally:
        if driver:
            driver.quit()