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

class SignalRequest(BaseModel):
    url: str
    blueprint: str = "" 
    proxy_mode: bool = False
    ai_valuation: bool = False
    scan_depth: int = 1 

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
        return webdriver.Chrome(service=service, options=chrome_options)
    except:
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=chrome_options)

def analyze_with_ai(text_content, blueprint, do_valuation):
    if not blueprint:
        return {"extracted_data": [{"raw_text": text_content[:500]}]}

    system_prompt = "You are a high-precision data scraper. Output strictly valid JSON."
    
    # We explicitly ask for an ARRAY of items to make the CSV converter work perfectly
    user_prompt = f"""
    Analyze this raw text from a website:
    "{text_content[:30000]}" 
    
    MISSION: Extract a clean LIST of items based on these fields: {blueprint}.
    
    REQUIREMENTS:
    1. The output MUST be a JSON Object.
    2. Key "extracted_data": An ARRAY of objects (e.g. [{{ "Title": "...", "Price": "..." }}]).
    3. Key "valuation_analysis": A short string assessing market value (if Valuation is requested).
    4. { 'Assess if items are Underpriced/Overpriced.' if do_valuation else 'Ignore valuation.' }
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
        logger.error(f"AI Error: {e}")
        return {"extracted_data": [], "error": str(e)}

@app.get("/")
def home():
    return {"status": "SIGNAL READY", "version": "1.0-LAUNCH"}

@app.post("/scrape_universal")
async def signal_operation(request: SignalRequest):
    driver = None
    logger.info(f"TARGET: {request.url} | DEPTH: {request.scan_depth}")
    
    try:
        driver = setup_driver(request.proxy_mode)
        driver.get(request.url)
        
        # Deep Scroll Logic
        for i in range(request.scan_depth):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for x in soup(["script", "style", "nav", "footer", "iframe", "svg"]): x.decompose()
        raw_text = soup.get_text(separator=' ', strip=True)
        
        # AI Processing
        ai_result = analyze_with_ai(raw_text, request.blueprint, request.ai_valuation)
        
        return {
            "success": True,
            "target": request.url,
            "scan_depth": request.scan_depth,
            "result": ai_result
        }

    except Exception as e:
        logger.error(f"Fail: {e}")
        return {"success": False, "error": str(e)}
    
    finally:
        if driver:
            driver.quit()