import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
import seaborn as sns

# Load the dataset
try:
    df = pd.read_csv('results.csv')
    print(f"Successfully loaded results.csv. Dataset size: {df.shape}")
except FileNotFoundError:
    print("Error: File 'results.csv' not found.")
    print("Please ensure you have run the BTL-BAI1.py script first and the CSV file is created in the same directory.")
    exit()
except Exception as e:
    print(f"Error while reading CSV file: {e}")
    exit()

# Extract player information
player_info = df[['Player', 'Team', 'Position', 'Age']].copy()

# Identify numeric and categorical features
potential_numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
cols_to_exclude = ['Age']
numeric_features = [col for col in potential_numeric_cols if col not in cols_to_exclude]
categorical_features = ['Position']

# Create features dataframe
features_df = df[numeric_features + categorical_features].copy()

# Define preprocessing pipelines
numeric_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='mean')),
    ('scaler', StandardScaler())
])

categorical_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='most_frequent')),
    ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
])

# Combine preprocessors
preprocessor = ColumnTransformer(
    transformers=[
        ('num', numeric_transformer, numeric_features),
        ('cat', categorical_transformer, categorical_features)
    ],
    remainder='drop'
)

# Preprocess the data
try:
    X_processed = preprocessor.fit_transform(features_df)
    print(f"Data preprocessing completed. Feature matrix size: {X_processed.shape}")
    try:
        feature_names_out = preprocessor.get_feature_names_out()
    except AttributeError:
        feature_names_out = numeric_features + \
                            list(preprocessor.transformers_[1][1].named_steps['onehot'] \
                                 .get_feature_names_out(categorical_features))
except Exception as e:
    print(f"Error during data preprocessing: {e}")
    print("Selected numeric columns:", numeric_features)
    print("Selected categorical columns:", categorical_features)
    print("Data types of numeric columns:")
    print(df[numeric_features].dtypes)
    print("Data types of categorical columns:")
    print(df[categorical_features].dtypes)
    print("Number of NA values in numeric columns:")
    print(df[numeric_features].isna().sum())
    print("Number of NA values in categorical columns:")
    print(df[categorical_features].isna().sum())
    exit()

# Calculate inertia for different k values (Elbow Method)
inertia = []
possible_k = range(2, 11)

print("\nCalculating Inertia for different k values (Elbow Method)...")
for k in possible_k:
    kmeans = KMeans(n_clusters=k, init='k-means++', random_state=42, n_init=10)
    kmeans.fit(X_processed)
    inertia.append(kmeans.inertia_)

# Plot the Elbow curve
plt.figure(figsize=(10, 6))
plt.plot(possible_k, inertia, marker='o')
plt.title('Elbow Method for Determining Optimal Number of Clusters (k)')
plt.xlabel('Number of Clusters (k)')
plt.ylabel('Inertia (Within-cluster Sum of Squares)')
plt.xticks(possible_k)
plt.grid(True)
plt.show()

# Select optimal number of clusters
optimal_k = 4
print(f"\n=> Based on the Elbow plot, selected k = {optimal_k}")

# Perform final clustering
kmeans_final = KMeans(n_clusters=optimal_k, init='k-means++', random_state=42, n_init=10)
clusters = kmeans_final.fit_predict(X_processed)

# Add cluster labels to dataframes
player_info['Cluster'] = clusters
df['Cluster'] = clusters

print(f"\nAssigned {len(df)} players to {optimal_k} clusters.")
print("Number of players in each cluster:")
print(player_info['Cluster'].value_counts().sort_index())

# Perform PCA for dimensionality reduction
print("\nPerforming PCA to reduce data to 2 dimensions...")
pca = PCA(n_components=2, random_state=42)
X_pca = pca.fit_transform(X_processed)

# Create PCA dataframe
pca_df = pd.DataFrame(data=X_pca, columns=['Principal Component 1', 'Principal Component 2'])
pca_df['Cluster'] = clusters
pca_df['Player'] = player_info['Player'].values
pca_df['Position'] = player_info['Position'].values

# Plot 2D cluster visualization
print("Plotting 2D cluster visualization...")
plt.figure(figsize=(12, 8))
sns.scatterplot(
    x="Principal Component 1", y="Principal Component 2",
    hue="Cluster",
    palette=sns.color_palette("hsv", optimal_k),
    data=pca_df,
    legend="full",
    alpha=0.8
)

plt.title(f'Player Clustering ({optimal_k} Clusters) After PCA Reduction')
plt.xlabel('Principal Component 1')
plt.ylabel('Principal Component 2')
plt.grid(True)
plt.show()

# Analyze cluster characteristics
print(f"\nAnalyzing basic characteristics of {optimal_k} clusters:")
cluster_summary = player_info.groupby('Cluster').agg(
    count=('Player', 'size'),
    common_position=('Position', lambda x: x.mode()[0] if not x.mode().empty else 'N/A'),
    avg_age=('Age', lambda x: pd.to_numeric(x, errors='coerce').mean())
).reset_index()

print("\nOverview of cluster characteristics (Count, Most Common Position, Average Age):")
print(cluster_summary)

# Calculate mean statistics for each cluster
print("\nMean values of original statistics for each cluster:")
numeric_original_df = df[numeric_features + ['Cluster']].copy()
for col in numeric_features:
    numeric_original_df[col] = pd.to_numeric(numeric_original_df[col], errors='coerce')

cluster_means = numeric_original_df.groupby('Cluster').mean()
print(cluster_means.round(2))

# PCA information
print("\nPCA Information:")
explained_variance = pca.explained_variance_ratio_
print(f"Variance explained by PC1: {explained_variance[0]:.2%}")
print(f"Variance explained by PC2: {explained_variance[1]:.2%}")
print(f"Total variance explained by 2 PCs: {explained_variance.sum():.2%}")

print("\n--- End ---")
