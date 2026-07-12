import numpy as np
from scipy.stats import ttest_rel

control = np.array([2, 2, 2, 3, 1, 1, 1, 3])
experimental = np.array([3, 3, 3, 2, 2, 3, 2, 4])

t_stat, p_value = ttest_rel(experimental, control)

differences = experimental - control

print("Control mean:", np.mean(control))
print("Experimental mean:", np.mean(experimental))
print("Mean difference:", np.mean(differences))
print("SD difference:", np.std(differences, ddof=1))
print("t-statistic:", t_stat)
print("p-value:", p_value)