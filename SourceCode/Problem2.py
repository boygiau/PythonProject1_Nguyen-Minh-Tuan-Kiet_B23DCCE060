import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
import traceback
import re

# --- Configuration ---
INPUT_CSV = 'results.csv'
OUTPUT_TOP_BOTTOM = 'top_3.txt'
OUTPUT_STATS_SUMMARY = 'results2.csv'
OUTPUT_HISTOGRAM_DIR = 'histograms'
HIST_SUBDIR_ALL = 'all_players'
HIST_SUBDIR_TEAMS = 'by_team'
OUTPUT_HIGHEST_SCORING_TEAMS = 'highest_scoring_teams.txt' # For highest scoring teams output

ID_COLS = ['Player', 'Team', 'Nation', 'Position', 'Age']

# Patterns for selecting specific stats for histograms
HISTOGRAM_OFFENSIVE_PATTERNS = [
    'gls', 'goal', 'sh', 'shot', 'sot', 'xg', 'npxg', 'xa', 'assist', 'keypass', 'kp',
    'sca', 'gca', 'att_pen', 'crspa', 'succ_dribbles', 'prog_passes_rec', 'touches_att_pen',
    'progcarry', 'progpass' # Added for progressive carries/passes if named as such
]
HISTOGRAM_DEFENSIVE_PATTERNS = [
    'tkl', 'tackle', 'tklw', 'int', 'interception', 'block', 'clr', 'clearance',
    'sav', 'save', 'cs', 'clean_sheet', 'ga', 'goals_against', 'err', # 'ga' and 'goals_against' for goals against
    'crdy', 'crdr', 'card', 'foul', 'aerialswon', 'pkcon', 'pressure', 'recover'
]


# --- Helper Functions ---
def clean_numeric_column(series):
    series_str = series.astype(str)
    series_cleaned = series_str.str.replace('%', '', regex=False)
    series_cleaned = series_cleaned.str.replace(',', '', regex=False)
    series_numeric = pd.to_numeric(series_cleaned, errors='coerce')
    return series_numeric

def get_numeric_columns(df, exclude_cols):
    numeric_cols = []
    potential_cols = [col for col in df.columns if col not in exclude_cols]
    print(f"  Potentially analyzing {len(potential_cols)} columns (excluding: {', '.join(exclude_cols)})")
    original_dtypes = df[potential_cols].dtypes

    for col in potential_cols:
        if pd.api.types.is_numeric_dtype(original_dtypes[col]):
            numeric_cols.append(col)
            continue
        try:
            # Attempt to coerce to numeric, then check ratio of valid numbers
            coerced = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
            valid_ratio = coerced.notna().sum() / len(coerced) if len(coerced) > 0 else 0
            if valid_ratio > 0.1: # Consider a column numeric if more than 10% can be converted
                numeric_cols.append(col)
        except Exception as e:
            print(f"  Skipping column '{col}' due to error during numeric check: {e}", file=sys.stderr)
    return sorted(list(set(numeric_cols)))

def format_player_list(series):
    return [f"{player} ({score})" for player, score in series.items()]

# --- Main Analysis Logic ---
if __name__ == "__main__":
    print(f"Loading data from {INPUT_CSV}...")
    try:
        df = pd.read_csv(INPUT_CSV)
        print(f"Data loaded successfully. Shape: {df.shape}")
        if df.empty:
            print(f"Error: {INPUT_CSV} is empty. Cannot proceed.", file=sys.stderr)
            sys.exit(1)
        print(f"Original columns ({len(df.columns)}): {', '.join(df.columns[:min(10, len(df.columns))])}...") # Show first 10
        if 'Player' in df.columns: df['Player'] = df['Player'].astype(str)
        if 'Team' in df.columns: df['Team'] = df['Team'].astype(str)
    except FileNotFoundError:
        print(f"Error: {INPUT_CSV} not found. Please ensure the file exists.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading {INPUT_CSV}: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(1)

    print("\nApplying cleaning to potential numeric columns...")
    df_cleaned = df.copy()
    potential_numeric_cols_for_cleaning = [col for col in df.columns if col not in ID_COLS]
    cleaned_count = 0
    for col in potential_numeric_cols_for_cleaning:
        if col in df_cleaned.columns and not pd.api.types.is_numeric_dtype(df_cleaned[col]):
            df_cleaned[col] = clean_numeric_column(df_cleaned[col])
            cleaned_count += 1
    print(f"Attempted cleaning on {cleaned_count} non-numeric columns (excluding ID cols).")

    print("\nIdentifying numeric columns for analysis after cleaning...")
    NON_STAT_COLS = list(ID_COLS)
    # Add specific playing time columns from your CSV structure to NON_STAT_COLS
    # Common playing time columns that might appear from Problem1.py
    # (e.g., Playing_Time_Min, Playing_Time_MP, Playing_Time_Starts)
    # Adjust these based on the actual output of Problem1.py if needed
    generated_playing_time_cols = ['Playing_Time_Min', 'Playing_Time_MP', 'Playing_Time_Starts', 'Min', 'MP', 'Starts']
    for pt_col in generated_playing_time_cols:
        if pt_col in df_cleaned.columns:
            NON_STAT_COLS.append(pt_col)
    NON_STAT_COLS = sorted(list(set(NON_STAT_COLS))) # Ensure unique

    stat_cols = get_numeric_columns(df_cleaned, NON_STAT_COLS)

    if not stat_cols:
        print("\nError: No numeric statistic columns identified after cleaning.", file=sys.stderr)
        print("Please check the input CSV structure and the cleaning/identification logic.")
        print(f"  Columns excluded as non-stats: {NON_STAT_COLS}")
        sys.exit(1)

    print(f"\nIdentified {len(stat_cols)} numeric statistic columns for analysis.")
    # Example: print first 5 stat_cols
    print(f"  Sample stats: {', '.join(stat_cols[:min(5, len(stat_cols))])}...")
    # GK stats identification (remains useful)
    potential_gk_cols_in_stats = [c for c in stat_cols if 'gk' in c.lower() or 'goal' in c.lower() or 'sav' in c.lower() or 'pk' in c.lower() or 'ga' in c.lower() or 'cs' in c.lower()]
    if potential_gk_cols_in_stats:
        print(f"  Potential GK stats identified: {', '.join(sorted(potential_gk_cols_in_stats))}")
    else:
        print("  No columns matching typical Goalkeeping patterns found in identified stats.")
    df_numeric = df_cleaned

    print(f"\nCalculating Top/Bottom 3 players per statistic -> {OUTPUT_TOP_BOTTOM}")
    try:
        with open(OUTPUT_TOP_BOTTOM, 'w', encoding='utf-8') as f:
            f.write("Top and Bottom 3 Players per Statistic\n")
            f.write("=======================================\n\n")
            for col in stat_cols:
                if 'Player' not in df_numeric.columns:
                    f.write(f"--- {col} ---\n")
                    f.write("Error: 'Player' column not found. Cannot determine top/bottom players.\n\n")
                    continue
                
                # Ensure the column actually exists in df_numeric before proceeding
                if col not in df_numeric.columns:
                    f.write(f"--- {col} ---\n")
                    f.write(f"Error: Column '{col}' not found in DataFrame for Top/Bottom analysis.\n\n")
                    continue

                stat_df = df_numeric[['Player', col]].copy()
                stat_df[col] = pd.to_numeric(stat_df[col], errors='coerce') # Coerce to numeric
                stat_df.dropna(subset=[col], inplace=True)

                if stat_df.empty:
                    f.write(f"--- {col} ---\n")
                    f.write(f"No valid numeric data for this statistic ('{col}').\n\n")
                    continue
                try:
                    highest = stat_df.sort_values(by=col, ascending=False).set_index('Player')[col]
                    lowest = stat_df.sort_values(by=col, ascending=True).set_index('Player')[col]
                    top_3 = highest.head(3)
                    bottom_3 = lowest.head(3)
                    f.write(f"--- {col} ---\n")
                    f.write("Top 3:\n")
                    if not top_3.empty:
                        for player, score in top_3.items():
                            score_str = f"{score:.2f}" if pd.notna(score) else "N/A"
                            f.write(f"  - {player}: {score_str}\n")
                    else:
                        f.write("  (No players found for Top 3)\n")
                    f.write("\nBottom 3:\n")
                    if not bottom_3.empty:
                        for player, score in bottom_3.items():
                            score_str = f"{score:.2f}" if pd.notna(score) else "N/A"
                            f.write(f"  - {player}: {score_str}\n")
                    else:
                        f.write("  (No players found for Bottom 3)\n")
                    f.write("\n---------------------------------------\n\n")
                except Exception as sort_err:
                    f.write(f"--- {col} ---\n")
                    f.write(f"Error sorting data for statistic '{col}': {sort_err}\n\n")
                    f.write("---------------------------------------\n\n")
        print("Top/Bottom 3 players saved.")
    except Exception as e:
        print(f"Error during Task 1 (Top/Bottom 3): {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)

    print(f"\nCalculating Median, Mean, Std Dev per statistic -> {OUTPUT_STATS_SUMMARY}")
    results_data = []
    try:
        if not stat_cols:
            print("Warning: No numeric stats columns identified for Task 2.", file=sys.stderr)
        else:
            # Ensure only existing stat_cols are used for aggregation
            valid_stat_cols_for_agg = [sc for sc in stat_cols if sc in df_numeric.columns]
            if not valid_stat_cols_for_agg:
                 print("Warning: None of the identified stat_cols exist in the DataFrame for aggregation.", file=sys.stderr)
            else:
                global_agg = df_numeric[valid_stat_cols_for_agg].agg(['median', 'mean', 'std'])
                for stat in valid_stat_cols_for_agg:
                    if stat in global_agg.columns:
                        results_data.append({
                            'Team': 'all',
                            'Statistic': stat,
                            'Median': global_agg.loc['median', stat],
                            'Mean': global_agg.loc['mean', stat],
                            'Std': global_agg.loc['std', stat]
                        })
                    else:
                        print(f"Warning: Statistic '{stat}' not found in global aggregation results.", file=sys.stderr)

        if 'Team' in df_numeric.columns:
            valid_teams_df = df_numeric[df_numeric['Team'].astype(str).str.lower() != 'all']
            if not valid_teams_df.empty:
                teams_for_grouping = valid_teams_df['Team'].unique()
                if len(teams_for_grouping) > 0 and valid_stat_cols_for_agg: # Also check if there are stats to group by
                    grouped = valid_teams_df.groupby('Team')[valid_stat_cols_for_agg]
                    if not grouped.groups:
                        print("Warning: Grouping by 'Team' resulted in empty groups.", file=sys.stderr)
                    else:
                        try:
                            team_agg = grouped.agg(['median', 'mean', 'std'])
                            if team_agg.empty:
                                print("Warning: Aggregation per team produced empty results.", file=sys.stderr)
                            else:
                                for team_name_idx in team_agg.index:
                                    for stat_col_name_agg in valid_stat_cols_for_agg:
                                        median_key = (stat_col_name_agg, 'median')
                                        mean_key = (stat_col_name_agg, 'mean')
                                        std_key = (stat_col_name_agg, 'std')
                                        if median_key in team_agg.columns and mean_key in team_agg.columns and std_key in team_agg.columns:
                                            results_data.append({
                                                'Team': team_name_idx,
                                                'Statistic': stat_col_name_agg,
                                                'Median': team_agg.loc[team_name_idx, median_key],
                                                'Mean': team_agg.loc[team_name_idx, mean_key],
                                                'Std': team_agg.loc[team_name_idx, std_key]
                                            })
                        except Exception as group_agg_e:
                            print(f"Error during per-team aggregation: {group_agg_e}", file=sys.stderr)
                            print(traceback.format_exc(), file=sys.stderr)
                elif not valid_stat_cols_for_agg:
                    print("Warning: No valid stat columns to perform per-team aggregation.", file=sys.stderr)
                else:
                    print("Warning: No unique teams found for per-team statistics (excluding 'all').", file=sys.stderr)
            else:
                print("Warning: DataFrame became empty after filtering out 'all' team. No per-team stats.", file=sys.stderr)
        else:
            print("Warning: 'Team' column not found. Cannot calculate per-team statistics.", file=sys.stderr)

        if not results_data:
            print("Error: No statistics could be calculated for Task 2.", file=sys.stderr)
        else:
            summary_long_df = pd.DataFrame(results_data)
            summary_long_df.fillna(value=np.nan, inplace=True)
            if summary_long_df.empty or not {'Team', 'Statistic', 'Median', 'Mean', 'Std'}.issubset(summary_long_df.columns):
                print("Error: Cannot create pivot table due to missing columns or empty data frame after aggregation.", file=sys.stderr)
            else:
                try:
                    summary_pivot = summary_long_df.pivot_table(
                        index='Team', columns='Statistic', values=['Median', 'Mean', 'Std']
                    )
                    if isinstance(summary_pivot.columns, pd.MultiIndex):
                        summary_pivot.columns = summary_pivot.columns.swaplevel(0, 1)
                        metric_order = pd.CategoricalDtype(['Median', 'Mean', 'Std'], ordered=True)
                        summary_pivot.sort_index(axis=1, level=0, inplace=True)
                        summary_pivot.sort_index(axis=1, level=1, key=lambda x: x.astype(metric_order), inplace=True)
                        summary_pivot.columns = [f"{metric} of {stat}" for stat, metric in summary_pivot.columns]
                    summary_pivot = summary_pivot.reset_index()
                    if 'all' in summary_pivot['Team'].values:
                        all_row = summary_pivot[summary_pivot['Team'] == 'all']
                        other_rows = summary_pivot[summary_pivot['Team'] != 'all'].sort_values(by='Team')
                        summary_pivot = pd.concat([all_row, other_rows], ignore_index=True)
                    summary_pivot.to_csv(OUTPUT_STATS_SUMMARY, index=False, encoding='utf-8-sig', float_format='%.3f')
                    print(f"Median/Mean/Std Dev summary saved to {OUTPUT_STATS_SUMMARY}")
                except Exception as pivot_e:
                    print(f"Error during pivoting or formatting results for Task 2: {pivot_e}", file=sys.stderr)
                    print(traceback.format_exc(), file=sys.stderr)
    except Exception as e:
        print(f"Error during Task 2 (Median/Mean/Std Dev): {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)

    # --- Task: Identify teams with the highest average score per statistic (Requirement 1) ---
    print(f"\nIdentifying teams with the highest average score per statistic -> {OUTPUT_HIGHEST_SCORING_TEAMS}")
    highest_scoring_teams_dict = {} # Renamed to avoid conflict
    if 'Team' in df_numeric.columns and stat_cols: # Check if stat_cols is not empty
        try:
            valid_teams_df_for_means = df_numeric[df_numeric['Team'].astype(str).str.lower() != 'all'].copy()
            # Ensure only existing stat_cols are used
            existing_stat_cols_for_means = [sc for sc in stat_cols if sc in valid_teams_df_for_means.columns]

            if not valid_teams_df_for_means.empty and existing_stat_cols_for_means:
                for col in existing_stat_cols_for_means: # Ensure numeric type for mean calculation
                    valid_teams_df_for_means[col] = pd.to_numeric(valid_teams_df_for_means[col], errors='coerce')
                
                team_means = valid_teams_df_for_means.groupby('Team')[existing_stat_cols_for_means].mean()

                if not team_means.empty:
                    with open(OUTPUT_HIGHEST_SCORING_TEAMS, 'w', encoding='utf-8') as f_highest:
                        f_highest.write("Team with Highest Average Score per Statistic\n")
                        f_highest.write("=============================================\n\n")
                        for col in existing_stat_cols_for_means:
                            if col in team_means.columns and team_means[col].notna().any():
                                try:
                                    best_team_idx = team_means[col].idxmax()
                                    highest_score_val = team_means[col].max()
                                    highest_scoring_teams_dict[col] = (best_team_idx, highest_score_val)
                                    f_highest.write(f"- Highest Avg {col}: {best_team_idx} ({highest_score_val:.2f})\n")
                                    # print(f"- Highest Avg {col}: {best_team_idx} ({highest_score_val:.2f})") # Optional console print
                                except ValueError:
                                    f_highest.write(f"- Highest Avg {col}: N/A (all values NaN or empty after grouping)\n")
                                except Exception as idxmax_e:
                                    f_highest.write(f"- Highest Avg {col}: Error ({idxmax_e})\n")
                            else:
                                f_highest.write(f"- Highest Avg {col}: N/A (column data insufficient or all NaN)\n")
                    print(f"Highest scoring team data saved to {OUTPUT_HIGHEST_SCORING_TEAMS}")
                else:
                    print("Warning: Calculating team means resulted in an empty DataFrame.", file=sys.stderr)
            elif not existing_stat_cols_for_means:
                 print("Warning: No valid statistic columns found in DataFrame to calculate team means.", file=sys.stderr)
            else: # valid_teams_df_for_means is empty
                print("Warning: No valid team data (excluding 'all') to calculate highest scores.", file=sys.stderr)
        except Exception as e:
            print(f"Error during Highest Team Scores task: {e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
    elif not 'Team' in df_numeric.columns:
        print("Warning: 'Team' column not found. Cannot perform Highest Team Scores task.", file=sys.stderr)
    else: # stat_cols is empty
        print("Warning: No numeric statistics identified. Cannot perform Highest Team Scores task.", file=sys.stderr)


    # --- Filter stats for histograms (Requirement 2) ---
    print("\nSelecting Offensive and Defensive statistics for histogram generation...")
    stats_for_histograms = []
    if stat_cols: # Ensure stat_cols is not empty
        all_hist_patterns = HISTOGRAM_OFFENSIVE_PATTERNS + HISTOGRAM_DEFENSIVE_PATTERNS
        for col in stat_cols:
            if col not in df_numeric.columns: continue # Skip if col somehow isn't in df
            col_lower = col.lower()
            if any(pattern in col_lower for pattern in all_hist_patterns):
                stats_for_histograms.append(col)

    if not stats_for_histograms:
        print("Warning: No offensive or defensive statistics identified for histogram plotting based on current patterns.", file=sys.stderr)
    else:
        print(f"Identified {len(stats_for_histograms)} offensive/defensive stats for histograms: {', '.join(stats_for_histograms[:min(5, len(stats_for_histograms))])}...")


    print(f"\nGenerating histograms for Offensive/Defensive Stats -> {OUTPUT_HISTOGRAM_DIR}/")
    hist_path_all = os.path.join(OUTPUT_HISTOGRAM_DIR, HIST_SUBDIR_ALL)
    hist_path_teams = os.path.join(OUTPUT_HISTOGRAM_DIR, HIST_SUBDIR_TEAMS)
    try:
        os.makedirs(hist_path_all, exist_ok=True)
        os.makedirs(hist_path_teams, exist_ok=True)
    except OSError as e:
        print(f"Error creating histogram directories: {e}", file=sys.stderr)
        # Decide if to exit or continue: sys.exit(1) or pass

    plot_errors_all = 0
    plots_generated_all = 0
    plot_errors_teams = 0
    plots_generated_teams = 0

    for col in stats_for_histograms: # Use the filtered list
        try:
            data_to_plot_all = df_numeric[col].dropna() # Ensure col exists
            if data_to_plot_all.empty or not pd.api.types.is_numeric_dtype(data_to_plot_all):
                pass
            else:
                plt.figure(figsize=(10, 6))
                plt.hist(data_to_plot_all, bins=20, edgecolor='black', color='skyblue')
                plt.title(f'Distribution of {col} (All Players)')
                plt.xlabel(col)
                plt.ylabel('Frequency (Number of Players)')
                plt.grid(axis='y', alpha=0.75)
                safe_col_name = "".join(c if c.isalnum() else "_" for c in col)
                plot_filename_all = os.path.join(hist_path_all, f'hist_all_{safe_col_name}.png')
                plt.savefig(plot_filename_all)
                plt.close()
                plots_generated_all += 1
        except Exception as e:
            plot_errors_all += 1
            print(f"Error generating histogram for {col} (All Players): {e}", file=sys.stderr)
            plt.close()

        if 'Team' in df_numeric.columns:
            # Ensure team names are strings for filtering and file naming
            teams_list = df_numeric[df_numeric['Team'].astype(str).str.lower() != 'all']['Team'].astype(str).dropna().unique()
            if len(teams_list) == 0:
                continue
            for team_name_str in teams_list:
                try:
                    team_data = df_numeric[df_numeric['Team'] == team_name_str][col].dropna()
                    if team_data.empty or not pd.api.types.is_numeric_dtype(team_data):
                        continue
                    plt.figure(figsize=(8, 5))
                    plt.hist(team_data, bins=15, edgecolor='black', color='lightcoral')
                    plt.title(f'Distribution of {col} for {team_name_str}', fontsize=10)
                    plt.xlabel(col, fontsize=9)
                    plt.ylabel('Frequency', fontsize=9)
                    plt.xticks(fontsize=8); plt.yticks(fontsize=8)
                    plt.grid(axis='y', alpha=0.6)
                    safe_col_name = "".join(c if c.isalnum() else "_" for c in col)
                    safe_team_name = "".join(c if c.isalnum() else "_" for c in team_name_str) # team_name_str is already string
                    plot_filename_team = os.path.join(hist_path_teams, f'hist_{safe_team_name}_{safe_col_name}.png')
                    plt.savefig(plot_filename_team)
                    plt.close()
                    plots_generated_teams += 1
                except Exception as e:
                    plot_errors_teams += 1
                    print(f"Error generating histogram for {col} - {team_name_str}: {e}", file=sys.stderr)
                    plt.close()

    print(f"\nHistograms generation summary (Offensive/Defensive Stats):")
    print(f"  - All Players: {plots_generated_all} successful, {plot_errors_all} errors.")
    if 'Team' in df_numeric.columns:
        print(f"  - Per Team:    {plots_generated_teams} successful, {plot_errors_teams} errors.")

    # --- Best Performing Team Analysis (using highest_scoring_teams_dict) ---
    print("\n--- Best Performing Team Analysis (Based on Average Stats) ---")
    analysis_text = "Based on the average statistics per team:\n"
    team_mentions_high = {}
    team_mentions_low = {}
    
    # Define patterns for interpreting stats (can be reused or adjusted)
    # These are used for the textual analysis part.
    LOWER_IS_BETTER_PATTERNS = ['ga', 'goals_against', 'offside', 'fls', 'foul', 'lost', 'crd', 'card', 'pkcon', 'err_leading_to_shot'] # Added more specific
    KEY_OFFENSIVE_PATTERNS_TEXT = ['gls', 'goal', 'xg', 'sot', 'sca', 'gca', 'att_pen', 'shot', 'assist', 'key_pass', 'prog_pass_rec']
    KEY_DEFENSIVE_PATTERNS_TEXT = ['tklw', 'tackles_won', 'int', 'interception', 'block', 'clr', 'clearance', 'sav', 'save', 'cs', 'clean_sheet', 'aerial_won']
    KEY_POSSESSION_PATTERNS_TEXT = ['cmp_pct', 'pass_accuracy', 'prgp', 'progressive_pass', 'prgc', 'progressive_carr', 'touch', 'progression', 'prog']


    if highest_scoring_teams_dict:
        current_team_means_for_analysis = pd.DataFrame() # Initialize
        if 'Team' in df_numeric.columns and stat_cols:
            temp_df = df_numeric[df_numeric['Team'].astype(str).str.lower() != 'all'].copy()
            valid_cols = [c for c in stat_cols if c in temp_df.columns]
            if valid_cols:
                for c in valid_cols: temp_df[c] = pd.to_numeric(temp_df[c], errors='coerce')
                current_team_means_for_analysis = temp_df.groupby('Team')[valid_cols].mean()

        for stat, (team, score) in highest_scoring_teams_dict.items():
            stat_lower = stat.lower()
            is_lower_better_stat = any(pattern in stat_lower for pattern in LOWER_IS_BETTER_PATTERNS)

            if is_lower_better_stat:
                if not current_team_means_for_analysis.empty and stat in current_team_means_for_analysis.columns and current_team_means_for_analysis[stat].notna().any():
                    try:
                        min_team_idx = current_team_means_for_analysis[stat].idxmin()
                        team_mentions_low[min_team_idx] = team_mentions_low.get(min_team_idx, 0) + 1
                    except ValueError: pass # All NaN for this stat
                    except Exception as min_err: print(f"  (Error determining min for {stat}: {min_err})")
            else:
                team_mentions_high[team] = team_mentions_high.get(team, 0) + 1
        
        most_mentioned_high = sorted(team_mentions_high.items(), key=lambda item: item[1], reverse=True)
        most_mentioned_low = sorted(team_mentions_low.items(), key=lambda item: item[1], reverse=True)

        if most_mentioned_high:
            analysis_text += f"- '{most_mentioned_high[0][0]}' leads {most_mentioned_high[0][1]} 'higher-is-better' stats.\n"
        if most_mentioned_low:
            analysis_text += f"- '{most_mentioned_low[0][0]}' leads {most_mentioned_low[0][1]} 'lower-is-better' stats.\n"

        def get_leaders_text_analysis(patterns, means_df, lower_better_def):
            leaders = {} # Store as {team: count_of_leading_stats}
            if means_df.empty: return {"N/A"}
            for stat_col in means_df.columns:
                stat_col_lower = stat_col.lower()
                if any(p in stat_col_lower for p in patterns):
                    if means_df[stat_col].notna().any():
                        try:
                            best_team = means_df[stat_col].idxmin() if any(lb in stat_col_lower for lb in lower_better_def) else means_df[stat_col].idxmax()
                            leaders[best_team] = leaders.get(best_team, 0) + 1
                        except ValueError: pass # All NaN
            # Return teams sorted by how many relevant stats they lead
            sorted_leaders = sorted(leaders.items(), key=lambda x:x[1], reverse=True)
            return {team for team, count in sorted_leaders[:3]} if sorted_leaders else {"N/A"} # Top 3 or N/A


        if not current_team_means_for_analysis.empty:
            off_leaders = get_leaders_text_analysis(KEY_OFFENSIVE_PATTERNS_TEXT, current_team_means_for_analysis, LOWER_IS_BETTER_PATTERNS)
            def_leaders = get_leaders_text_analysis(KEY_DEFENSIVE_PATTERNS_TEXT + LOWER_IS_BETTER_PATTERNS, current_team_means_for_analysis, LOWER_IS_BETTER_PATTERNS) # include lower_is_better in def patterns
            poss_leaders = get_leaders_text_analysis(KEY_POSSESSION_PATTERNS_TEXT, current_team_means_for_analysis, LOWER_IS_BETTER_PATTERNS)
            analysis_text += f"- Offensive Leaders (top teams by # of led stats): {', '.join(sorted(list(off_leaders)))}\n"
            analysis_text += f"- Defensive Leaders: {', '.join(sorted(list(def_leaders)))}\n"
            analysis_text += f"- Possession Leaders: {', '.join(sorted(list(poss_leaders)))}\n"
        else:
             analysis_text += "Could not generate detailed categorical leaders as team means were not available for analysis.\n"

    else:
        analysis_text += "Could not determine highest scoring teams, so further detailed analysis is limited.\n"

    analysis_text += "\nDisclaimer: This analysis is based solely on average player statistics per team derived from the input data..."
    print(analysis_text)
    try:
        with open("team_performance_analysis_summary.txt", "w", encoding="utf-8") as f_analysis:
            f_analysis.write(analysis_text)
        print("\nTeam performance analysis summary saved to team_performance_analysis_summary.txt")
    except Exception as e_write_analysis:
        print(f"Error writing team performance analysis summary: {e_write_analysis}")

    print("\n--- Analysis Finished ---")
