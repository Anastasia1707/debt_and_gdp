import wbgapi as wb
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import pyflux as pf

import seaborn as sns
from scipy.optimize import curve_fit

from sklearn.metrics import r2_score
from sklearn.metrics import mean_squared_error

# Part 0. Data
# Fetching data from World Bank(1995-2021)
wb_dataset = wb.data.DataFrame(
    ['NY.GDP.MKTP.KD.ZG', 'DT.TDS.DPPF.XP.ZS', 'BN.RES.INCL.CD', 'FP.CPI.TOTL.ZG', 'NE.EXP.GNFS.ZS'],
    ['KAZ', 'KGZ', 'RUS', 'BLR'], range(1995, 2022), columns='series')

# Cleanup
wb_dataset.rename(
    columns={'NY.GDP.MKTP.KD.ZG': 'gdp_growth', 'DT.TDS.DPPF.XP.ZS': 'debt_service', 'BN.RES.INCL.CD': 'reserves',
             'FP.CPI.TOTL.ZG': 'cpi', 'NE.EXP.GNFS.ZS': 'export'}, inplace=True)
wb_dataset.reset_index(inplace=True)
wb_dataset['year'] = wb_dataset['time'].str.replace('YR', '', regex=False)
wb_dataset.drop(['time'], axis=1, inplace=True)

# Data normalization: Reserves
wb_dataset['reserves'] = wb_dataset.groupby('economy')['reserves'].transform(lambda x: (x - x.mean()) / x.std())

# Sort and reset index.
country_order = {'BLR': '1', 'KGZ': '2', 'RUS': '3', 'KAZ': '4'}
wb_dataset['idx'] = wb_dataset['economy'].replace(country_order) + wb_dataset['economy'] + wb_dataset['year']
wb_dataset.sort_values(by=['idx'], inplace=True)
wb_dataset.set_index(['idx'], inplace=True)

# Part 1. Curve fitting.
# Laffer curve shape:
def laffer_curve(x, a, b):
    return a * x **2 + b * x

x = wb_dataset['debt_service'] # Debt, %
y = wb_dataset['gdp_growth'] # GDP, %

# Curve fitting
popt, pcov = curve_fit(laffer_curve, x, y)

xdata = np.linspace(0, 15, 50)
plt.plot(xdata, laffer_curve(xdata, *popt), 'b-',
         label='fit: a=%5.3f, b=%5.3f' % tuple(popt))

plt.show()

f = laffer_curve(x, *popt)
print("Params: ", popt)
print("Condition number of the covariance matrix: ", np.linalg.cond(pcov))
print ("Mean Squared Error: ", mean_squared_error(y, f))
print ("Mean R :",  r2_score(y, f))


# Part 2. ARIMAX modeling and Simulations

# PyFlux ARIMAX
# https://pyflux.readthedocs.io/en/latest/arimax.html

model = pf.ARIMAX(data=wb_dataset, formula='gdp_growth~ 1 + debt_service + cpi + export + reserves',
                  ar=1, ma=1, family=pf.Normal())
x = model.fit("MLE")
x.summary()


# Simulate using average for Kazakhstan
wb_dataset_kz = wb_dataset.reset_index().set_index('economy').filter(like = 'KAZ', axis= 0).mean().to_frame().T
wb_dataset_kz['economy'] = ['KAZ']
wb_dataset_kz['idx'] = ['FUTURE']
wb_dataset_kz.set_index(['idx'], inplace=True)

# 10 years
future = wb_dataset_kz.loc[wb_dataset_kz.index.repeat(10)]

# Optimistic scenario
future['debt_service'] = 6.0

forecast = model.predict(h=10, oos_data=future)
forecast['gdp_growth_accum'] = 1 + forecast['gdp_growth'] / 100
forecast['gdp_growth_accum']= forecast['gdp_growth_accum'].cumprod()

scenarios = pd.DataFrame()
scenarios['optimistic'] = forecast['gdp_growth_accum']
scenarios['year'] = range(len(scenarios))
scenarios['year'] = scenarios['year'] + 2022

# Pessimistic scenario
future['debt_service'] = 10.0

forecast = model.predict(h=10, oos_data=future)
forecast['gdp_growth_accum'] = 1 + forecast['gdp_growth'] / 100
forecast['gdp_growth_accum'] = forecast['gdp_growth_accum'].cumprod()

scenarios['pessimistic'] = forecast['gdp_growth_accum']

scenarios.set_index(['year'], inplace=True)
scenarios.plot.line()
plt.show()