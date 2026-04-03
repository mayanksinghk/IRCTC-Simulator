#!/usr/bin/env python3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.mixture import GaussianMixture
from sklearn.neighbors import KernelDensity
from sklearn.model_selection import GridSearchCV

# 1. Load and prepare the data
df = pd.read_csv('Analysis_Results/8-9_http_delays.csv')
data = df['HTTP_Response_Time_Seconds'].values.reshape(-1, 1)

# Filter out negative/zero values and extreme outliers for a cleaner fit
data = data[(data > 0) & (data < 2.0)].reshape(-1, 1)

# ==========================================
# 2. AUTOMATIC GMM SELECTION (Using BIC)
# ==========================================
print("Calculating optimal GMM components (this may take a moment)...")
n_components_range = range(2, 25) # Test between 2 and 24 components
bics = []
gmm_models = []

for n in n_components_range:
    gmm = GaussianMixture(n_components=n, covariance_type='full', random_state=42)
    gmm.fit(data)
    bics.append(gmm.bic(data)) # Calculate Bayesian Information Criterion
    gmm_models.append(gmm)
    print(f"Tested GMM with n_components={n}, BIC={bics[-1]:.2f}")

# Find the model with the lowest BIC
optimal_n_index = np.argmin(bics)
best_gmm = gmm_models[optimal_n_index]
optimal_n = n_components_range[optimal_n_index]

print(f"--> Best GMM n_components found: {optimal_n}")

# ==========================================
# 3. AUTOMATIC KDE SELECTION (Using Grid Search CV)
# ==========================================
print("Calculating optimal KDE bandwidth (this may take a moment)...")
# Create a range of bandwidths to test, from 0.001 to 0.5
bandwidth_grid = {'bandwidth': np.logspace(-3, np.log10(0.5), 30)}

# Use 3-fold Cross Validation to find the best bandwidth
grid = GridSearchCV(KernelDensity(kernel='gaussian'), bandwidth_grid, cv=3, n_jobs=-1, verbose=3)
grid.fit(data)

best_kde = grid.best_estimator_
optimal_bw = best_kde.bandwidth

print(f"--> Best KDE bandwidth found: {optimal_bw:.5f}")

# ==========================================
# 4. VISUALIZE THE AUTOMATED RESULTS
# ==========================================
# Generate points for the X-axis (Zooming in slightly to see detail)
x_plot = np.linspace(0, 0.5, 2000).reshape(-1, 1)

# Calculate densities
# Note: sklearn's KDE returns log-density, so we use np.exp()
gmm_density = np.exp(best_gmm.score_samples(x_plot))
kde_density = np.exp(best_kde.score_samples(x_plot))

# Plotting
plt.figure(figsize=(12, 6))

plt.hist(data, bins=1000, density=True, alpha=0.3, color='gray', label='Original Data', range=(0, 0.5))
plt.plot(x_plot, gmm_density, color='red', lw=2, label=f'Auto GMM (n={optimal_n})')
plt.plot(x_plot, kde_density, color='blue', linestyle='--', lw=2, label=f'Auto KDE (bw={optimal_bw:.4f})')

plt.title('Auto-Tuned Digital Twin Models: GMM vs KDE')
plt.xlabel('Response Time (Seconds)')
plt.ylabel('Probability Density')
plt.xlim(0, 0.5)
plt.legend()
plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('auto_tuned_models.png')
plt.show()