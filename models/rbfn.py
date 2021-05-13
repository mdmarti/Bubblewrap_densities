#%%
"""
An implementation of `Interpretable Nonlinear Dynamic Modeling of Neural Trajectories`
Yuan Zhao, Il Memming Park, NIPS 2016

Equations are exact matches to those in the paper.
Generate data from a van der pol oscillator, fit with MSE, and draw vector field.
Takes ~5 ms to run per step on a 4 GHz Coffee Lake CPU.

"""

from functools import partial
from typing import Callable, Optional

import jax.numpy as np
from jax import jit
from jax.api import value_and_grad
from jax.interpreters.xla import DeviceArray
from jax.ops import index, index_update


#%%
class RBFN:
    # When subclassing, don't forget class name in self._mse. Static method limitation.
    def __init__(self, ker: Callable, params, optimizer: tuple[Callable, ...], window=100) -> None:
        assert {"W", "τ", "c", "σ"} <= params.keys()
        assert params["W"].shape == params["c"].shape
        assert params["W"].shape[0] == params["σ"].size
        assert np.all(params["τ"] > 0) and np.all(params["σ"] > 0)

        self.init_params, self.opt_update, self.get_params = optimizer
        self.opt_update = jit(self.opt_update)
        self.opt_state = self.init_params(params)

        self.ker = ker
        self._obj = self._mse_vgrad = jit(value_and_grad(self._mse, argnums=2), static_argnums=0)
        self.t = 1
        self.window = window
        self.mask = np.zeros((self.window - 1, 1))  # For online training. -1 since this is multiplied with x[:-1].

    @property
    def params(self):
        """Params are in in PyTree in self.opt_state for optimizer."""
        return self.get_params(self.opt_state)

    def g(self, x):
        return self._g(self.ker, x, self.params)

    def obj(self, x):
        return self._obj(self.ker, x, self.params)

    def step(self, x, loop=3, _mask=None, **kwargs):
        for _ in range(loop):
            value, grads = self._obj(self.ker, x, self.params, mask=_mask, **kwargs)
            self.opt_state = self.opt_update(self.t, grads, self.opt_state)
        self.t += 1
        return value

    def step_online(self, x, loop=3, **kwargs):
        """
        Assuming the role for splitting up data for online learning for now.
        Pad for t=0...self.window.
        """
        self.mask = index_update(self.mask, self.t - 1, 1.0)
        if self.t < self.window:
            z = index_update(np.zeros((self.window, x.shape[1])), index[: self.t + 1, :], x[: self.t + 1, :])
        else:
            z = x[self.t : self.t + self.window]
        return self.step(z, loop, self.mask, **kwargs)

    @staticmethod
    @partial(jit, static_argnums=0)
    def _g(ker, x, p: dict):
        W, τ, c, σ = p["W"], p["τ"], p["c"], p["σ"]
        return ker(x, c, σ) @ W - np.exp(-(τ ** 2)) * x  # (4)

    @staticmethod
    def _mse(ker: Callable, x: DeviceArray, p: dict[str, DeviceArray], mask: Optional[DeviceArray]):
        """||g(x_{t-1}) + x_{t-1} - x_t||²"""
        if mask is None:
            return np.mean(np.square(RBFN._g(ker, x[:-1], p) + x[:-1] - x[1:]))
        return np.sum(np.square(RBFN._g(ker, x[:-1], p) + x[:-1] - x[1:]) * mask) / np.sum(mask)


# %%