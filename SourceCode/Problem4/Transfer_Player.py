# --- Import necessary libraries ---
import time
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException

# --- Function to set up Selenium WebDriver ---
def setup_driver():
    """Initialize and return an instance of Chrome WebDriver."""
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)
        print("WebDriver initialized successfully.")
        return driver
    except WebDriverException as e:
        print(f"Error initializing WebDriver: {e}")
        print("Ensure Google Chrome is installed.")
        print("Or try updating webdriver-manager: pip install --upgrade webdriver-manager")
        return None
    except Exception as e:
        print(f"Unknown error initializing driver: {e}")
        return None

# --- Function to scrape data from a specific URL ---
def scrape_page(driver, url):
    """Scrape player data from a URL using Selenium driver."""
    if driver is None:
        print("Error: Invalid driver.")
        return []
    try:
        driver.get(url)
        print(f"Accessing: {url}")
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        table = soup.find('table', class_='table table-hover no-cursor table-striped leaguetable mvp-table similar-players-table mb-0')
        if not table:
            print(f"Warning: No data table found on page {url}")
            return []

        tbody = table.find('tbody')
        if not tbody:
            print(f"Warning: No tbody tag found in table on page {url}")
            return []

        data = []
        rows = tbody.find_all('tr')
        print(f"Found {len(rows)} rows on page {url}")

        for row in rows:
            try:
                skill_div = row.find('div', class_='table-skill__skill')
                pot_div = row.find('div', class_='table-skill__pot')
                skill_text = skill_div.text.strip() if skill_div else None
                pot_text = pot_div.text.strip() if pot_div else None
                skill = float(skill_text) if skill_text else None
                pot = float(pot_text) if pot_text else None
                skill_pot = f"{skill}/{pot}" if skill is not None and pot is not None else None

                player_link = row.select_one('td.td-player div.text a')
                player_name = player_link.text.strip() if player_link else None

                team_span = row.find('span', class_='td-team__teamname')
                team = team_span.text.strip() if team_span else None

                etv_span = row.find('span', class_='player-tag')
                etv = etv_span.text.strip() if etv_span else None

                if player_name and team and etv and skill_pot:
                    data.append({
                        'player_name': player_name,
                        'team': team,
                        'price': etv,
                        'skill/pot': skill_pot
                    })

            except Exception as e:
                print(f"Error processing a row: {e}. Skipping this row.")
                continue

        return data

    except WebDriverException as e:
        print(f"WebDriver error accessing {url}: {e}")
        return []
    except Exception as e:
        print(f"Unknown error scraping page {url}: {e}")
        return []

# --- Main section to perform scraping ---
base_url = "https://www.footballtransfers.com/en/players/uk-premier-league"
total_pages = 22
all_data = []

print("Initializing WebDriver...")
driver = setup_driver()

if driver:
    try:
        print(f"Starting to scrape data from {total_pages} pages...")
        for page in range(1, total_pages + 1):
            print(f"\n--- Processing page {page}/{total_pages} ---")
            if page == 1:
                url = base_url
            else:
                url = f"{base_url}/{page}"

            page_data = scrape_page(driver, url)

            if page_data:
                all_data.extend(page_data)
                print(f"Added {len(page_data)} records from page {page}.")
            else:
                print(f"No valid data returned from page {page}.")

    except Exception as e:
        print(f"An error occurred during scraping: {e}")
    finally:
        print("\nClosing WebDriver...")
        driver.quit()

    if all_data:
        print(f"\nTotal of {len(all_data)} records scraped.")
        df_final = pd.DataFrame(all_data)
        try:
            df_final.to_csv('football_transfers_players.csv', index=False, encoding='utf-8-sig')
            print("Data successfully saved to 'football_transfers_players.csv'")
            print("\nPreview of the first 5 rows of data:")
            print(df_final.head())
        except Exception as e:
            print(f"Error saving CSV file: {e}")
    else:
        print("\nNo data collected. CSV file will not be created.")
else:
    print("Failed to initialize WebDriver. Unable to proceed with scraping.")

print("\nCompleted.")
