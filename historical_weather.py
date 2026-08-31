import time
import requests
import numpy as np
import pandas as pd
from pathlib import Path


def gms_to_degree(degree, minutes, seconds, direction):
    '''
    Umrechung von 51°58'38.93"N zu Dezimalgrad für Longitude (Längengrad) und Latidude (Breitengrad)
    '''
    dd = float(degree) + float(minutes) / 60 + float(seconds) / 3600
    if direction in ['S', 'W']:
        dd *= -1
    return dd

class Weather:
    def __init__(self, API_KEY, lat, lon, unit):
        self.lat = lat
        self.lon = lon
        self.unit = unit
        self.API_KEY = API_KEY

    def weather_request(self, lat, lon, unit, dt, API_KEY):
        url_history = (
            'https://api.openweathermap.org/data/3.0/onecall/timemachine'
            f'?lat={lat}&lon={lon}&dt={dt}&appid={API_KEY}&units={unit}'
        )
        response = requests.get(url_history)
        payload = response.json()

        return payload

    def weather_api(self, df, max_requests, sensor_point, agg, save_dir):
        # Letzte N_SENSOR_POINTS Sensor-Zeitstempel zu Stundenblöcken zusammenfassen (Mittelwert je Block)
        last_points = df[['temperature', 'humidity', 'pressure']].iloc[-sensor_point:].copy()
        last_points['block'] = np.arange(len(last_points)) // agg

        hourly_sensor = last_points.groupby('block')[['temperature', 'humidity', 'pressure']].mean()
        block_start = last_points.index[np.arange(0, len(last_points), agg)]
        hourly_sensor.index = pd.DatetimeIndex(block_start).round('h')

        print(f'{len(last_points)} Sensor-Zeitstempel zu {len(hourly_sensor)} Stundenblöcken zusammengefasst '
              f'(1 API-Anfrage pro Block)')

        records = []
        for n_requests, ts in enumerate(hourly_sensor.index, start=1):
            if n_requests > max_requests:  # Notbremse
                break

            dt = int(ts.timestamp())
            payload = self.weather_request(self.lat, self.lon, self.unit, dt, self.API_KEY)

            if not payload.get('data'):
                print(f'Keine historischen Daten für {ts}: {payload}')
                continue

            api_point = payload['data'][0]
            sensor_row = hourly_sensor.loc[ts]

            records.append({
                'datetime': ts,
                'sensor_temp': sensor_row['temperature'],
                'api_temp': api_point.get('temp'),
                'sensor_humidity': sensor_row['humidity'],
                'api_humidity': api_point.get('humidity'),
                'sensor_pressure': sensor_row['pressure'],
                'api_pressure': api_point.get('pressure'),
            })

            time.sleep(1)  # Anfragen zeitlich entzerren

        print(f'{n_requests} Anfragen gestellt, {len(records)} davon erfolgreich '
              f'(max. {max_requests} erlaubt)')

        weather_df = pd.DataFrame(records).set_index('datetime')

        weather_df.to_csv(save_dir / 'weather_compare.csv', encoding='utf-8', sep=';')

        return weather_df

path = Path(__file__).resolve().parent
data = path / 'Daten' / 'data_aug.csv'
data_aug = pd.read_csv(data, sep=';', encoding='utf-8')
data_aug['datetime'] = pd.to_datetime(data_aug['datetime'])
data_aug = data_aug.set_index('datetime')

N_SENSOR_POINTS = 500  # letzte N Sensor-Zeitstempel (15-min-Takt)
AGG_SIZE = 4            # 4 x 15 min = 1 Stunde, passend zur stündlichen Auflösung der History-API
MAX_REQUESTS = 150      # Sicherheitsgrenze für die Anfrageschleife

lat_gms = (51, 58, 38.93, 'N') # Breitengrad als Gradminuten
lon_gms = (7, 33, 53.08, 'E') # Längengrad als Gradminuten

# Umrechung in Dezimalgrad
lat = gms_to_degree(*lat_gms)
lon = gms_to_degree(*lon_gms)

assert N_SENSOR_POINTS % AGG_SIZE == 0, 'N_SENSOR_POINTS muss ein Vielfaches von AGG_SIZE sein'

compare = Weather(API_KEY = 'Hier API KEY eingeben',
                     lat=lat,
                     lon=lon,
                     unit='metric')

compare = compare.weather_api(data_aug, max_requests=MAX_REQUESTS, sensor_point=N_SENSOR_POINTS, agg=AGG_SIZE, save_dir=path / 'Daten')




