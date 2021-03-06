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
import copy

import pandas as pd
import numpy as np

from ..returns import AlphaSource, MarketReturns
from .base_test import BaseTest
from ..costs import TcostModel, HcostModel
from ..simulator import MarketSimulator
from ..policies import Hold
from ..result import SimulationResult

DATAFILE = os.path.dirname(__file__) + os.path.sep + 'sample_data.pickle'

class TestSimulator(BaseTest):

    def setUp(self):
        with open(DATAFILE, 'rb') as f:
            self.returns, self.sigma, self.volume, self.a, self.b, self.s = \
            pickle.load(f)
        self.volume['cash']=np.NaN
        self.portfolio = pd.Series(index = self.returns.columns, data=1E6)
        returns_model = MarketReturns(self.returns)
        self.tcost_term = TcostModel(self.volume, self.sigma, self.a, self.b, cash_key='cash')
        self.hcost_term = HcostModel(self.s, cash_key='cash')
        self.Simulator = MarketSimulator(returns_model,  self.volume, costs=[self.tcost_term, self.hcost_term])

    def test_propag(self):
        """Test propagation of portfolio."""
        t = self.returns.index[1]
        h = copy.copy(self.portfolio)
        results = SimulationResult(initial_portfolio=h, policy=None,
                                    cash_key='cash',simulator=self.Simulator)
        u=pd.Series(index=self.portfolio.index, data=1E4)
        h_next, u = self.Simulator.propagate(h, u=u, t=t)
        results.log_simulation(t=t, u=u, h_next=h_next, exec_time=0)
        self.assertAlmostEquals(results.simulator_TcostModel.sum().sum(), 157.604, 3)
        self.assertAlmostEquals(results.simulator_HcostModel.sum(), 0., 3)
        self.assertAlmostEqual(sum(h_next), 28906767.251, 3)

    def test_propag_list(self):
        """Test propagation of portfolio, list of trades."""
        t = self.returns.index[1]
        h = copy.copy(self.portfolio)
        results = SimulationResult(initial_portfolio=h, policy=None,
                                    cash_key='cash',simulator=self.Simulator)
        u = pd.Series(index=self.portfolio.index, data=[1E4]*29)
        h_next, u = self.Simulator.propagate(h,u, t=t)
        results.log_simulation(t=t, u=u, h_next=h_next, exec_time=0)
        self.assertAlmostEquals(results.simulator_TcostModel.sum().sum(), 157.604, 3)
        self.assertAlmostEquals(results.simulator_HcostModel.sum(), 0., 3)
        self.assertAlmostEqual(sum(h_next), 28906767.251, 3)

    def test_propag_neg(self):
        """Test propagation of portfolio, negative trades."""
        t = self.returns.index[1]
        h = copy.copy(self.portfolio)
        results = SimulationResult(initial_portfolio=h, policy=None,
                                    cash_key='cash',simulator=self.Simulator)
        u = pd.Series(index=self.portfolio.index, data=[-1E4]*29)
        h_next, u =self.Simulator.propagate(h,u,t=t)
        results.log_simulation(t=t, u=u, h_next=h_next, exec_time=0)
        self.assertAlmostEquals(results.simulator_TcostModel.sum().sum(), 157.604, 3)
        self.assertAlmostEquals(results.simulator_HcostModel.sum(), 0., 3)
        self.assertAlmostEqual(sum(h_next), 28908611.931, 3)

    def test_hcost_pos(self):
        """Test hcost function, positive positions."""
        self.hcost_term.borrow_costs += 0
        t = self.returns.index[1]
        h = copy.copy(self.portfolio)
        results = SimulationResult(initial_portfolio=h, policy=None,
                                    cash_key='cash',simulator=self.Simulator)
        u=pd.Series(index=self.portfolio.index, data=1E4)
        h_next, u = self.Simulator.propagate(h,u, t=t)
        results.log_simulation(t=t, u=u, h_next=h_next, exec_time=0)
        self.assertAlmostEquals(results.simulator_HcostModel.sum(), 0.)

    def test_hcost_neg(self):
        """Test hcost function, negative positions."""
        self.hcost_term.borrow_costs += .0001
        t = self.returns.index[1]
        h = copy.copy(self.portfolio)
        results = SimulationResult(initial_portfolio=h, policy=None,
                                    cash_key='cash',simulator=self.Simulator)
        u=pd.Series(index=self.portfolio.index,data=-2E6)
        h_next, u = self.Simulator.propagate(h,u, t=t)
        results.log_simulation(t=t, u=u, h_next=h_next, exec_time=0)
        self.assertAlmostEquals(results.simulator_HcostModel.sum(), 2800.0)
