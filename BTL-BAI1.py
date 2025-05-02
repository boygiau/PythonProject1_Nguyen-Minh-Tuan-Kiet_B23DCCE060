# Nhập các thư viện cần thiết
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

# Hàm lấy text an toàn, trả về 'N/a' nếu lỗi
def safe_get_text(element, default='N/a'):
    if element is None:
        return default
    text = element.get_text(strip=True)
    return text if text else default

# Hàm xử lý quốc tịch (cho mã 3 chữ cái)
def get_nationality(td_element):
    if td_element is None: return 'N/a'
    try:
        strings = list(td_element.stripped_strings)
        full_text = ' '.join(strings)
        if not full_text: return 'N/a'
        parts = full_text.split()
        if not parts: return 'N/a'
        for i in range(len(parts) - 1, -1, -1):
             part = parts[i]
             if len(part) == 3 and part.isupper() and part.isalpha():
                  return part
        link = td_element.find('a')
        if link:
            link_text = safe_get_text(link)
            if link_text != 'N/a' and len(link_text) >= 2 and len(link_text) <= 4 and link_text.isupper() and link_text.isalpha():
                return link_text
        last_part = parts[-1]
        if len(last_part) <= 4 and last_part.isupper() and last_part.isalpha():
             return last_part
        return 'N/a'
    except Exception as e:
        return 'N/a'

# Hàm tính tuổi từ chuỗi năm sinh
def calculate_age(birth_year_str, current_year=None):
    if current_year is None:
        try: current_year = pd.Timestamp.now().year
        except: current_year = 2025 # Năm dự phòng
    if not isinstance(birth_year_str, str) or birth_year_str == 'N/a': return 'N/a'

    birth_year_str = birth_year_str.strip()

    try:
        if '(' in birth_year_str and ' years old)' in birth_year_str:
             age_part = birth_year_str.split('(')[1].split(' ')[0]
             if age_part.isdigit(): return age_part
    except Exception: pass

    try:
        if '-' in birth_year_str and len(birth_year_str.split('-')) == 3:
            parts = birth_year_str.split('-')
            if len(parts[0]) == 4 and parts[0].isdigit():
                birth_year = int(parts[0])
                if 1900 < birth_year <= current_year:
                    return str(current_year - birth_year)
    except (ValueError, TypeError, IndexError): pass

    try:
        if len(birth_year_str) == 4 and birth_year_str.isdigit():
             birth_year = int(birth_year_str)
             if 1900 < birth_year <= current_year:
                 return str(current_year - birth_year)
    except (ValueError, TypeError): pass

    if birth_year_str.isdigit() and 14 < int(birth_year_str) < 50:
        return birth_year_str

    return 'N/a'

# Hàm cào một bảng từ URL cho trước
def scrape_fbref_table(driver, url, table_id=None, required_stats=None, min_minutes=90):
    print(f"Đang thử cào dữ liệu: {url}")
    try:
        print("  Yêu cầu trang bằng Selenium...")
        driver.get(url)
        print("  Đã yêu cầu trang. Chờ bảng xuất hiện...")

        wait_time = 25
        if table_id:
            locator = (By.ID, table_id)
            print(f"  Chờ bảng có ID: {table_id}")
        else:
            locator = (By.CSS_SELECTOR, "table.stats_table")
            print("  Chờ bảng có class 'stats_table'")

        try:
            WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located(locator)
            )
            print(f"  Bảng {locator} đã được định vị và hiển thị.")
        except TimeoutException:
            print(f"  Cảnh báo: Bảng {locator} không hiển thị trong {wait_time} giây trên {url}. Kiểm tra comment HTML...")

        print("  Lấy mã nguồn trang...")
        time.sleep(1)
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        print("  Đã lấy và phân tích mã nguồn trang.")

        data_table = None
        if table_id:
            data_table = soup.find('table', {'id': table_id})
        if not data_table:
             data_table = soup.find('table', {'class': lambda x: x and 'stats_table' in x.split()})

        if not data_table:
            comments = soup.find_all(string=lambda text: isinstance(text, Comment))
            for comment in comments:
                comment_soup = BeautifulSoup(comment, 'html.parser')
                potential_table = None
                if table_id: potential_table = comment_soup.find('table', {'id': table_id})
                if not potential_table: potential_table = comment_soup.find('table', {'class': lambda x: x and 'stats_table' in x.split()})
                if potential_table:
                    print(f"  Tìm thấy bảng {'có ID '+table_id if table_id else ''} trong comment HTML.")
                    data_table = potential_table
                    break

        if not data_table:
            print(f"Lỗi: Không tìm thấy bảng trên {url}.")
            return pd.DataFrame()

        print("  Đã xác định bảng. Tìm tbody...")
        tbody = data_table.find('tbody')
        rows = []
        if tbody:
             rows = tbody.find_all('tr')
        else:
             print("Cảnh báo: Không tìm thấy tbody. Kiểm tra hàng trực tiếp trong table.")
             all_rows = data_table.find_all('tr')
             rows = [r for r in all_rows if r.find(['th', 'td'], {'data-stat': True}) and not r.find('th', {'scope':'col'})]
             if not rows:
                  print(f"Lỗi: Không tìm thấy hàng dữ liệu trong bảng trên {url}")
                  return pd.DataFrame()
             print(f"  Tìm thấy {len(rows)} hàng dữ liệu tiềm năng trực tiếp trong table.")

        print(f"  Tìm thấy {len(rows)} hàng trong tbody/table cho {url}. Đang xử lý...")

        header_stats = set()
        thead = data_table.find('thead')
        if thead:
            header_rows = thead.find_all('tr')
            if header_rows:
                 last_header_row = header_rows[-1]
                 header_stats = {th.get('data-stat', '').strip() for th in last_header_row.find_all('th')}
                 header_stats = {stat for stat in header_stats if stat and stat not in ['ranker', 'matches', 'match_report']}
                 print(f"  Các chỉ số trích xuất động từ header: {sorted(list(header_stats))}")
            else: print("  Cảnh báo: Không tìm thấy hàng header (tr) trong thead.")
        else:
            print("  Cảnh báo: Không tìm thấy table header (thead). Các chỉ số động có thể thiếu.")
            header_stats = None

        base_stats_needed = {'player', 'team', 'nationality', 'position', 'birth_year', 'age', 'minutes', 'minutes_90s'}
        stats_to_extract = set(base_stats_needed)
        if required_stats:
             stats_to_extract.update(required_stats)
             print(f"  Sử dụng danh sách chỉ số yêu cầu được cung cấp (kết hợp với cơ bản). Tổng cộng: {len(stats_to_extract)}")
        elif header_stats is not None:
             stats_to_extract.update(header_stats)
             print(f"  Sử dụng chỉ số từ header (kết hợp với cơ bản). Tổng cộng: {len(stats_to_extract)}")
        else:
             print("  Cảnh báo: Không có chỉ số yêu cầu hoặc header, sẽ lấy mọi data-stat tìm thấy trong hàng.")

        players_data = []
        collected_count = 0
        skipped_header = 0
        skipped_minutes = 0
        skipped_no_player = 0

        for i, row in enumerate(rows):
            if row.has_attr('class') and ('thead' in row['class'] or 'partial_table' in row['class']):
                skipped_header += 1; continue

            if not row.find(['th','td'], {'data-stat' : True}):
                continue

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
                if minutes_played_num < min_minutes:
                    skipped_minutes += 1; continue
            except (ValueError, TypeError, AttributeError) as e:
                 skipped_minutes += 1; continue

            player_stats = {}
            all_cells = row.find_all(['th', 'td'])

            if header_stats is None and not required_stats:
                 row_stats = {cell.get('data-stat', '').strip() for cell in all_cells if cell.get('data-stat')}
                 stats_to_extract.update(row_stats)

            processed_stats_in_row = set()

            for cell in all_cells:
                stat = cell.get('data-stat', '').strip()
                if stat and stat in stats_to_extract and stat not in processed_stats_in_row:
                    processed_stats_in_row.add(stat)

                    if stat == 'nationality':
                        player_stats['nationality'] = get_nationality(cell)
                    elif stat == 'birth_year':
                         birth_year_text = safe_get_text(cell)
                         player_stats['birth_year'] = birth_year_text
                         player_stats['Age'] = calculate_age(birth_year_text)
                    elif stat == 'player':
                         player_stats['Player'] = player_name
                    elif stat == 'team':
                         team_name = safe_get_text(cell.find('a'))
                         if team_name == 'N/a': team_name = safe_get_text(cell)
                         player_stats['Team'] = team_name
                    elif stat == 'position':
                         position_text = safe_get_text(cell)
                         if ',' in position_text:
                             first_position = position_text.split(',')[0].strip()
                             player_stats['Position'] = first_position if first_position else 'N/a'
                         else:
                             player_stats['Position'] = position_text
                    elif stat == 'minutes':
                         player_stats['minutes'] = minutes_str
                    elif stat == 'minutes_90s':
                         player_stats['minutes_90s'] = minutes_90s_str
                    elif stat == 'age':
                         pass
                    else:
                        player_stats[stat] = safe_get_text(cell)

            if 'Player' not in player_stats: player_stats['Player'] = player_name
            if 'Team' not in player_stats:
                 team_td_fallback = row.find('td', {'data-stat': 'team'})
                 team_name_fallback = safe_get_text(team_td_fallback.find('a')) if team_td_fallback else 'N/a'
                 if team_name_fallback == 'N/a' and team_td_fallback: team_name_fallback = safe_get_text(team_td_fallback)
                 player_stats['Team'] = team_name_fallback
            if 'Position' not in player_stats:
                pos_td_fallback = row.find('td', {'data-stat': 'position'})
                position_text_fallback = safe_get_text(pos_td_fallback)
                if ',' in position_text_fallback:
                    first_position_fallback = position_text_fallback.split(',')[0].strip()
                    player_stats['Position'] = first_position_fallback if first_position_fallback else 'N/a'
                else:
                    player_stats['Position'] = position_text_fallback
            if 'Age' not in player_stats:
                 birth_year_td_fallback = row.find('td', {'data-stat': 'birth_year'})
                 player_stats['Age'] = calculate_age(safe_get_text(birth_year_td_fallback))
            if 'nationality' not in player_stats:
                 nat_td_fallback = row.find('td', {'data-stat': 'nationality'})
                 player_stats['nationality'] = get_nationality(nat_td_fallback)
            if 'minutes' not in player_stats: player_stats['minutes'] = minutes_str
            if 'minutes_90s' not in player_stats: player_stats['minutes_90s'] = minutes_90s_str

            players_data.append(player_stats)
            collected_count += 1

        print(f"  Đã xử lý xong các hàng cho {url}.")
        print(f"  Tóm tắt - Tổng số hàng tìm thấy: {len(rows)}, Hàng header bỏ qua: {skipped_header}, Bỏ qua vì không có tên cầu thủ: {skipped_no_player}, Bỏ qua vì ít phút: {skipped_minutes}, Cầu thủ đã thu thập: {collected_count}")

        if not players_data:
            print(f"Cảnh báo: Không có dữ liệu cầu thủ nào thỏa mãn tiêu chí từ {url}.")
            return pd.DataFrame()

        df = pd.DataFrame(players_data)

        if 'Player' in df.columns and 'Team' in df.columns:
            if 'minutes' in df.columns:
                 df['minutes_numeric'] = pd.to_numeric(df['minutes'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                 df = df.sort_values(by=['Player', 'Team', 'minutes_numeric'], ascending=[True, True, False])
                 df = df.drop_duplicates(subset=['Player', 'Team'], keep='first')
                 df = df.drop(columns=['minutes_numeric'])
            else:
                 df = df.drop_duplicates(subset=['Player', 'Team'], keep='first')

            try:
                df['Player'] = df['Player'].astype(str)
                df['Team'] = df['Team'].astype(str)

                if 'position' in df.columns and 'Position' not in df.columns:
                    df.rename(columns={'position': 'Position'}, inplace=True)
                elif 'position' in df.columns and 'Position' in df.columns:
                     df.drop(columns=['position'], inplace=True)

                df = df.set_index(['Player', 'Team'])
                print(f"  Đã tạo và đặt index cho DataFrame {url}. Kích thước: {df.shape}")
            except KeyError as e:
                 print(f"Lỗi: Không thể đặt index 'Player', 'Team'. Các cột hiện có: {df.columns.tolist()}. Lỗi: {e}")
                 if not df.empty: return df
                 return pd.DataFrame()
        else:
            print(f"Lỗi: Thiếu cột 'Player' hoặc 'Team' sau khi cào {url}. Không thể đặt index.")
            print(f"Các cột hiện có: {df.columns.tolist()}")
            if not df.empty: return df
            return pd.DataFrame()

        time.sleep(1.5)
        return df

    except TimeoutException as e:
        print(f"Lỗi cào dữ liệu {url}: Page element timed out. {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Lỗi cào dữ liệu {url}: {e}")
        print(f"Traceback (để debug):\n{traceback.format_exc()}")
        return pd.DataFrame()

# --- Thực thi script chính ---

urls = {
    'standard': 'https://fbref.com/en/comps/9/stats/Premier-League-Stats',
    'shooting': 'https://fbref.com/en/comps/9/shooting/Premier-League-Stats',
    'passing': 'https://fbref.com/en/comps/9/passing/Premier-League-Stats',
    'passing_types': 'https://fbref.com/en/comps/9/passing_types/Premier-League-Stats',
    'gca': 'https://fbref.com/en/comps/9/gca/Premier-League-Stats',
    'defense': 'https://fbref.com/en/comps/9/defense/Premier-League-Stats',
    'possession': 'https://fbref.com/en/comps/9/possession/Premier-League-Stats',
    'playingtime': 'https://fbref.com/en/comps/9/playingtime/Premier-League-Stats',
    'misc': 'https://fbref.com/en/comps/9/misc/Premier-League-Stats',
    'keepers': 'https://fbref.com/en/comps/9/keepers/Premier-League-Stats',
}

print("Đang thiết lập Selenium WebDriver...")
try:
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("WebDriver dùng ChromeDriverManager.")
    except Exception as driver_manager_err:
        print(f"Cảnh báo: ChromeDriverManager lỗi ({driver_manager_err}). Thử đường dẫn ChromeDriver mặc định trong PATH...")
        try:
             driver = webdriver.Chrome(options=options)
             print("WebDriver dùng ChromeDriver từ system PATH.")
        except Exception as path_err:
             print(f"Lỗi: Không thể khởi tạo WebDriver bằng cả DriverManager và system PATH.")
             print(f"PATH Error: {path_err}")
             sys.exit(1)

    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    print("Thiết lập WebDriver hoàn tất.")
except Exception as e:
    print(f"Lỗi nghiêm trọng khi thiết lập WebDriver: {e}")
    sys.exit(1)

all_dfs = {}
table_ids = {
    'standard': 'stats_standard',
    'shooting': 'stats_shooting',
    'passing': 'stats_passing',
    'passing_types': 'stats_passing_types',
    'gca': 'stats_gca',
    'defense': 'stats_defense',
    'possession': 'stats_possession',
    'playingtime': 'stats_playing_time',
    'misc': 'stats_misc',
    'keepers': 'stats_keeper',
}
MIN_MINUTES_PLAYED = 90
scraping_successful = False

required_stat_mapping = {
    ('Playing Time', '', 'MP'): 'games',
    ('Playing Time', '', 'Starts'): 'games_starts',
    ('Playing Time', '', 'Min'): 'minutes',
    ('Playing Time', '', '90s'): 'minutes_90s',
    ('Performance', '', 'Gls'): 'goals',
    ('Performance', '', 'Ast'): 'assists',
    ('Performance', '', 'G+A'): 'goals_assists',
    ('Performance', '', 'G-PK'): 'goals_pens',
    ('Performance', '', 'PK'): 'pens_made',
    ('Performance', '', 'PKatt'): 'pens_att',
    ('Performance', '', 'CrdY'): 'cards_yellow',
    ('Performance', '', 'CrdR'): 'cards_red',
    ('Expected', '', 'xG'): 'xg',
    ('Expected', '', 'npxG'): 'npxg',
    ('Expected', '', 'xAG'): 'xg_assist',
    ('Expected', '', 'npxG+xAG'): 'npxg_xg_assist',
    ('Progression', '', 'PrgC'): 'progressive_carries',
    ('Progression', '', 'PrgP'): 'progressive_passes',
    ('Progression', '', 'PrgR'): 'progressive_passes_received',
    ('Per 90 Minutes', '', 'Gls'): 'goals_per90',
    ('Per 90 Minutes', '', 'Ast'): 'assists_per90',
    ('Per 90 Minutes', '', 'G+A'): 'goals_assists_per90',
    ('Per 90 Minutes', '', 'G-PK'): 'goals_pens_per90',
    ('Per 90 Minutes', '', 'G+A-PK'): 'goals_assists_pens_per90',
    ('Per 90 Minutes', '', 'xG'): 'xg_per90',
    ('Per 90 Minutes', '', 'xAG'): 'xg_assist_per90',
    ('Per 90 Minutes', '', 'xG+xAG'): 'xg_xg_assist_per90',
    ('Per 90 Minutes', '', 'npxG'): 'npxg_per90',
    ('Per 90 Minutes', '', 'npxG+xAG'): 'npxg_xg_assist_per90',

    ('Goalkeeping', 'Playing Time', 'MP'): 'gk_games',
    ('Goalkeeping', 'Playing Time', 'Starts'): 'gk_games_starts',
    ('Goalkeeping', 'Playing Time', 'Min'): 'gk_minutes',
    ('Goalkeeping', 'Performance', 'GA'): 'gk_goals_against',
    ('Goalkeeping', 'Performance', 'GA90'): 'gk_goals_against_per90',
    ('Goalkeeping', 'Performance', 'SoTA'): 'gk_shots_on_target_against',
    ('Goalkeeping', 'Performance', 'Saves'): 'gk_saves',
    ('Goalkeeping', 'Performance', 'Save%'): 'gk_save_pct',
    ('Goalkeeping', 'Performance', 'W'): 'gk_wins',
    ('Goalkeeping', 'Performance', 'D'): 'gk_ties',
    ('Goalkeeping', 'Performance', 'L'): 'gk_losses',
    ('Goalkeeping', 'Performance', 'CS'): 'gk_clean_sheets',
    ('Goalkeeping', 'Performance', 'CS%'): 'gk_clean_sheets_pct',
    ('Goalkeeping', 'Penalty Kicks', 'PKatt'): 'gk_pens_att',
    ('Goalkeeping', 'Penalty Kicks', 'PKA'): 'gk_pens_allowed',
    ('Goalkeeping', 'Penalty Kicks', 'PKsv'): 'gk_pens_saved',
    ('Goalkeeping', 'Penalty Kicks', 'PKm'): 'gk_pens_missed',
    ('Goalkeeping', 'Penalty Kicks', 'Save%'): 'gk_pens_save_pct',

    ('Shooting', 'Standard', 'Gls'): 'goals',
    ('Shooting', 'Standard', 'Sh'): 'shots',
    ('Shooting', 'Standard', 'SoT'): 'shots_on_target',
    ('Shooting', 'Standard', 'SoT%'): 'shots_on_target_pct',
    ('Shooting', 'Standard', 'Sh/90'): 'shots_per90',
    ('Shooting', 'Standard', 'SoT/90'): 'shots_on_target_per90',
    ('Shooting', 'Standard', 'G/Sh'): 'goals_per_shot',
    ('Shooting', 'Standard', 'G/SoT'): 'goals_per_shot_on_target',
    ('Shooting', 'Standard', 'Dist'): 'average_shot_distance',
    ('Shooting', 'Standard', 'FK'): 'shots_free_kicks',
    ('Shooting', 'Standard', 'PK'): 'pens_made',
    ('Shooting', 'Standard', 'PKatt'): 'pens_att',
    ('Shooting', 'Expected', 'xG'): 'xg',
    ('Shooting', 'Expected', 'npxG'): 'npxg',
    ('Shooting', 'Expected', 'npxG/Sh'): 'npxg_per_shot',
    ('Shooting', 'Expected', 'G-xG'): 'xg_net',
    ('Shooting', 'Expected', 'np:G-xG'): 'npxg_net',

    ('Passing', 'Total', 'Cmp'): 'passes_completed',
    ('Passing', 'Total', 'Att'): 'passes',
    ('Passing', 'Total', 'Cmp%'): 'passes_pct',
    ('Passing', 'Total', 'TotDist'): 'passes_total_distance',
    ('Passing', 'Total', 'PrgDist'): 'passes_progressive_distance',
    ('Passing', 'Short', 'Cmp'): 'passes_completed_short',
    ('Passing', 'Short', 'Att'): 'passes_short',
    ('Passing', 'Short', 'Cmp%'): 'passes_pct_short',
    ('Passing', 'Medium', 'Cmp'): 'passes_completed_medium',
    ('Passing', 'Medium', 'Att'): 'passes_medium',
    ('Passing', 'Medium', 'Cmp%'): 'passes_pct_medium',
    ('Passing', 'Long', 'Cmp'): 'passes_completed_long',
    ('Passing', 'Long', 'Att'): 'passes_long',
    ('Passing', 'Long', 'Cmp%'): 'passes_pct_long',
    ('Passing', '', 'Ast'): 'assists',
    ('Passing', '', 'xAG'): 'xg_assist',
    ('Passing', '', 'xA'): 'pass_xa',
    ('Passing', '', 'KP'): 'assisted_shots',
    ('Passing', '', '1/3'): 'passes_into_final_third',
    ('Passing', '', 'PPA'): 'passes_into_penalty_area',
    ('Passing', '', 'CrsPA'): 'crosses_into_penalty_area',
    ('Passing', '', 'PrgP'): 'progressive_passes',

    ('Pass Types', '', 'Att'): 'passes',
    ('Pass Types', '', 'Live'): 'passes_live',
    ('Pass Types', '', 'Dead'): 'passes_dead',
    ('Pass Types', '', 'FK'): 'passes_free_kicks',
    ('Pass Types', '', 'TB'): 'through_balls',
    ('Pass Types', '', 'Sw'): 'passes_switches',
    ('Pass Types', '', 'Crs'): 'crosses',
    ('Pass Types', '', 'TI'): 'throw_ins',
    ('Pass Types', '', 'CK'): 'corner_kicks',
    ('Pass Types', 'Corner Kicks', 'In'): 'corner_kicks_in',
    ('Pass Types', 'Corner Kicks', 'Out'): 'corner_kicks_out',
    ('Pass Types', 'Corner Kicks', 'Str'): 'corner_kicks_straight',
    ('Pass Types', '', 'Cmp'): 'passes_completed',
    ('Pass Types', '', 'Off'): 'passes_offsides',
    ('Pass Types', '', 'Blocks'): 'passes_blocked',

    ('Goal and Shot Creation', 'SCA', 'SCA'): 'sca',
    ('Goal and Shot Creation', 'SCA', 'SCA90'): 'sca_per90',
    ('Goal and Shot Creation', 'SCA Types', 'PassLive'): 'sca_passes_live',
    ('Goal and Shot Creation', 'SCA Types', 'PassDead'): 'sca_passes_dead',
    ('Goal and Shot Creation', 'SCA Types', 'TO'): 'sca_take_ons',
    ('Goal and Shot Creation', 'SCA Types', 'Sh'): 'sca_shots',
    ('Goal and Shot Creation', 'SCA Types', 'Fld'): 'sca_fouled',
    ('Goal and Shot Creation', 'SCA Types', 'Def'): 'sca_defense',
    ('Goal and Shot Creation', 'GCA', 'GCA'): 'gca',
    ('Goal and Shot Creation', 'GCA', 'GCA90'): 'gca_per90',
    ('Goal and Shot Creation', 'GCA Types', 'PassLive'): 'gca_passes_live',
    ('Goal and Shot Creation', 'GCA Types', 'PassDead'): 'gca_passes_dead',
    ('Goal and Shot Creation', 'GCA Types', 'TO'): 'gca_take_ons',
    ('Goal and Shot Creation', 'GCA Types', 'Sh'): 'gca_shots',
    ('Goal and Shot Creation', 'GCA Types', 'Fld'): 'gca_fouled',
    ('Goal and Shot Creation', 'GCA Types', 'Def'): 'gca_defense',

    ('Defensive Actions', 'Tackles', 'Tkl'): 'tackles',
    ('Defensive Actions', 'Tackles', 'TklW'): 'tackles_won',
    ('Defensive Actions', 'Tackles', 'Def 3rd'): 'tackles_def_3rd',
    ('Defensive Actions', 'Tackles', 'Mid 3rd'): 'tackles_mid_3rd',
    ('Defensive Actions', 'Tackles', 'Att 3rd'): 'tackles_att_3rd',
    ('Defensive Actions', 'Challenges', 'Tkl'): 'challenge_tackles',
    ('Defensive Actions', 'Challenges', 'Att'): 'challenges',
    ('Defensive Actions', 'Challenges', 'Tkl%'): 'challenge_tackles_pct',
    ('Defensive Actions', 'Challenges', 'Lost'): 'challenges_lost',
    ('Defensive Actions', 'Blocks', 'Blocks'): 'blocks',
    ('Defensive Actions', 'Blocks', 'Sh'): 'blocked_shots',
    ('Defensive Actions', 'Blocks', 'Pass'): 'blocked_passes',
    ('Defensive Actions', '', 'Int'): 'interceptions',
    ('Defensive Actions', '', 'Tkl+Int'): 'tackles_interceptions',
    ('Defensive Actions', '', 'Clr'): 'clearances',
    ('Defensive Actions', '', 'Err'): 'errors',

    ('Possession', 'Touches', 'Touches'): 'touches',
    ('Possession', 'Touches', 'Def Pen'): 'touches_def_pen_area',
    ('Possession', 'Touches', 'Def 3rd'): 'touches_def_3rd',
    ('Possession', 'Touches', 'Mid 3rd'): 'touches_mid_3rd',
    ('Possession', 'Touches', 'Att 3rd'): 'touches_att_3rd',
    ('Possession', 'Touches', 'Att Pen'): 'touches_att_pen_area',
    ('Possession', 'Touches', 'Live'): 'touches_live_ball',
    ('Possession', 'Take-Ons', 'Att'): 'take_ons',
    ('Possession', 'Take-Ons', 'Succ'): 'take_ons_won',
    ('Possession', 'Take-Ons', 'Succ%'): 'take_ons_won_pct',
    ('Possession', 'Take-Ons', 'Tkld'): 'take_ons_tackled',
    ('Possession', 'Take-Ons', 'Tkld%'): 'take_ons_tackled_pct',
    ('Possession', 'Carries', 'Carries'): 'carries',
    ('Possession', 'Carries', 'TotDist'): 'carries_distance',
    ('Possession', 'Carries', 'PrgDist'): 'carries_progressive_distance',
    ('Possession', 'Carries', 'PrgC'): 'progressive_carries',
    ('Possession', 'Carries', '1/3'): 'carries_into_final_third',
    ('Possession', 'Carries', 'CPA'): 'carries_into_penalty_area',
    ('Possession', 'Carries', 'Mis'): 'miscontrols',
    ('Possession', 'Carries', 'Dis'): 'dispossessed',
    ('Possession', 'Receiving', 'Rec'): 'passes_received',
    ('Possession', 'Receiving', 'PrgR'): 'progressive_passes_received',

    ('Miscellaneous Stats', 'Performance', 'CrdY'): 'cards_yellow',
    ('Miscellaneous Stats', 'Performance', 'CrdR'): 'cards_red',
    ('Miscellaneous Stats', 'Performance', '2CrdY'): 'cards_yellow_red',
    ('Miscellaneous Stats', 'Performance', 'Fls'): 'fouls',
    ('Miscellaneous Stats', 'Performance', 'Fld'): 'fouled',
    ('Miscellaneous Stats', 'Performance', 'Off'): 'offsides',
    ('Miscellaneous Stats', 'Performance', 'Crs'): 'crosses',
    ('Miscellaneous Stats', 'Performance', 'Int'): 'interceptions',
    ('Miscellaneous Stats', 'Performance', 'TklW'): 'tackles_won',
    ('Miscellaneous Stats', 'Performance', 'PKwon'): 'pens_won',
    ('Miscellaneous Stats', 'Performance', 'PKcon'): 'pens_conceded',
    ('Miscellaneous Stats', 'Performance', 'OG'): 'own_goals',
    ('Miscellaneous Stats', 'Performance', 'Recov'): 'ball_recoveries',
    ('Miscellaneous Stats', 'Aerial Duels', 'Won'): 'aerials_won',
    ('Miscellaneous Stats', 'Aerial Duels', 'Lost'): 'aerials_lost',
    ('Miscellaneous Stats', 'Aerial Duels', 'Won%'): 'aerials_won_pct',
}

required_stats = list(set([v for k, v in required_stat_mapping.items()]))
print(f"\nTổng số {len(required_stats)} chỉ số FBRef được xác định từ mapping.")

print("\n--- Bắt đầu cào dữ liệu ---")
for category, url in urls.items():
    table_id = table_ids.get(category)
    if not table_id:
         print(f"Cảnh báo: Không có table ID định nghĩa cho mục '{category}'. Thử dùng class selector.")

    df_cat = scrape_fbref_table(driver, url, table_id=table_id, min_minutes=MIN_MINUTES_PLAYED, required_stats=required_stats)

    if df_cat is not None and not df_cat.empty:
        all_dfs[category] = df_cat
        print(f"--> Thành công: Đã lấy và xử lý dữ liệu cho mục: {category} ({df_cat.shape[0]} cầu thủ)")
        scraping_successful = True
    else:
        print(f"--> Cảnh báo: Lấy dữ liệu thất bại hoặc không có dữ liệu thỏa mãn cho mục: {category} từ {url}")
    print("-" * 30)

print("Đang đóng WebDriver...")
driver.quit()

if not scraping_successful or not all_dfs:
    print("Lỗi: Không có dữ liệu nào được lấy thành công. Không thể tiếp tục.")
    sys.exit(1)

print("\n--- Đang gộp các DataFrame ---")
merged_df = None
df_keys_priority = ['standard', 'keepers'] + [k for k in all_dfs.keys() if k not in ['standard', 'keepers']]

for category in df_keys_priority:
    if category not in all_dfs: continue

    df_cat = all_dfs[category]
    if df_cat is None or df_cat.empty: continue

    if merged_df is None:
        merged_df = df_cat
        print(f"Bắt đầu gộp với '{category}'. Kích thước: {merged_df.shape}")
    else:
        try:
            if merged_df.index.names != df_cat.index.names and merged_df.index.nlevels == df_cat.index.nlevels:
                 print(f"Cảnh báo: Tên index không khớp cho '{category}'. Gộp: {merged_df.index.names}, Hiện tại: {df_cat.index.names}.")

            merged_df = merged_df.merge(
                df_cat, left_index=True, right_index=True, how='outer',
                suffixes=(None, f'__{category}')
            )
            print(f"  Đã gộp '{category}'. Kích thước hiện tại: {merged_df.shape}")
        except Exception as merge_error:
            print(f"Lỗi khi gộp mục '{category}': {merge_error}")
            print(f"  Index của merged_df: {merged_df.index.names}, Index của df_cat: {df_cat.index.names}")
            print(f"  Các cột của merged_df (5 cột đầu): {merged_df.columns.tolist()[:5]}")
            print(f"  Các cột của df_cat (5 cột đầu): {df_cat.columns.tolist()[:5]}")

if merged_df is None:
     print("Lỗi: Không có DataFrame nào được gộp thành công.")
     sys.exit(1)

print("Hoàn tất gộp ban đầu.")
print(f"Tổng số cặp Cầu thủ/Đội duy nhất sau khi gộp: {len(merged_df)}")

merged_df = merged_df.reset_index()
merged_df = merged_df.fillna('N/a')

print("\n--- Định nghĩa các cột cơ bản cần giữ lại ---")
base_cols_map = {
    ('', '', 'Nation'): 'nationality',
    ('', '', 'Position'): 'Position',
    ('', '', 'Age'): 'Age',
}

print("Chuẩn bị final DataFrame với tất cả các cột yêu cầu...")
final_df = pd.DataFrame()
final_df['Player'] = merged_df['Player']
final_df['Team'] = merged_df['Team']

final_columns_structure = []
missing_stats_log = []
processed_fbref_keys = set(['Player', 'Team'])

def find_column_match(df_columns, base_key, suffix_marker='__'):
    if base_key in df_columns:
        return base_key
    suffixed_cols = [c for c in df_columns if isinstance(c, str) and c.startswith(base_key + suffix_marker)]
    if suffixed_cols:
        return suffixed_cols[0]
    return None

merged_df_columns = merged_df.columns.tolist()

print("  Thêm các cột cơ bản (Nation, Position, Age)...")
for col_tuple, base_key in base_cols_map.items():
     final_columns_structure.append(col_tuple)
     matched_col = find_column_match(merged_df_columns, base_key)
     if matched_col:
         final_df[col_tuple] = merged_df[matched_col]
         processed_fbref_keys.add(matched_col)
         if matched_col != base_key:
             missing_stats_log.append(f"Dùng hậu tố '{matched_col}' cho cột cơ bản {col_tuple} (key gốc: {base_key})")
     else:
         final_df[col_tuple] = 'N/a'
         missing_stats_log.append(f"Thiếu chỉ số cơ bản {col_tuple} (key gốc: {base_key}).")

print(f"  Thêm {len(required_stat_mapping)} chỉ số được yêu cầu từ mapping...")
for col_tuple, base_key in required_stat_mapping.items():
    if col_tuple in base_cols_map or base_key in ['Player', 'Team']: continue

    final_columns_structure.append(col_tuple)
    matched_col = find_column_match(merged_df_columns, base_key)

    if matched_col:
        final_df[col_tuple] = merged_df[matched_col]
        processed_fbref_keys.add(matched_col)
        if matched_col != base_key:
            missing_stats_log.append(f"Dùng hậu tố '{matched_col}' cho chỉ số {col_tuple} (key gốc: {base_key})")
    else:
         final_df[col_tuple] = 'N/a'
         missing_stats_log.append(f"Thiếu chỉ số yêu cầu {col_tuple} (key gốc: {base_key}).")

print("\n--- Kiểm tra các cột không sử dụng và chỉ số bị thiếu ---")
unused_original_columns = [col for col in merged_df_columns if col not in processed_fbref_keys]
if unused_original_columns:
    print(f"Cảnh báo: {len(unused_original_columns)} cột sau từ dữ liệu gốc đã được cào nhưng KHÔNG được yêu cầu/ánh xạ và sẽ bị loại bỏ:")
    print(f"  (Ví dụ: {', '.join(sorted(unused_original_columns)[:15])}{'...' if len(unused_original_columns) > 15 else ''})")
else:
    print("Tất cả các cột từ dữ liệu gốc dường như đã được xử lý hoặc yêu cầu.")
print("-" * 20)
if missing_stats_log:
     print("Cảnh báo: Các chỉ số YÊU CẦU sau không tìm thấy trong dữ liệu đã cào hoặc phải dùng tên có hậu tố:")
     unique_warnings = sorted(list(set(missing_stats_log)))
     for warning in unique_warnings: print(f"  - {warning}")
else:
    print("Tất cả các chỉ số yêu cầu dường như đã được tìm thấy và ánh xạ thành công.")
print("-------------------------------------------------------\n")

print("Tạo MultiIndex cho các cột cuối cùng...")
try:
    multiindex_tuples = [('','','Player'), ('','','Team')] + final_columns_structure
    if len(multiindex_tuples) == final_df.shape[1]:
         final_df.columns = pd.MultiIndex.from_tuples(
             multiindex_tuples,
             names=['Category', 'Sub-Category', 'Statistic']
         )
         print("Tạo MultiIndex thành công.")
    else:
         raise ValueError(f"Số cột không khớp: DataFrame có {final_df.shape[1]} cột, nhưng có {len(multiindex_tuples)} tuple được tạo.")
except Exception as multiindex_error:
     print(f"Lỗi khi tạo MultiIndex: {multiindex_error}")
     flat_fallback_cols = ['Player', 'Team'] + ['_'.join(filter(None, map(str, tpl))) for tpl in final_columns_structure]
     final_df.columns = flat_fallback_cols
     print("Chuyển sang sử dụng tên cột phẳng làm phương án dự phòng.")

print("\nSắp xếp DataFrame theo tên Cầu thủ...")
is_multiindex = isinstance(final_df.columns, pd.MultiIndex)
player_col_id = ('', '', 'Player') if is_multiindex else 'Player'

if player_col_id in final_df.columns:
    try:
        final_df = final_df.sort_values(by=player_col_id, ascending=True, key=lambda col: col.astype(str).str.lower(), na_position='last')
        print("Sắp xếp hoàn tất.")
    except Exception as e:
        print(f"Không thể sắp xếp theo tên cầu thủ ('{player_col_id}'): {e}.")
else:
     print(f"Cảnh báo: Không tìm thấy cột Player '{player_col_id}' để sắp xếp.")

print("\nSắp xếp lại thứ tự các cột...")
PROTECTED_COLS_TUPLE = [
    ('', '', 'Player'), ('', '', 'Team'), ('', '', 'Nation'), ('', '', 'Position'),
    ('', '', 'Age'),
    ('Playing Time', '', 'Min'), ('Playing Time', '', 'MP'),
    ('Goalkeeping', 'Playing Time', 'Min'),
    ('Goalkeeping', 'Playing Time', 'MP'),
    ('Goalkeeping', 'Performance', 'GA'),
    ('Goalkeeping', 'Performance', 'Saves'),
    ('Goalkeeping', 'Performance', 'Save%'),
    ('Goalkeeping', 'Performance', 'CS'),
]
PROTECTED_COLS_FLAT = ['Player', 'Team', 'Nation', 'Position', 'Age',
                       'Playing_Time_Min', 'Playing_Time_MP',
                       'Goalkeeping_Playing_Time_Min', 'Goalkeeping_Playing_Time_MP',
                       'Goalkeeping_Performance_GA', 'Goalkeeping_Performance_Saves',
                       'Goalkeeping_Performance_SavePct', 'Goalkeeping_Performance_CS']

is_multiindex = isinstance(final_df.columns, pd.MultiIndex)
id_cols_definition = PROTECTED_COLS_TUPLE if is_multiindex else PROTECTED_COLS_FLAT

all_current_cols = final_df.columns.tolist()
id_cols_present = [col for col in id_cols_definition if col in all_current_cols]
other_cols = [col for col in all_current_cols if col not in id_cols_present]

if is_multiindex:
    other_cols = sorted(other_cols)
else:
    other_cols = sorted(other_cols)

final_column_order = id_cols_present + other_cols

try:
    final_df = final_df[final_column_order]
    print("Sắp xếp lại cột thành công.")
except Exception as e:
    print(f"Lỗi khi sắp xếp lại cột: {e}.")
    print(f"Các cột mong đợi: {final_column_order}")
    print(f"Các cột thực tế: {all_current_cols}")


print("\nChuẩn bị xuất file CSV cuối cùng...")
final_df_export = final_df.copy()

if isinstance(final_df_export.columns, pd.MultiIndex):
    print("Làm phẳng cột MultiIndex cho CSV...")
    flat_columns = []
    processed_flat_names = set()
    name_duplicates = Counter()

    for col_tuple in final_df_export.columns:
        parts = [str(c).strip().replace(' ', '_').replace('/', '_').replace('%', 'Pct')
                 .replace('+/-','_Net').replace('#','Num').replace('(','').replace(')','')
                 .replace(':','').replace('.','').replace('&','_and_').replace('[','').replace(']','')
                 .replace('-', '_')
                 for c in col_tuple if str(c).strip()]

        base_flat_col = '_'.join(parts) if parts else f"col_{len(flat_columns)}"
        original_base = base_flat_col

        current_count = 1
        while base_flat_col in processed_flat_names:
             base_flat_col = f"{original_base}_{current_count}"
             current_count += 1

        flat_columns.append(base_flat_col)
        processed_flat_names.add(base_flat_col)

    if len(flat_columns) == final_df_export.shape[1]:
        final_df_export.columns = flat_columns
        print("Làm phẳng MultiIndex thành công.")
    else:
        print(f"LỖI NGHIÊM TRỌNG: Số cột không khớp sau khi làm phẳng ({len(flat_columns)} vs {final_df_export.shape[1]}). Hủy lưu file.")
        sys.exit(1)
else:
     print("Các cột có vẻ đã phẳng. Chuẩn bị xuất.")

PROTECTED_COLS_FLAT_FINAL = [c.replace('%', 'Pct').replace('-', '_') for c in PROTECTED_COLS_FLAT]
id_cols_flat_final = [c for c in PROTECTED_COLS_FLAT_FINAL if c in final_df_export.columns]
other_cols_flat_final = [c for c in final_df_export.columns if c not in id_cols_flat_final]
final_export_order_flat = id_cols_flat_final + sorted(other_cols_flat_final)

try:
    final_df_export = final_df_export[final_export_order_flat]
    print("Sắp xếp cột phẳng thành công.")
except Exception as e:
    print(f"Lỗi khi sắp xếp cột phẳng: {e}")
    print(f"Các cột mong đợi (có thể không tồn tại): {final_export_order_flat}")
    print(f"Các cột thực tế trong DataFrame: {final_df_export.columns.tolist()}")

print("\n--- Loại bỏ các cột có tỷ lệ N/A cao (Đã vô hiệu hóa) ---")
print("Đã bỏ qua bước loại bỏ cột có tỷ lệ N/A cao theo yêu cầu để giữ lại tất cả các chỉ số, bao gồm cả goalkeeping.")

output_filename = 'result.csv'
print(f"\nĐang lưu kết quả cuối cùng vào {output_filename}...")
try:
    if final_df_export.empty or final_df_export.shape[1] == 0:
         print("Cảnh báo: DataFrame cuối cùng rỗng hoặc không có cột. Sẽ lưu file rỗng.")

    missing_protected = [col for col in id_cols_flat_final if col not in final_df_export.columns]
    if missing_protected:
        print(f"CẢNH BÁO NGHIÊM TRỌNG: Các cột ID cơ bản sau đã bị mất trước khi lưu: {missing_protected}. Điều này không nên xảy ra.")

    final_df_export.to_csv(output_filename, index=False, encoding='utf-8-sig')
    print(f"Đã lưu thành công kết quả vào {output_filename}")
    print(f"Kích thước DataFrame cuối cùng (hàng, cột): {final_df_export.shape}")
    print(f"Các cột cuối cùng được lưu (ví dụ): {final_df_export.columns.tolist()[:25]}{'...' if len(final_df_export.columns) > 25 else ''}")

    gk_cols_final = [col for col in final_df_export.columns if 'Goalkeeping' in col or 'keeper' in col.lower() or 'gk_' in col.lower() or 'save' in col.lower() or 'clean_sheet' in col.lower() or 'sota' in col.lower() or 'ga' in col.lower() or 'pk' in col.lower()]
    if gk_cols_final:
        print("\nCác cột liên quan đến thủ môn được giữ lại trong file cuối cùng:")
        print(f"  {', '.join(sorted(gk_cols_final))}")
    else:
        print("\nKhông tìm thấy cột nào có tên gợi ý là chỉ số thủ môn trong kết quả cuối cùng (có thể do tên cột sau khi làm phẳng khác đi hoặc không có thủ môn nào đủ điều kiện).")

except Exception as e:
    print(f"Lỗi khi lưu file CSV: {e}")
    print(f"Traceback (để debug):\n{traceback.format_exc()}")

print("\n--- Script hoàn tất ---")
