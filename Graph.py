import pandas as pd
import numpy as np
import plotly.express as px
import datetime as dt
import os

def generate_graph(file, sep, group=False, resolution='hour'):
    """
    Génère un graphique à partir d'un fichier CSV
    """
    try:
        print(f"Lecture du fichier: {file}")
        
        # Lire le fichier CSV avec des options de parsing robustes
        df = pd.read_csv(file, sep=sep, quotechar='"', skipinitialspace=True)
        
        # Nettoyer les noms de colonnes (supprimer les \n et espaces)
        df.columns = [col.replace('\n', '').replace('"', '').strip() for col in df.columns]
        
        print(f"Fichier lu avec succès. Colonnes: {df.columns.tolist()}")
        print(f"Nombre de lignes: {len(df)}")
        
        # Vérifier que les colonnes nécessaires existent
        if 'Horodate' not in df.columns:
            raise ValueError("La colonne 'Horodate' est manquante dans le fichier")
            
        # Set Horodate column to current year
        if '.' in str(df['Horodate'].iloc[0]):
            df['Horodate'] = pd.to_datetime('2025.' + df['Horodate'].astype(str), format='%Y.%d.%m. %H:%M')
        elif '/' in str(df['Horodate'].iloc[0]):
            df['Horodate'] = pd.to_datetime(df['Horodate'], format='%d/%m/%Y %H:%M')
        else:
            df['Horodate'] = pd.to_datetime(df['Horodate'], infer_datetime_format=True)
        
        print(f"Dates converties. Plage: {df['Horodate'].min()} à {df['Horodate'].max()}")

        # Convertir toutes les colonnes numériques (remplacer ',' par '.')
        for col in df.columns[1:]:  # Ignorer la colonne Horodate
            if df[col].dtype == 'object':  # Seulement pour les colonnes texte
                # Nettoyer et convertir
                df[col] = df[col].astype(str).str.replace(',', '.').str.replace('"', '')
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                except:
                    print(f"Attention: impossible de convertir la colonne {col} en numérique")

        print(f"Colonnes après nettoyage: {df.columns.tolist()}")

        # Supprimer la colonne auto_cons_rate si elle existe
        auto_cons_rate_cols = [col for col in df.columns if 'auto_cons_rate' in col]
        if auto_cons_rate_cols:
            df.drop(auto_cons_rate_cols, axis=1, inplace=True)
            print(f"Colonnes auto_cons_rate supprimées: {auto_cons_rate_cols}")

        # Identifier les colonnes d'autoconsommation (contiennent 'auto_cons')
        auto_cons_cols = [col for col in df.columns if 'auto_cons' in col and col != 'Horodate']
        
        if not auto_cons_cols:
            raise ValueError("Aucune colonne d'autoconsommation trouvée")
            
        print(f"Colonnes d'autoconsommation trouvées: {auto_cons_cols}")

        # Group by type of consumers si demandé
        if group:
            # Grouper les colonnes Parking_Harmony
            harmony_cols = [col for col in auto_cons_cols if 'Parking_Harmony' in col]
            if len(harmony_cols) >= 2:
                df['Parking_Harmony_total'] = df[harmony_cols].sum(axis=1)
                df.drop(harmony_cols, axis=1, inplace=True)
                auto_cons_cols = [col for col in df.columns if 'auto_cons' in col and col != 'Horodate']
                print(f"Colonnes groupées. Nouvelles colonnes: {auto_cons_cols}")

        # Identifier la colonne de production (probablement la première après Horodate)
        prod_col = None
        for col in df.columns[1:]:
            if col not in auto_cons_cols:
                prod_col = col
                break
                
        if prod_col:
            print(f"Colonne de production identifiée: {prod_col}")
            # Calculer la production restante
            df['Production_restante'] = df[prod_col] - df[auto_cons_cols].sum(axis=1)
            auto_cons_cols.append('Production_restante')

        # Préparer les données pour le graphique en aires empilées
        area_data = []
        
        for col in auto_cons_cols:
            for idx, row in df.iterrows():
                area_data.append({
                    'Horodate': row['Horodate'],
                    'auto_cons': row[col],
                    'id_cons': col.replace('auto_cons', '').replace('_', ' ').strip()
                })

        area = pd.DataFrame(area_data)
        
        if area.empty:
            raise ValueError("Aucune donnée d'autoconsommation trouvée après transformation")

        print(f"Données transformées: {len(area)} lignes, consommateurs: {area['id_cons'].unique()}")

        # Ajouter les colonnes de temps
        area['hour'] = area['Horodate'].dt.hour
        area['day'] = area['Horodate'].dt.day
        area['month'] = area['Horodate'].dt.month
        area['year'] = area['Horodate'].dt.year

        # Créer le tableau pivot selon la résolution
        if resolution == 'mois':
            piv = pd.pivot_table(area, values='auto_cons', index=['id_cons', 'year', 'month'], aggfunc='sum').reset_index()
            piv['date'] = pd.to_datetime(piv[['year', 'month']].assign(day=1))
        elif resolution == 'jour':
            piv = pd.pivot_table(area, values='auto_cons', index=['id_cons', 'year', 'month', 'day'], aggfunc='sum').reset_index()
            piv['date'] = pd.to_datetime(piv[['year', 'month', 'day']])
        else:  # hour
            piv = pd.pivot_table(area, values='auto_cons', index=['id_cons', 'year', 'month', 'day', 'hour'], aggfunc='sum').reset_index()
            piv['date'] = pd.to_datetime(piv[['year', 'month', 'day', 'hour']])

        print(f"Données pivotées: {len(piv)} lignes")

        # Créer le graphique
        fig = px.area(piv,
                      x='date',
                      y='auto_cons',
                      color='id_cons',
                      title=f'Autoconsommation par consommateur - {resolution}',
                      labels={'date': 'Date', 'auto_cons': 'Autoconsommation (kWh)', 'id_cons': 'Consommateur'})

        # Configuration de l'axe des X
        if resolution == 'jour':
            fig.update_xaxes(
                dtick='M1',
                tickformat='%B',
                showgrid=True,
                gridcolor='lightgray'
            )
        else:
            fig.update_xaxes(
                showgrid=True,
                gridcolor='gray',
                gridwidth=1
            )

        print("Graphique généré avec succès")
        return fig

    except Exception as e:
        print(f"Erreur dans generate_graph: {str(e)}")
        import traceback
        traceback.print_exc()
        raise