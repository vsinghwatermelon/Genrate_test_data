import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import sys
import os

def extract_url_from_script(script_path):
    with open(script_path, 'r') as f:
        content = f.read()
    match = re.search(r"driver\.go_to\('([^']+)'\)", content)
    return match.group(1) if match else None

def download_and_extract_html(url, output_html='downloaded_page.html'):
    # You can use webdriver-manager for automatic driver management
    # from webdriver_manager.chrome import ChromeDriverManager
    # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver = webdriver.Chrome()  # Assumes chromedriver is in PATH
    driver.get(url)
    html = driver.page_source
    driver.quit()
    soup = BeautifulSoup(html, 'html.parser')
    # Save prettified HTML to file
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    # Optionally, return all tags as a list
    return [tag.name for tag in soup.find_all(True)]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_html_from_selenium.py <selenium_script_path>")
        sys.exit(1)
    script_path = sys.argv[1]
    if not os.path.exists(script_path):
        print(f"File not found: {script_path}")
        sys.exit(1)
    url = extract_url_from_script(script_path)
    if url:
        print(f"Extracted URL: {url}")
        tags = download_and_extract_html(url)
        print(f"HTML tags found: {set(tags)}")
        print("HTML saved to downloaded_page.html")
    else:
        print("No URL found in the script.")
