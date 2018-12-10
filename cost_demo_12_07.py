import torch
import mpc
from mpc import mpc
from mpc.mpc import QuadCost, LinDx, GradMethods
from mpc.env_dx import pendulum
from mpc.env_dx import gp_dynamic

import numpy as np
import numpy.random as npr

import matplotlib.pyplot as plt

import os
import io
import base64
import tempfile
from IPython.display import HTML

from tqdm import tqdm
import time

params = torch.tensor((10., 1., 1.))
#dx = pendulum.PendulumDx(params, simple=True)
n_batch, T, mpc_T = 8, 5, 10
train_x = np.random.random((n_batch, 4))
train_y = np.random.random((n_batch, 3))
train_r = np.random.random(n_batch)
# these train datas are used to fit gp model in dynamics and gp model in cost

dx = gp_dynamic.gp_dynamics_dx(train_x, train_y)
#dx = pendulum.PendulumDx(params, simple=True) #thier demo


def uniform(shape, low, high):
    r = high-low
    return torch.rand(shape)*r+low

torch.manual_seed(0)
th = uniform(n_batch, -(1/2)*np.pi, (1/2)*np.pi)
thdot = uniform(n_batch, -1., 1.)
xinit = torch.stack((torch.cos(th), torch.sin(th), thdot), dim=1)

x = xinit
print('xinit shape', xinit, xinit.shape)
u_init = None

# The cost terms for the swingup task can be alternatively obtained
# for this pendulum environment with:
# q, p = dx.get_true_obj()

mode = 'swingup'
# mode = 'spin'

if mode == 'swingup':
    goal_weights = torch.Tensor((1., 1., 0.1))
    goal_state = torch.Tensor((1., 0. ,0.))
    ctrl_penalty = 0.001
    q = torch.cat((
        goal_weights,
        ctrl_penalty*torch.ones(1)
    ))
    px = -torch.sqrt(goal_weights)*goal_state
    p = torch.cat((px, torch.zeros(1)))
    Q = torch.diag(q).unsqueeze(0).unsqueeze(0).repeat(
        mpc_T, n_batch, 1, 1
    )
    p = p.unsqueeze(0).repeat(mpc_T, n_batch, 1)
elif mode == 'spin':
    Q = 0.001*torch.eye(dx.n_state+dx.n_ctrl).unsqueeze(0).unsqueeze(0).repeat(
        mpc_T, n_batch, 1, 1
    )
    p = torch.tensor((0., 0., -1., 0.))
    p = p.unsqueeze(0).repeat(mpc_T, n_batch, 1)

t_dir = tempfile.mkdtemp()
print('Tmp dir: {}'.format(t_dir))
n_state= 3
n_ctrl=1

#for t in tqdm(range(T)):
for t in range(T):
    nominal_states, nominal_actions, nominal_objs = mpc.MPC(
        n_state, n_ctrl, mpc_T,
        n_batch = n_batch,
        u_init=u_init,
        u_lower=-2.0, u_upper=2.0,
        lqr_iter=1,#3 is bug
        verbose=0,
        exit_unconverged=False,
        detach_unconverged=False,
        linesearch_decay=0.2,
        max_linesearch_iter=5,
        grad_method=GradMethods.ANALYTIC,
        eps=1e-2,
        train_x = train_x,
        train_y = train_y,
        train_r = train_r
    )(x, QuadCost(Q, p), dx)
    print('times', t, 'x', x)
    print('norminal states', nominal_states)
    next_action = nominal_actions[0]
    print('next action', next_action)
    u_init = torch.cat((nominal_actions[1:], torch.zeros(1, n_batch, n_ctrl)), dim=0)
    u_init[-2] = u_init[-3]
    _, x = dx.grad_input(x, next_action)
    x = torch.Tensor(x)
    print('new x after action', x)