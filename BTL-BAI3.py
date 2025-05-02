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

try:
    df = pd.read_csv('result.csv')
    print(f"Đã tải thành công file result.csv. Kích thước: {df.shape}")
except FileNotFoundError:
    print("Lỗi: Không tìm thấy file 'result.csv'.")
    print("Vui lòng đảm bảo bạn đã chạy script BTL-BAI1.py trước và file CSV đã được tạo trong cùng thư mục.")
    exit()
except Exception as e:
    print(f"Lỗi khi đọc file CSV: {e}")
    exit()

player_info = df[['Player', 'Team', 'Position', 'Age']].copy()

potential_numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
cols_to_exclude = ['Age']
numeric_features = [col for col in potential_numeric_cols if col not in cols_to_exclude]
categorical_features = ['Position']

features_df = df[numeric_features + categorical_features].copy()

numeric_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='mean')),
    ('scaler', StandardScaler())
])

categorical_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='most_frequent')),
    ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
])

preprocessor = ColumnTransformer(
    transformers=[
        ('num', numeric_transformer, numeric_features),
        ('cat', categorical_transformer, categorical_features)
    ],
    remainder='drop'
)

try:
    X_processed = preprocessor.fit_transform(features_df)
    print(f"Đã xử lý dữ liệu. Kích thước ma trận features: {X_processed.shape}")
    try:
        feature_names_out = preprocessor.get_feature_names_out()
    except AttributeError:
        feature_names_out = numeric_features + \
                            list(preprocessor.transformers_[1][1].named_steps['onehot'] \
                                 .get_feature_names_out(categorical_features))
except Exception as e:
    print(f"Lỗi trong quá trình tiền xử lý dữ liệu: {e}")
    print("Các cột số được chọn:", numeric_features)
    print("Các cột phân loại được chọn:", categorical_features)
    print("Kiểu dữ liệu của các cột số:")
    print(df[numeric_features].dtypes)
    print("Kiểu dữ liệu của các cột phân loại:")
    print(df[categorical_features].dtypes)
    print("Số giá trị NA trong các cột số:")
    print(df[numeric_features].isna().sum())
    print("Số giá trị NA trong các cột phân loại:")
    print(df[categorical_features].isna().sum())
    exit()

inertia = []
possible_k = range(2, 11)

print("\nĐang tính toán Inertia cho các giá trị k khác nhau (Elbow Method)...")
for k in possible_k:
    kmeans = KMeans(n_clusters=k, init='k-means++', random_state=42, n_init=10)
    kmeans.fit(X_processed)
    inertia.append(kmeans.inertia_)

plt.figure(figsize=(10, 6))
plt.plot(possible_k, inertia, marker='o')
plt.title('Phương pháp Elbow để xác định số cụm tối ưu (k)')
plt.xlabel('Số lượng cụm (k)')
plt.ylabel('Inertia (Within-cluster sum of squares)')
plt.xticks(possible_k)
plt.grid(True)
plt.show()

optimal_k = 4
print(f"\n=> Dựa trên biểu đồ Elbow, chọn k = {optimal_k}")

kmeans_final = KMeans(n_clusters=optimal_k, init='k-means++', random_state=42, n_init=10)
clusters = kmeans_final.fit_predict(X_processed)

player_info['Cluster'] = clusters
df['Cluster'] = clusters

print(f"\nĐã phân {len(df)} cầu thủ vào {optimal_k} cụm.")
print("Số lượng cầu thủ trong mỗi cụm:")
print(player_info['Cluster'].value_counts().sort_index())

print("\nĐang thực hiện PCA để giảm chiều dữ liệu xuống 2...")
pca = PCA(n_components=2, random_state=42)
X_pca = pca.fit_transform(X_processed)

pca_df = pd.DataFrame(data=X_pca, columns=['Principal Component 1', 'Principal Component 2'])
pca_df['Cluster'] = clusters
pca_df['Player'] = player_info['Player'].values
pca_df['Position'] = player_info['Position'].values

print("Đang vẽ biểu đồ phân cụm 2D...")
plt.figure(figsize=(12, 8))
sns.scatterplot(
    x="Principal Component 1", y="Principal Component 2",
    hue="Cluster",
    palette=sns.color_palette("hsv", optimal_k),
    data=pca_df,
    legend="full",
    alpha=0.8
)

plt.title(f'Phân cụm cầu thủ ({optimal_k} cụm) sau khi giảm chiều bằng PCA')
plt.xlabel('Principal Component 1')
plt.ylabel('Principal Component 2')
plt.grid(True)
plt.show()

print(f"\nPhân tích đặc điểm cơ bản của {optimal_k} cụm:")
cluster_summary = player_info.groupby('Cluster').agg(
    count=('Player', 'size'),
    common_position=('Position', lambda x: x.mode()[0] if not x.mode().empty else 'N/A'),
    avg_age=('Age', lambda x: pd.to_numeric(x, errors='coerce').mean())
).reset_index()

print("\nĐặc điểm tổng quan các cụm (Số lượng, Vị trí phổ biến, Tuổi trung bình):")
print(cluster_summary)

print("\nGiá trị trung bình của các chỉ số thống kê gốc cho mỗi cụm:")
numeric_original_df = df[numeric_features + ['Cluster']].copy()
for col in numeric_features:
    numeric_original_df[col] = pd.to_numeric(numeric_original_df[col], errors='coerce')

cluster_means = numeric_original_df.groupby('Cluster').mean()
print(cluster_means.round(2))

print("\nThông tin về PCA:")
explained_variance = pca.explained_variance_ratio_
print(f"Phương sai được giải thích bởi PC1: {explained_variance[0]:.2%}")
print(f"Phương sai được giải thích bởi PC2: {explained_variance[1]:.2%}")
print(f"Tổng phương sai được giải thích bởi 2 PCs: {explained_variance.sum():.2%}")
print("\n--- Kết thúc ---")
