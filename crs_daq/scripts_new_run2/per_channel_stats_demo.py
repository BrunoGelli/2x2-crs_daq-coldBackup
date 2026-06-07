#!/usr/bin/env python3
# analysis/per_channel_stats_demo.py
import h5py, numpy as np, sys

fn = sys.argv[1]
with h5py.File(fn, 'r') as f:
    pk = f['packets'][:]

# Select good data packets
mask = (pk['packet_type']==0) & (pk['valid_parity']==1)
view = pk[mask]

# Build uid and adc arrays
uid = ((view['io_group'].astype(np.int64)*1000 + view['io_channel'].astype(np.int64))*1000
       + view['chip_id'].astype(np.int64))*100 + view['channel_id'].astype(np.int64)
adc = view['dataword'].astype(np.float32)

# Group-by uid (fast path)
uids, inv = np.unique(uid, return_inverse=True)
counts = np.bincount(inv)
sums   = np.bincount(inv, weights=adc.astype(np.float64))
sumsq  = np.bincount(inv, weights=(adc.astype(np.float64)**2))

# Stats
mean = sums / counts
var  = np.maximum(sumsq / counts - mean*mean, 0.0)
std  = np.sqrt(var)

# Livetime (if you have packet_type==4)
ts = pk['timestamp'][pk['packet_type']==4]
livetime = float(ts.max() - ts.min()) if ts.size else 0.0
rate = counts / livetime if livetime > 0 else np.zeros_like(counts)

print(f"Channels: {uids.size}, median hits/ch: {int(np.median(counts))}, livetime ticks: {livetime:.0f}")
# Example: print top 5 noisiest channels
top = np.argsort(std)[-5:][::-1]
for i in top:
    print(int(uids[i]), f"std={std[i]:.2f}", f"hits={int(counts[i])}")
