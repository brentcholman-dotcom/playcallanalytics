import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

STADIUM_COORDS = {
    'KC': (39.0489, -94.4839),
    'SEA': (47.5952, -122.3316),
    'NO': (29.9511, -90.0812),
    'PHI': (39.9008, -75.1675),
    'BAL': (39.2780, -76.6227),
    'GB': (44.5013, -88.0622),
    'BUF': (42.7738, -78.7870),
    'CIN': (39.0955, -84.5161),
    'DEN': (39.7439, -105.0201),
    'MIN': (44.9735, -93.2575),
    # ... other stadiums would be added here
}

class WeatherTracker:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('OPENWEATHER_API_KEY')
        self.cache = {}
        self.last_update = 0

    def get_current_weather(self, lat, lon):
        if not self.api_key:
            return None
            
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={self.api_key}&units=imperial"
        try:
            response = requests.get(url)
            data = response.json()
            return {
                'temp': data['main']['temp'],
                'wind_speed': data['wind']['speed'],
                'wind_direction': data['wind'].get('deg'),
                'precipitation': data.get('weather', [{}])[0].get('main', 'None')
            }
        except Exception:
            return None

    def get_stadium_weather(self, team_code):
        coords = STADIUM_COORDS.get(team_code)
        if not coords:
            return None
        
        # Cache for 5 minutes
        if team_code in self.cache and (time.time() - self.last_update) < 300:
            return self.cache[team_code]
            
        weather = self.get_current_weather(*coords)
        if weather:
            self.cache[team_code] = weather
            self.last_update = time.time()
        return weather
