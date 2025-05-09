# Import necessary libraries
import time
import pandas as pd
from collections import Counter
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup, Comment
import sys
import traceback
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Safe text retrieval function, returns 'N/a' on error
def safe_get_text(element, default='N/a'):
    if not element: return default
    text = element.get_text(strip=True)
    return text or default

# Function to process nationality (for 3-letter codes)
def get_nationality(td_element):
    if td_element is None: return 'N/a'
    try:
        strings = list(td_element.stripped_strings)
        full_text = ' '.join(strings)
        if not full_text: return 'N/a'
        parts = full_text.split()
        if not parts: return 'N/a'
        # Prioritize standalone 3-letter uppercase codes
        for i in range(len(parts) - 1, -1, -1):
             part = parts[i]
             if len(part) == 3 and part.isupper() and part.isalpha():
                  return part
        # If not found, check text within link (if any)
        link = td_element.find('a')
        if link:
            link_text = safe_get_text(link)
            if link_text != 'N/a' and len(link_text) >= 2 and len(link_text) <= 4 and link_text.isupper() and link_text.isalpha():
                return link_text
        # If still not found, take the last element if it's a country code (can be 2-4 letters)
        last_part = parts[-1]
        if len(last_part) <= 4 and last_part.isupper() and last_part.isalpha():
             return last_part
        # Last case, if only one element and it's a country code
        if len(parts) == 1 and len(parts[0]) <= 4 and parts[0].isupper() and parts[0].isalpha():
            return parts[0]
        return 'N/a'
    except Exception as e:
        # print(f"Error processing nationality: {e} for element: {td_element}")
        return 'N/a'

# Function to calculate age from birth year string or age string
def calculate_age(age_or_birth_str, current_year=None):
    if current_year is None:
        try: current_year = pd.Timestamp.now().year
        except: current_year = 2025 # Fallback year

    if not isinstance(age_or_birth_str, str) or age_or_birth_str == 'N/a': return 'N/a'
    age_or_birth_str = age_or_birth_str.strip()

    # Case 1: String already contains age
    try:
        if '-' in age_or_birth_str:
            age_part = age_or_birth_str.split('-')[0]
            if age_part.isdigit() and 14 < int(age_part) < 50: return age_part
        elif age_or_birth_str.isdigit() and 14 < int(age_or_birth_str) < 50: return age_or_birth_str
    except (ValueError, TypeError): pass

    # Case 2: String contains birth year
    try:
        if '-' in age_or_birth_str and len(age_or_birth_str.split('-')) == 3: # YYYY-MM-DD format
            parts = age_or_birth_str.split('-')
            if len(parts[0]) == 4 and parts[0].isdigit():
                birth_year = int(parts[0])
                if 1900 < birth_year <= current_year: return str(current_year - birth_year)

        year_part = ''.join(filter(str.isdigit, age_or_birth_str)) # Find any 4-digit year
        if len(year_part) >= 4:
            potential_years = [year_part[i:i+4] for i in range(len(year_part) - 3)]
            for year_str in potential_years:
                 try:
                     birth_year = int(year_str)
                     if 1900 < birth_year <= current_year: return str(current_year - birth_year)
                 except ValueError: continue

        if ',' in age_or_birth_str: # "Month Day, YYYY" format
            year_str = age_or_birth_str.split(',')[-1].strip()
            if len(year_str) == 4 and year_str.isdigit():
                 birth_year = int(year_str)
                 if 1900 < birth_year <= current_year: return str(current_year - birth_year)
    except (ValueError, TypeError, IndexError): pass

    # Case 3: Only a 4-digit birth year
    try:
        if len(age_or_birth_str) == 4 and age_or_birth_str.isdigit():
             birth_year = int(age_or_birth_str)
             if 1900 < birth_year <= current_year: return str(current_year - birth_year)
    except (ValueError, TypeError): pass
    return 'N/a'

# Function to scrape a table from a given URL
def scrape_fbref_table(driver, url, table_id=None, required_stats=None, min_minutes=90):
    print(f"Attempting to scrape data from: {url}")
    try:
        driver.get(url)
        print("  Page requested. Waiting for table...")

        wait_time = 25
        locator = (By.ID, table_id) if table_id else (By.CSS_SELECTOR, "table.stats_table")
        print(f"  Waiting for table with {'ID: ' + table_id if table_id else 'class stats_table'}")

        try:
            WebDriverWait(driver, wait_time).until(EC.visibility_of_element_located(locator))
            print(f"  Table {locator} visible.")
        except TimeoutException:
            print(f"  Warning: Table {locator} not visible within {wait_time}s on {url}. Checking HTML comments...")

        time.sleep(1) # Allow JS to fully render
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        print("  Parsed page source.")

        data_table = soup.find('table', {'id': table_id}) if table_id else None
        if not data_table: data_table = soup.find('table', {'class': lambda x: x and 'stats_table' in x.split()})

        if not data_table: # Check HTML comments
            comments = soup.find_all(string=lambda text: isinstance(text, Comment))
            for comment in comments:
                comment_soup = BeautifulSoup(comment, 'html.parser')
                potential_table = comment_soup.find('table', {'id': table_id}) if table_id else None
                if not potential_table: potential_table = comment_soup.find('table', {'class': lambda x: x and 'stats_table' in x.split()})
                if potential_table:
                    print(f"  Found table {'with ID '+table_id if table_id else ''} in HTML comment.")
                    data_table = potential_table
                    break
        if not data_table:
            print(f"Error: Table not found on {url}.")
            return pd.DataFrame()

        tbody = data_table.find('tbody')
        rows = tbody.find_all('tr') if tbody else [r for r in data_table.find_all('tr') if r.find(['th', 'td'], {'data-stat': True}) and not r.find('th', {'scope':'col'})]
        if not tbody and not rows:
            print(f"Error: No data rows found in table on {url}")
            return pd.DataFrame()
        elif not tbody:
            print(f"  Found {len(rows)} potential data rows directly in table.")

        print(f"  Found {len(rows)} rows for {url}. Processing...")

        base_stats_needed = {'player', 'team', 'nationality', 'position', 'age', 'birth_year', 'minutes', 'minutes_90s'}
        stats_to_extract = set(base_stats_needed)
        if required_stats:
             stats_to_extract.update(required_stats)
        else: # If no required_stats, get from header
             print("  Warning: No specific list of required stats, will fetch from table header.")
             thead = data_table.find('thead')
             if thead and (header_rows := thead.find_all('tr')):
                 last_header_row = header_rows[-1]
                 header_stats = {th.get('data-stat', '').strip() for th in last_header_row.find_all('th')}
                 stats_to_extract.update(stat for stat in header_stats if stat and stat not in ['ranker', 'matches', 'match_report'])
                 print(f"  Dynamically fetching stats from header: {sorted(list(stats_to_extract - base_stats_needed))}")

        players_data = []
        collected_count, skipped_header, skipped_minutes, skipped_no_player = 0, 0, 0, 0

        for i, row in enumerate(rows):
            if row.has_attr('class') and any(c in row['class'] for c in ['thead', 'partial_table', 'spacer']):
                skipped_header += 1; continue
            if not row.find(['th','td'], {'data-stat' : True}): continue

            player_cell = row.find(['th', 'td'], {'data-stat': 'player'})
            player_name = safe_get_text(player_cell)
            if player_name == 'N/a' or player_name == '' or player_name == 'Player':
                skipped_no_player += 1; continue

            minutes_played_num = -1
            minutes_td = row.find('td', {'data-stat': 'minutes'})
            minutes_90s_td = row.find('td', {'data-stat': 'minutes_90s'})
            minutes_str = safe_get_text(minutes_td, '').replace(',', '')
            minutes_90s_str = safe_get_text(minutes_90s_td, '').replace(',', '')

            try:
                if minutes_str.isdigit():
                    minutes_played_num = int(minutes_str)
                elif minutes_90s_str:
                    try: minutes_played_num = float(minutes_90s_str) * 90
                    except ValueError:
                         if minutes_90s_str.isdigit(): minutes_played_num = int(minutes_90s_str) * 90
                         else: minutes_played_num = -1
                if not (minutes_played_num < 0 and minutes_td is None and minutes_90s_td is None) and minutes_played_num < min_minutes: # Allow players with no minutes data if fields are missing, otherwise filter
                    skipped_minutes += 1; continue
            except (ValueError, TypeError, AttributeError):
                 skipped_minutes += 1; continue

            player_stats = {}
            all_cells = row.find_all(['th', 'td'])
            processed_stats_in_row = set()

            for cell in all_cells:
                stat = cell.get('data-stat', '').strip()
                if stat and stat in stats_to_extract and stat not in processed_stats_in_row:
                    processed_stats_in_row.add(stat)
                    if stat == 'nationality': player_stats['nationality'] = get_nationality(cell)
                    elif stat == 'birth_year' or stat == 'age': # 'age' column often contains birth year or age
                         age_birth_text = safe_get_text(cell)
                         if 'original_age_value' not in player_stats: player_stats['original_age_value'] = age_birth_text
                         calculated_age = calculate_age(age_birth_text)
                         if calculated_age != 'N/a': player_stats['Age'] = calculated_age
                         elif player_stats.get('Age', 'N/a') == 'N/a': player_stats['Age'] = age_birth_text if age_birth_text != 'N/a' else 'N/a'
                    elif stat == 'player': player_stats['Player'] = player_name
                    elif stat == 'team':
                         team_name = safe_get_text(cell.find('a'), default=safe_get_text(cell))
                         player_stats['Team'] = team_name
                    elif stat == 'position':
                         position_text = safe_get_text(cell)
                         player_stats['Position'] = position_text.split(',')[0].strip() if ',' in position_text and position_text.split(',')[0].strip() else position_text
                    elif stat == 'minutes': player_stats['minutes'] = minutes_str or '0'
                    elif stat == 'minutes_90s': player_stats['minutes_90s'] = minutes_90s_str or '0.0'
                    else: player_stats[stat] = safe_get_text(cell)

            # Fallbacks for essential columns if not picked up by general loop
            player_stats.setdefault('Player', player_name)
            if 'Team' not in player_stats:
                team_td_fallback = row.find('td', {'data-stat': 'team'})
                player_stats['Team'] = safe_get_text(team_td_fallback.find('a'), default=safe_get_text(team_td_fallback)) if team_td_fallback else 'N/a'
            if 'Position' not in player_stats:
                pos_td_fallback = row.find('td', {'data-stat': 'position'})
                pos_text_fb = safe_get_text(pos_td_fallback)
                player_stats['Position'] = (pos_text_fb.split(',')[0].strip() if ',' in pos_text_fb and pos_text_fb.split(',')[0].strip() else pos_text_fb) if pos_td_fallback else 'N/a'
            if player_stats.get('Age', 'N/a') == 'N/a':
                 age_td_fallback = row.find('td', {'data-stat': 'age'})
                 age_text_fallback = safe_get_text(age_td_fallback)
                 player_stats['Age'] = calculate_age(age_text_fallback)
                 if 'original_age_value' not in player_stats: player_stats['original_age_value'] = age_text_fallback
            if 'nationality' not in player_stats:
                 nat_td_fallback = row.find('td', {'data-stat': 'nationality'})
                 player_stats['nationality'] = get_nationality(nat_td_fallback)
            player_stats.setdefault('minutes', minutes_str or '0')
            player_stats.setdefault('minutes_90s', minutes_90s_str or '0.0')

            players_data.append(player_stats)
            collected_count += 1

        print(f"  Finished processing rows for {url}. Summary - Found: {len(rows)}, Skipped header: {skipped_header}, No player name: {skipped_no_player}, Low minutes ({min_minutes}): {skipped_minutes}, Collected: {collected_count}")
        if not players_data:
            print(f"Warning: No player data met criteria from {url}.")
            return pd.DataFrame()

        df = pd.DataFrame(players_data)
        if 'Player' in df.columns and 'Team' in df.columns: # Deduplication
            if 'minutes' in df.columns:
                 df['minutes_numeric'] = pd.to_numeric(df['minutes'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                 df = df.sort_values(by=['Player', 'Team', 'minutes_numeric'], ascending=[True, True, False])
                 df = df.drop_duplicates(subset=['Player', 'Team'], keep='first').drop(columns=['minutes_numeric'])
            else: df = df.drop_duplicates(subset=['Player', 'Team'], keep='first')

            try: # Set index
                df['Player'] = df['Player'].astype(str)
                df['Team'] = df['Team'].astype(str)
                if 'position' in df.columns and 'Position' not in df.columns: df.rename(columns={'position': 'Position'}, inplace=True)
                elif 'position' in df.columns and 'Position' in df.columns: df.drop(columns=['position'], inplace=True)
                df = df.set_index(['Player', 'Team'])
                print(f"  Created and indexed DataFrame for {url}. Shape: {df.shape}")
            except KeyError as e:
                 print(f"Error setting index for {url}: {e}. Columns: {df.columns.tolist()}")
                 return df if not df.empty else pd.DataFrame()
        else:
            print(f"Error: Missing 'Player' or 'Team' in {url}. Columns: {df.columns.tolist()}")
            return df if not df.empty else pd.DataFrame()
        time.sleep(1.5) # Anti-blocking delay
        return df
    except TimeoutException as e:
        print(f"Scraping error for {url}: Page element timed out. {e}")
    except Exception as e:
        print(f"Unknown error scraping {url}: {e}\nTraceback: {traceback.format_exc()}")
    return pd.DataFrame()

# User-requested stats and FBRef mapping (Category, Sub-Category, Statistic Name) -> FBRef Key
USER_REQUESTED_STAT_MAPPING = {
    ('', '', 'Nation'): 'nationality', ('', '', 'Position'): 'Position', ('', '', 'Age'): 'Age',
    ('Playing Time', '', 'MP'): 'games', ('Playing Time', '', 'Starts'): 'games_starts', ('Playing Time', '', 'Min'): 'minutes',
    ('Performance', '', 'Gls'): 'goals', ('Performance', '', 'Ast'): 'assists', ('Performance', '', 'CrdY'): 'cards_yellow', ('Performance', '', 'CrdR'): 'cards_red',
    ('Expected', '', 'xG'): 'xg', ('Expected', '', 'xAG'): 'xg_assist', # FBRef uses xAG
    ('Progression', '', 'PrgC'): 'progressive_carries', ('Progression', '', 'PrgP'): 'progressive_passes', ('Progression', '', 'PrgR'): 'progressive_passes_received',
    ('Per 90 Minutes', '', 'Gls'): 'goals_per90', ('Per 90 Minutes', '', 'Ast'): 'assists_per90', ('Per 90 Minutes', '', 'xG'): 'xg_per90', ('Per 90 Minutes', '', 'xGA'): 'xg_assist_per90',
    ('Goalkeeping', 'Performance', 'GA90'): 'gk_goals_against_per90', ('Goalkeeping', 'Performance', 'Save%'): 'gk_save_pct', ('Goalkeeping', 'Performance', 'CS%'): 'gk_clean_sheets_pct', ('Goalkeeping', 'Penalty Kicks', 'Save%'): 'gk_pens_save_pct',
    ('Shooting', 'Standard', 'SoT%'): 'shots_on_target_pct', ('Shooting', 'Standard', 'SoT/90'): 'shots_on_target_per90', ('Shooting', 'Standard', 'G/Sh'): 'goals_per_shot', ('Shooting', 'Standard', 'Dist'): 'average_shot_distance',
    ('Passing', 'Total', 'Cmp'): 'passes_completed', ('Passing', 'Total', 'Cmp%'): 'passes_pct', ('Passing', 'Total', 'TotDist'): 'passes_total_distance',
    ('Passing', 'Short', 'Cmp%'): 'passes_pct_short', ('Passing', 'Medium', 'Cmp%'): 'passes_pct_medium', ('Passing', 'Long', 'Cmp%'): 'passes_pct_long',
    ('Passing', 'Expected', 'KP'): 'assisted_shots', ('Passing', 'Expected', '1/3'): 'passes_into_final_third', ('Passing', 'Expected', 'PPA'): 'passes_into_penalty_area', ('Passing', 'Expected', 'CrsPA'): 'crosses_into_penalty_area', ('Passing', 'Expected', 'PrgP'): 'progressive_passes',
    ('Goal and Shot Creation', 'SCA', 'SCA'): 'sca', ('Goal and Shot Creation', 'SCA', 'SCA90'): 'sca_per90', ('Goal and Shot Creation', 'GCA', 'GCA'): 'gca', ('Goal and Shot Creation', 'GCA', 'GCA90'): 'gca_per90',
    ('Defensive Actions', 'Tackles', 'Tkl'): 'tackles', ('Defensive Actions', 'Tackles', 'TklW'): 'tackles_won', ('Defensive Actions', 'Challenges', 'Att'): 'challenges', ('Defensive Actions', 'Challenges', 'Lost'): 'challenges_lost',
    ('Defensive Actions', 'Blocks', 'Blocks'): 'blocks', ('Defensive Actions', 'Blocks', 'Sh'): 'blocked_shots', ('Defensive Actions', 'Blocks', 'Pass'): 'blocked_passes', ('Defensive Actions', 'Blocks', 'Int'): 'interceptions',
    ('Possession', 'Touches', 'Touches'): 'touches', ('Possession', 'Touches', 'Def Pen'): 'touches_def_pen_area', ('Possession', 'Touches', 'Def 3rd'): 'touches_def_3rd', ('Possession', 'Touches', 'Mid 3rd'): 'touches_mid_3rd', ('Possession', 'Touches', 'Att 3rd'): 'touches_att_3rd', ('Possession', 'Touches', 'Att Pen'): 'touches_att_pen_area',
    ('Possession', 'Take-Ons', 'Att'): 'take_ons', ('Possession', 'Take-Ons', 'Succ%'): 'take_ons_won_pct', ('Possession', 'Take-Ons', 'Tkld%'): 'take_ons_tackled_pct',
    ('Possession', 'Carries', 'Carries'): 'carries', ('Possession', 'Carries', 'PrgDist'): 'carries_progressive_distance', ('Possession', 'Carries', 'ProgC'): 'progressive_carries', ('Possession', 'Carries', '1/3'): 'carries_into_final_third', ('Possession', 'Carries', 'CPA'): 'carries_into_penalty_area', ('Possession', 'Carries', 'Mis'): 'miscontrols', ('Possession', 'Carries', 'Dis'): 'dispossessed',
    ('Possession', 'Receiving', 'Rec'): 'passes_received', ('Possession', 'Receiving', 'PrgR'): 'progressive_passes_received',
    ('Miscellaneous Stats', 'Performance', 'Fls'): 'fouls', ('Miscellaneous Stats', 'Performance', 'Fld'): 'fouled', ('Miscellaneous Stats', 'Performance', 'Off'): 'offsides', ('Miscellaneous Stats', 'Performance', 'Crs'): 'crosses', ('Miscellaneous Stats', 'Performance', 'Recov'): 'ball_recoveries',
    ('Miscellaneous Stats', 'Aerial Duels', 'Won'): 'aerials_won', ('Miscellaneous Stats', 'Aerial Duels', 'Lost'): 'aerials_lost', ('Miscellaneous Stats', 'Aerial Duels', 'Won%'): 'aerials_won_pct',
}
required_fbref_keys = set(USER_REQUESTED_STAT_MAPPING.values()) | {'player', 'team', 'birth_year', 'minutes_90s'} # Add basic keys
print(f"\nTargeting {len(required_fbref_keys)} FBRef keys for scraping (user-requested + basic).")

urls = {
    'standard': 'https://fbref.com/en/comps/9/stats/Premier-League-Stats', 'shooting': 'https://fbref.com/en/comps/9/shooting/Premier-League-Stats',
    'passing': 'https://fbref.com/en/comps/9/passing/Premier-League-Stats', 'gca': 'https://fbref.com/en/comps/9/gca/Premier-League-Stats',
    'defense': 'https://fbref.com/en/comps/9/defense/Premier-League-Stats', 'possession': 'https://fbref.com/en/comps/9/possession/Premier-League-Stats',
    'misc': 'https://fbref.com/en/comps/9/misc/Premier-League-Stats', 'keepers': 'https://fbref.com/en/comps/9/keepers/Premier-League-Stats',
}
table_ids = {
    'standard': 'stats_standard', 'shooting': 'stats_shooting', 'passing': 'stats_passing', 'gca': 'stats_gca',
    'defense': 'stats_defense', 'possession': 'stats_possession', 'playingtime': 'stats_playing_time', # Keep ID if URL re-enabled
    'misc': 'stats_misc', 'keepers': 'stats_keeper',
}

print("\nSetting up Selenium WebDriver...")
try:
    options = Options()
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3") # Reduce browser logs
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("WebDriver using ChromeDriverManager.")
    except Exception as driver_manager_err:
        print(f"Warning: ChromeDriverManager failed ({driver_manager_err}). Trying default ChromeDriver from PATH...")
        driver = webdriver.Chrome(options=options) # Fallback to system PATH
        print("WebDriver using ChromeDriver from system PATH.")
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})") # Hide webdriver property
    print("WebDriver setup complete.")
except Exception as e:
    print(f"Critical error during WebDriver setup: {e}")
    sys.exit(1)

all_dfs = {}
MIN_MINUTES_PLAYED = 90
scraping_successful = False

print("\n--- Starting to scrape data from URLs ---")
for category, url in urls.items():
    table_id = table_ids.get(category)
    df_cat = scrape_fbref_table(driver, url, table_id=table_id, min_minutes=MIN_MINUTES_PLAYED, required_stats=required_fbref_keys)
    if df_cat is not None and not df_cat.empty:
        cols_to_keep = [col for col in df_cat.columns if col in required_fbref_keys]
        if cols_to_keep:
             all_dfs[category] = df_cat[cols_to_keep]
             print(f"--> Success: Fetched data for {category} ({all_dfs[category].shape[0]} players, {len(cols_to_keep)} stats)")
             scraping_successful = True
        else: print(f"--> Warning: {category} contained no required stats.")
    else: print(f"--> Warning: Fetching failed or no data for {category} from {url}")
    print("-" * 30)
driver.quit()

if not scraping_successful or not all_dfs:
    print("ERROR: No data successfully fetched. Cannot continue.")
    sys.exit(1)

print("\n--- Merging scraped DataFrames ---")
merged_df = None
df_keys_priority = ['standard', 'keepers'] + [k for k in all_dfs.keys() if k not in ['standard', 'keepers']]
for category in df_keys_priority:
    if category not in all_dfs or all_dfs[category].empty: continue
    df_cat = all_dfs[category]
    if merged_df is None: merged_df = df_cat
    else:
        try:
            merged_df = merged_df.merge(df_cat, left_index=True, right_index=True, how='outer', suffixes=(None, f'__{category}'))
        except Exception as merge_error:
            print(f"CRITICAL ERROR merging '{category}': {merge_error}") # Potentially log more details or stop
    print(f"  {'Started with' if merged_df is df_cat else 'Merged'} '{category}'. Current shape: {merged_df.shape if merged_df is not None else 'N/A'}")
if merged_df is None:
     print("ERROR: No DataFrames merged. Cannot create result file.")
     sys.exit(1)
print(f"\nInitial merge complete. Total unique Player/Team pairs: {len(merged_df)}")
merged_df = merged_df.reset_index().fillna('N/a')

print("\n--- Building final DataFrame based on user request ---")
final_df = pd.DataFrame({'Player': merged_df['Player'], 'Team': merged_df['Team']})
final_columns_structure = []
missing_stats_log = []
processed_fbref_keys_final = {'Player', 'Team'}
merged_df_columns_list = merged_df.columns.tolist()

def find_column_match(df_columns, base_key, suffix_marker='__'):
    if base_key in df_columns: return base_key
    suffixed_cols = [c for c in df_columns if isinstance(c, str) and c.startswith(base_key + suffix_marker)]
    return suffixed_cols[0] if suffixed_cols else None

print(f"Processing {len(USER_REQUESTED_STAT_MAPPING)} requested stats...")
for col_tuple, base_key in USER_REQUESTED_STAT_MAPPING.items():
    final_columns_structure.append(col_tuple)
    matched_col = find_column_match(merged_df_columns_list, base_key)
    if matched_col:
        final_df[col_tuple] = merged_df[matched_col]
        processed_fbref_keys_final.add(matched_col)
        if matched_col != base_key: missing_stats_log.append(f"Used suffixed '{matched_col}' for {col_tuple} (orig: {base_key})")
    else:
         final_df[col_tuple] = 'N/a'
         missing_stats_log.append(f"Missing {col_tuple} (orig: {base_key}).")

print("\n--- Checks and Reports ---")
unused_original_columns = [col for col in merged_df_columns_list if col not in processed_fbref_keys_final]
if unused_original_columns: print(f"Info: {len(unused_original_columns)} unrequested columns dropped. (e.g., {', '.join(sorted(unused_original_columns)[:5])}{'...' if len(unused_original_columns) > 5 else ''})")
if missing_stats_log:
     print("Warning - Mapping issues:")
     for warning in sorted(list(set(missing_stats_log))): print(f"  - {warning}")
else: print("All requested stats mapped successfully.")
print("-------------------------------------------------------\n")

print("Creating column index for final DataFrame...")
try:
    multiindex_tuples = [('','','Player'), ('','','Team')] + final_columns_structure
    if len(multiindex_tuples) == final_df.shape[1]:
         final_df.columns = pd.MultiIndex.from_tuples(multiindex_tuples, names=['Category', 'Sub-Category', 'Statistic'])
         print("MultiIndex created.")
    else: raise ValueError(f"Column count mismatch for MultiIndex: DF has {final_df.shape[1]}, tuples {len(multiindex_tuples)}.")
except Exception as multiindex_error:
     print(f"Error creating MultiIndex: {multiindex_error}. Using flat column names as fallback.")
     flat_fallback_cols = ['Player', 'Team'] + ['_'.join(filter(None, map(str, tpl))) for tpl in final_columns_structure]
     final_df.columns = [f"{col}_{i}" if flat_fallback_cols.count(col) > 1 else col for i, col in enumerate(flat_fallback_cols)]

is_multiindex = isinstance(final_df.columns, pd.MultiIndex)
player_col_id = ('', '', 'Player') if is_multiindex else 'Player'
if player_col_id in final_df.columns:
    try:
        final_df = final_df.sort_values(by=player_col_id, ascending=True, key=lambda col: col.astype(str).str.lower(), na_position='last')
        print("Sorted DataFrame by Player name.")
    except Exception as e: print(f"Warning: Could not sort by Player ('{player_col_id}'): {e}.")
else: print(f"Warning: Player column '{player_col_id}' not found for sorting.")

print("\nReordering final columns...")
PRIORITY_COLS_TUPLE = [('', '', 'Player'), ('', '', 'Team'), ('', '', 'Nation'), ('', '', 'Position'), ('', '', 'Age')]
PRIORITY_COLS_FLAT = ['Player', 'Team', 'Nation', 'Position', 'Age']
priority_cols_definition = PRIORITY_COLS_TUPLE if is_multiindex else PRIORITY_COLS_FLAT
all_current_cols = final_df.columns.tolist()
priority_cols_present = [col for col in priority_cols_definition if col in all_current_cols]
other_cols = sorted([col for col in all_current_cols if col not in priority_cols_present])
final_column_order = priority_cols_present + other_cols
try:
    final_df = final_df[final_column_order]
    print("Column reordering successful.")
except Exception as e: print(f"Error reordering columns: {e}.")

print("\nPreparing to export final CSV file...")
final_df_export = final_df.copy()
if isinstance(final_df_export.columns, pd.MultiIndex):
    print("Flattening MultiIndex columns for CSV...")
    flat_columns = []
    processed_flat_names = set()
    for col_tuple in final_df_export.columns:
        parts = [str(c).strip().replace(' ', '_').replace('/', '_').replace('%', 'Pct').replace('+/-','_Net').replace('#','Num').replace('(','').replace(')','').replace(':','').replace('.','').replace('&','_and_').replace('[','').replace(']','').replace('-', '_') for c in col_tuple if str(c).strip()]
        base_flat_col = '_'.join(parts) if parts else f"col_{len(flat_columns)}"
        original_base = base_flat_col
        current_count = 1
        while base_flat_col in processed_flat_names:
             base_flat_col = f"{original_base}_{current_count}"; current_count += 1
        flat_columns.append(base_flat_col)
        processed_flat_names.add(base_flat_col)
    if len(flat_columns) == final_df_export.shape[1]: final_df_export.columns = flat_columns
    else:
        print(f"CRITICAL ERROR: Column count mismatch after flattening ({len(flat_columns)} vs {final_df_export.shape[1]}). Aborting save.")
        sys.exit(1)

print("Reordering flattened columns for export...")
PRIORITY_COLS_FLAT_FINAL = ['Player', 'Team', 'Nation', 'Position', 'Age']
id_cols_flat_final = [c for c in PRIORITY_COLS_FLAT_FINAL if c in final_df_export.columns]
other_cols_flat_final = sorted([c for c in final_df_export.columns if c not in id_cols_flat_final])
final_export_order_flat = id_cols_flat_final + other_cols_flat_final
try:
    final_df_export = final_df_export[final_export_order_flat]
    print("Flat column reordering for export successful.")
except Exception as e: print(f"Error reordering flat columns for export: {e}")

output_filename = 'results.csv'
print(f"\nSaving final results to {output_filename}...")
try:
    if final_df_export.empty or final_df_export.shape[1] == 0: print("Warning: Final DataFrame is empty or has no columns. Saving empty CSV.")
    missing_protected = [col for col in id_cols_flat_final if col not in final_df_export.columns]
    if missing_protected: print(f"CRITICAL WARNING: Basic ID columns lost before saving: {missing_protected}.")
    final_df_export.to_csv(output_filename, index=False, encoding='utf-8-sig')
    print(f"Successfully saved results to {output_filename}. Shape: {final_df_export.shape}")
    print(f"Final columns (first 25): {final_df_export.columns.tolist()[:25]}{'...' if len(final_df_export.columns) > 25 else ''}")
except Exception as e:
    print(f"ERROR saving CSV '{output_filename}': {e}\nTraceback: {traceback.format_exc()}")
print("\n--- Script complete ---")
