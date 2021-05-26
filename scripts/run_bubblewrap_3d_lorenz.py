import time
import numpy as np

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pylab as plt
from matplotlib.patches import Ellipse
from mpl_toolkits.mplot3d import Axes3D

from scipy.integrate import solve_ivp
from scipy.stats import multivariate_normal as mvn

from field.gqds import GQDS
from datagen.diffeq import vanderpol, lorenz
from field.utils import center_mass
from datagen import plots

from math import atan2, floor

s = np.load('lorenz_1trajectories_3dim_500to20500_noise0.05.npz')
data = s['y'][0]
T = data.shape[0]
d = data.shape[1]

## parameters

# num_d = 10
d = 3
N = 10**3 #num_d**d
step = 8e-1
lam = 1e-3
nu = 1e-3 # 2 #1e-2   #2
# sigma_scale = 1e3 #1e4
# mu_scale = 2
eps = 1e-3

M = 100
# T = 300    #500 + M

t_wait = 1 #M #100
B_thresh = -10 #5.8
n_thresh = 5e-4

batch = False
batch_size = 1 #50

gq = GQDS(N, d, step=step, lam=lam, M=M, eps=eps, nu=nu, t_wait=t_wait, B_thresh=B_thresh, n_thresh=n_thresh, batch=batch, batch_size=batch_size)

## initialize things
for i in np.arange(0,M): #,batch_size):
    gq.observe(data[i]) #:i+batch_size])

gq.init_nodes()
print('Nodes initialized')

# Visualization
make_movie = False

if make_movie:
    ## Plotting during mesh refinement
    # fig, axs = plt.subplots(ncols=2, figsize=(6, 3), dpi=100)
    fig = plt.figure()
    axs = plt.gca(projection='3d')
    # axs = plt.gca()
    axs.view_init(40,23)
    # parameters for animation
    sweep_duration = 5#15
    hold_duration = 10
    total_duration = sweep_duration + hold_duration
    fps = 5#15

    # setup animation writer
    import matplotlib.animation
    writer_class = matplotlib.animation.writers['ffmpeg']
    writer = writer_class(fps=fps, bitrate=1000)
    writer.setup(fig, 'bubblewrap_2d_jpca.mp4')


# Set of all spherical angles to draw our ellipsoid
n_points = 10
theta = np.linspace(0, 2*np.pi, n_points)
phi = np.linspace(0, np.pi, n_points)

# Get the xyz points for plotting
# Cartesian coordinates that correspond to the spherical angles:
X = np.outer(np.cos(theta), np.sin(phi))
Y = np.outer(np.sin(theta), np.sin(phi)).flatten()
Z = np.outer(np.ones_like(theta), np.cos(phi)).flatten()
old_shape = X.shape
X = X.flatten()

## run online
timer = time.time()
times = []
times_obs = []

init = -M
end = T-M
step = batch_size

for i in np.arange(init, end, step):
    # print(i)
    t1 = time.time()
    gq.observe(data[i+M])
    times_obs.append(time.time()-t1)
    t2 = time.time()
    gq.em_step()    
    gq.grad_Q()
    times.append(time.time()-t2)    

    if make_movie:
        if True: #i < 200 or i > 300:
            # plots.plot3d_color(data[:i+1+M], t[:i+1+M], axs, alpha=1) #, cmap='PuBu')
            axs.scatter(data[:i+1+M+step,0], data[:i+1+M+step,1], color='b', alpha=0.6)
            for n in np.arange(N):
                if n in gq.dead_nodes: # or (gq.n_obs[n] < 0.08):
            # #         ## don't plot dead nodes
                    pass
                else:
                    el = np.linalg.inv(gq.L[n][:2,:2])
                    sig = el.T @ el
                    u,s,v = np.linalg.svd(sig)
                    width, height = s[0]*1, s[1]*1 #*=4
                    # if width>1e5 or height>1e5:
                    #     pass
                    # else:
                    angle = atan2(v[0,1],v[0,0])*360 / (2*np.pi)
                    # breakpoint()
                    el = Ellipse((gq.mu[n,0],gq.mu[n,1]), width, height, angle, zorder=8)
                    el.set_alpha(0.2)
                    el.set_clip_box(axs.bbox)
                    el.set_facecolor('r')  ##ed6713')
                    axs.add_artist(el)
                
                    # axs.text(gq.mu[n,0]+0.1, gq.mu[n,1], gq.mu[n,2], s=str(n))

        # else: #i between 200 and 300
        #     # find node closest to data point
        #     node = np.argmax(gq.alpha)
        #     A = gq.A.copy()
        #     A[A<=(1/N)] = 0
        #     plots.plot_color(data[:i+M+1, 0], data[:i+M+1, 1], t[:i+M+1], axs, alpha=1) #, cmap='PuBu')
        #     for j in np.arange(N):
        #         if A[node,j] > 0 and not node==j:
        #             print('Arrow from ', str(node), ' to ', str(j))
        #             axs.arrow(gq.mu[node,0], gq.mu[node,1], gq.mu[j,0]-gq.mu[node,0], gq.mu[j,1]-gq.mu[node,1], length_includes_head=True, width=A[node,j], head_width=0.8, color='k', zorder=9)


            # plt.xlim([0,1600])
            # plt.ylim([-25,15])
            # axs.set_zlim([-1550,0])

            mask = np.ones(gq.mu.shape[0], dtype=bool)
            if gq.dead_nodes:
                mask[np.array(gq.dead_nodes)] = False
            # mask[gq.n_obs<1e-8] = False
            # breakpoint()
            axs.scatter(gq.mu[mask,0], gq.mu[mask,1], c='k' , zorder=10)

            # axs.set_xticks([-15,15])
            # axs.set_yticks([-15,20])
            axs.set_xticks([])
            axs.set_yticks([])

            plt.draw()
            writer.grab_frame()

            # if i >= 200 and i <= 300:
            #     writer.grab_frame()

            # if i+M in [M-1, floor(T/4)-1, floor(T/2)-1, T-1]:
            #     figS = plt.gcf()
            #     figS.savefig('vdp_'+str(i+1)+'.svg', bbox_inches='tight')
            
            # axs[0].cla()
            # axs[1].cla()
            axs.cla()


    # print(i)
    if (i+M) % 50 == 0  and i>0:
        print(i+M, 'frames processed. Time elapsed ', time.time()-timer)

print('Done fitting all data online')
print('Average cycle time: ', np.mean(np.array(times)[20:]))
print('Average observation time: ', np.mean(np.array(times_obs)[20:]))
# print('Average prediction time: ', np.mean(np.array(gq.time_pred)[20:]))


if make_movie:
    writer.finish()

## plotting

# plt.figure()
# Q = np.array(gq.Q_list)
# if np.min(Q) < 0:
#     Q -= np.min(Q)
# plt.plot(Q)

# plt.figure()
# plt.semilogy(Q)


plt.figure()
plt.plot(np.array(gq.pred))
var_tmp = np.convolve(np.array(gq.pred), np.ones(500)/500, mode='valid')
plt.plot(var_tmp, 'k')
# for tt in gq.teleported_times:
#     plt.axvline(x=tt, color='r', lw=1)


plt.figure()
plt.plot(np.array(gq.entropy_list))
plt.hlines(np.log2(N), 0, T, 'k', '--')


plt.figure()
axs = plt.gca(projection='3d')
axs.plot(data[:i+1+M+step,0], data[:i+1+M+step,1], data[:i+1+M+step,2], color='gray', alpha=0.8)
# axs.plot(data[i+M+step-1:i+1+M+step,0], data[i+M+step-1:i+1+M+step,1], lw=2, color='b')
for n in np.arange(N):
    if n in gq.dead_nodes: # or (gq.n_obs[n] < 0.08):
# #         ## don't plot dead nodes
        pass
    else:
        el = np.linalg.inv(gq.L[n]).T
        sig = el @ el.T
        # Find and sort eigenvalues to correspond to the covariance matrix
        eigvals, eigvecs = np.linalg.eigh(sig)
        idx = np.sum(sig,axis=0).argsort()
        eigvals_temp = eigvals[idx]
        idx = eigvals_temp.argsort()
        eigvals = eigvals[idx]
        eigvecs = eigvecs[:,idx]

        # Width, height and depth of ellipsoid
        nstd = 3
        rx, ry, rz = nstd * np.sqrt(eigvals)

        # Rotate ellipsoid for off axis alignment
        a,b,c = np.matmul(eigvecs, np.array([X*rx,Y*ry,Z*rz]))
        a,b,c = a.reshape(old_shape), b.reshape(old_shape), c.reshape(old_shape)

        # Add in offsets for the mean
        a = a + gq.mu[n,0]
        b = b + gq.mu[n,1]
        c = c + gq.mu[n,2]
        
        axs.plot_surface(a, b, c, color='r', alpha=0.3)

    
        # axs.text(gq.mu[n,0]+0.01, gq.mu[n,1], s=str(n))

axs.view_init(40,23)

mask = np.ones(gq.mu.shape[0], dtype=bool)
if gq.dead_nodes:
    mask[np.array(gq.dead_nodes)] = False
mask[gq.n_obs<1e-4] = False
axs.scatter(gq.mu[:,0], gq.mu[:,1], gq.mu[:,2], c='k' , zorder=10)

plt.show()

print('----------------')

breakpoint()