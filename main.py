from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
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

# --- CORS (THE FIX FOR YOUR CONNECTION ERROR) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows ALL sites to connect (secure enough for MVP)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATA MODELS ---
class ScrapeRequest(BaseModel):
    target_url: str
    data_blueprint: str  # e.g., "Email, Phone, Name"
    proxy_mode: bool = True

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
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(3): 
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

def ai_extract(html, blueprint):
    """
    Uses OpenAI to find the specific data requested in the 'blueprint'
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Clean up HTML to save tokens
    for script in soup(["script", "style", "nav", "footer"]):
        script.decompose()
    text_content = soup.get_text(separator=' ', strip=True)[:15000] # Limit size

    prompt = f"""
    Extract data from this text based on these fields: {blueprint}.
    Return a valid JSON object with a key "items" containing a list of objects.
    If no data found, return empty list.
    Text: {text_content}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"error": str(e), "items": []}

# --- ENDPOINTS ---
@app.get("/")
def home():
    return {"status": "Clarence 6.0 Universal Backend Online"}

@app.post("/scrape")
async def run_scraper(request: ScrapeRequest):
    print(f"Mission: {request.target_url}")
    
    driver = None
    try:
        driver = setup_driver(request.proxy_mode)
        driver.get(request.target_url)
        smart_scroll(driver)
        html = driver.page_source
        
        # AI Analysis
        data = ai_extract(html, request.data_blueprint)
        
        return {"success": True, "url": request.target_url, "result": data}
        
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if driver:
            driver.quit()