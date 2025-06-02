import json
import matplotlib.pyplot as plt
import numpy as np

# Load JSON
with open('performance_report.json') as f:
    data = json.load(f)

# ----------- Graphs -----------

# 1. DID Operations Timing
creation = data['did_operations']['creation']
verification = data['did_operations']['verification']

labels = ['Creation', 'Verification']
avg_times = [creation['avg'], verification['avg']]
min_times = [creation['min'], verification['min']]
max_times = [creation['max'], verification['max']]

x = np.arange(len(labels))
width = 0.2

fig, ax = plt.subplots()
rects1 = ax.bar(x - width, min_times, width, label='Min')
rects2 = ax.bar(x, avg_times, width, label='Avg')
rects3 = ax.bar(x + width, max_times, width, label='Max')

ax.set_ylabel('Time (ms)')
ax.set_title('DID Operation Times')
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend()

plt.tight_layout()
plt.savefig('did_operations_times.png')
plt.close()

# 2. Gas Costs
gas = data['gas_costs']

labels = list(gas.keys())
avg_gas_used = [gas[op]['avg_gas_used'] for op in labels]
avg_gas_cost_eth = [gas[op]['avg_gas_cost_eth'] for op in labels]

x = np.arange(len(labels))

fig, ax1 = plt.subplots()

color = 'tab:blue'
ax1.set_xlabel('Operation')
ax1.set_ylabel('Avg Gas Used', color=color)
ax1.bar(x - 0.2, avg_gas_used, 0.4, label='Avg Gas Used', color=color)
ax1.tick_params(axis='y', labelcolor=color)

ax2 = ax1.twinx()  
color = 'tab:red'
ax2.set_ylabel('Avg Gas Cost (ETH)', color=color)
ax2.bar(x + 0.2, avg_gas_cost_eth, 0.4, label='Avg Gas Cost', color=color)
ax2.tick_params(axis='y', labelcolor=color)

plt.xticks(x, labels)

fig.tight_layout()
plt.title('Gas Costs and Usage per Operation')
plt.savefig('gas_costs.png')
plt.close()

# 3. Data Request Time
data_request = data['data_requests']

percentiles = data_request['percentiles']
labels = list(percentiles.keys())
values = list(percentiles.values())

plt.bar(labels, values, color='green')
plt.ylabel('Time (ms)')
plt.title('Data Request Percentile Times')
plt.tight_layout()
plt.savefig('data_request_times.png')
plt.close()

# 4. Scalability
scalability = data['scalability']
vehicles = [entry['vehicles'] for entry in scalability]
response_times = [entry['avg_response_time'] for entry in scalability]

plt.plot(vehicles, response_times, marker='o')
plt.xlabel('Number of Vehicles')
plt.ylabel('Avg Response Time (ms)')
plt.title('Scalability Analysis')
plt.grid(True)

# Set x-axis to start from first vehicle count
# plt.xlim(left=vehicles[0])
min_x = min(vehicles) - 20
max_x = max(vehicles) + 20

plt.xlim(min_x, max_x)

# Add padding to y-axis for better visualization
min_y = min(response_times) - 400
max_y = max(response_times) + 400
plt.ylim(min_y, max_y)

plt.tight_layout()
plt.savefig('scalability.png')
plt.close()



# 5. API Latency
api_latency = data['api_latency']

percentiles = api_latency['percentiles']
labels = list(percentiles.keys())
values = list(percentiles.values())

plt.bar(labels, values, color='purple')
plt.ylabel('Latency (ms)')
plt.title('API Latency Percentile')
plt.tight_layout()
plt.savefig('api_latency.png')
plt.close()

# ----------- LaTeX Tables -----------

# 1. Latency Table (DID + API)
latex_latency_table = r"""
\begin{table}[ht]
\centering
\begin{tabular}{|l|c|c|c|c|}
\hline
Operation & Avg (ms) & Min (ms) & Max (ms) & Std Dev \\
\hline
DID Creation & %.2f & %.2f & %.2f & %.2f \\
DID Verification & %.2f & %.2f & %.2f & %.2f \\
API Latency & %.2f & %.2f & %.2f & %.2f \\
\hline
\end{tabular}
\caption{Latency results for DID operations and API calls}
\label{tab:latency}
\end{table}
""" % (
    creation['avg'], creation['min'], creation['max'], creation['std_dev'],
    verification['avg'], verification['min'], verification['max'], verification['std_dev'],
    api_latency['avg'], api_latency['min'], api_latency['max'], api_latency['std_dev']
)

# 2. Gas Costs Table
latex_gas_table = r"""
\begin{table}[ht]
\centering
\begin{tabular}{|l|c|c|c|c|c|}
\hline
Operation & Avg Gas Used & Min Gas Used & Max Gas Used & Avg Gas Cost (ETH) & Total Gas Used \\
\hline
Creation & %d & %.0f & %.0f & %.6f & %d \\
Data Request & %d & %.0f & %.0f & %.6f & %.0f \\
Data Response & %d & %.0f & %.0f & %.6f & %d \\
\hline
\end{tabular}
\caption{Gas usage and cost metrics for operations}
\label{tab:gas_costs}
\end{table}
""" % (
    gas['creation']['avg_gas_used'], gas['creation']['min_gas_used'], gas['creation']['max_gas_used'],
    gas['creation']['avg_gas_cost_eth'], gas['creation']['total_gas_used'],

    gas['data_request']['avg_gas_used'], gas['data_request']['min_gas_used'], gas['data_request']['max_gas_used'],
    gas['data_request']['avg_gas_cost_eth'], gas['data_request']['total_gas_used'],

    gas['data_response']['avg_gas_used'], gas['data_response']['min_gas_used'], gas['data_response']['max_gas_used'],
    gas['data_response']['avg_gas_cost_eth'], gas['data_response']['total_gas_used'],
)

# Save LaTeX tables to files
with open('latency_table.tex', 'w') as f:
    f.write(latex_latency_table)

with open('gas_costs_table.tex', 'w') as f:
    f.write(latex_gas_table)

print("Graphs saved as PNG files.")
print("LaTeX tables saved as .tex files.")
