#!/usr/bin/env python
# coding: utf-8

# In[1]:


#Step 1 Import packages
import pandas as pd
#import matplotlib.pyplot as plt
import plotly.express as px
import urllib
import json
from scipy import interpolate
from copy import deepcopy


pd.options.plotting.backend = "plotly"
get_ipython().run_line_magic('matplotlib', 'notebook')


import plotly.graph_objects as go
from plotly.subplots import make_subplots


# In[131]:


#Stores Data
#
#To restore data instead of pulling again
get_ipython().run_line_magic('store', '-r')
mod_data = deepcopy(data)


# In[5]:


#ONLY RUN IF YOU HAVE NO STORED DATA
#Step 2 import calibration files, sensor lists, sensor dictionary with interpolation functions
def make_inter_func(cali_file):
    if cali_file['code'] == 'good':
        cali_file = cali_file['data']
        return interpolate.interp1d([i[1] for i in cali_file], [i[0] for i in cali_file])
    else:
        raise Exception('Cali File aint good')
def pull_web_info(url):
    return json.loads((urllib.request.urlopen(f'{url}')).read())
        
#Import calibration files for thermometers
'''
dc2018 = pull_web_info('http://132.163.53.82:3200/database/calibration.db/dc2018')
'''

rox6951 = pull_web_info('http://132.163.53.82:3200/database/calibration.db/rox6951')
ro600 = pull_web_info('http://132.163.53.82:3200/database/calibration.db/ro600')
ruo2mean = pull_web_info('http://132.163.53.82:3200/database/calibration.db/ruo2mean')
dt670 = pull_web_info('http://132.163.53.82:3200/database/calibration.db/dt670')
#Import sensor Lists
diode_list = pull_web_info('http://132.163.53.82:3200/database/log.db/diode_list')
lockin_list = pull_web_info('http://132.163.53.82:3200/database/log.db/lockins_list')
heater_list = pull_web_info('http://132.163.53.82:3200/database/log.db/heaters_list')

f_dc2018 = make_inter_func(dc2018)
f_rox6951 = make_inter_func(rox6951)
f_ro600 = make_inter_func(ro600)
f_ruo2mean = make_inter_func(ruo2mean)
f_dt670 = make_inter_func(dt670)

def sensor_list_to_dict(sensor_list):
    if sensor_list['code'] == 'good':
        sensor_list = sensor_list['data'] #I know what to expect
        sensor_dict = {}
        id_calibration_list = []
        for sensor in sensor_list:
            sensor_dict[sensor[1]] = {
                'id': sensor[0],
            }
            if sensor[3] != None:
                if sensor[3] == 'DC2018':
                    sensor_dict[sensor[1]]['calibration'] = f_dc2018
                if sensor[3] == 'DT670':
                    sensor_dict[sensor[1]]['calibration'] = f_dt670
                if sensor[3] == 'ROX6951':
                    sensor_dict[sensor[1]]['calibration'] = f_rox6951
                if sensor[3] == 'RO600':
                    sensor_dict[sensor[1]]['calibration'] = f_ro600
                if sensor[3] == 'RuO2Mean':
                    sensor_dict[sensor[1]]['calibration'] = f_ruo2mean
                
        return sensor_dict
    else:
        raise Exception('Sensor list aint good')
        
#Generate sensor dictionary with interpolation functions
diode_dict = sensor_list_to_dict(diode_list)
lockin_dict = sensor_list_to_dict(lockin_list)
heater_dict = sensor_list_to_dict(heater_list)
dr_sensor_dict = dict(diode_dict, **lockin_dict, **heater_dict)
get_ipython().run_line_magic('store', 'dr_sensor_dict')


# In[15]:


#ONLY RUN IF YOU HAVE NO STORED DATA
#Step 3 pull DR Data
def pull_dr_data(sensor_dict, time_secs):
    dr_data = {}
    for sensor in sensor_dict:
        sensor_id  = sensor_dict[sensor]['id']
        print("Sensor ID =", sensor_id)
        sensor_data = pull_web_info(f'http://132.163.53.82:3200/database/log.db/data?id={sensor_id}&start=-{time_secs}')
        if sensor_data['code'] == 'good':
            dr_data[sensor] = sensor_data['data']
        else:
            raise Exception('Sensor data aint good')
    return dr_data
#num pts = 20 gives either 1 or 2 readings. I assume 10 = 1 readings, so 100 = 10 readings
data = pull_dr_data(dr_sensor_dict, 75000) #time_secs collections the last X seconds at end of list (newest x seconds worth of data)
get_ipython().run_line_magic('store', 'data')


# In[32]:


#Stores Data
#
#To restore data instead of pulling again
get_ipython().run_line_magic('store', '-r')
mod_data = deepcopy(data)


# In[132]:


#Exterpolate DR data from voltage to temperature
def convert_dr_data(dr_data, sensor_dict):
    converted_data = {}   
    earliest_time_step = dr_data[list(sensor_dict.keys())[0]][0][0]
    x_axis = 'Time (M)'
    y_axis = 'y_data'
    name = 'name'
    sensor_list = list(sensor_dict.keys())
    converted_data = pd.DataFrame({
        name : sensor_list,
        x_axis: [0]*len(sensor_list),
        y_axis: [0]*len(sensor_list)
    })
    for sensor in dr_data:
        try:            
            first_time_step = dr_data[sensor][0][0]
            if (first_time_step < earliest_time_step) and first_time_step != 0:
                earliest_time_step = first_time_step
                earliest_sensor_name = sensor
        except:
            continue
        x_list = []
        y_list = []
        for i in range(len(dr_data[sensor])):
            dr_data[sensor][i][0] -= earliest_time_step #Have zero start time from starting epoch
            dr_data[sensor][i][0] /= 60 #conver to min
            x_list.append(dr_data[sensor][i][0])

            if 'calibration' in sensor_dict[sensor]:
                    #converted_data[sensor][y_axis] = [0]*len(dr_data[sensor])
                    y_list.append(sensor_dict[sensor]['calibration'](dr_data[sensor][i][2]))
            else:
                y_list.append(dr_data[sensor][i][2])
                
        temp_df = pd.DataFrame({
            name : sensor,
            x_axis : x_list,
            y_axis : y_list
        })
        converted_data = pd.concat([converted_data, temp_df])
    return converted_data

def dataframe_x_zeroing(df):
    x_axis = 'Time (M)'
    y_axis = 'y_data'
    name = 'name'
    print('here')
    mod_df = pd.DataFrame({
    })
    for sensor_name, group in df.groupby('name'):
        
        temp_df = pd.DataFrame({
            name : sensor_name,
            x_axis : group[x_axis] - group[x_axis].iloc[0],
            y_axis : group[y_axis]
        })
        mod_df = pd.concat([mod_df, temp_df])
    return mod_df

conv_data = convert_dr_data(mod_data, dr_sensor_dict)
#133.6719
sectioned_df = conv_data.where(conv_data['Time (M)'] > 133.6719)
dr_df = dataframe_x_zeroing(sectioned_df)


# In[34]:


#133.6719
sectioned_df = conv_data.where(conv_data['Time (M)'] > 133.6719)
#Graph conv_data and find where to snip data seciton
x_axis = 'Time (M)'
y_axis = 'y_data'
name = 'name'
fig = px.line(dr_df, x = x_axis, y = y_axis, color = name)
fig.show()


# In[89]:


#Import Excel Data
sg_data = pd.read_excel('C:/Users/rdm8/Documents/DR__Data/2022-05-25-14-20-25.xlsx')
chase_data = pd.read_excel('C:/Users/rdm8/Documents/DR__Data/CRCMD-002 run data reduced.xlsx', sheet_name=['Cooldown'])
chase_2_data = pd.read_excel('C:/Users/rdm8/Documents/DR__Data/CMD Operation example.xlsx', sheet_name=['Cooldown'])
#excel_list = [snodgress_data, chase_data, chase_data_2]


# #Notes from SG Data
# Time in minutes;
# tilt/azimuth in degrees; 
# thermometry in K; 
# still/mxc/thermosiphon/switches/3pots heat in uW; 
# stage1/stage2 heat in W; 
# pump heats in W  
# ...cycle parameters at the time of save:
# countA NEWLINE ramp~4switchA~0~0~0~2~0;
# ramp~3switchA~0~0~0~2~0 NEWLINE until~3pumpA~0.1~0.1~>1.1~ch_3pot_A~5;
# until~4pumpA~0.2~0.2~>1.4~ch_4pot_A~5 NEWLINE until~3pumpA~0.33~0.033~>45~ch_3pump_A~25;
# until~4pumpA~0.6~0.06~>45~ch_4pump_A~25 NEWLINE ramp~4pumpA~0~0~0~15~0 NEWLINE until~A~4switchA~2500~1500~>18~ch_4switch_A~10;
# until~B~4switchA~2500~750~>18~ch_4switch_A~10 NEWLINE until~A~4switchA~1500~1500~<0.9~ch_4pot_A~25;
# until~B~4switchA~750~750~<0.9~ch_4pot_A~25 NEWLINE ramp~3pumpA~0~0~0~0.01~0 NEWLINE until~A~3switchA~2500~2000~>18~ch_3switch_A~10;
# until~B~3switchA~2500~750~>18~ch_3switch_A~10 NEWLINE ramp~A~3pumpA~0~0~0~25~0;ramp~B~3pumpA~0~0~0~50~0

# In[129]:


import numpy as np

sg_df['sg_3pumpA']


# In[113]:


fig.show()
#1644.44

#TODO
#cONVERT PUMP WATTAGE TO VOLTAGE FOR EAISER VIEWING, THE SWITCHES CAN STAY AS uW


# In[125]:


#Get column names of data
#if sg_data != None:
sg_names_a = [sg_data.columns[1]]
sg_names_b = list(sg_data.columns[4:44])
sg_names_a.extend(sg_names_b)
if chase_data != None:
    chase_names_a = list(chase_data['Cooldown'].columns[2:14])
    chase_names_b = list(chase_data['Cooldown'].columns[28:36])
    chase_names_a.extend(chase_names_b)
if chase_2_data != None:
    chase_names_a_2 = list(chase_2_data['Cooldown'].columns[1:14])
    chase_names_b_2 = list(chase_2_data['Cooldown'].columns[14:21])
    chase_names_a_2.extend(chase_names_b_2)


#Format column names of data
#Make new DF with formated columns

def format_df_and_names(name_list, origin_str, df):
    new_name_list = [0]*len(name_list)
    for i in range(len(name_list)):
        if 'CC ' in name_list[i]:
            new_name_list[i] = name_list[i].replace('CC ', f'{origin_str}')
        else:
            new_name_list[i] =  f'{origin_str}'+name_list[i]
        if 'cc_2_' in origin_str:
            new_name_list[i] = new_name_list[i].replace('.1', ' b')
        if 'cc' in origin_str:
            new_name_list[i] = new_name_list[i].replace('1', 'Voltage')
        if 'sg' in origin_str:
            new_name_list[i] =  f'{origin_str}'+ name_list[i]
        
        df = df.rename({name_list[i] : new_name_list[i]}, axis='columns', errors = 'raise')

    return new_name_list, df

chase_2_names, chase_2_df = format_df_and_names(chase_names_a_2, 'cc_2_', chase_2_data['Cooldown'])
chase_names, chase_df = format_df_and_names(chase_names_a, 'cc_', chase_data['Cooldown'])
sg_names, sg_df = format_df_and_names(sg_names_a, 'sg_', sg_data)

#---------------------------------------------------------------------#
def choose_start_loc(chase_df, chase_2_df, sg_df, sequence = True):
    pump_list = [
        'sg_4pumpA',
        'sg_4pumpB',
        'sg_3pumpA',
        'sg_3pumpB'
    ]
    if sequence == True:
        #chase_2_range = 2654
        chase_2_range = 3754 #skips the first 3 pump voltages 
        chase_range = 12447
        sg_range = 19607
        
        drop_chase_2_df = chase_2_df.drop(range(0,chase_2_range))
        drop_chase_df = chase_df.drop(range(0, chase_range))
        drop_sg_df = sg_df.drop(range(0, sg_range))       
            
        drop_chase_2_df['Time (M)'] -= drop_chase_2_df['Time (M)'][chase_2_range]
        drop_chase_df['Time Mins'] -= drop_chase_df['Time Mins'][chase_range]
        drop_sg_df['sg_Time min']-= drop_sg_df['sg_Time min'][sg_range]
        

        for pump in pump_list:
            drop_sg_df[pump] = np.sqrt(drop_sg_df[pump]*300)
            
        return drop_chase_df, drop_chase_2_df, drop_sg_df
    else:
        chase_2_range = 282
        chase_range = 9167
        drop_chase_2_df = chase_2_df.drop(range(0,chase_2_range))
        drop_chase_df = chase_df.drop(range(0, chase_range))
                                
        drop_chase_2_df['Time (M)'] -= drop_chase_2_df['Time (M)'][chase_2_range]
        drop_chase_df['Time Mins'] -= drop_chase_df['Time Mins'][chase_range]
        return drop_chase_df, drop_chase_2_df
    
chase_df, chase_2_df, sg_df = choose_start_loc(chase_df,chase_2_df, sg_df)


# In[135]:


#Chose 1 point before pump voltage first start or sequence start

#Start of pump sequence for sg = 1072.99
#sg_seq_start = sg_df['Time (M)'][2654:].subtract(sg_df['Time (M)'][2654])

#SG pump first start = 307.0308
#sg_first_start = sg_df['Time (M)'][282:].subtract(sg_df['Time (M)'][282])

#Start of pump sequence for chase = 2818.833
#chase_seq_start = chase_df['Time Mins'][12447:].subtract(chase_df['Time Mins'][12447])

#Chase first start = 2129.014
#chase_first_start = chase_df['Time Mins'][9167:].subtract(chase_df['Time Mins'][9167])
#-------------------------------------------------------------------------------------------------------------------#
chase_2_pump_n_switch = ['Time (M)', 'cc_2_3head a', 'cc_2_4head a','cc_2_3head b', 'cc_2_4head b',
                         'cc_2_4pump a Voltage', 'cc_2_3pump a Voltage', 'cc_2_4pump b Voltage','cc_2_3pump b Voltage', 
                         'cc_2_4switch Voltage', 'cc_2_3switch Voltage','cc_2_4switch Voltage b', 'cc_2_3switch Voltage b']

chase_pump_n_switch =['Time Mins','cc_3head a', 'cc_4head a','cc_3head b', 'cc_4head b', 
                      'cc_4pump a Voltage', 'cc_3pump a Voltage', 'cc_4pump b Voltage', 'cc_3pump b Voltage',
                      'cc_4switch a', 'cc_3switch a', 'cc_4switch b', 'cc_3switch b']

fig_sg = px.line(sg_df, x = 'sg_Time min', y = sg_names, color_discrete_sequence=px.colors.qualitative.Bold)

x_axis = 'Time (M)'
y_axis = 'y_data'
name = 'name'
fig_dr = px.line(dr_df, x = x_axis, y = y_axis, color = name, color_discrete_sequence=px.colors.qualitative.Antique)

fig_chase_2 = px.line(chase_2_df.to_dict(), x='Time (M)', y=chase_2_pump_n_switch, log_y=False,
                color_discrete_sequence=px.colors.qualitative.Light24)

fig_chase = px.line(chase_df.to_dict(), x='Time Mins', y=chase_pump_n_switch, log_y=False,
                   color_discrete_sequence=px.colors.qualitative.Dark24,)

fig_chase_2.add_traces(
    list(fig_chase.select_traces())
)
fig_chase_2.add_traces(
    list(fig_dr.select_traces())
)
fig_chase_2.add_traces(
    list(fig_sg.select_traces())
)
fig_chase_2.show()

#sg_traces = go.Scatter(snodgrass_data['Cooldown'].to_dict(), x='Time (M)', y=sg_names_a)
#chase_traces = go.Scatter(chase_data['Cooldown'].to_dict(), x='Time Mins', y=chase_names_a)
fig_chase_2.write_html('./cooldown_compare.html')

