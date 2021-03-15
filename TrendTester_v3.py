# -*- coding: utf-8 -*-
"""
Created on Tue Jan  5 20:49:09 2021

@author: miste
version  3, adds EM stuff
"""
#########
##dependencies
import datetime
import pandas as pd
import numpy as np
import DownloadData_v2
import statsmodels.api as sm
###not needed as using bloomberg for now
#import quandl

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
                signals['ret_cum'].iloc[i+1] = signals['rets'].iloc[i] # signals['rets'].cumsum()
                
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
    endDate = datetime.datetime(2021,2,27)#datetime.datetime.today()
    
    
    data_tens = DownloadData_v2.DownloadData('USGG10YR Index', ['PX_OPEN', 'PX_LAST', 'PX_LOW', 'PX_HIGH'],
                                 startDate, endDate, 'DAILY', 'blp').get_data_blp_historical(1)
    #instance 
    class_tens = FedTrendStudy(symbol = '10ys_yield', bars = data_tens,short_window = 1, long_window = 55, price_or_percent = 'price' )      
    #create df
    signals_tens = class_tens.generate_signals()
    historical_trend_synopsis_tens = signals_tens[signals_tens['loop'] != 0]
    cleaned_tens = historical_trend_synopsis_tens[['entry_track', 'trend_length', 'entry_level','loop', 'inten', 'trend_sum']]
    
    
    data_ty = DownloadData_v2.DownloadData('TY1 Comdty', ['PX_OPEN', 'PX_LAST', 'PX_LOW', 'PX_HIGH'],
                                  startDate, endDate, 'DAILY', 'blp').get_data_blp_historical(1)
    #class isntance 
    class_ty = FedTrendStudy(symbol = 'ty_futs', bars = data_ty ,short_window = 1, long_window = 55, price_or_percent = 'percent' )
    signals_ty = class_ty.generate_signals()
    
    historical_trend_synopsis_ty = signals_ty[signals_ty['loop'] != 0 ]
    cleaned_ty = historical_trend_synopsis_ty[['entry_track', 'trend_length', 'entry_level','loop', 'inten', 'trend_sum']]
    
    
    data_eurusd=  DownloadData_v2.DownloadData('EURUSD Curncy', ['PX_OPEN', 'PX_LAST', 'PX_LOW', 'PX_HIGH'],
                                  startDate, endDate, 'DAILY', 'blp').get_data_blp_historical(1)
    
    #class isntance 
    class_eurusd = FedTrendStudy(symbol = 'eurusd', bars = data_eurusd ,short_window = 1, long_window = 55, price_or_percent = 'price' )    
    signals_eurusd = class_eurusd.generate_signals()
    
    historical_trend_synopsis_eurusd = signals_eurusd[signals_eurusd['loop'] != 0 ]
    cleaned_eur = historical_trend_synopsis_eurusd[['entry_track', 'trend_length', 'entry_level','loop', 'inten', 'trend_sum']]
    
    
    data_usdidr =  DownloadData_v2.DownloadData('USDIDR Curncy', ['PX_OPEN', 'PX_LAST', 'PX_LOW', 'PX_HIGH'],
                                  startDate, endDate, 'DAILY', 'blp').get_data_blp_historical(1)

    #class isntance 
    class_usdidr = FedTrendStudy(symbol = 'usdidr', bars = data_usdidr ,short_window = 1, long_window = 55, price_or_percent = 'price' )    
    signals_usdidr = class_usdidr.generate_signals()
    
    historical_trend_synopsis_usdidr = signals_usdidr[signals_usdidr['loop'] != 0 ]
    
 
    data_ppswn4 =  DownloadData_v2.DownloadData('PPSWN4 Curncy', ['PX_OPEN', 'PX_LAST', 'PX_LOW', 'PX_HIGH'],
                                  startDate, endDate, 'DAILY', 'blp').get_data_blp_historical(1)

    #class isntance 
    class_ppswn4 = FedTrendStudy(symbol = 'PPSWN4', bars = data_ppswn4 ,short_window = 1, long_window = 55, price_or_percent = 'price' )    
    signals_ppswn4 = class_ppswn4.generate_signals()
    
    historical_trend_synopsis_ppswn4 = signals_ppswn4[signals_ppswn4['loop'] != 0 ]
    
    
    #some local pairs databest after 2004, so dwnload from 2004 onwards
    startDateEm = datetime.datetime(2004,1,1 )
    data_PPN1M = DownloadData_v2.DownloadData('PPN+1M Curncy', 'PX_LAST', startDateEm, endDate, 'DAILY', 'blp').get_data_blp_historical(0)#level 0 labels the underlying, label 1 is PX_LASt
    data_PPSWN4 = DownloadData_v2.DownloadData('PPSWN4 Curncy', 'PX_LAST', startDateEm, endDate, 'DAILY', 'blp').get_data_blp_historical(0)
    data_IHSWN4 = DownloadData_v2.DownloadData('IHSWN4 Curncy', 'PX_LAST', startDateEm, endDate, 'DAILY', 'blp').get_data_blp_historical(0)
    
    #join together
    data_aggregate_EM = pd.concat([data_PPN1M, data_PPSWN4, data_IHSWN4], axis = 1).fillna(method = 'ffill')
    
    'what i want to check now is on clenaned_tens what were the prices at start and end of the EM stuff'
    #set 'entry_track' as Datetimeobject
    cleaned_tens['entry_track'] = pd.to_datetime(cleaned_tens['entry_track'], errors = 'coerce')
    cleaned_tens2 = cleaned_tens.iloc[1:] #remove first row as null  , so can change from type Object to Datetime 
    cleaned_tens2.reset_index(inplace = True) #reset index
    
    #merge cleaned_tens2 with EM data,by  matching 'entry_track' on left,  with 'date' on right
    test_merge = pd.merge(cleaned_tens2, data_aggregate_EM, left_on = 'entry_track', right_on = 'date')
    #merge again this time thit ime matching on date.   
    test_merge2 = pd.merge(test_merge, data_aggregate_EM, on = 'date')
    
    '''silly hack if forgot to merge df
    
    test_merge2['dumbo'] = 0.0
    for i in range(len(test_merge2)):
        print(i, test_merge2['entry_track'].iloc[i], data_aggregate.index[i])
        test_merge2['dumbo'].iloc[i] = data_aggregate['PPN+1M Curncy'].loc[test_merge2['entry_track'].iloc[i]]'''
        
    
    test_merge2['ppn_delta'] = test_merge2['PPN+1M Curncy_y'] - test_merge2['PPN+1M Curncy_x'] 
    test_merge2['PPWSN_delta'] = test_merge2['PPSWN4 Curncy_y'] - test_merge2['PPSWN4 Curncy_x'] 
    test_merge2['IHSWN_delta'] = test_merge2['IHSWN4 Curncy_y'] - test_merge2['IHSWN4 Curncy_x'] 
    
    #reset index as date
    test_merge2.set_index('date', inplace = True)
    
    xdat = test_merge2['trend_sum']
    xdat = sm.add_constant(xdat)
    ydat = test_merge2['PPWSN_delta']
    result = sm.OLS(ydat, xdat).fit()
    print(result.summary())
    
    plt.plot(xdat, ydat, 'r.')
    ax = plt.axis() #grab axis value
    x = np.linspace(ax[0], ax[1] + 0.01)
    plt.plot(x, -0.0137 + 3.1869 * x , 'b' , lw = 2)
    plt.grid(True)
    plt.axis('tight')
    plt.xlabel('yields_trendsum')
    plt.ylabel('PPSWN_delta')
    
    
