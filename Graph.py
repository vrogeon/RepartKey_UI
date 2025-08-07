import pandas as pd
import numpy as np

import matplotlib.pyplot as plt
import plotly.express as px
from math import sqrt

import datetime as dt

def generate_graph(file,
                  sep,
                  group = False,
                  resolution = 'hour'): # Resolution can be 'hour', 'day' or 'month'
    df = pd.read_csv(file, sep=sep)

    # Set Horodate column to current year
    if '.' in  df['Horodate'].iloc[0]:
        df['Horodate'] = pd.to_datetime('2025.' + df['Horodate'], format='%Y.%d.%m. %H:%M')
    elif '/' in  df['Horodate'].iloc[0]:
        df['Horodate'] = pd.to_datetime(df['Horodate'], format='%d/%m/%Y %H:%M')

    # Replace ',' by '.' for all columns except first one which is Horodate
    for col in df.columns[1:]:
        df[col] = df[col].astype(str).str.replace(',','.').astype(float)

    df.drop(['auto_cons_rate'],axis=1, inplace=True)

    # Group by type of consumers
    if group:
        df['Parking_Harmony'] = df['Parking_Harmony1\nauto_cons'] \
                                + df['Parking_Harmony2\nauto_cons']
        df.drop(['Parking_Harmony1\nauto_cons','Parking_Harmony2\nauto_cons'],
                axis=1, inplace=True)

        df['ParvisDuBreuil'] = df['1ParvisDuBreuil\nauto_cons'] \
                                + df['2ParvisDuBreuil\nauto_cons'] \
                                + df['3ParvisDuBreuil\nauto_cons']
        df.drop(['1ParvisDuBreuil\nauto_cons','2ParvisDuBreuil\nauto_cons','3ParvisDuBreuil\nauto_cons'],
                axis=1, inplace=True)

        df['ParvisDeLaBievre'] = df['2ParvisDeLaBievre\nauto_cons'] \
                                + df['3ParvisDeLaBievre\nauto_cons'] \
                                + df['5ParvisDeLaBievre\nauto_cons']
        df.drop(['2ParvisDeLaBievre\nauto_cons','3ParvisDeLaBievre\nauto_cons','5ParvisDeLaBievre\nauto_cons'],
                axis=1, inplace=True)

    # Add last column with contain difference between production and all auto_consumption
    df['_Production restante'] = df.iloc[:,1] - df.iloc[:,2:].sum(axis=1)

    # Add auto_cons value on the same column and add another column for cons id
    list_df = list()
    area = pd.DataFrame()
    for index, col in enumerate(df.columns[2:]):
        list_df.append(pd.DataFrame())

        list_df[index]['Horodate'] = df['Horodate']
        list_df[index]['auto_cons'] = df[col]
        list_df[index]['id_cons'] = df.columns[index+2].replace('\nauto_cons','')
        area = pd.concat([area,list_df[index]])

    # Get day and month values
    area['hour'] = area['Horodate'].dt.hour
    area['day'] = area['Horodate'].dt.day
    area['month'] = area['Horodate'].dt.month

    # Create pivot table to summarize consumption
    if resolution == 'mois':
        piv = pd.pivot_table(area, values='auto_cons', index=['id_cons', 'month'], aggfunc='sum').reset_index()
        piv['month'] = piv['month'].astype(str)
        piv['date'] = pd.to_datetime(piv['month'], format='%m')
    elif resolution == 'jour':
        piv = pd.pivot_table(area, values='auto_cons', index=['id_cons', 'month', 'day'], aggfunc='sum').reset_index()
        piv['month'], piv['day'] = piv['month'].astype(str), piv['day'].astype(str)
        piv['date'] = pd.to_datetime(piv['month'] + '.' + piv['day'], format='%m.%d')
    else:
        piv = pd.pivot_table(area, values='auto_cons', index=['id_cons', 'month', 'day', 'hour'], aggfunc='sum').reset_index()
        piv['month'], piv['day'], piv['hour'] = piv['month'].astype(str), piv['day'].astype(str), piv['hour'].astype(str)
        piv['date'] = pd.to_datetime(piv['month'] + '.' + piv['day'] + '.' + piv['hour'], format='%m.%d.%H')

    fig = px.area(piv,
                  x='date',
                  y='auto_cons',
                  color='id_cons',
                  title='Profil d\'autoconsommation par consommateur cumulé par '+ resolution,
                  labels={'date': 'Date', 'auto_cons': 'Autoconsommation (kWh)'})

    if resolution == 'jour':
        fig.update_xaxes(
            range=['1900-01-01', '1900-12-31'],
            dtick='M1',  # Un trait par mois
            tickformat='%d %B',  # Format d'affichage des dates
            minor=dict(
                dtick='D1',  # Traits mineurs tous les jours
                showgrid=True,  # Afficher le quadrillage mineur
                gridcolor='lightgray',  # Couleur du quadrillage des jours
                gridwidth=0.5,  # Épaisseur des lignes de quadrillage
            )
        )
    else:
        fig.update_xaxes(
            range=['1900-01-01', '1900-12-31'],
            dtick='M1',  # Un trait par mois
            tickformat='%B'  # Format d'affichage des dates
        )

    # Optionnel : personnaliser le quadrillage principal (mois)
    fig.update_xaxes(
        showgrid=True,
        gridcolor='gray',
        gridwidth=1
    )

    # fig.show()

    return fig

