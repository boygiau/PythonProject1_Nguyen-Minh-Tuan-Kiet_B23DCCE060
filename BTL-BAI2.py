import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
import traceback
import re

# --- Configuration ---
INPUT_CSV = 'result.csv'
OUTPUT_TOP_BOTTOM = 'top_3.txt'
OUTPUT_STATS_SUMMARY = 'results2.csv'
OUTPUT_HISTOGRAM_DIR = 'histograms'
HIST_SUBDIR_ALL = 'all_players'
HIST_SUBDIR_TEAMS = 'by_team'

ID_COLS = ['Player', 'Team', 'Nation', 'Position', 'Age']

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
            coerced = pd.to_numeric(df[col], errors='coerce')
            valid_ratio = coerced.notna().sum() / len(coerced) if len(coerced) > 0 else 0
            if valid_ratio > 0.1:
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
        print(f"Original columns ({len(df.columns)}): {', '.join(df.columns[:10])}...")
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
        if not pd.api.types.is_numeric_dtype(df[col]):
            df_cleaned[col] = clean_numeric_column(df[col])
            cleaned_count += 1
    print(f"Attempted cleaning on {cleaned_count} non-numeric columns.")

    print("\nIdentifying numeric columns for analysis after cleaning...")
    NON_STAT_COLS = list(ID_COLS)
    if 'Playing_Time_Min' in df_cleaned.columns:
        NON_STAT_COLS.append('Playing_Time_Min')
    elif 'Playing_Time_MP' in df_cleaned.columns:
         NON_STAT_COLS.append('Playing_Time_MP')
    stat_cols = get_numeric_columns(df_cleaned, NON_STAT_COLS)

    if not stat_cols:
        print("\nError: No numeric statistic columns identified after cleaning.", file=sys.stderr)
        print("Please check the input CSV structure and the cleaning/identification logic.")
        sys.exit(1)

    print(f"\nIdentified {len(stat_cols)} numeric statistic columns for analysis.")
    potential_gk_cols_in_stats = [c for c in stat_cols if 'gk' in c.lower() or 'goal' in c.lower() or 'sav' in c.lower() or 'pk' in c.lower() or 'ga' in c.lower() or 'cs' in c.lower()]
    print(f"  Sample stats: {', '.join(stat_cols[:5])}...")
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
                stat_df = df_numeric[['Player', col]].dropna(subset=[col])
                if stat_df.empty or not pd.api.types.is_numeric_dtype(stat_df[col]):
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
            global_agg = df_numeric[stat_cols].agg(['median', 'mean', 'std'])
            for stat in stat_cols:
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
            valid_teams = df_numeric[df_numeric['Team'].str.lower() != 'all']['Team'].unique()
            if len(valid_teams) > 0:
                grouped = df_numeric[df_numeric['Team'].isin(valid_teams)].groupby('Team')[stat_cols]
                if not grouped.groups:
                     print("Warning: Grouping by 'Team' resulted in empty groups. Cannot calculate per-team stats.", file=sys.stderr)
                else:
                    try:
                        team_agg = grouped.agg(['median', 'mean', 'std'])
                        if team_agg.empty:
                             print("Warning: Aggregation per team produced empty results.", file=sys.stderr)
                        else:
                            for team in team_agg.index:
                                for stat in stat_cols:
                                    median_key = (stat, 'median')
                                    mean_key = (stat, 'mean')
                                    std_key = (stat, 'std')
                                    if median_key in team_agg.columns and \
                                       mean_key in team_agg.columns and \
                                       std_key in team_agg.columns:
                                        median_val = team_agg.loc[team, median_key]
                                        mean_val = team_agg.loc[team, mean_key]
                                        std_val = team_agg.loc[team, std_key]
                                        results_data.append({
                                            'Team': team,
                                            'Statistic': stat,
                                            'Median': median_val,
                                            'Mean': mean_val,
                                            'Std': std_val
                                        })
                    except Exception as group_agg_e:
                        print(f"Error during per-team aggregation: {group_agg_e}", file=sys.stderr)
                        print(traceback.format_exc(), file=sys.stderr)
            else:
                print("Warning: No valid teams found for per-team statistics (excluding 'all').", file=sys.stderr)
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
                    else:
                         print("Warning: Pivot table did not return a MultiIndex. Column formatting might be incorrect.", file=sys.stderr)
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

    print(f"\nGenerating histograms -> {OUTPUT_HISTOGRAM_DIR}/")
    hist_path_all = os.path.join(OUTPUT_HISTOGRAM_DIR, HIST_SUBDIR_ALL)
    hist_path_teams = os.path.join(OUTPUT_HISTOGRAM_DIR, HIST_SUBDIR_TEAMS)
    try:
        os.makedirs(hist_path_all, exist_ok=True)
        os.makedirs(hist_path_teams, exist_ok=True)
    except OSError as e:
         print(f"Error creating histogram directories: {e}", file=sys.stderr)
         sys.exit(1)

    plot_errors_all = 0
    plots_generated_all = 0
    plot_errors_teams = 0
    plots_generated_teams = 0

    for col in stat_cols:
        try:
            data_to_plot_all = df_numeric[col].dropna()
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
            teams = df_numeric[df_numeric['Team'].str.lower() != 'all']['Team'].dropna().unique()
            if len(teams) == 0:
                 continue
            for team in teams:
                try:
                    team_data = df_numeric[df_numeric['Team'] == team][col].dropna()
                    if team_data.empty or not pd.api.types.is_numeric_dtype(team_data):
                        continue
                    plt.figure(figsize=(8, 5))
                    plt.hist(team_data, bins=15, edgecolor='black', color='lightcoral')
                    plt.title(f'Distribution of {col} for {team}', fontsize=10)
                    plt.xlabel(col, fontsize=9)
                    plt.ylabel('Frequency', fontsize=9)
                    plt.xticks(fontsize=8)
                    plt.yticks(fontsize=8)
                    plt.grid(axis='y', alpha=0.6)
                    safe_col_name = "".join(c if c.isalnum() else "_" for c in col)
                    safe_team_name = "".join(c if c.isalnum() else "_" for c in str(team))
                    plot_filename_team = os.path.join(hist_path_teams, f'hist_{safe_team_name}_{safe_col_name}.png')
                    plt.savefig(plot_filename_team)
                    plt.close()
                    plots_generated_teams += 1
                except Exception as e:
                    plot_errors_teams += 1
                    print(f"Error generating histogram for {col} - {team}: {e}", file=sys.stderr)
                    plt.close()

    print(f"\nHistograms generation summary:")
    print(f"  - All Players: {plots_generated_all} successful, {plot_errors_all} errors.")
    if 'Team' in df_numeric.columns:
        print(f"  - Per Team:    {plots_generated_teams} successful, {plot_errors_teams} errors.")

    print("\nIdentifying teams with the highest average score per statistic...")
    highest_scoring_teams = {}
    if 'Team' in df_numeric.columns and len(stat_cols) > 0:
        try:
            valid_teams_df = df_numeric[df_numeric['Team'].str.lower() != 'all']
            if not valid_teams_df.empty:
                team_means = valid_teams_df.groupby('Team')[stat_cols].mean()
                if not team_means.empty:
                     for col in stat_cols:
                         if col in team_means.columns and team_means[col].notna().any():
                             try:
                                 best_team_idx = team_means[col].idxmax()
                                 highest_score = team_means[col].max()
                                 highest_scoring_teams[col] = (best_team_idx, highest_score)
                                 print(f"- Highest Avg {col}: {best_team_idx} ({highest_score:.2f})")
                             except ValueError:
                                 print(f"- Could not find highest avg for {col} (all values might be NaN after grouping).")
                             except Exception as idxmax_e:
                                 print(f"- Error finding highest avg for {col}: {idxmax_e}")
                         else:
                             print(f"- Could not calculate highest avg for {col} (column missing or all NaN in grouped means?).")
                else:
                     print("Warning: Calculating team means resulted in an empty DataFrame.")
            else:
                print("Warning: No valid team data (excluding 'all') to calculate highest scores.")
        except Exception as e:
            print(f"Error during Task 4 (Highest Team Scores): {e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
    elif not 'Team' in df_numeric.columns:
        print("Warning: 'Team' column not found. Cannot perform Task 4.", file=sys.stderr)
    else:
         print("Warning: No numeric statistics identified. Cannot perform Task 4.", file=sys.stderr)

    print("\n--- Best Performing Team Analysis (Based on Average Stats) ---")
    analysis_text = "Based on the average statistics per team:\n"
    team_mentions_high = {}
    team_mentions_low = {}
    LOWER_IS_BETTER_PATTERNS = ['ga', 'goals_against', 'off', 'offsides', 'fls', 'fouls', 'lost', 'crd', 'cards']
    KEY_OFFENSIVE_PATTERNS = ['gls', 'goals', 'xg', 'sot', 'sca', 'gca', 'att_pen']
    KEY_DEFENSIVE_PATTERNS = ['tklw', 'tackles_won', 'int', 'interceptions', 'blocks', 'clr', 'clearances', 'sav', 'save', 'cs', 'clean_sheet']
    KEY_POSSESSION_PATTERNS = ['cmp%', 'pass_accuracy', 'prgp', 'progressive_passes', 'prgc', 'progressive_carries', 'touches', 'progression', 'prog']

    if highest_scoring_teams:
        for stat, (team, score) in highest_scoring_teams.items():
            stat_lower = stat.lower()
            is_lower_better_stat = any(pattern in stat_lower for pattern in LOWER_IS_BETTER_PATTERNS)
            if is_lower_better_stat:
                try:
                    if 'team_means' in locals() and not team_means.empty and stat in team_means.columns and team_means[stat].notna().any():
                        min_team_idx = team_means[stat].idxmin()
                        lowest_score = team_means[stat].min()
                        team_mentions_low[min_team_idx] = team_mentions_low.get(min_team_idx, 0) + 1
                    else:
                         pass
                except Exception as min_err:
                    print(f"  (Could not determine minimum for lower-is-better stat '{stat}': {min_err})")
            else:
                team_mentions_high[team] = team_mentions_high.get(team, 0) + 1

        most_mentioned_high = sorted(team_mentions_high.items(), key=lambda item: item[1], reverse=True)
        most_mentioned_low = sorted(team_mentions_low.items(), key=lambda item: item[1], reverse=True)

        if most_mentioned_high:
            top_team_high, top_count_high = most_mentioned_high[0]
            analysis_text += f"- '{top_team_high}' appears most frequently ({top_count_high} times) leading stats where HIGHER is better.\n"
        else:
             analysis_text += "- No single team dominated the 'higher is better' statistics.\n"
        if most_mentioned_low:
            top_team_low, top_count_low = most_mentioned_low[0]
            analysis_text += f"- '{top_team_low}' appears most frequently ({top_count_low} times) leading stats where LOWER is better (e.g., fewest goals against, fewest fouls).\n"
        else:
             analysis_text += "- No single team dominated the 'lower is better' statistics.\n"

        def get_leaders(patterns, source_dict, lower_better_list=None):
            leaders = set()
            if lower_better_list is None:
                for stat, (team, _) in source_dict.items():
                     stat_lower = stat.lower()
                     if any(p in stat_lower for p in patterns):
                         leaders.add(team)
            else:
                 if 'team_means' in locals() and not team_means.empty:
                     for stat in team_means.columns:
                          stat_lower = stat.lower()
                          if any(p in stat_lower for p in patterns) and any(lb in stat_lower for lb in lower_better_list):
                                if team_means[stat].notna().any():
                                    try:
                                         min_team = team_means[stat].idxmin()
                                         leaders.add(min_team)
                                    except ValueError: pass
                                    except Exception: pass
                 else:
                      return {"Analysis Error: Team means unavailable"}
            return leaders or {"N/A"}

        off_leaders = get_leaders(KEY_OFFENSIVE_PATTERNS, highest_scoring_teams)
        def_leaders_high = get_leaders(KEY_DEFENSIVE_PATTERNS, highest_scoring_teams)
        def_leaders_low = get_leaders(LOWER_IS_BETTER_PATTERNS, highest_scoring_teams, lower_better_list=LOWER_IS_BETTER_PATTERNS)
        poss_leaders = get_leaders(KEY_POSSESSION_PATTERNS, highest_scoring_teams)

        analysis_text += f"- Key Offensive Leaders (Highest Avg): {', '.join(sorted(list(off_leaders)))}\n"
        analysis_text += f"- Key Defensive Leaders (Highest Avg - Tkl, Int, etc.): {', '.join(sorted(list(def_leaders_high)))}\n"
        analysis_text += f"- Key Defensive Leaders (Lowest Avg - GA, Cards, etc.): {', '.join(sorted(list(def_leaders_low)))}\n"
        analysis_text += f"- Key Possession/Progression Leaders (Highest Avg): {', '.join(sorted(list(poss_leaders)))}\n"

        analysis_text += "\nConclusion:\n"
        all_round_strength = set()
        if most_mentioned_high:
            top_high_team = most_mentioned_high[0][0]
            analysis_text += f"- '{top_high_team}' leads the most 'higher-is-better' categories. "
            if most_mentioned_low and top_high_team == most_mentioned_low[0][0]:
                analysis_text += f"Notably, this team also leads in 'lower-is-better' stats, indicating strong all-round performance based on averages. "
                all_round_strength.add(top_high_team)
            analysis_text += "\n"

        strong_off_poss = off_leaders.intersection(poss_leaders) - {"N/A"}
        strong_off_def = off_leaders.intersection(def_leaders_high.union(def_leaders_low)) - {"N/A"}

        if strong_off_poss:
             analysis_text += f"- Teams like {', '.join(sorted(list(strong_off_poss)))} show strength in both offense and possession.\n"
        if strong_off_def:
             analysis_text += f"- Teams like {', '.join(sorted(list(strong_off_def)))} combine offensive strength with solid defensive metrics (high good stats or low bad stats).\n"
        if not most_mentioned_high and not most_mentioned_low:
             analysis_text += "- No single team clearly dominates across multiple statistical areas based on average player performance.\n"
        elif not all_round_strength and not strong_off_poss and not strong_off_def :
             analysis_text += "- While teams lead individual categories, there isn't a clear overlap indicating a dominant 'best' team across different facets of the game based purely on these averages.\n"
    else:
        analysis_text += "Could not determine highest scoring teams, possibly due to lack of data, 'Team' column, or numeric stats.\n"

    analysis_text += "\nDisclaimer: This analysis is based solely on average player statistics per team derived from the input data. It does not include team league points, actual goal difference, fixture difficulty, specific match outcomes, or advanced team-level metrics (like PPDA, build-up speed etc.), which would provide a more complete picture of overall team performance."
    print(analysis_text)

    print("\n--- Analysis Finished ---")
