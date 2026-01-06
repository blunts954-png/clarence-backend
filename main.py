from fastapi import FastAPI, HTTPException
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
import os
import json
from openai import OpenAI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATA MODELS ---
class SignalRequest(BaseModel):
    url: str
    blueprint: str = "" 
    proxy_mode: bool = False
    ai_valuation: bool = False
    scan_depth: int = 1 # New Parameter (1 = Normal, 5 = Deep)

# --- CORE LOGIC ---
def setup_driver(proxy_mode=False):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled") 
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    binary_path = shutil.which("chromium") or shutil.which("google-chrome")
    if binary_path:
        chrome_options.binary_location = binary_path

    try:
        service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        logger.error(f"Primary Driver Init Failed: {e}")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver

def analyze_with_ai(text_content, blueprint, do_valuation):
    if not blueprint:
        return {"raw_text": text_content[:500]} 

    system_prompt = "You are a data extraction engine. Output strictly JSON."
    # We allow more text tokens now for deeper scans
    user_prompt = f"""
    Analyze this website text:
    "{text_content[:25000]}" 
    
    TASK 1: Extract a LIST of items based on these fields: {blueprint}.
    
    TASK 2: { 'Provide a strict "Market Valuation" (Underpriced/Overpriced) and estimated profit margin %.' if do_valuation else 'Ignore valuation.' }
    
    Return ONLY a JSON object with keys: "extracted_data" (array of objects) and "valuation_analysis" (string).
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"AI Analysis Failed: {e}")
        return {"error": str(e)}

# --- ENDPOINTS ---
@app.get("/")
def home():
    return {"status": "SIGNAL INTELLIGENCE ONLINE", "clearance": "Top Secret"}

@app.post("/scrape_universal")
async def signal_operation(request: SignalRequest):
    driver = None
    logger.info(f"SIGNAL LOCKED: {request.url} (Depth: {request.scan_depth})")
    
    try:
        # 1. ACQUIRE
        driver = setup_driver(request.proxy_mode)
        driver.get(request.url)
        
        # 2. DEEP SCROLL (Simulates Pagination)
        # We scroll multiple times based on 'scan_depth'
        for i in range(request.scan_depth):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5) # Wait for content to load
            
        # 3. EXTRACT
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for x in soup(["script", "style", "nav", "footer", "iframe"]): x.decompose()
        raw_text = soup.get_text(separator=' ', strip=True)
        
        # 4. ANALYZE
        logger.info("Engaging Neural Engine...")
        ai_result = analyze_with_ai(raw_text, request.blueprint, request.ai_valuation)
        
        return {
            "success": True,
            "target": request.url,
            "scan_depth": request.scan_depth,
            "result": ai_result
        }

    except Exception as e:
        logger.error(f"Operation Failed: {e}")
        return {"success": False, "error": str(e)}
    
    finally:
        if driver:
            driver.quit()