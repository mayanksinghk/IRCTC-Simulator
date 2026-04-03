#!/usr/bin/env python3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 1. Turbocharge the CPU for the GMM calculation
from sklearnex import patch_sklearn
patch_sklearn()

from sklearn.mixture import GaussianMixture
from sklearn.model_selection import GridSearchCV

# 2. Use the NVIDIA GPU for the heavy KDE calculation
from cuml.neighbors import KernelDensity

# Load and prepare the data
df = pd.read_csv('Analysis_Results/8-9_http_delays.csv')
data = df['HTTP_Response_Time_Seconds'].values.reshape(-1, 1)

# Filter out negative/zero values and extreme outliers
data = data[(data > 0) & (data < 2.0)].reshape(-1, 1)

# CRITICAL CHANGE: GPUs strongly prefer float32 for speed
data = data.astype(np.float32)

# ==========================================
# 2. AUTOMATIC GMM SELECTION (Using Optimized CPU)
# ==========================================
print("Calculating optimal GMM components (CPU)...")
n_components_range = range(2, 25) 
bics = []
gmm_models = []

for n in n_components_range:
    gmm = GaussianMixture(n_components=n, covariance_type='full', random_state=42)
    gmm.fit(data)
    bics.append(gmm.bic(data)) 
    gmm_models.append(gmm)
    print(f"Tested GMM with n_components={n}, BIC={bics[-1]:.2f}")

optimal_n_index = np.argmin(bics)
best_gmm = gmm_models[optimal_n_index]
optimal_n = n_components_range[optimal_n_index]

print(f"--> Best GMM n_components found: {optimal_n}")

# ==========================================
# 3. AUTOMATIC KDE SELECTION (Using NVIDIA GPU)
# ==========================================
print("Calculating optimal KDE bandwidth on NVIDIA GPU (this will be fast)...")
bandwidth_grid = {'bandwidth': np.logspace(-3, np.log10(0.5), 30).astype(np.float32)}

# We pass the cuML KernelDensity estimator into standard sklearn GridSearchCV
# Do NOT use n_jobs=-1 here, as multiple threads fighting for VRAM will crash it
grid = GridSearchCV(KernelDensity(kernel='gaussian'), bandwidth_grid, cv=3, verbose=3)
grid.fit(data)

best_kde = grid.best_estimator_
optimal_bw = best_kde.bandwidth

print(f"--> Best KDE bandwidth found: {optimal_bw:.5f}")

# ==========================================
# 4. VISUALIZE THE AUTOMATED RESULTS
# ==========================================
x_plot = np.linspace(0, 0.5, 2000, dtype=np.float32).reshape(-1, 1)

# Calculate densities. cuML gracefully returns NumPy arrays if you feed it NumPy arrays!
gmm_density = np.exp(best_gmm.score_samples(x_plot))
kde_density = np.exp(best_kde.score_samples(x_plot))

# Plotting
plt.figure(figsize=(12, 6))

plt.hist(data, bins=1000, density=True, alpha=0.3, color='gray', label='Original Data', range=(0, 0.5))
plt.plot(x_plot, gmm_density, color='red', lw=2, label=f'Auto GMM (n={optimal_n})')
plt.plot(x_plot, kde_density, color='blue', linestyle='--', lw=2, label=f'Auto KDE (bw={optimal_bw:.4f})')

plt.title('Auto-Tuned Digital Twin Models: GMM (CPU) vs KDE (GPU)')
plt.xlabel('Response Time (Seconds)')
plt.ylabel('Probability Density')
plt.xlim(0, 0.5)
plt.legend()
plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('auto_tuned_models.png')
plt.show()