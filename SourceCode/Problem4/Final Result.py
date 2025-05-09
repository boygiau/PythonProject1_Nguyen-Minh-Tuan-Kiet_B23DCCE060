import pandas as pd

def combine_and_filter_player_data():
    """
    Combine data from football_transfers_players.csv and results.csv,
    then filter players with playing time > 900 minutes and display that time.
    """
    try:
        df_transfers = pd.read_csv('football_transfers_players.csv')
        df_fbref = pd.read_csv('results.csv')
        print("Successfully read 'football_transfers_players.csv' and 'results.csv'.")
    except FileNotFoundError as e:
        print(f"Error: One of the required CSV files not found: {e}")
        print("Ensure 'football_transfers_players.csv' and 'results.csv' are created and in the same directory.")
        return
    except pd.errors.EmptyDataError as e:
        print(f"Error: One of the CSV files is empty: {e}")
        return
    except Exception as e:
        print(f"Unknown error reading CSV files: {e}")
        return

    if 'player_name' in df_transfers.columns:
        df_transfers.rename(columns={'player_name': 'Player'}, inplace=True)
    elif 'Player' not in df_transfers.columns:
        print("Error: No player name column ('player_name' or 'Player') found in 'football_transfers_players.csv'.")
        return

    if 'Player' not in df_fbref.columns:
        print("Error: No 'Player' column found in 'results.csv'.")
        return

    minutes_col_fbref = None
    candidate_minute_cols = ['Playing_Time_Min', 'Min', 'minutes']

    for col_name in candidate_minute_cols:
        if col_name in df_fbref.columns:
            minutes_col_fbref = col_name
            break

    if minutes_col_fbref is None:
        possible_min_cols = [col for col in df_fbref.columns if 'min' in col.lower() and ('time' in col.lower() or 'play' in col.lower() or col.lower() == 'min')]
        if possible_min_cols:
            minutes_col_fbref = possible_min_cols[0]
            print(f"Warning: No standard minutes column found. Using heuristic column: '{minutes_col_fbref}'")
        else:
            print(f"Error: Could not identify minutes played column in 'results.csv'. Available columns: {df_fbref.columns.tolist()}")
            return

    print(f"Using column '{minutes_col_fbref}' from 'results.csv' for filtering minutes played.")

    df_fbref[minutes_col_fbref] = pd.to_numeric(df_fbref[minutes_col_fbref], errors='coerce')
    df_fbref.dropna(subset=[minutes_col_fbref], inplace=True)

    df_fbref_filtered = df_fbref[df_fbref[minutes_col_fbref] > 900][['Player', minutes_col_fbref]].copy()

    if df_fbref_filtered.empty:
        print(f"\nNo players in 'results.csv' with playing time ({minutes_col_fbref}) > 900 minutes.")
        return

    df_fbref_filtered.rename(columns={minutes_col_fbref: 'Total_Minutes_Played'}, inplace=True)

    players_with_high_minutes_count = df_fbref_filtered['Player'].nunique()
    print(f"\nFound {players_with_high_minutes_count} players in 'results.csv' with > 900 minutes played.")

    players_to_keep = df_fbref_filtered['Player'].unique()
    df_transfers_filtered_by_name = df_transfers[df_transfers['Player'].isin(players_to_keep)].copy()

    df_fbref_for_merge = df_fbref_filtered.drop_duplicates(subset=['Player'], keep='first')
    df_final_output = pd.merge(df_transfers_filtered_by_name, df_fbref_for_merge, on='Player', how='left')

    print(f"\nInitial number of players in 'football_transfers_players.csv': {len(df_transfers)}")
    print(f"Final number of players (matching > 900 minutes criteria and in transfers): {len(df_final_output)}")

    if not df_final_output.empty:
        print("\n--- Preview of first 5 rows of filtered player data (including total minutes played): ---")
        print(df_final_output.head())

        try:
            output_filename = 'filtered_football_transfers_players_gt900min_with_total_time.csv'
            cols = ['Player'] + [col for col in df_final_output.columns if col != 'Player' and col != 'Total_Minutes_Played'] + ['Total_Minutes_Played']
            cols_exist = [col for col in cols if col in df_final_output.columns]
            df_final_output_ordered = df_final_output[cols_exist]
            df_final_output_ordered.to_csv(output_filename, index=False, encoding='utf-8-sig')
            print(f"\nSaved filtered player data to '{output_filename}'")
        except Exception as e:
            print(f"Error saving output CSV file: {e}")
    else:
        print("\nNo players from 'football_transfers_players.csv' match the > 900 minutes criteria or could not be merged.")

if __name__ == '__main__':
    combine_and_filter_player_data()
