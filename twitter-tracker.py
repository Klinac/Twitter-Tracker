import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
from discord_webhook import DiscordWebhook
from datetime import datetime, timedelta


DISCORD_WEBHOOK_URL = "YOUR-DISCORD-WEBHOOK-URL"

# Account to track
TRACKED_ACCOUNT = "UtopiaTM_stake"

# URL
TWITTER_URL = f"https://x.com/{TRACKED_ACCOUNT}"

# To store the last tweet ID
last_tweet_id = None

# Configure Selenium WebDriver
options = Options()
options.add_argument("--headless")  # Run in headless mode (no browser UI)
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def load_cookies(file_path="cookies.txt"):
    cookies_list = []
    try:
        with open(file_path, "r") as f:
            for line in f:
                if line.strip():
                    cookies_list.append(parse_cookie_string(line.strip()))
        print(f"DEBUG: Loaded {len(cookies_list)} cookies from {file_path}.")
    except FileNotFoundError:
        print("DEBUG: cookies.txt file not found. Make sure it exists.")
    return cookies_list


def parse_cookie_string(cookie_string):
    """Parse a cookie string into a list of Selenium-compatible dicts."""
    cookies = []
    for item in cookie_string.split(";"):
        name, value = item.strip().split("=", 1)
        cookies.append({"name": name, "value": value, "domain": ".x.com"})
    return cookies

# Function to add cookies to the browser
def add_cookies(cookies):
    """Add cookies to the browser session."""
    driver.get("https://x.com")  # Open Twitter to match the cookie domain
    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
        except Exception as e:
            print(f"DEBUG: Failed to add cookie {cookie['name']}: {e}")
    print("DEBUG: Cookies added successfully.")

def get_relative_time(tweet_datetime):
    """Convert datetime to a human-readable relative time."""
    current_time = datetime.utcnow()
    time_difference = current_time - tweet_datetime

    if time_difference < timedelta(seconds=60):
        return f"{int(time_difference.total_seconds())}s"
    elif time_difference < timedelta(minutes=60):
        return f"{int(time_difference.total_seconds() // 60)}m"
    elif time_difference < timedelta(hours=24):
        return f"{int(time_difference.total_seconds() // 3600)}h"
    else:
        return f"{int(time_difference.total_seconds() // 86400)}d"

def get_latest_tweet():
    global last_tweet_id
    try:
        print(f"DEBUG: Fetching Twitter page: {TWITTER_URL}")
        driver.get(TWITTER_URL)
        time.sleep(5)  # Allow time for the page to load and JavaScript to execute

        # Debugging: Capture page source
        page_source = driver.page_source
        with open("debug_page_source.html", "w", encoding="utf-8") as f:
            f.write(page_source)
        print("DEBUG: Page source saved to debug_page_source.html.")

        # Find the first tweet using Selenium
        articles = driver.find_elements(By.TAG_NAME, "article")
        print(f"DEBUG: Number of <article> tags found: {len(articles)}")

        if not articles:
            print("No tweets found! Check if the page structure has changed or cookies are invalid.")
            return None, None

        # Extract the first tweet content
        tweet = articles[0]
        tweet_text_elements = tweet.find_elements(By.XPATH, ".//div[@dir='auto']")
        tweet_content = "\n".join([element.text for element in tweet_text_elements if element.text]).strip()
        print(f"DEBUG: Extracted tweet content: {tweet_content}")

        # Extract timestamp (e.g., '2m', '3h')
        timestamp_element = tweet.find_element(By.TAG_NAME, "time")
        tweet_time = timestamp_element.get_attribute("datetime")
        print(f"DEBUG: Extracted tweet time: {tweet_time}")

        # Extract tweet permalink
        permalink_element = tweet.find_element(By.XPATH, ".//a[contains(@href, '/status/')]")
        tweet_permalink = permalink_element.get_attribute('href')  # Fix: Use the href directly without prepending
        print(f"DEBUG: Extracted tweet permalink: {tweet_permalink}")

        # Convert timestamp to datetime
        tweet_datetime = datetime.strptime(tweet_time, "%Y-%m-%dT%H:%M:%S.%fZ")
        relative_time = get_relative_time(tweet_datetime)

        # Check if the tweet is older than 45 seconds
        if datetime.utcnow() - tweet_datetime > timedelta(seconds=45):
            print("DEBUG: Tweet is older than 45 seconds. Skipping.")
            return None, None

        # Extract image URLs (if any)
        image_elements = tweet.find_elements(By.TAG_NAME, "img")
        image_urls = [img.get_attribute("src") for img in image_elements if "media" in img.get_attribute("src")]

        # Extract video URLs (if any)
        video_elements = tweet.find_elements(By.TAG_NAME, "video")
        is_video_tweet = len(video_elements) > 0

        # Include permalink only for video tweets
        media_urls = image_urls if not is_video_tweet else image_urls + [tweet_permalink]
        print(f"DEBUG: Combined media URLs: {media_urls}")

        # Use a unique part of the tweet text as an identifier
        if tweet_content and tweet_content != last_tweet_id:
            last_tweet_id = tweet_content
            return f"{tweet_content}\nAgo: {relative_time}", media_urls
        return None, None
    except Exception as e:
        print(f"Error fetching latest tweet: {e}")
        return None, None

def send_to_discord(message, media_urls):
    """Send a message to Discord using a webhook."""
    if media_urls:
        message += "\n\nImages/Videos:\n" + "\n".join(media_urls)

    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=message)
    response = webhook.execute()
    if response.status_code == 200:
        print("DEBUG: Notification sent to Discord!")
    else:
        print(f"DEBUG: Failed to send notification to Discord: {response.status_code}, {response.text}")

# Load cookies from file
cookies_list = load_cookies()

if not cookies_list:
    print("No cookies found. Exiting.")
    exit()

cookie_index = 0

print(f"Tracking @{TRACKED_ACCOUNT} for new tweets...")
while True:
    # Rotate cookies
    current_cookies = cookies_list[cookie_index]
    cookie_index = (cookie_index + 1) % len(cookies_list)  # Round-robin logic

    # Add cookies to the session
    add_cookies(current_cookies)

    # Fetch latest tweet
    latest_tweet, media_urls = get_latest_tweet()
    if latest_tweet:
        print(f"New tweet detected: {latest_tweet}")
        send_to_discord(f"@{TRACKED_ACCOUNT} just tweeted:\n{latest_tweet}", media_urls)
    else:
        print(f"Newest tweet: {last_tweet_id if last_tweet_id else 'Waiting...'}")

    time.sleep(0.5)  # Adjust as needed
