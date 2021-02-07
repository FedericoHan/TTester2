# -*- coding: utf-8 -*-
"""
Created on Sun Jan 31 11:38:03 2021

@author: miste
"""

import datetime
import datetime as dt#  --->NameError: name 'datetime' is not defined
from datetime import date
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import DownloadData_v3

    
#create objects 
def get_time_series(start, end, freq, securities):
    
    securities_obj = []
    i = 0
    for i in range(len(securities)):
        securities_obj.append('') #initialize
    
        securities_obj[i] = DownloadData_v3.DownloadData(pair = securities[i], \
                                                 fields = ['PX_LAST'], \
                                                 startDate = start, \
                                                 endDate = end, \
                                                 period = frequency, \
                                                source = 'blp')
    #create dictionary to store the time series  
    container = {}
    i = 0
    
    #returns dictionary of dateframe_timeseries
    for pair in securities_obj:
    
        container[pair] = []
    
        container[pair] = securities_obj[i].get_data_blp_historical(1) #for some reason returns ('SPX Index', 'PX_LAST')
        i += 1
    
    #merge the dataframes_timeseries
    container = pd.concat([container[j] for j in securities_obj], join = 'outer',\
                           axis = 1, keys = securities)
    
    #make numeric
    container = container.apply(pd.to_numeric, errors = 'coerce', axis = 0)
    #ffill 
    container = container.fillna(method = 'ffill')
    
    return container

start = dt.datetime(2000, 1, 20)  #year, month, day
end = dt.datetime.today()
frequency = 'DAILY'

study_set = ['SPX Index', 'USDCNY Curncy', 'IHN+1M Curncy', 'IRN+1M Curncy', 'KWN+1M Curncy', \
             'PPN+1M Curncy',\
             'USDSGD Curncy', 'NTN+1M Curncy']

df_study_set2 = get_time_series(start = start, end = end, freq = frequency, securities = study_set)

for col in df_study_set:
    df_study_set[col[0]+'_%change'] = df_study_set[col].pct_change()
    
idxmask = df_study_set.index[df_study_set['SPX Index_%change']< -0.02]

temp_index = [df_study_set.loc[timestamp - pd.Timedelta(5, unit = 'd'):timestamp + pd.Timedelta(5, unit = 'd')].index for timestamp in idxmask]
idx = np.unique(np.concatenate((temp_index)))

df1 = df_study_set.loc[idx]
                            

temp_index_before = [df_study_set.loc[timestamp - pd.Timedelta(5, unit = 'd'): timestamp].index for timestamp in idxmask]
temp_index_after = [df_study_set.loc[timestamp: timestamp+ pd.Timedelta(5, unit = 'd')].index for timestamp in idxmask]

idx_before = np.unique(np.concatenate(temp_index_before))
idx_after = np.unique(np.concatenate(temp_index_after))

df_before = df_study_set.loc[idx_before]
df_after = df_study_set.loc[idx_after]
