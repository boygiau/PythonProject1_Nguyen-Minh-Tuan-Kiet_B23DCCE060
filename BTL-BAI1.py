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
        # Ưu tiên mã 3 chữ cái viết hoa đứng riêng biệt
        for i in range(len(parts) - 1, -1, -1):
             part = parts[i]
             if len(part) == 3 and part.isupper() and part.isalpha():
                  return part
        # Nếu không tìm thấy, kiểm tra text trong link (nếu có)
        link = td_element.find('a')
        if link:
            link_text = safe_get_text(link)
            if link_text != 'N/a' and len(link_text) >= 2 and len(link_text) <= 4 and link_text.isupper() and link_text.isalpha():
                return link_text
        # Nếu vẫn không tìm thấy, lấy phần tử cuối cùng nếu nó là mã quốc gia (có thể 2-4 chữ cái)
        last_part = parts[-1]
        if len(last_part) <= 4 and last_part.isupper() and last_part.isalpha():
             return last_part
        # Trường hợp cuối cùng, nếu chỉ có một phần tử và là mã quốc gia
        if len(parts) == 1 and len(parts[0]) <= 4 and parts[0].isupper() and parts[0].isalpha():
            return parts[0]
        return 'N/a' # Mặc định nếu không tìm thấy
    except Exception as e:
        # print(f"Lỗi khi xử lý quốc tịch: {e} cho element: {td_element}")
        return 'N/a'

# Hàm tính tuổi từ chuỗi năm sinh hoặc tuổi
def calculate_age(age_or_birth_str, current_year=None):
    if current_year is None:
        try: current_year = pd.Timestamp.now().year
        except: current_year = 2025 # Năm dự phòng

    if not isinstance(age_or_birth_str, str) or age_or_birth_str == 'N/a': return 'N/a'

    age_or_birth_str = age_or_birth_str.strip()

    # Case 1: Chuỗi đã chứa tuổi (ví dụ: "25-100" hoặc chỉ "25")
    try:
        if '-' in age_or_birth_str:
            age_part = age_or_birth_str.split('-')[0]
            if age_part.isdigit() and 14 < int(age_part) < 50:
                return age_part
        elif age_or_birth_str.isdigit() and 14 < int(age_or_birth_str) < 50:
             return age_or_birth_str
    except (ValueError, TypeError):
        pass

    # Case 2: Chuỗi chứa năm sinh (ví dụ: "1998-01-15" hoặc "May 5, 1998")
    try:
        # Thử định dạng YYYY-MM-DD
        if '-' in age_or_birth_str and len(age_or_birth_str.split('-')) == 3:
            parts = age_or_birth_str.split('-')
            if len(parts[0]) == 4 and parts[0].isdigit():
                birth_year = int(parts[0])
                if 1900 < birth_year <= current_year:
                    return str(current_year - birth_year)

        # Thử tìm năm 4 chữ số bất kỳ trong chuỗi
        year_part = ''.join(filter(str.isdigit, age_or_birth_str))
        if len(year_part) >= 4:
            # Tìm chuỗi 4 chữ số có khả năng là năm sinh
            potential_years = [year_part[i:i+4] for i in range(len(year_part) - 3)]
            for year_str in potential_years:
                 try:
                     birth_year = int(year_str)
                     if 1900 < birth_year <= current_year:
                         return str(current_year - birth_year)
                 except ValueError:
                     continue

        # Thử định dạng "Month Day, YYYY" (lấy phần tử cuối sau dấu phẩy)
        if ',' in age_or_birth_str:
            year_str = age_or_birth_str.split(',')[-1].strip()
            if len(year_str) == 4 and year_str.isdigit():
                 birth_year = int(year_str)
                 if 1900 < birth_year <= current_year:
                     return str(current_year - birth_year)

    except (ValueError, TypeError, IndexError):
        pass

    # Case 3: Chỉ có năm sinh 4 chữ số
    try:
        if len(age_or_birth_str) == 4 and age_or_birth_str.isdigit():
             birth_year = int(age_or_birth_str)
             if 1900 < birth_year <= current_year:
                 return str(current_year - birth_year)
    except (ValueError, TypeError): pass

    return 'N/a' # Mặc định

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
        time.sleep(1) # Cho phép JS render hoàn chỉnh sau khi bảng hiển thị
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        print("  Đã lấy và phân tích mã nguồn trang.")

        # Tìm bảng, kể cả trong comment HTML
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
             # Lấy tất cả các hàng, loại bỏ hàng header (thường có scope='col')
             all_rows = data_table.find_all('tr')
             rows = [r for r in all_rows if r.find(['th', 'td'], {'data-stat': True}) and not r.find('th', {'scope':'col'})]
             if not rows:
                  print(f"Lỗi: Không tìm thấy hàng dữ liệu trong bảng trên {url}")
                  return pd.DataFrame()
             print(f"  Tìm thấy {len(rows)} hàng dữ liệu tiềm năng trực tiếp trong table.")

        print(f"  Tìm thấy {len(rows)} hàng trong tbody/table cho {url}. Đang xử lý...")

        # Định nghĩa các chỉ số cơ bản luôn cần lấy
        base_stats_needed = {'player', 'team', 'nationality', 'position', 'age', 'birth_year', 'minutes', 'minutes_90s'}
        stats_to_extract = set(base_stats_needed)
        if required_stats:
             stats_to_extract.update(required_stats)
             print(f"  Sẽ trích xuất {len(stats_to_extract)} chỉ số (bao gồm cơ bản và yêu cầu).")
        else:
             print("  Cảnh báo: Không có danh sách chỉ số yêu cầu cụ thể, sẽ lấy mọi data-stat tìm thấy.")
             # Trong trường hợp không có required_stats, lấy từ header để tránh lấy quá nhiều thứ không cần thiết
             thead = data_table.find('thead')
             if thead:
                 header_rows = thead.find_all('tr')
                 if header_rows:
                     last_header_row = header_rows[-1]
                     header_stats = {th.get('data-stat', '').strip() for th in last_header_row.find_all('th')}
                     stats_to_extract.update(stat for stat in header_stats if stat and stat not in ['ranker', 'matches', 'match_report'])
                     print(f"  Lấy động các chỉ số từ header: {sorted(list(stats_to_extract))}")


        players_data = []
        collected_count = 0
        skipped_header = 0
        skipped_minutes = 0
        skipped_no_player = 0

        for i, row in enumerate(rows):
            # Bỏ qua các hàng header phụ hoặc hàng phân cách
            if row.has_attr('class') and ('thead' in row['class'] or 'partial_table' in row['class'] or 'spacer' in row['class']):
                skipped_header += 1; continue

            # Đảm bảo hàng có chứa dữ liệu (có thẻ th hoặc td với data-stat)
            if not row.find(['th','td'], {'data-stat' : True}):
                continue

            # Lấy tên cầu thủ - điều kiện tiên quyết
            player_cell = row.find(['th', 'td'], {'data-stat': 'player'})
            player_name = safe_get_text(player_cell)
            if player_name == 'N/a' or player_name == '' or player_name == 'Player':
                skipped_no_player += 1; continue

            # Kiểm tra số phút chơi tối thiểu
            minutes_played_num = -1
            minutes_td = row.find('td', {'data-stat': 'minutes'})
            minutes_90s_td = row.find('td', {'data-stat': 'minutes_90s'}) # Thêm kiểm tra 90s

            minutes_str = safe_get_text(minutes_td, '').replace(',', '')
            minutes_90s_str = safe_get_text(minutes_90s_td, '').replace(',', '') # Lấy giá trị 90s

            try:
                if minutes_str.isdigit():
                    minutes_played_num = int(minutes_str)
                elif minutes_90s_str: # Nếu không có 'minutes' nhưng có 'minutes_90s'
                    try: minutes_played_num = float(minutes_90s_str) * 90
                    except ValueError: # Xử lý trường hợp minutes_90s không phải số thập phân
                         if minutes_90s_str.isdigit(): minutes_played_num = int(minutes_90s_str) * 90
                         else: minutes_played_num = -1 # Không thể xác định phút
                # Nếu vẫn không xác định được phút từ cả hai cột
                if minutes_played_num < 0 and minutes_td is None and minutes_90s_td is None:
                    pass # Cho phép cầu thủ không có phút (ví dụ: thủ môn dự bị không ra sân)
                elif minutes_played_num < min_minutes:
                    skipped_minutes += 1; continue
            except (ValueError, TypeError, AttributeError) as e:
                 # print(f"Debug: Lỗi khi xử lý phút cho {player_name}. Min: '{minutes_str}', 90s: '{minutes_90s_str}'. Lỗi: {e}")
                 skipped_minutes += 1; continue

            # Thu thập các chỉ số cần thiết
            player_stats = {}
            all_cells = row.find_all(['th', 'td'])
            processed_stats_in_row = set() # Tránh ghi đè nếu có cột trùng tên

            for cell in all_cells:
                stat = cell.get('data-stat', '').strip()
                # Chỉ lấy các chỉ số trong danh sách yêu cầu và chưa được xử lý trong hàng này
                if stat and stat in stats_to_extract and stat not in processed_stats_in_row:
                    processed_stats_in_row.add(stat)

                    if stat == 'nationality':
                        player_stats['nationality'] = get_nationality(cell)
                    elif stat == 'birth_year' or stat == 'age': # Cột age thường chứa năm sinh hoặc tuổi
                         age_birth_text = safe_get_text(cell)
                         # Lưu giá trị gốc từ cột 'age' nếu có, hoặc 'birth_year'
                         if 'original_age_value' not in player_stats:
                              player_stats['original_age_value'] = age_birth_text
                         # Tính toán tuổi nếu chưa có hoặc ghi đè nếu tìm thấy giá trị tốt hơn
                         current_age = player_stats.get('Age', 'N/a')
                         calculated_age = calculate_age(age_birth_text)
                         if calculated_age != 'N/a':
                             player_stats['Age'] = calculated_age # Ưu tiên tuổi tính được
                         elif current_age == 'N/a': # Nếu chưa tính được và giá trị gốc không phải N/a
                              player_stats['Age'] = age_birth_text if age_birth_text != 'N/a' else 'N/a'

                    elif stat == 'player':
                         player_stats['Player'] = player_name # Đã lấy ở trên
                    elif stat == 'team':
                         # Ưu tiên lấy text từ thẻ <a> bên trong <td>
                         team_name = safe_get_text(cell.find('a'))
                         if team_name == 'N/a': # Nếu không có thẻ <a>, lấy text của <td>
                            team_name = safe_get_text(cell)
                         player_stats['Team'] = team_name
                    elif stat == 'position':
                         position_text = safe_get_text(cell)
                         # Chỉ lấy vị trí đầu tiên nếu có nhiều vị trí
                         if ',' in position_text:
                             first_position = position_text.split(',')[0].strip()
                             player_stats['Position'] = first_position if first_position else 'N/a'
                         else:
                             player_stats['Position'] = position_text
                    elif stat == 'minutes':
                         player_stats['minutes'] = minutes_str if minutes_str else '0' # Đảm bảo có giá trị
                    elif stat == 'minutes_90s':
                         player_stats['minutes_90s'] = minutes_90s_str if minutes_90s_str else '0.0' # Đảm bảo có giá trị
                    else:
                        # Lấy text và thay thế giá trị rỗng bằng 'N/a'
                        value = safe_get_text(cell)
                        player_stats[stat] = value

            #---- Đảm bảo các cột cơ bản luôn tồn tại ----
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
            if 'Age' not in player_stats or player_stats.get('Age') == 'N/a':
                 # Thử lại với cột 'age' nếu chưa có hoặc là N/a
                 age_td_fallback = row.find('td', {'data-stat': 'age'})
                 age_text_fallback = safe_get_text(age_td_fallback)
                 calculated_fallback_age = calculate_age(age_text_fallback)
                 player_stats['Age'] = calculated_fallback_age # Ghi đè nếu tính được
                 # Lưu giá trị gốc nếu chưa lưu
                 if 'original_age_value' not in player_stats:
                     player_stats['original_age_value'] = age_text_fallback

            if 'nationality' not in player_stats:
                 nat_td_fallback = row.find('td', {'data-stat': 'nationality'})
                 player_stats['nationality'] = get_nationality(nat_td_fallback)
            if 'minutes' not in player_stats: player_stats['minutes'] = minutes_str if minutes_str else '0'
            if 'minutes_90s' not in player_stats: player_stats['minutes_90s'] = minutes_90s_str if minutes_90s_str else '0.0'
            #---------------------------------------------

            # Thêm dữ liệu cầu thủ vào danh sách
            players_data.append(player_stats)
            collected_count += 1

        print(f"  Đã xử lý xong các hàng cho {url}.")
        print(f"  Tóm tắt - Tổng số hàng tìm thấy: {len(rows)}, Hàng header/phân cách bỏ qua: {skipped_header}, Bỏ qua vì không có tên cầu thủ: {skipped_no_player}, Bỏ qua vì ít phút ({min_minutes}): {skipped_minutes}, Cầu thủ đã thu thập: {collected_count}")

        if not players_data:
            print(f"Cảnh báo: Không có dữ liệu cầu thủ nào thỏa mãn tiêu chí từ {url}.")
            return pd.DataFrame()

        # Tạo DataFrame
        df = pd.DataFrame(players_data)

        # Xử lý trùng lặp dựa trên 'Player' và 'Team' (giữ hàng có số phút cao nhất nếu có cột 'minutes')
        if 'Player' in df.columns and 'Team' in df.columns:
            if 'minutes' in df.columns:
                 # Chuyển 'minutes' sang số để sắp xếp, xử lý lỗi nếu không thể chuyển
                 df['minutes_numeric'] = pd.to_numeric(df['minutes'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                 df = df.sort_values(by=['Player', 'Team', 'minutes_numeric'], ascending=[True, True, False])
                 df = df.drop_duplicates(subset=['Player', 'Team'], keep='first')
                 df = df.drop(columns=['minutes_numeric']) # Bỏ cột tạm
            else:
                 # Nếu không có cột minutes, chỉ giữ lại hàng đầu tiên gặp
                 df = df.drop_duplicates(subset=['Player', 'Team'], keep='first')

            # Đặt 'Player' và 'Team' làm index
            try:
                # Đảm bảo kiểu dữ liệu là string trước khi đặt làm index
                df['Player'] = df['Player'].astype(str)
                df['Team'] = df['Team'].astype(str)

                # Đổi tên cột 'position' thành 'Position' nếu tồn tại để thống nhất
                if 'position' in df.columns and 'Position' not in df.columns:
                    df.rename(columns={'position': 'Position'}, inplace=True)
                elif 'position' in df.columns and 'Position' in df.columns:
                     # Nếu cả hai tồn tại (không nên xảy ra), bỏ cột 'position' thường
                     df.drop(columns=['position'], inplace=True)

                df = df.set_index(['Player', 'Team'])
                print(f"  Đã tạo và đặt index cho DataFrame {url}. Kích thước: {df.shape}")
            except KeyError as e:
                 print(f"Lỗi: Không thể đặt index 'Player', 'Team'. Các cột hiện có: {df.columns.tolist()}. Lỗi: {e}")
                 # Trả về df không có index nếu lỗi
                 if not df.empty: return df
                 return pd.DataFrame()
        else:
            print(f"Lỗi: Thiếu cột 'Player' hoặc 'Team' sau khi cào {url}. Không thể đặt index.")
            print(f"Các cột hiện có: {df.columns.tolist()}")
            if not df.empty: return df # Trả về df không có index
            return pd.DataFrame()

        # Thêm độ trễ nhỏ để tránh bị block
        time.sleep(1.5)
        return df

    except TimeoutException as e:
        print(f"Lỗi cào dữ liệu {url}: Page element timed out. {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Lỗi không xác định khi cào dữ liệu {url}: {e}")
        print(f"Traceback (để debug):\n{traceback.format_exc()}")
        return pd.DataFrame()

# --- Định nghĩa các chỉ số người dùng yêu cầu và ánh xạ FBRef ---
# Tuple format: (Category, Sub-Category, Statistic Name) -> FBRef Key
USER_REQUESTED_STAT_MAPPING = {
    # Basic Info
    ('', '', 'Nation'): 'nationality',
    ('', '', 'Position'): 'Position', # Sẽ được chuẩn hóa từ 'position'
    ('', '', 'Age'): 'Age', # Sẽ được tính toán từ 'age'/'birth_year'

    # Playing Time
    ('Playing Time', '', 'MP'): 'games',
    ('Playing Time', '', 'Starts'): 'games_starts',
    ('Playing Time', '', 'Min'): 'minutes',

    # Performance
    ('Performance', '', 'Gls'): 'goals',
    ('Performance', '', 'Ast'): 'assists',
    ('Performance', '', 'CrdY'): 'cards_yellow',
    ('Performance', '', 'CrdR'): 'cards_red',

    # Expected
    ('Expected', '', 'xG'): 'xg',
    ('Expected', '', 'xAG'): 'xg_assist', # FBRef dùng xAG

    # Progression
    ('Progression', '', 'PrgC'): 'progressive_carries',
    ('Progression', '', 'PrgP'): 'progressive_passes',
    ('Progression', '', 'PrgR'): 'progressive_passes_received',

    # Per 90 minutes
    ('Per 90 Minutes', '', 'Gls'): 'goals_per90',
    ('Per 90 Minutes', '', 'Ast'): 'assists_per90',
    ('Per 90 Minutes', '', 'xG'): 'xg_per90',
    ('Per 90 Minutes', '', 'xGA'): 'xg_assist_per90', # Ánh xạ xGA của user sang xAG của FBRef

    # Goalkeeping
    ('Goalkeeping', 'Performance', 'GA90'): 'gk_goals_against_per90',
    ('Goalkeeping', 'Performance', 'Save%'): 'gk_save_pct',
    ('Goalkeeping', 'Performance', 'CS%'): 'gk_clean_sheets_pct',
    ('Goalkeeping', 'Penalty Kicks', 'Save%'): 'gk_pens_save_pct',

    # Shooting
    ('Shooting', 'Standard', 'SoT%'): 'shots_on_target_pct',
    ('Shooting', 'Standard', 'SoT/90'): 'shots_on_target_per90',
    ('Shooting', 'Standard', 'G/Sh'): 'goals_per_shot',
    ('Shooting', 'Standard', 'Dist'): 'average_shot_distance',

    # Passing
    ('Passing', 'Total', 'Cmp'): 'passes_completed',
    ('Passing', 'Total', 'Cmp%'): 'passes_pct',
    ('Passing', 'Total', 'TotDist'): 'passes_total_distance', # User yêu cầu TotDist
    ('Passing', 'Short', 'Cmp%'): 'passes_pct_short',
    ('Passing', 'Medium', 'Cmp%'): 'passes_pct_medium',
    ('Passing', 'Long', 'Cmp%'): 'passes_pct_long',
    # Passing Expected (gộp từ yêu cầu của user)
    ('Passing', 'Expected', 'KP'): 'assisted_shots',
    ('Passing', 'Expected', '1/3'): 'passes_into_final_third',
    ('Passing', 'Expected', 'PPA'): 'passes_into_penalty_area',
    ('Passing', 'Expected', 'CrsPA'): 'crosses_into_penalty_area',
    ('Passing', 'Expected', 'PrgP'): 'progressive_passes', # Trùng với Progression, FBRef chỉ có 1 key

    # Goal and Shot Creation
    ('Goal and Shot Creation', 'SCA', 'SCA'): 'sca',
    ('Goal and Shot Creation', 'SCA', 'SCA90'): 'sca_per90',
    ('Goal and Shot Creation', 'GCA', 'GCA'): 'gca',
    ('Goal and Shot Creation', 'GCA', 'GCA90'): 'gca_per90',

    # Defensive Actions
    ('Defensive Actions', 'Tackles', 'Tkl'): 'tackles',
    ('Defensive Actions', 'Tackles', 'TklW'): 'tackles_won',
    ('Defensive Actions', 'Challenges', 'Att'): 'challenges', # FBRef key cho Att trong Challenges
    ('Defensive Actions', 'Challenges', 'Lost'): 'challenges_lost',
    ('Defensive Actions', 'Blocks', 'Blocks'): 'blocks',
    ('Defensive Actions', 'Blocks', 'Sh'): 'blocked_shots',
    ('Defensive Actions', 'Blocks', 'Pass'): 'blocked_passes',
    ('Defensive Actions', 'Blocks', 'Int'): 'interceptions', # Int nằm ở đây theo yêu cầu user (FBRef có thể để riêng)

    # Possession
    ('Possession', 'Touches', 'Touches'): 'touches',
    ('Possession', 'Touches', 'Def Pen'): 'touches_def_pen_area',
    ('Possession', 'Touches', 'Def 3rd'): 'touches_def_3rd',
    ('Possession', 'Touches', 'Mid 3rd'): 'touches_mid_3rd',
    ('Possession', 'Touches', 'Att 3rd'): 'touches_att_3rd',
    ('Possession', 'Touches', 'Att Pen'): 'touches_att_pen_area',
    ('Possession', 'Take-Ons', 'Att'): 'take_ons',
    ('Possession', 'Take-Ons', 'Succ%'): 'take_ons_won_pct',
    ('Possession', 'Take-Ons', 'Tkld%'): 'take_ons_tackled_pct',
    ('Possession', 'Carries', 'Carries'): 'carries',
    ('Possession', 'Carries', 'PrgDist'): 'carries_progressive_distance', # Ánh xạ ProDist của user
    ('Possession', 'Carries', 'ProgC'): 'progressive_carries', # Trùng với Progression
    ('Possession', 'Carries', '1/3'): 'carries_into_final_third',
    ('Possession', 'Carries', 'CPA'): 'carries_into_penalty_area',
    ('Possession', 'Carries', 'Mis'): 'miscontrols',
    ('Possession', 'Carries', 'Dis'): 'dispossessed',
    ('Possession', 'Receiving', 'Rec'): 'passes_received',
    ('Possession', 'Receiving', 'PrgR'): 'progressive_passes_received', # Trùng với Progression

    # Miscellaneous Stats
    ('Miscellaneous Stats', 'Performance', 'Fls'): 'fouls',
    ('Miscellaneous Stats', 'Performance', 'Fld'): 'fouled',
    ('Miscellaneous Stats', 'Performance', 'Off'): 'offsides',
    ('Miscellaneous Stats', 'Performance', 'Crs'): 'crosses',
    ('Miscellaneous Stats', 'Performance', 'Recov'): 'ball_recoveries',
    ('Miscellaneous Stats', 'Aerial Duels', 'Won'): 'aerials_won',
    ('Miscellaneous Stats', 'Aerial Duels', 'Lost'): 'aerials_lost',
    ('Miscellaneous Stats', 'Aerial Duels', 'Won%'): 'aerials_won_pct',
}

# Lấy danh sách các FBRef keys cần thiết TỪ ÁNH XẠ YÊU CẦU
required_fbref_keys = set(USER_REQUESTED_STAT_MAPPING.values())
# Thêm các key cơ bản không có trong mapping tường minh nhưng cần cho xử lý/index
required_fbref_keys.update(['player', 'team', 'birth_year', 'minutes_90s']) # Thêm birth_year để tính Age, minutes_90s dự phòng
print(f"\nTổng số {len(required_fbref_keys)} khóa FBRef sẽ được nhắm mục tiêu để cào (từ yêu cầu người dùng + cơ bản).")


# --- Thực thi script chính ---

urls = {
    'standard': 'https://fbref.com/en/comps/9/stats/Premier-League-Stats',
    'shooting': 'https://fbref.com/en/comps/9/shooting/Premier-League-Stats',
    'passing': 'https://fbref.com/en/comps/9/passing/Premier-League-Stats',
    'gca': 'https://fbref.com/en/comps/9/gca/Premier-League-Stats', # Goal/Shot Creation
    'defense': 'https://fbref.com/en/comps/9/defense/Premier-League-Stats',
    'possession': 'https://fbref.com/en/comps/9/possession/Premier-League-Stats',
    # 'playingtime': 'https://fbref.com/en/comps/9/playingtime/Premier-League-Stats', # Nhiều chỉ số đã có trong standard
    'misc': 'https://fbref.com/en/comps/9/misc/Premier-League-Stats',
    'keepers': 'https://fbref.com/en/comps/9/keepers/Premier-League-Stats',
    # Các bảng không cần thiết trực tiếp vì các chỉ số đã được map vào bảng khác hoặc không yêu cầu:
    # 'passing_types': 'https://fbref.com/en/comps/9/passing_types/Premier-League-Stats',
    # 'keepersadv': 'https://fbref.com/en/comps/9/keepersadv/Premier-League-Stats',
}

print("\nĐang thiết lập Selenium WebDriver...")
try:
    options = Options()
    # options.add_argument("--headless") # Bỏ comment nếu muốn chạy ẩn
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3") # Giảm log của trình duyệt
    # Giả lập User Agent thông thường
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36") # Cập nhật UA mới hơn
    # Các tùy chọn tránh bị phát hiện là bot
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    try:
        # Ưu tiên sử dụng ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("WebDriver dùng ChromeDriverManager.")
    except Exception as driver_manager_err:
        print(f"Cảnh báo: ChromeDriverManager lỗi ({driver_manager_err}). Thử đường dẫn ChromeDriver mặc định trong PATH...")
        try:
             # Nếu DriverManager lỗi, thử dùng ChromeDriver có sẵn trong PATH hệ thống
             driver = webdriver.Chrome(options=options)
             print("WebDriver dùng ChromeDriver từ system PATH.")
        except Exception as path_err:
             print(f"LỖI NGHIÊM TRỌNG: Không thể khởi tạo WebDriver bằng cả DriverManager và system PATH.")
             print(f"Lỗi PATH: {path_err}")
             sys.exit(1) # Thoát nếu không khởi tạo được WebDriver

    # Chạy script để ẩn thuộc tính 'webdriver'
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    print("Thiết lập WebDriver hoàn tất.")
except Exception as e:
    print(f"Lỗi nghiêm trọng khi thiết lập WebDriver: {e}")
    sys.exit(1) # Thoát nếu có lỗi nghiêm trọng

# --- Bắt đầu cào dữ liệu ---
all_dfs = {}
# IDs bảng tương ứng với URLs (quan trọng để nhắm đúng bảng)
table_ids = {
    'standard': 'stats_standard',
    'shooting': 'stats_shooting',
    'passing': 'stats_passing',
    # 'passing_types': 'stats_passing_types', # Không dùng
    'gca': 'stats_gca',
    'defense': 'stats_defense',
    'possession': 'stats_possession',
    'playingtime': 'stats_playing_time', # Vẫn cần ID nếu URL được kích hoạt lại
    'misc': 'stats_misc',
    'keepers': 'stats_keeper',
    # 'keepersadv': 'stats_keeper_adv', # Không dùng
}
MIN_MINUTES_PLAYED = 90 # Ngưỡng phút tối thiểu (có thể đặt = 0 nếu muốn tất cả)
scraping_successful = False

print("\n--- Bắt đầu cào dữ liệu từ các URL ---")
for category, url in urls.items():
    table_id = table_ids.get(category) # Lấy ID bảng tương ứng
    if not table_id:
         print(f"Cảnh báo: Không có table ID được định nghĩa cho mục '{category}'. Thử dùng class selector chung.")
         # Vẫn tiếp tục thử cào bằng class selector nếu không có ID

    # Gọi hàm cào với danh sách required_fbref_keys đã lọc
    df_cat = scrape_fbref_table(driver, url, table_id=table_id,
                                min_minutes=MIN_MINUTES_PLAYED,
                                required_stats=required_fbref_keys) # Truyền các key FBRef cần thiết

    # Kiểm tra kết quả trả về
    if df_cat is not None and not df_cat.empty:
        # Chỉ giữ lại các cột có trong required_fbref_keys (và index)
        cols_to_keep = [col for col in df_cat.columns if col in required_fbref_keys]
        if cols_to_keep: # Chỉ thêm nếu có cột dữ liệu cần giữ
             all_dfs[category] = df_cat[cols_to_keep] # Tạo df mới chỉ với cột cần thiết
             print(f"--> Thành công: Đã lấy và xử lý dữ liệu cho mục: {category} ({all_dfs[category].shape[0]} cầu thủ, {len(cols_to_keep)} chỉ số)")
             scraping_successful = True
        else:
             print(f"--> Cảnh báo: Mục {category} không chứa chỉ số nào trong danh sách yêu cầu.")
    else:
        print(f"--> Cảnh báo: Lấy dữ liệu thất bại hoặc không có dữ liệu thỏa mãn cho mục: {category} từ {url}")
    print("-" * 30)

print("Đang đóng WebDriver...")
driver.quit()

# Kiểm tra nếu không có dữ liệu nào được cào thành công
if not scraping_successful or not all_dfs:
    print("LỖI: Không có dữ liệu nào được lấy thành công từ các URL. Không thể tiếp tục.")
    sys.exit(1) # Thoát nếu không cào được gì

# --- Gộp các DataFrame ---
print("\n--- Đang gộp các DataFrame đã cào ---")
merged_df = None
# Ưu tiên gộp 'standard' và 'keepers' trước nếu có
df_keys_priority = ['standard', 'keepers'] + [k for k in all_dfs.keys() if k not in ['standard', 'keepers']]

for category in df_keys_priority:
    if category not in all_dfs: continue # Bỏ qua nếu category không được cào thành công

    df_cat = all_dfs[category]
    # df_cat ở đây đã được lọc chỉ chứa các cột cần thiết
    if df_cat is None or df_cat.empty: continue # Bỏ qua nếu df rỗng

    if merged_df is None:
        # DataFrame đầu tiên để bắt đầu gộp
        merged_df = df_cat
        print(f"Bắt đầu gộp với '{category}'. Kích thước: {merged_df.shape}, Chỉ số: {merged_df.columns.tolist()}")
    else:
        # Gộp các DataFrame tiếp theo dựa trên index ('Player', 'Team')
        try:
            # Kiểm tra index trước khi gộp
            if merged_df.index.names != df_cat.index.names:
                 print(f"Cảnh báo: Tên index không khớp khi gộp '{category}'. Gộp: {merged_df.index.names}, Hiện tại: {df_cat.index.names}. Đang thử gộp...")
                 # Có thể thêm xử lý reset_index/set_index lại nếu cần, nhưng merge thường xử lý được
            elif not merged_df.index.is_unique:
                 print(f"Cảnh báo: Index của merged_df không duy nhất trước khi gộp '{category}'.")
            elif not df_cat.index.is_unique:
                 print(f"Cảnh báo: Index của df_cat '{category}' không duy nhất.")


            # Thực hiện gộp, sử dụng 'outer' để giữ tất cả cầu thủ từ cả hai bảng
            # Không cần suffixes vì các cột trùng lặp (ngoài index) nên được xử lý trước đó
            # Tuy nhiên, để an toàn, vẫn thêm suffixes phòng trường hợp có key trùng nhau không mong muốn
            merged_df = merged_df.merge(
                df_cat, left_index=True, right_index=True, how='outer',
                suffixes=(None, f'__{category}') # Suffix chỉ áp dụng nếu có cột trùng tên không phải index
            )
            print(f"  Đã gộp '{category}'. Kích thước hiện tại: {merged_df.shape}")
            # Kiểm tra cột trùng lặp sau khi gộp (nếu có suffix)
            suffixed_cols = [col for col in merged_df.columns if f'__{category}' in col]
            if suffixed_cols:
                 print(f"  Cảnh báo: Đã tạo các cột có hậu tố khi gộp '{category}': {suffixed_cols}")

        except Exception as merge_error:
            print(f"LỖI NGHIÊM TRỌNG khi gộp mục '{category}': {merge_error}")
            print(f"  Index của merged_df: {merged_df.index.names}, Kích thước: {merged_df.shape}")
            print(f"  Index của df_cat: {df_cat.index.names}, Kích thước: {df_cat.shape}")
            print(f"  Các cột của merged_df (5 cột đầu): {merged_df.columns.tolist()[:5]}")
            print(f"  Các cột của df_cat (5 cột đầu): {df_cat.columns.tolist()[:5]}")
            # Cân nhắc dừng hoặc tiếp tục tùy vào mức độ nghiêm trọng

if merged_df is None:
     print("LỖI: Không có DataFrame nào được gộp thành công. Không thể tạo file kết quả.")
     sys.exit(1)

print("\nHoàn tất gộp ban đầu.")
print(f"Tổng số cặp Cầu thủ/Đội duy nhất sau khi gộp: {len(merged_df)}")

# Reset index để 'Player' và 'Team' trở thành cột thông thường
merged_df = merged_df.reset_index()
# Điền giá trị NaN/None bằng 'N/a' cho nhất quán
merged_df = merged_df.fillna('N/a')

# --- Xây dựng DataFrame cuối cùng CHỈ với các cột yêu cầu ---
print("\n--- Xây dựng DataFrame cuối cùng theo yêu cầu người dùng ---")

final_df = pd.DataFrame()
# Thêm cột Player và Team trước tiên
final_df['Player'] = merged_df['Player']
final_df['Team'] = merged_df['Team']

# Danh sách để lưu cấu trúc cột MultiIndex cuối cùng
final_columns_structure = []
# Danh sách để theo dõi các chỉ số yêu cầu không tìm thấy trong dữ liệu đã cào
missing_stats_log = []
# Set để theo dõi các cột gốc đã được xử lý
processed_fbref_keys_final = set(['Player', 'Team']) # Bắt đầu với Player, Team


# Hàm tìm cột khớp trong DataFrame đã gộp (ưu tiên tên gốc, sau đó tên có hậu tố)
def find_column_match(df_columns, base_key, suffix_marker='__'):
    if base_key in df_columns:
        return base_key # Tìm thấy tên gốc
    # Tìm các cột có dạng base_key + suffix
    suffixed_cols = [c for c in df_columns if isinstance(c, str) and c.startswith(base_key + suffix_marker)]
    if suffixed_cols:
        return suffixed_cols[0] # Trả về cột có hậu tố đầu tiên tìm thấy
    return None # Không tìm thấy

merged_df_columns_list = merged_df.columns.tolist()

# Lặp qua ÁNH XẠ YÊU CẦU CỦA NGƯỜI DÙNG để xây dựng DataFrame cuối cùng
print(f"Xử lý {len(USER_REQUESTED_STAT_MAPPING)} chỉ số được yêu cầu...")
for col_tuple, base_key in USER_REQUESTED_STAT_MAPPING.items():
    # col_tuple là ('Category', 'Sub-Category', 'Statistic Name')
    # base_key là tên cột FBRef tương ứng (ví dụ: 'goals', 'assists')

    # Thêm cấu trúc cột vào danh sách final_columns_structure
    final_columns_structure.append(col_tuple)

    # Tìm cột tương ứng trong DataFrame đã gộp
    matched_col = find_column_match(merged_df_columns_list, base_key)

    if matched_col:
        # Nếu tìm thấy cột (tên gốc hoặc có hậu tố), thêm vào final_df
        final_df[col_tuple] = merged_df[matched_col]
        processed_fbref_keys_final.add(matched_col) # Đánh dấu cột gốc đã sử dụng
        # Ghi log nếu phải dùng cột có hậu tố
        if matched_col != base_key:
            missing_stats_log.append(f"Dùng cột có hậu tố '{matched_col}' cho chỉ số {col_tuple} (key gốc: {base_key})")
    else:
         # Nếu không tìm thấy cột nào khớp, thêm cột với giá trị 'N/a'
         final_df[col_tuple] = 'N/a'
         missing_stats_log.append(f"Thiếu chỉ số yêu cầu {col_tuple} (key gốc: {base_key}).")

# --- Kiểm tra và báo cáo ---
print("\n--- Kiểm tra các cột không sử dụng và chỉ số bị thiếu ---")
# Tìm các cột trong merged_df không được sử dụng trong final_df
unused_original_columns = [col for col in merged_df_columns_list if col not in processed_fbref_keys_final]
if unused_original_columns:
    print(f"Thông tin: {len(unused_original_columns)} cột sau từ dữ liệu gốc đã được cào nhưng KHÔNG nằm trong yêu cầu cuối cùng và đã bị loại bỏ:")
    print(f"  (Ví dụ: {', '.join(sorted(unused_original_columns)[:15])}{'...' if len(unused_original_columns) > 15 else ''})")
else:
    print("Tất cả các cột từ dữ liệu gốc đã được cào dường như đã được yêu cầu hoặc là cột cơ bản (Player/Team).")
print("-" * 20)
# In ra các cảnh báo về chỉ số bị thiếu hoặc phải dùng hậu tố
if missing_stats_log:
     print("Cảnh báo: Các vấn đề sau xảy ra khi ánh xạ chỉ số yêu cầu:")
     unique_warnings = sorted(list(set(missing_stats_log)))
     for warning in unique_warnings: print(f"  - {warning}")
else:
    print("Tất cả các chỉ số yêu cầu dường như đã được tìm thấy và ánh xạ thành công.")
print("-------------------------------------------------------\n")

# --- Tạo MultiIndex cho các cột cuối cùng ---
print("Tạo MultiIndex cho các cột DataFrame cuối cùng...")
try:
    # Tạo list các tuple cho MultiIndex, bắt đầu bằng Player và Team
    multiindex_tuples = [('','','Player'), ('','','Team')] + final_columns_structure
    # Kiểm tra số lượng tuple khớp với số cột của final_df
    if len(multiindex_tuples) == final_df.shape[1]:
         final_df.columns = pd.MultiIndex.from_tuples(
             multiindex_tuples,
             names=['Category', 'Sub-Category', 'Statistic'] # Đặt tên cho các level
         )
         print("Tạo MultiIndex thành công.")
    else:
         # Lỗi không khớp số cột -> không tạo MultiIndex
         raise ValueError(f"Số cột không khớp: DataFrame có {final_df.shape[1]} cột, nhưng có {len(multiindex_tuples)} tuple được tạo.")
except Exception as multiindex_error:
     print(f"Lỗi khi tạo MultiIndex: {multiindex_error}")
     # Phương án dự phòng: Tạo tên cột phẳng nếu MultiIndex lỗi
     flat_fallback_cols = ['Player', 'Team'] + ['_'.join(filter(None, map(str, tpl))) for tpl in final_columns_structure]
     # Đảm bảo không có tên cột trùng lặp trong fallback
     flat_fallback_cols = [f"{col}_{i}" if flat_fallback_cols.count(col) > 1 else col for i, col in enumerate(flat_fallback_cols)]
     final_df.columns = flat_fallback_cols
     print("Chuyển sang sử dụng tên cột phẳng làm phương án dự phòng.")

# --- Sắp xếp DataFrame và Cột ---
print("\nSắp xếp DataFrame theo tên Cầu thủ...")
is_multiindex = isinstance(final_df.columns, pd.MultiIndex)
# Xác định cột Player dựa trên loại index
player_col_id = ('', '', 'Player') if is_multiindex else 'Player'

if player_col_id in final_df.columns:
    try:
        # Sắp xếp không phân biệt chữ hoa/thường, NA để cuối
        final_df = final_df.sort_values(by=player_col_id, ascending=True, key=lambda col: col.astype(str).str.lower(), na_position='last')
        print("Sắp xếp theo tên cầu thủ hoàn tất.")
    except Exception as e:
        print(f"Cảnh báo: Không thể sắp xếp theo tên cầu thủ ('{player_col_id}'): {e}.")
else:
     print(f"Cảnh báo: Không tìm thấy cột Player '{player_col_id}' để sắp xếp.")


print("\nSắp xếp lại thứ tự các cột cuối cùng (Player, Team, Nation, Pos, Age trước)...")
# Định nghĩa các cột ưu tiên (dựa trên cấu trúc tuple nếu là MultiIndex)
PRIORITY_COLS_TUPLE = [
    ('', '', 'Player'), ('', '', 'Team'), ('', '', 'Nation'), ('', '', 'Position'),
    ('', '', 'Age')
]
# Định nghĩa các cột ưu tiên nếu là cột phẳng
PRIORITY_COLS_FLAT = ['Player', 'Team', 'Nation', 'Position', 'Age']

# Chọn danh sách cột ưu tiên phù hợp
priority_cols_definition = PRIORITY_COLS_TUPLE if is_multiindex else PRIORITY_COLS_FLAT

all_current_cols = final_df.columns.tolist()
# Lấy các cột ưu tiên có trong DataFrame hiện tại
priority_cols_present = [col for col in priority_cols_definition if col in all_current_cols]
# Lấy các cột còn lại
other_cols = [col for col in all_current_cols if col not in priority_cols_present]

# Sắp xếp các cột còn lại theo thứ tự bảng chữ cái (tuple hoặc string)
if is_multiindex:
    # Sắp xếp tuple theo thứ tự Category -> Sub-Category -> Statistic
    other_cols = sorted(other_cols)
else:
    # Sắp xếp tên cột phẳng theo thứ tự bảng chữ cái
    other_cols = sorted(other_cols)

# Tạo thứ tự cột cuối cùng
final_column_order = priority_cols_present + other_cols

try:
    # Áp dụng thứ tự cột mới
    final_df = final_df[final_column_order]
    print("Sắp xếp lại cột thành công.")
except Exception as e:
    print(f"Lỗi khi sắp xếp lại cột: {e}.")
    print(f"Các cột mong đợi: {final_column_order}")
    print(f"Các cột thực tế: {all_current_cols}")


# --- Chuẩn bị và Xuất file CSV ---
print("\nChuẩn bị xuất file CSV cuối cùng...")
# Tạo bản sao để tránh thay đổi DataFrame gốc
final_df_export = final_df.copy()

# Làm phẳng cột MultiIndex nếu có, để phù hợp với định dạng CSV
if isinstance(final_df_export.columns, pd.MultiIndex):
    print("Làm phẳng cột MultiIndex cho CSV...")
    flat_columns = []
    processed_flat_names = set() # Để kiểm tra tên trùng lặp

    for col_tuple in final_df_export.columns:
        # Tạo tên cột phẳng từ các phần của tuple, loại bỏ phần rỗng
        # Thay thế các ký tự không phù hợp cho tên file/cột
        parts = [str(c).strip().replace(' ', '_').replace('/', '_').replace('%', 'Pct')
                 .replace('+/-','_Net').replace('#','Num').replace('(','').replace(')','')
                 .replace(':','').replace('.','').replace('&','_and_').replace('[','').replace(']','')
                 .replace('-', '_') # Thay thế gạch nối bằng gạch dưới
                 for c in col_tuple if str(c).strip()]

        base_flat_col = '_'.join(parts) if parts else f"col_{len(flat_columns)}" # Tên cơ bản
        original_base = base_flat_col # Lưu tên gốc phòng trường hợp trùng

        # Xử lý tên cột trùng lặp bằng cách thêm hậu tố số
        current_count = 1
        while base_flat_col in processed_flat_names:
             base_flat_col = f"{original_base}_{current_count}"
             current_count += 1

        flat_columns.append(base_flat_col)
        processed_flat_names.add(base_flat_col) # Thêm tên đã xử lý vào set

    # Kiểm tra lại số cột sau khi làm phẳng
    if len(flat_columns) == final_df_export.shape[1]:
        final_df_export.columns = flat_columns # Gán tên cột đã làm phẳng
        print("Làm phẳng MultiIndex thành công.")
    else:
        # Lỗi nghiêm trọng nếu số cột không khớp
        print(f"LỖI NGHIÊM TRỌNG: Số cột không khớp sau khi làm phẳng ({len(flat_columns)} vs {final_df_export.shape[1]}). Hủy lưu file.")
        sys.exit(1)
else:
     # Nếu cột đã phẳng sẵn (do lỗi MultiIndex trước đó hoặc thiết kế)
     print("Các cột đã ở định dạng phẳng. Chuẩn bị xuất.")

# Sắp xếp lại các cột đã làm phẳng (đảm bảo các cột ưu tiên vẫn đứng đầu)
print("Sắp xếp lại thứ tự các cột đã làm phẳng...")
# Tạo lại danh sách cột ưu tiên với tên đã làm phẳng
PRIORITY_COLS_FLAT_FINAL = [
    'Player', 'Team', 'Nation', 'Position', 'Age'
]
# Lấy các cột ưu tiên có trong DataFrame export
id_cols_flat_final = [c for c in PRIORITY_COLS_FLAT_FINAL if c in final_df_export.columns]
# Lấy các cột còn lại
other_cols_flat_final = [c for c in final_df_export.columns if c not in id_cols_flat_final]
# Sắp xếp các cột còn lại theo alphabet
final_export_order_flat = id_cols_flat_final + sorted(other_cols_flat_final)

try:
    # Áp dụng thứ tự cột phẳng cuối cùng
    final_df_export = final_df_export[final_export_order_flat]
    print("Sắp xếp cột phẳng thành công.")
except Exception as e:
    print(f"Lỗi khi sắp xếp cột phẳng: {e}")
    print(f"Các cột mong đợi (có thể không tồn tại): {final_export_order_flat}")
    print(f"Các cột thực tế trong DataFrame: {final_df_export.columns.tolist()}")

# --- Lưu file CSV ---
output_filename = 'result.csv'
print(f"\nĐang lưu kết quả cuối cùng vào {output_filename}...")
try:
    # Kiểm tra DataFrame có rỗng không
    if final_df_export.empty:
         print("Cảnh báo: DataFrame cuối cùng rỗng. Sẽ lưu file CSV rỗng.")
    elif final_df_export.shape[1] == 0:
         print("Cảnh báo: DataFrame cuối cùng không có cột nào. Sẽ lưu file CSV rỗng.")

    # Kiểm tra lần cuối xem các cột ID cơ bản còn tồn tại không
    missing_protected = [col for col in id_cols_flat_final if col not in final_df_export.columns]
    if missing_protected:
        print(f"CẢNH BÁO NGHIÊM TRỌNG: Các cột ID cơ bản sau đã bị mất trước khi lưu: {missing_protected}. Điều này không nên xảy ra.")

    # Lưu vào file CSV với encoding utf-8-sig (để Excel đọc tiếng Việt tốt)
    final_df_export.to_csv(output_filename, index=False, encoding='utf-8-sig')
    print(f"Đã lưu thành công kết quả vào {output_filename}")
    print(f"Kích thước DataFrame cuối cùng (hàng, cột): {final_df_export.shape}")
    # In ra một vài cột đầu tiên để kiểm tra
    print(f"Các cột cuối cùng được lưu (25 cột đầu): {final_df_export.columns.tolist()[:25]}{'...' if len(final_df_export.columns) > 25 else ''}")

except Exception as e:
    print(f"LỖI khi lưu file CSV '{output_filename}': {e}")
    print(f"Traceback (để debug):\n{traceback.format_exc()}")

print("\n--- Script hoàn tất ---")
