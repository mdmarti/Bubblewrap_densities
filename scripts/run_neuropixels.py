#%%
import time
import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from matplotlib.collections import LineCollection

from field.gqds import GQDS
from field.utils import center_mass
from datagen.plots import draw_graph, draw_bubbles, plot_scatter_connected, plot_color

from math import atan2
import umap

#%% for smoothing log prob
def ewma(data, com):
    return np.array(pd.DataFrame(data=dict(data=data)).ewm(com).mean()['data'])

#%% # load ssSVD trajectories

npz = np.load('/hdd/pgupta/stringer2019/neuropixel_reduced.npz')
projed = npz['ssSVD10'].T

total = projed.shape[0] # not all the timepoints
data = projed[:total, :]

# %%time

##%% Visualization
make_movie = False

# general params
dt = 0.1
M = 500 # 6 dims? # init size, one trial
T = total - M # iters
t = np.linspace(0, dt*T, T)

# bubblewrap params
d = data.shape[1]
num_d = 2 #?
N = 100
lam = 1e-3
nu = 1e-3
step = 1e-3
eps = 0

B_thresh = -10
n_thresh = 1e-5
P = 0 

t_wait = 1 # breadcrumbing

gq = GQDS(N, num_d, d, step=step, lam=lam, eps=eps, M=M,
          nu=nu, t_wait=t_wait, n_thresh=n_thresh, B_thresh=B_thresh)

##%% init
for i in np.arange(M):
    gq.observe(data[i])

gq.init_nodes()
print('Nodes initialized')
gq.printing = False
# breakpoint()

# visualize
if make_movie:
    ## Plotting during mesh refinement
    # fig, axs = plt.subplots(ncols=2, figsize=(6, 3), dpi=100)
    fig = plt.figure()
    axs = plt.gca()
    # parameters for animation
    sweep_duration = 15
    hold_duration = 10
    total_duration = sweep_duration + hold_duration
    fps = 30

    # setup animation writer
    import matplotlib.animation
    writer_class = matplotlib.animation.writers['ffmpeg']
    writer = writer_class(fps=fps, bitrate=1000)
    writer.setup(fig, 'gqds_movie.mp4')
else:
    fig = plt.figure(figsize=(14,8))
    ts_to_plot = [100, 500, 1500, 3000, T-M-3]
    ax_ind = 1

size = 10

com = center_mass(gq.mu)

max_x = np.max(np.abs(gq.mu[:,0].flatten())) * 1.1
max_y = np.max(np.abs(gq.mu[:,1].flatten())) * 1.1

x = np.linspace(-max_x, max_x, size)
y = np.linspace(-max_y, max_y, size)
x, y = np.meshgrid(x, y)
pos = np.dstack((x, y))

xmin, ymin = data.min(axis=0)[:2] - 3
xmax, ymax = data.max(axis=0)[:2] + 3

## run online
timer = time.time()
times = []
for i in np.arange(-M, T - M - 1):
    # print(i)
    t1 = time.time()
    gq.observe(data[i+M])
    gq.em_step()
    times.append(time.time()-t1)    

    if make_movie:
        if True: #i < 200 or i > 300:
            plot_color(data[:i+1+M, 0], data[:i+1+M, 1], t[:i+1+M], axs, alpha=1) #, cmap='PuBu')
            for n in np.arange(N):
                if n in gq.dead_nodes:
                    ## don't plot dead nodes
                    pass
                else:
                    # sig = gq.L[n] @ gq.L[n].T
                    u,s,v = np.linalg.svd(gq.L[n])
                    width, height = s[0]*2.25, s[1]*2.25 #*=4
                    if width>1e5 or height>1e5:
                        pass
                    else:
                        angle = atan2(v[0,1],v[0,0])*360 / (2*np.pi)
                        # breakpoint()
                        el = Ellipse((gq.mu[n,0],gq.mu[n,1]), width, height, angle, zorder=8)
                        el.set_alpha(0.2)
                        el.set_clip_box(axs.bbox)
                        el.set_facecolor('r')  ##ed6713')
                        axs.add_artist(el)
                
                    # plt.text(gq.mu[n,0]+1, gq.mu[n,1], str(n))

        else: #i between 200 and 300
            # find node closest to data point
            node = np.argmax(gq.alpha)
            A = gq.A.copy()
            A[A<=(1/N)] = 0
            plots.plot_color(data[:i+M+1, 0], data[:i+M+1, 1], t[:i+M+1], axs, alpha=1) #, cmap='PuBu')
            for j in np.arange(N):
                if A[node,j] > 0 and not node==j:
                    print('Arrow from ', str(node), ' to ', str(j))
                    axs.arrow(gq.mu[node,0], gq.mu[node,1], gq.mu[j,0]-gq.mu[node,0], gq.mu[j,1]-gq.mu[node,1], length_includes_head=True, width=A[node,j], head_width=0.8, color='k', zorder=9)

        axs.scatter(gq.mu[:,0], gq.mu[:,1], c='k' , zorder=10)
        plt.draw()
        writer.grab_frame()

        if i >= 200 and i <= 300:
            writer.grab_frame()
        
        # axs[0].cla()
        # axs[1].cla()
        axs.cla()
    else:
        if i in ts_to_plot:
            ax = fig.add_subplot(2, 3, ax_ind)
            draw_bubbles(gq, sig_ell=2, ax=ax)
            ax.set(xlim=(xmin, xmax), ylim=(ymin, ymax),
                   title='{} bins ({:.2f} seconds)'.format(i, i*.033))
            ax_ind += 1
        if i % 50 == 0:
            print(gq.pred[-1])
    # print(i)
    # if i % 100 == 0:
    #     print(i, 'frames processed. Time elapsed ', time.time()-timer)

# print('Done fitting all data online')
# print('Average cycle time: ', np.mean(np.array(times)[1:]))

if make_movie:
    writer.finish()

ax = fig.add_subplot(2, 3, ax_ind)
ax.plot(gq.pred, color='grey', alpha=0.2)
ax.plot(ewma(gq.pred, 100), color='black')
ax.set(xlabel='timesteps', ylabel='log probability')

# make up extra datapoints (for init)
for i in range(M+1):
    gq.observe(data[i])
    gq.em_step()

#%% run UMAP
neighb = 5
min_dist = .5
ufit = umap.UMAP(n_neighbors=neighb, min_dist=min_dist, 
                 n_components=2).fit(data)

data_umap = np.array([ufit.embedding_[:, 0], ufit.embedding_[:, 1]]).T
mu_umap = ufit.transform(gq.mu)

#%% get new trajectory
trial = 1
start, end = 1000, 1250
newtrial = data[start:end, :]
closest_nodes = []
for i in range(newtrial.shape[0]):
    gq.observe(newtrial[i])
    gq.em_step()
    closest_nodes.append(gq.current_node)
closest_nodes = np.array(closest_nodes, dtype='int')
nodes_to_bubble = np.unique(closest_nodes)
A = np.copy(np.array(gq.A))
A_mask = np.ones(A.shape) # all true (to discard)
A_mask[nodes_to_bubble, :] = np.zeros(A_mask.shape[1]) # keep closest nodes
A_mask = A_mask.astype('bool')
A[A_mask] = 0

# umap of new trajectory
newtrial_umap = ufit.transform(newtrial[:, :2])

#%% plotting (part of) figure 4?
# plotting params
thresh = 1/N
steps = data.shape[0]
alpha_graph = .5
alpha_data = 0.05 # for beneath graph
alpha_line = .2

# svd and umap
fig, axs = plt.subplots(2, 2, figsize=(12,12), 
           sharex='row', sharey='row')
fig.subplots_adjust(wspace=0.3, hspace=.1)


# svd
axs[0, 0].scatter(data[:steps, 0], data[:steps, 1], 
                  alpha=alpha_data, color='gray')
axs[0, 0].plot(newtrial[:, 0], newtrial[:, 1], color='blue',
               lw=2)
draw_graph(gq, axs[0, 1], A=A, thresh=thresh, 
           alpha=alpha_graph, node_color='orange') # svd space
axs[0, 1].plot(newtrial[:, 0], newtrial[:, 1], 
                  alpha=alpha_line, color='blue', 
                  zorder=0)
axs[0, 1].plot(newtrial[:, 0], newtrial[:, 1], color='blue',
               lw=2, alpha=0.2)

# umap
axs[1, 0].scatter(data_umap[:steps, 0], data_umap[:steps, 1], 
                  alpha=alpha_data, color='gray')
axs[1, 0].plot(newtrial_umap[:, 0], newtrial_umap[:, 1], 
               color='blue', lw=2)
draw_graph(gq, axs[1, 1], A=A, mu=mu_umap, thresh=thresh, 
           alpha=alpha_graph, node_color='orange') # svd space
axs[1, 1].plot(newtrial_umap[:, 0], newtrial_umap[:, 1], 
                  alpha=alpha_data, color='gray', 
                  zorder=0)
axs[1, 1].plot(newtrial_umap[:, 0], newtrial_umap[:, 1], 
               color='blue', lw=2, alpha=alpha_line)

axs[1,0].axis('off')
axs[0,0].axis('off')

axs[0,0].set_title('svd space, trajectories')
axs[0,1].set_title('svd space,\ntop bubblewrap transitions')

axs[1,0].set_title('umap space, trajectories')
axs[1,1].set_title('umap space,\ntop bubblewrap transitions')

#%% log prob comparison
vjf = np.load('models/logprob_vjf_neuropixel.npy')
zp2016 = np.load('models/logprob_zp2016_neuropixel.npy')
bwrap = np.array(gq.pred)

plt.ioff()
nn = vjf.shape[0]

plt.plot(np.linspace(100, nn - 1, nn - 100), zp2016, color='red', alpha=0.2)
plt.plot(vjf, color='grey', alpha=0.2)
plt.plot(bwrap, color='lightblue', alpha=0.2)

ax = plt.gca()
ax.plot(np.linspace(100, nn - 1, nn - 100), ewma(zp2016, 100), color='red', label='ZP2016')
ax.plot(ewma(vjf, 100), color='black', label='vjf')
ax.plot(ewma(bwrap, 100), color='blue', label='bubblewrap')
ax.ticklabel_format(useOffset=False, style='plain')

ax.set_xlabel('time step')
ax.set_ylabel('log probability')
ax.set_title('predictive log probability at each time step')
ax.legend()
ax.set(ylim=(-30, 15))

