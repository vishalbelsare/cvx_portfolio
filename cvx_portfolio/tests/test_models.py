"""
Copyright 2016 Stephen Boyd, Enzo Busseti, Steven Diamond, BlackRock Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os
import pickle

import cvxpy as cvx
import numpy as np
import pandas as pd

from ..costs import HcostModel, TcostModel
from ..returns import AlphaSource, AlphaStream
from ..constraints import (LongOnly, LeverageLimit,LongCash, MaxTrade)
from .base_test import BaseTest

DATAFILE = os.path.dirname(__file__) + os.path.sep + 'sample_data.pickle'


class TestModels(BaseTest):

    def setUp(self):
        with open(DATAFILE, 'rb') as f:
            self.returns, self.sigma, self.volume, self.a, self.b, self.s = \
            pickle.load(f)
        #self.volume['cash']=np.NaN
        self.universe = self.returns.columns
        self.times = self.returns.index

    def test_alpha(self):
        """Test alpha models.
        """
        # Alpha source
        w = cvx.Variable(len(self.universe))
        source = AlphaSource(self.returns)
        t = self.times[1]
        alpha = source.weight_expr(t, w)
        w.value = np.ones(len(self.universe))
        self.assertAlmostEqual(alpha.value, self.returns.loc[t].sum())
        # with delta
        source = AlphaSource(self.returns, self.returns/10)
        alpha = source.weight_expr(t, w)
        tmp = np.ones(len(self.universe))
        tmp[0] = -1
        w.value = tmp
        value = self.returns.loc[t].sum() - 2*self.returns.loc[t].values[0]
        value -= self.returns.loc[t].sum()/10
        self.assertAlmostEqual(alpha.value, value)

        # alpha stream
        source1 = AlphaSource(self.returns)
        source2 = AlphaSource(-self.returns)
        stream = AlphaStream([source1, source2], [1,1])
        alpha = stream.weight_expr(t, w)
        self.assertEqual(alpha.value, 0)

        stream = AlphaStream([source1, source2], [-1,1])
        alpha = stream.weight_expr(t, w)
        value = self.returns.loc[t].sum()
        w.value = np.ones(len(self.universe))
        self.assertEqual(alpha.value, -2*value)

        # with exp decay
        w = cvx.Variable(len(self.universe))
        source = AlphaSource(self.returns, half_life=2)
        t = self.times[1]
        td = pd.Timedelta('1 days')
        tau = self.times[3]
        diff = (tau - t).days
        w.value = np.ones(len(self.universe))
        alpha_t = source.weight_expr(t, w)
        alpha_tau = source.weight_expr_ahead(t, (tau,tau+td), w)
        decay = 2**(-diff/2)
        self.assertAlmostEqual(alpha_tau.value, decay*alpha_t.value)

        alpha = 0
        for i in range(3):
            alpha += source.weight_expr_ahead(t, tau+i*td, w)
        alpha_range = source.weight_expr_ahead(t, (tau, tau+3*td), w)
        self.assertAlmostEqual(alpha.value, alpha_range.value)

    def test_tcost(self):
        """Test tcost model.
        """
        n = len(self.universe)
        value = 1e6
        model = TcostModel(self.volume, self.sigma, self.a, self.b*0)
        t = self.times[1]
        z = np.arange(n) - n/2
        z_var = cvx.Variable(n)
        z_var.value = z
        tcost = model.weight_expr(t, None, z_var, value)
        est_tcost_lin = np.abs(z[:-1]).dot(self.a.loc[t].values)
        self.assertAlmostEqual(tcost.value, est_tcost_lin)

        model = TcostModel(self.volume, self.sigma, self.a*0, self.b, power=2)
        tcost = model.weight_expr(t, None, z_var, value)
        coeff = self.b.loc[t] * self.sigma.loc[t] * (value / self.volume.loc[t])
        est_tcost_nonlin = np.square(z[:-1]).dot(coeff.values)
        self.assertAlmostEqual(tcost.value, est_tcost_nonlin)

        model = TcostModel(self.volume, self.sigma, self.a*0, self.b, power=1.5)
        tcost = model.weight_expr(t, None, z_var, value)
        coeff = self.b.loc[t] * self.sigma.loc[t] * np.sqrt(value / self.volume.loc[t])
        est_tcost_nonlin = np.power(np.abs(z[:-1]), 1.5).dot(coeff.values)
        self.assertAlmostEqual(tcost.value, est_tcost_nonlin)

        model = TcostModel(self.volume, self.sigma, self.a, self.b)
        tcost = model.weight_expr(t, None, z_var, value)
        self.assertAlmostEqual(tcost.value, est_tcost_nonlin + est_tcost_lin)

        # with tau
        model = TcostModel(self.volume, self.sigma, self.a, self.b)
        tau = self.times[2]
        tcost = model.weight_expr_ahead(t, tau, None, z_var, value)
        self.assertAlmostEqual(tcost.value, est_tcost_nonlin + est_tcost_lin)

        tau = t + 10*pd.Timedelta('1 days')
        tcost_tau = model.est_period(t, t, tau, None, z_var, value)
        tcost_t = model.weight_expr(t, None, z_var / 10, value) * 10
        self.assertAlmostEqual(tcost_tau.value, tcost_t.value)

    def test_hcost(self):
        """Test holding cost model.
        """
        div = self.s/2
        n = len(self.universe)
        wplus = cvx.Variable(n)
        wplus.value = np.arange(n) - n/2
        t = self.times[1]
        model = HcostModel(self.s, div*0)
        hcost = model.weight_expr(t, wplus, None, None)
        bcost = wplus[:-1].value.T @ self.s.loc[t].values
        self.assertAlmostEqual(hcost.value, bcost)

        model = HcostModel(self.s*0, div)
        hcost = model.weight_expr(t, wplus, None, None)
        divs = wplus[:-1].value.T @ div.loc[t].values
        self.assertAlmostEqual(-hcost.value, divs)

        model = HcostModel(self.s, div)
        hcost = model.weight_expr(t, wplus, None, None)
        self.assertAlmostEqual(hcost.value, bcost - divs)

    def test_hold_constrs(self):
        """Test holding constraints.
        """
        n = len(self.universe)
        wplus = cvx.Variable(n)
        t = self.times[1]

        # long only
        model = LongOnly()
        cons = model.weight_expr(t, wplus, None, None)
        wplus.value = np.ones(n)
        assert cons.value
        wplus.value = -np.ones(n)
        assert not cons.value

        # long cash
        model = LongCash()
        cons = model.weight_expr(t, wplus, None, None)
        wplus.value = np.ones(n)
        assert cons.value
        tmp = np.ones(n)
        tmp[-1] = -1
        wplus.value = tmp
        assert not cons.value

        # leverage limit
        model = LeverageLimit(2)
        cons = model.weight_expr(t, wplus, None, None)
        wplus.value = np.ones(n)/n
        assert cons.value
        tmp = np.zeros(n)
        tmp[0] = 4
        tmp[-1] = -3
        wplus.value = tmp
        assert not cons.value
        model = LeverageLimit(7)
        cons = model.weight_expr(t, wplus, None, None)
        tmp = np.zeros(n)
        tmp[0] = 4
        tmp[-1] = -3
        wplus.value = tmp
        assert cons.value

        limits = pd.Series(index=self.times, data=2)
        limits.iloc[1] = 7
        model = LeverageLimit(limits)
        cons = model.weight_expr(t, wplus, None, None)
        tmp = np.zeros(n)
        tmp[0] = 4
        tmp[-1] = -3
        wplus.value = tmp
        assert cons.value
        cons = model.weight_expr(self.times[2], wplus, None, None)
        assert not cons.value

    def test_trade_constr(self):
        """Test trading constraints.
        """
        n = len(self.universe)
        z = cvx.Variable(n)
        t = self.times[1]

        # avg daily value limits.
        value = 1e6
        model = MaxTrade(self.volume, max_fraction=.1)
        cons = model.weight_expr(t, None, z, value)
        tmp = np.zeros(n)
        tmp[:-1] = self.volume.loc[t].values / value * 0.05
        z.value = tmp
        assert cons.value
        z.value = -100*z.value#-100*np.ones(n)
        assert not cons.value
