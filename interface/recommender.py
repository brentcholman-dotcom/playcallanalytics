import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RecommendationEngine:
    def __init__(self, conversion_model, live_feed=None, weather_tracker=None, 
                 injury_tracker=None, noise_tracker=None):
        self.model = conversion_model
        self.live_feed = live_feed
        self.weather_tracker = weather_tracker
        self.injury_tracker = injury_tracker
        self.noise_tracker = noise_tracker

    def get_recommendation(self, situation=None):
        """
        Calculates recommendations for 4th down.
        """
        if situation is None and self.live_feed:
            situation = self.live_feed.get_current_situation()
        
        if not situation:
            return None
            
        # Get current context from trackers
        weather = self.weather_tracker.get_stadium_weather(situation.get('defteam')) if self.weather_tracker else None
        injuries = {
            'offense': self.injury_tracker.get_current_injuries(situation.get('posteam')) if self.injury_tracker else [],
            'defense': self.injury_tracker.get_current_injuries(situation.get('defteam')) if self.injury_tracker else []
        }
        crowd_db = self.noise_tracker.get_current_estimate(situation) if self.noise_tracker else None
        
        # Calculate conversion probability
        pred = self.model.calculate_conversion_probability(situation, injuries=injuries, weather=weather, crowd_db=crowd_db)
        
        # Build recommendation object
        # Note: WP calculations would normally require a separate WP model (like nflfastR's)
        # For MVP we'll stub those or use simple heuristics
        
        go_prob = pred['final_probability']
        
        rec = {
            'situation': situation,
            'options': {
                'go_for_it': {
                    'conversion_prob': go_prob,
                    'recommendation_strength': 'strong' if go_prob > 0.6 else 'neutral'
                },
                'punt': {
                    'expected_wp': 0.50 # stub
                },
                'field_goal': {
                    'in_range': situation.get('yardline_100', 100) <= 35,
                    'make_prob': 0.80 # stub
                }
            },
            'recommendation': 'go_for_it' if go_prob > 0.52 else 'punt',
            'key_factors': [
                {'factor': 'momentum', 'impact': f"{pred['momentum_modifier']:.1%}"},
                {'factor': 'crowd_noise', 'impact': f"{pred['crowd_modifier']:.1%}"},
                {'factor': 'injuries', 'impact': f"{pred['injury_modifier']:.1%}"}
            ]
        }
        return rec
