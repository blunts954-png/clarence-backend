from fastapi import FastAPI
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import logging
from fastapi.middleware.cors import CORSMiddleware

# --- LOGGING & APP SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ENABLE CORS (So your Netlify site can talk to this)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins
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
    # Masking automation flags
    chrome_options.add_argument("--disable-blink-features=AutomationControlled") 
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        logger.error(f"Driver Init Failed: {e}")
        raise e

def clean_html_content(html):
    soup = BeautifulSoup(html, 'html.parser')
    # Remove junk to save bandwidth
    for element in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
        element.decompose()
    text = soup.get_text(separator=' ', strip=True)
    return text[:10000] # Return first 10k chars

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
        
        # Smart Scroll (to trigger lazy loading)
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