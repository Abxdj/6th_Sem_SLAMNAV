#!/usr/bin/env python3
"""Plots and contact sheet from bag_analysis.py output.
Usage: plot_phase1.py <phase1_dir> <out_dir> [events.csv ...]   (events overlaid if given)"""
import sys, os
import numpy as np, pandas as pd, cv2
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

P, OUT = sys.argv[1], sys.argv[2]
evs = sys.argv[3:]
F = pd.read_csv(f'{P}/frames.csv'); S = pd.read_csv(f'{P}/samples.csv')
th = np.load(f'{P}/thumbs.npz'); thumbs, tidx = th['thumbs'], th['idx']


def overlay(ax):
    for e in evs:
        E = pd.read_csv(e)
        for typ, c in (('new_map', 'red'), ('merge', 'green'), ('loop_detected', 'blue')):
            for x in E.loc[E.type == typ, 'bag_t']:
                ax.axvline(x, color=c, lw=0.8, alpha=0.6)


# 1. keypoints / matchability / intensity over time
fig, ax = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
ax[0].plot(S.t_rel, S.kp5, lw=0.5, label='ORB kp, FAST 5'); ax[0].plot(S.t_rel, S.kp20, lw=0.5, label='ORB kp, FAST 20')
ax[0].set_ylabel('keypoints'); ax[0].legend(loc='lower right')
ax[1].plot(S.t_rel, S.inl5, lw=0.5, label='F-inliers to +3 frames, FAST 5')
ax[1].plot(S.t_rel, S.inl20, lw=0.5, label='F-inliers to +3 frames, FAST 20'); ax[1].set_ylabel('inliers'); ax[1].legend(loc='lower right')
ax[2].plot(S.t_rel, S['mean'], lw=0.5, label='mean'); ax[2].plot(S.t_rel, S['std'], lw=0.5, label='std')
ax[2].set_ylabel('intensity'); ax[2].legend(loc='lower right')
mad = F.mad_prev.clip(lower=0).rolling(67, center=True).mean()
ax[3].plot(F.t_rel, mad, lw=0.5); ax[3].set_ylabel('mean |frame diff|\n(1 s rolling)'); ax[3].set_yscale('log')
static = F.mad_prev < 0.1
ax[3].fill_between(F.t_rel, 1e-3, 10, where=static.rolling(67, center=True).mean() > 0.8, color='grey', alpha=0.3, lw=0)
ax[3].set_ylim(1e-2, 10); ax[3].set_xlabel('bag time (s)')
for a in ax: overlay(a)
ax[0].set_title('drive1.bag: texture, matchability, intensity, motion (grey = robot static)' +
                ('  | red=new map, green=merge, blue=loop' if evs else ''))
fig.tight_layout(); fig.savefig(f'{OUT}/phase1_timeline.png', dpi=80); plt.close(fig)

# 2. duplicate / near-duplicate rate over time (per 10 s)
b = (F.t_rel // 10).astype(int)
g = pd.DataFrame({'dup': F.dup_exact, 'near': F.mad_prev < 0.1, 'b': b}).groupby('b').mean() * 100
fig, ax = plt.subplots(figsize=(14, 3))
ax.plot(g.index * 10, g.near, label='MAD<0.1 (near-duplicate)'); ax.plot(g.index * 10, g.dup, label='exact duplicate')
ax.set_ylabel('% of frames per 10 s'); ax.set_xlabel('bag time (s)'); ax.legend(); overlay(ax)
fig.tight_layout(); fig.savefig(f'{OUT}/phase1_duplicates.png', dpi=80); plt.close(fig)

# 3. contact sheet: 6 flattest (lowest FAST-20 keypoints) + 6 evenly spaced
order = S.sort_values('kp20')
pick = list(order.idx[:6]) + list(S.idx[np.linspace(0, len(S) - 1, 6).astype(int)])
tiles = []
for i in pick:
    j = int(np.argmin(np.abs(tidx - i))); im = cv2.cvtColor(thumbs[j], cv2.COLOR_GRAY2BGR)
    r = S.loc[S.idx == i].iloc[0]
    cv2.putText(im, f't={r.t_rel:.0f}s k20={int(r.kp20)}', (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
    tiles.append(im)
sheet = np.vstack([np.hstack(tiles[k:k + 6]) for k in (0, 6)])
cv2.imwrite(f'{OUT}/contact_sheet.jpg', sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
print('wrote plots; contact sheet picks', pick)
