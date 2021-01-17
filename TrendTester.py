# -*- coding: utf-8 -*-
"""
Created on Tue Jan  5 20:49:09 2021

@author: miste
"""

import datetime
import pandas as pd
import numpy as np
import DownloadData_v2
import quandl
quandl.ApiConfig.api_key = 'eZ2QKTMzUvQ8z5R3s2bw'

import matplotlib.pyplot as plt

#based on https://www.quantstart.com/articles/Research-Backtesting-Environments-in-Python-with-pandas/
from backtest import Strategy, Portfolio

#if using BBG for data 
startDate = datetime.datetime(2013, 1, 1) #year month day
endDate = datetime.datetime(2015,12,30)#datetime.datetime.today()

usgg10yr = DownloadData_v2.DownloadData('USGG10YR Index', ['PX_OPEN', 'PX_LAST', 'PX_LOW', 'PX_HIGH'],
                                  startDate, endDate, 'DAILY', 'blp').get_data_blp_historical(1) 


class FedTrendStudy(Strategy):
    
    '''given some metric say a price  crossbelow some MA, which defines the 'trend' '
    begin counting days, such that time = exit(t) - entry(t)
    then intensity = entry - low 
    and move_lenght  = entr - exit
    can also calculate speed of the above
    instance example: tens = FedTrendStudy(symbol = '10ys_yield', bars = usgg10yr,short_window = 1, long_window = 55, price_or_percent = 'percent' )    
    '''
    
    def __init__(self,  symbol, bars, short_window, long_window, price_or_percent):
        
        self.symbol = symbol #the security, kinda useless?
        self.bars = bars  #the input df with timeseries
        self.short_window = short_window #only need this if do some crossing over, here i just use PX_LAST 
        self.long_window =long_window 
        self.price_or_percent =  price_or_percent #takes string for 'price =any FX, commo, equity  vs 'percent' = any volatiltiy or yield
        
    def generate_signals(self):
        
        #create container df for signals, rows = historical data from bars df
        signals = pd.DataFrame(index = self.bars.index)
        #initialize signals array
        signals['signal'] = 0.0
        #debug check
        print(self.bars.head())
        #calcualte slow and long mas
        signals['short_mavg'] = self.bars['PX_LAST'].rolling(window = self.short_window, \
                                                        min_periods = 1, center = False).mean()
        
        signals['long_mavg'] = self.bars['PX_LAST'].rolling(window = self.long_window, \
                                                      min_periods = 1, center = False).mean()
            
        #signals['PX_OPEN'] = self.bars['PX_OPEN']
        signals['PX_LAST'] = self.bars['PX_LAST']
        #signals['PX_LOW'] = self.bars['PX_LOW']
        #signals['PX_HIGH'] = self.bars['PX_HIGH']
        
        #if time series is a yield or vol the return is a difference
        if self.price_or_percent == 'percent':
            signals['rets'] = signals['PX_LAST'] - signals['PX_LAST'].shift(1)
        #if time series is a price, take logreturn
        else:
            signals['rets'] = np.log(signals['PX_LAST']/signals['PX_LAST'].shift(1))
            
        #cumulative returns..might need to shift by 1 to avoid clairvoyance, so first actual
        signals['ret_cum_actual'] = signals['rets'].cumsum()

        # geneate signals is always in the market, starting from after long window, else no data
        signals['signal'][self.long_window:] = np.where(signals['PX_LAST'][self.long_window:] >\
                                                         signals['long_mavg'][self.long_window:], \
                                                          1.0, -1.0)
            
        #take difference of signals for actual trading odas
        signals['positions'] = signals['signal'].diff()
        
        
        #now i use loops even if less pythonic
        obs = len(signals['PX_LAST'])
        #entry or exit price..when signals generated 
        signals['loop'] = 0.0
        #returns in trend
        signals['ret_cum'] = 0.0
        #max or min ret_cum
        signals['inten'] = 0.0
        # returns over trend
        signals['trend_sum'] = 0.0
        signals['trend_sum2'] =0.0
        #days
        signals['days'] = 0.0
        #dummy columns
        signals['dummy'] =signals.index
        #entry tracker
        signals['entry_track'] = 0.0
        
        
    
        for i in range(self.long_window, obs):
    
            #if cross above
            if signals['PX_LAST'].iloc[i] >= signals['long_mavg'].iloc[i] and signals['PX_LAST'].iloc[i-1] < signals['long_mavg'].iloc[i-1] : 
                signals['loop'].iloc[i] = signals['PX_LAST'].iloc[i]
                #then for the trend ones, shift by one 
                signals['ret_cum'].iloc[i+1] = signals['rets'].iloc[i] # signals['rets'].cumsum()
        
            #if cross below
            elif signals['PX_LAST'].iloc[i] <= signals['long_mavg'].iloc[i] and signals['PX_LAST'].iloc[i-1] > signals['long_mavg'].iloc[i-1] : 
                signals['loop'].iloc[i] = signals['PX_LAST'].iloc[i]
                signals['ret_cum'].iloc[i+1] = signals['rets'].iloc[i] # signals['rets'].cumsum(
                
            #days counter..when no crossovers just add one day 
            if signals['loop'].iloc[i] == 0:
                signals['days'].iloc[i] = signals['days'].iloc[i-1] + 1
                signals['ret_cum'].iloc[i] = signals['ret_cum'].iloc[i-1] + signals['rets'].iloc[i]
        

        
        #find intensity
        start = 0#-1
        stop = 0#-1
        count = 0
            
        for i in range(self.long_window, obs):# toy_C.index:
            if stop > obs: # max(toy_C.index):
                break
            #print(i)
            #when a signal is generated 
            if signals['loop'].iloc[i] != 0: #can use this if index is not datetime:  toy_C.loc[i,'loop'] != 0:
                #enter = toy_C['loop'].iloc[i]
                #start counting
                if count == 0:
                    start = i
                #at the next signal, ie when exit
                else: 
                    stop = i
                    
                    signals['entry_track'].iloc[i] = signals['dummy'].iloc[start]
               
                    #print(str(loop stop + toy_C['loop'].iloc[stop]))
                    #print(str('start and stop :'),start, stop)
                    #print((toy_C['loop'].iloc[stop]/ toy_C['loop'].iloc[start]) -1)
                    
                    #if mean in interval < 0 we know is downtrend and take the min
                    if signals['ret_cum'].iloc[start:stop].mean() <= 0:  #toy_C.loc[start:stop,'ret_cum'].mean() <= 0:
                        signals['inten'].iloc[i] = signals['ret_cum'].iloc[start:stop].min() #toy_C.loc[i, 'inten'] = toy_C.loc[start:stop, 'ret_cum'].min()
                    else:
                        signals['inten'].iloc[i] = signals['ret_cum'].iloc[start:stop].max()#toy_C.loc[i, 'inten'] = toy_C.loc[start:stop, 'ret_cum'].max()
                    start = stop + 1
                count += 1
             
        #find entry vs exit chagnes
        start2 = 0
        stop2 = 0
        count2 = 0     
            
                    
        #find trend entry and exit
        for i in range(self.long_window, obs):
                
            if signals['loop'].iloc[i] != 0:
             
                #print(i)
                if count2 == 0:
                    #print(i)
                    start2 = i
                else:
                    #print(i)
                    stop2 = i
                    if self.price_or_percent == 'price':
                        signals['trend_sum'].iloc[i] =(signals['loop'].iloc[stop2] /signals['loop'][start2]) - 1
                    else:
                        signals['trend_sum'].iloc[i]  = signals['loop'].iloc[stop2] -signals['loop'][start2]
                    start2 = stop2
                count2 += 1
         

        #find trend legnth    
        signals['trend_length'] = np.where(signals['days'] == 0, signals['days'].shift(1), 0)
        ''' 
        tens_signals['entry'][long_window:] = np.where(((tens_signals['PX_LAST'][long_window:] > tens_signals['long_mavg'][long_window:]) &\
                                               (tens_signals['PX_LAST'][long_window:].shift(-1) <tens_signals['PX_LAST'][long_window:].shift(-1))), 1, 0)#tens_signals['PX_LAST']
    
        tens_signals['entry'][long_window:] = np.where(np.logical_and(np.greater_equal(tens_signals['PX_LAST'][long_window:],tens_signals['long_mavg'][long_window:]),\
                                                              np.greater_equal(tens_signals['long_mavg'][long_window:].shift(-1),tens_signals['PX_LAST'][long_window:].shift(-1))),tens_signals['PX_LAST'][long_window:],0)

        
        #below in market only outside rangess.
    
        print(SD)
        signals['short_mavg_minus_long_mavg'] = signals['short_mavg'] - signals['long_mavg']
        signals['signal'][self.long_window:] = np.where(signals['short_mavg_minus_long_mavg'][self.long_window:]\
                                                        > SD, 1.0, 0.0)
        
        #print(signals)
        signals['signal'][self.long_window:] = np.where(signals['short_mavg_minus_long_mavg'][self.long_window:]\
                                                        < SD, -1.0, signals['signal'][self.long_window:])
        '''

        #signals.to_csv('sign.csv')
        #print(signals['signal'].value_counts())
        return signals #df with signal  short_mavg   long_mavg  positions
        
  
if __name__ == "__main__":
    
    #instance 
    tens = FedTrendStudy(symbol = '10ys_yield', bars = usgg10yr,short_window = 1, long_window = 55, price_or_percent = 'percent' )      
    #create df
    tens_signals = tens.generate_signals()
    
    
    #tens_signals['entry'][long_window:] = np.where(tens_signals['positions'][long_window:] == 2, tens_signals['PX_LAST'][long_window:], 0.0 )
    #tens_signals['entry'][long_window:] = np.where( tens_signals['positions'][long_window:] == -2, tens_signals['PX_LAST'][long_window:], 0.0 )                                              
    