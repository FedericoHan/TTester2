# -*- coding: utf-8 -*-
"""
Created on Tue Jan  5 20:49:09 2021

@author: miste
"""
#########
##dependencies
import datetime
import pandas as pd
import numpy as np
import DownloadData_v2
###not needed as using bloomberg for now
#import quandl
#quandl.ApiConfig.api_key = 'eZ2QKTMzUvQ8z5R3s2bw'

import matplotlib.pyplot as plt

#based on https://www.quantstart.com/articles/Research-Backtesting-Environments-in-Python-with-pandas/
from backtest import Strategy, Portfolio


##############
 
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
        
        
        #now use loops even if less pythonic cuz dont know how to vectorzie yet and small enough 
        obs = len(signals['PX_LAST'])
        #entry or exit price..when signals generated ..using simple price xover here
        signals['loop'] = 0.0
        #returns cumulative in trend,
        signals['ret_cum'] = 0.0
        #max or min ret_cumulative...so from entry to highest accumulated price inside 'loop'
        signals['inten'] = 0.0
        #returns  from whatever entry is in 'loop' to whenever gets out
        signals['trend_sum'] = 0.0
        #if want to clean below and run into just one loop ,set this up i nthe future 
        signals['trend_sum2'] =0.0
        #days
        signals['days'] = 0.0
        #dummy columns
        signals['dummy'] =signals.index
        #entry tracker for date and price
        signals['entry_track'] = 0.0
        signals['entry_level']= 0.0
        
        signals['index_dummy'] = 0
        for i in range(0, obs):
            signals['index_dummy'].iloc[i] = signals['index_dummy'].iloc[i-1]+ 1
        
        #loop trackers for 'inten' calcs
        start = 0#-1
        stop = 0#-1
        count = 0
        
        for i in range(self.long_window, obs):
            
            #if prices cross above
            if signals['PX_LAST'].iloc[i] >= signals['long_mavg'].iloc[i] and signals['PX_LAST'].iloc[i-1] < signals['long_mavg'].iloc[i-1] : 
                signals['loop'].iloc[i] = signals['PX_LAST'].iloc[i]
                #then for the trend ones, shift by one else you have 'CLAIRVOYANCE'
                signals['ret_cum'].iloc[i+1] = signals['rets'].iloc[i] # signals['rets'].cumsum()
        
            #if  prices cross below
            elif signals['PX_LAST'].iloc[i] <= signals['long_mavg'].iloc[i] and signals['PX_LAST'].iloc[i-1] > signals['long_mavg'].iloc[i-1] : 
                signals['loop'].iloc[i] = signals['PX_LAST'].iloc[i]
                signals['ret_cum'].iloc[i+1] = signals['rets'].iloc[i] # signals['rets'].cumsum(
                
            #days counter..when no crossovers just accumlate one day 
            if signals['loop'].iloc[i] == 0:
                signals['days'].iloc[i] = signals['days'].iloc[i-1] + 1
                signals['ret_cum'].iloc[i] = signals['ret_cum'].iloc[i-1] + signals['rets'].iloc[i]
                
                
            ###infinite loop preventer 
            if stop > obs: # max(toy_C.index):
                break
            #print(i)
            #when a signal is generated 
            if signals['loop'].iloc[i] != 0: #can use this if index is not datetime:  toy_C.loc[i,'loop'] != 0:
                #if it's the first one, start counting
                if count == 0:
                    start = i
                    print('first start is '+str(i))
                #at the next signal, ie when exit
                else: 
                    stop = i
                    
                    #tracker for entry into trend
                    signals['entry_track'].iloc[i] = signals['dummy'].iloc[start]
                    signals['entry_level'].iloc[i] = signals['PX_LAST'].iloc[start]
                    
                    
                    #could be key piece  :  start2 = stop2
                    
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
            
        #find entry vs exit chagnes..i know its redudant but dont wanan clutter above to omuch , can clean up later
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
        
        #delete dummy  (ie dates taken from index ) array
        del signals['dummy']
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
    
    #if using BBG for data 
    startDate = datetime.datetime(1990, 10, 9) #year month day
    endDate = datetime.datetime(2021,1,22)#datetime.datetime.today()
    '''
    usgg10yr = DownloadData_v2.DownloadData('USGG10YR Index', ['PX_OPEN', 'PX_LAST', 'PX_LOW', 'PX_HIGH'],
     #                             startDate, endDate, 'DAILY', 'blp').get_data_blp_historical(1)
    #instance 
    tens = FedTrendStudy(symbol = '10ys_yield', bars = usgg10yr,short_window = 1, long_window = 55, price_or_percent = 'price' )      
    #create df
    tens_signals = tens.generate_signals()
    
    historical_trend_synopsis = tens_signals[tens_signals['loop'] != 0]'''
    
    data_ty = data_ty #= DownloadData_v2.DownloadData('TY1 Comdty', ['PX_OPEN', 'PX_LAST', 'PX_LOW', 'PX_HIGH'],
         #                         startDate, endDate, 'DAILY', 'blp').get_data_blp_historical(1)
    
    #class isntance 
    class_ty = FedTrendStudy(symbol = 'ty_futs', bars = data_ty ,short_window = 1, long_window = 55, price_or_percent = 'percent' )    
    signals_ty = class_ty.generate_signals()
    
    historical_trend_synopsis_ty = ty_futs_signals[ty_futs_signals['loop'] != 0 ]
    
    data_eurusd=  DownloadData_v2.DownloadData('EURUSD Curncy', ['PX_OPEN', 'PX_LAST', 'PX_LOW', 'PX_HIGH'],
                                  startDate, endDate, 'DAILY', 'blp').get_data_blp_historical(1)
    
    #class isntance 
    class_eurusd = FedTrendStudy(symbol = 'eurusd', bars = data_eurusd ,short_window = 1, long_window = 55, price_or_percent = 'price' )    
    signals_eurusd = class_eurusd.generate_signals()
    
    historical_trend_synopsis_eurusd = signals_eurusd[signals_eurusd['loop'] != 0 ]
    
    data_usdidr =  DownloadData_v2.DownloadData('USDIDR Curncy', ['PX_OPEN', 'PX_LAST', 'PX_LOW', 'PX_HIGH'],
                                  startDate, endDate, 'DAILY', 'blp').get_data_blp_historical(1)
    
    #class isntance 
    class_usdidr = FedTrendStudy(symbol = 'usdidr', bars = data_usdidr ,short_window = 1, long_window = 55, price_or_percent = 'price' )    
    signals_usdidr = class_usdidr.generate_signals()
    
    historical_trend_synopsis_usdidr = signals_usdidr[signals_usdidr['loop'] != 0 ]
    
    

    
    #tens_signals['entry'][long_window:] = np.where(tens_signals['positions'][long_window:] == 2, tens_signals['PX_LAST'][long_window:], 0.0 )
    #tens_signals['entry'][long_window:] = np.where( tens_signals['positions'][long_window:] == -2, tens_signals['PX_LAST'][long_window:], 0.0 )                                              
    