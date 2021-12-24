from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime as dt  # For datetime objects
import os.path  # To manage paths
import sys  # To find out the script name (in argv[0])
import backtrader as bt
import requests                    # for "get" request to API
import json                        # parse json into a list
import pandas as pd                # working with data frames
import mysql.connector
from sqlalchemy import create_engine

class TestStrategy(bt.Strategy):
    params = (
        ('ob', 25),
        ('ovs', 75),
        ('period',14),
        )

    buyy = False
    inmarket = False
    sz = 1
    liquid = False
    closed = False

    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        self.dataclose = self.datas[0].close

        # To keep track of pending orders and buy price/commission
        self.order = None
        self.rsi = bt.indicators.RSI(self.datas[0].close, period=self.params.period)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            #self.log('ORDER ACCEPTED/SUBMITTED', dt=order.created.dt)
            self.order = order
            return
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            #self.log('Order Canceled/Margin/Rejected') 
            self.liquid = True
            return       
        self.order = None



    def next(self):
        if self.liquid:                
            return
        if self.order:
            return
        if self.broker.getvalue() <= 0:
            print ('liquid...' , self.datetime.datetime(ago=0) , ' ----  value : ' , self.broker.getvalue() , ' --- period : ' , self.params.period)
            if not self.closed:
                self.order = self.close(exectype=bt.Order.Market) 
            self.liquid = True
            return
        
        
        if not self.inmarket:     
            if self.rsi[0] <= self.params.ob:
                self.buyy = True
                self.inmarket = True
                self.order = self.buy(exectype=bt.Order.Market) 
            elif self.rsi[0] >= self.params.ovs:
                self.buyy = False
                self.inmarket = True
                self.order = self.sell(exectype=bt.Order.Market) 
        else:              
            if self.closed:
                self.closed = False
                if not self.buyy:
                    self.order = self.buy(exectype=bt.Order.Market) 
                    self.buyy = True                    
                else:
                    self.order = self.sell(exectype=bt.Order.Market) 
                    self.buyy = False
                return
            else: 
                if self.rsi[0] <= self.params.ob:
                    if not self.buyy:
                        self.order = self.close(exectype=bt.Order.Market) 
                        self.closed = True
                        self.inmarket = True                   
                if self.rsi[0] >= self.params.ovs:
                    if self.buyy:
                        self.order = self.close(exectype=bt.Order.Market)
                        self.closed = True
                        self.inmarket = True  

       
def get_binance_bars(): 
    user = 'root'
    passw = ''
    host =  'localhost'  
    port = 3306 
    database = 'binance'

    engine = create_engine('mysql+mysqlconnector://' + user + ':' + passw + '@' + host + ':' + str(port) + '/' + database , echo=False)

    dbConnection = engine.connect()
    df= pd.read_sql("select * from btcdaily2", dbConnection)

 
    if (len(df.index) == 0):
        return None
     
    df = df.iloc[:, 0:6]
    df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
 
    df.open      = df.open.astype("float")
    df.high      = df.high.astype("float")
    df.low       = df.low.astype("float")
    df.close     = df.close.astype("float")
    df.volume    = df.volume.astype("float")
    
    df['adj_close'] = df['close']
     
    df.index = [dt.datetime.fromtimestamp(x / 1000.0) for x in df.datetime]
 
    return df

if __name__ == '__main__':
    cerebro = bt.Cerebro(optreturn=False)
    cerebro.optstrategy(TestStrategy, period=range(20,25), ob=range(25,27), ovs=range(70,72))
    data = bt.feeds.PandasData(dataname=get_binance_bars())
    cerebro.adddata(data)

    cerebro.broker.setcash(100000)
    marketFee = float(input('Please enter Exchange Fee : '))
    cerebro.broker.setcommission(commission = marketFee)
    cerebro.broker.set_coc(True)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=20)
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    print('cash : ' , cerebro.broker.get_cash())
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="mysharpe_1")
    
    opt_runs = cerebro.run()

    final_results_list = []
    for run in opt_runs:
        for strategy in run:
            value = round(strategy.broker.get_value(),2)
            PnL = round(value - 20000 ,2)
            period = strategy.params.period
            ovs = strategy.params.ovs
            ob = strategy.params.ob
            sr = strategy.analyzers.mysharpe_1.get_analysis()
            final_results_list.append([period,PnL,ovs,ob,sr])

    by_period = sorted(final_results_list, key=lambda x: x[0])

    print('Results: Ordered by period:')
    for result in by_period:
        print('Period: {}, PnL: {}, OVS: {}, OB: {}, SharpRatio: {}'.format(result[0], result[1], result[2], result[3], result[4]))
