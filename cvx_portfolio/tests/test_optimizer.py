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

from ..policies import SinglePeriodOpt, MultiPeriodOpt
from ..costs import HcostModel, TcostModel
from ..returns import AlphaSource
from ..risks import FullSigma
from .base_test import BaseTest

DATAFILE = os.path.dirname(__file__) + os.path.sep + 'sample_data.pickle'


class TestOptimizer(BaseTest):

    def setUp(self):
        with open(DATAFILE, 'rb') as f:
            self.returns, self.sigma, self.volume, self.a, self.b, self.s = \
            pickle.load(f)
        self.s = self.s + 1e-3
        self.universe = self.returns.columns
        self.times = self.returns.index

    def test_single_period_opt(self):
        """Test single period optimizer.
        """
        # Alpha source
        gamma = 100.
        n = len(self.universe)
        alpha_model = AlphaSource(self.returns)
        emp_Sigma = np.cov(self.returns.as_matrix().T) + np.eye(n)*1e-3
        risk_model = FullSigma(emp_Sigma)
        tcost_model = TcostModel(self.volume, self.sigma,
                                self.a*0, self.b, power=2)
        hcost_model = HcostModel(self.s*0, self.s)
        pol = SinglePeriodOpt(alpha_model,
                            [gamma*risk_model, tcost_model, hcost_model],
                            [], solver=cvx.ECOS)
        t = self.times[1]
        p_0 = pd.Series(index=self.universe, data=1E6)
        z = pol.get_trades(p_0, t)  #TODO this gives an error in nosetests (MKL)
        self.assertAlmostEqual(z.sum(), 0)
        # Compare with CP calculation.
        h = z + p_0.h
        rho = self.b.loc[t]*self.sigma.loc[t]*(p_0.v/self.volume.loc[t])
        rho = np.hstack([rho, 0])
        A = 2*gamma*emp_Sigma + 2*np.diag(rho)
        s_val = self.s.loc[t]
        s_val['cash'] = 0
        b = self.returns.loc[t] + 2*rho*p_0.w + s_val
        h0 = np.linalg.solve(A, b) + bmark
        offset = np.linalg.solve(A, np.ones(n))
        nu = (1 - h0.sum())/offset.sum()
        hstar = h0 + nu*offset
        self.assertAlmostEqual(hstar.sum(), 1)
        self.assertItemsAlmostEqual(h/p_0.v, hstar, places=4)

    def test_multi_period(self):
        """Test multiperiod optimizer.
        """
        # Alpha source
        gamma = 100.
        n = len(self.universe)
        alpha_model = AlphaSource(self.returns)
        emp_Sigma = np.cov(self.returns.as_matrix().T) + np.eye(n)*1e-3
        risk_model = FullSigma(emp_Sigma,gamma_half_life=np.inf)
        tcost_model = TcostModel(self.volume, self.sigma,
                                self.a*0, self.b, power=2)
        hcost_model = HcostModel(self.s*0, self.s)
        pol = MultiPeriodOpt(2, alpha_model,
                            [gamma*risk_model, tcost_model, hcost_model],
                            [], solver=cvx.ECOS, terminal_constr=True)

        t = self.times[1]
        p_0 =pd.Series(index=self.universe, data=1E6)
        z = pol.get_trades(p_0, t)
        self.assertAlmostEqual(z.sum(), 0)
        # Compare with CP calculation. Terminal constraint.
        h = z + p_0.h
        rho = self.b.loc[t]*self.sigma.loc[t]*(p_0.v/self.volume.loc[t])
        rho = np.hstack([rho, 0])
        A = 2*gamma*emp_Sigma + 4*np.diag(rho)
        s_val = self.s.loc[t]
        s_val['cash'] = 0
        b = self.returns.loc[t] + 2*rho*(p_0.w + bmark) + s_val
        h0 = np.linalg.solve(A, b) + bmark
        offset = np.linalg.solve(A, np.ones(n))
        nu = (1 - h0.sum())/offset.sum()
        hstar = h0 + nu*offset
        self.assertAlmostEqual(hstar.sum(), 1)
        self.assertItemsAlmostEqual(h/p_0.v, hstar, places=4)


        pol = MultiPeriodOpt(2, alpha_model, [risk_model, tcost_model, hcost_model], [], solver=cvx.ECOS,
                                    terminal_constr=False)

        t = self.times[1]
        bmark = pd.Series(index=self.universe, data=0.)
        p_0 = portfolio.Portfolio(pd.Series(index=self.universe, data=1E6),
                                  benchmark=bmark)
        z = pol.get_trades(p_0, t)
        self.assertAlmostEqual(z.sum(), 0)
        # Compare with CP calculation.
        h = z + p_0.h
        rho = self.b.loc[t]*self.sigma.loc[t]*(p_0.v/self.volume.loc[t])
        rho = np.hstack([rho, 0])
        D = np.diag(rho)
        A = np.bmat([[2*gamma*emp_Sigma + 4*D, -2*D, np.ones((n,1)), np.zeros((n,1))],
                     [-2*D, 2*gamma*emp_Sigma, np.zeros((n,1)), np.ones((n,1))],
                     [np.ones((1,n)), np.zeros((1,n+2))],
                     [np.zeros((1,n)), np.ones((1, n)), np.zeros((1,2))]])
        s_val = self.s.loc[t]
        s_val['cash'] = 0
        b = self.returns.loc[t] + 2*rho*p_0.w + s_val
        b = np.hstack([b, self.returns.loc[t] + s_val, 1, 1])
        x = np.linalg.solve(A, b)
        w1 = x[:n]
        w2 = x[n:2*n]
        self.assertAlmostEqual(w1.sum(), 1)
        self.assertAlmostEqual(w2.sum(), 1)
        self.assertItemsAlmostEqual(h/p_0.v, w1, places=4)
