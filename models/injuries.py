import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Position value weights by situation
DEFENSE_WEIGHTS = {
    'SHORT': { # 1-2 yards
        'DT': 0.8, 'NT': 0.8, 'MLB': 0.8, 'ILB': 0.8,
        'EDGE': 0.5, 'OLB': 0.5, 'SS': 0.5, 'FS': 0.4, 'CB': 0.2
    },
    'MEDIUM': { # 3-5 yards
        'MLB': 0.8, 'ILB': 0.8, 'EDGE': 0.7, 'OLB': 0.7,
        'CB': 0.6, 'SS': 0.5, 'FS': 0.5, 'DT': 0.5, 'NT': 0.5
    },
    'LONG': { # 6+ yards
        'CB': 0.9, 'EDGE': 0.8, 'OLB': 0.8, 'FS': 0.7,
        'SS': 0.7, 'MLB': 0.5, 'ILB': 0.5, 'DT': 0.3, 'NT': 0.3
    }
}

OFFENSE_WEIGHTS = {
    'SHORT': {
        'RB': 0.8, 'C': 0.8, 'OG': 0.7, 'FB': 0.6, 'TE': 0.6,
        'OT': 0.5, 'QB': 0.4, 'WR': 0.2
    },
    'MEDIUM': {
        'WR': 0.7, 'TE': 0.7, 'QB': 0.6, 'OT': 0.6,
        'RB': 0.5, 'OG': 0.5, 'C': 0.5
    },
    'LONG': {
        'WR': 0.9, 'QB': 0.8, 'OT': 0.7, 'TE': 0.6,
        'RB': 0.3, 'OG': 0.3, 'C': 0.3
    }
}

# Player quality tiers
TIERS = {
    'STARTER': 1.0,
    'QUALITY_BACKUP': 0.8,
    'DEPTH': 0.6,
    'PRACTICE_SQUAD': 0.4
}

class InjuryTracker:
    def __init__(self):
        self.injuries = {} # {team_code: [injury_dicts]}

    def add_injury(self, team, player_name, position, tier='STARTER', backup_tier='QUALITY_BACKUP'):
        if team not in self.injuries:
            self.injuries[team] = []
        self.injuries[team].append({
            'name': player_name,
            'pos': position,
            'tier': tier,
            'backup_tier': backup_tier
        })

    def get_injuries(self, team):
        return self.injuries.get(team, [])

def get_situation_key(yards_to_go):
    if yards_to_go <= 2: return 'SHORT'
    if yards_to_go <= 5: return 'MEDIUM'
    return 'LONG'

def calculate_injury_modifier(injuries, situation_key, weights_dict):
    total_impact = 0
    ol_backups = 0
    
    for injury in injuries:
        pos = injury['pos']
        # OL positions
        if pos in ['C', 'OG', 'OT']:
            ol_backups += 1
            
        weight = weights_dict.get(situation_key, {}).get(pos, 0.3)
        tier_diff = TIERS[injury['tier']] - TIERS[injury['backup_tier']]
        
        # QB Special Case (only for offense)
        if pos == 'QB' and weights_dict == OFFENSE_WEIGHTS.get(situation_key):
             # STARTER_OUT_QUALITY_BACKUP = -0.20, STARTER_OUT_DEPTH_BACKUP = -0.40
             if injury['backup_tier'] == 'QUALITY_BACKUP':
                 total_impact += 0.20
             else:
                 total_impact += 0.40
        else:
            total_impact += weight * tier_diff * 0.1

    # OL shuffle penalty
    if ol_backups == 2:
        total_impact *= 1.3
    elif ol_backups >= 3:
        total_impact *= 1.6
        
    return total_impact

def calculate_defensive_injury_modifier(injuries, yards_to_go):
    """Positive impact helps offense"""
    situation = get_situation_key(yards_to_go)
    return calculate_injury_modifier(injuries, situation, DEFENSE_WEIGHTS)

def calculate_offensive_injury_modifier(injuries, yards_to_go):
    """Negative impact hurts offense"""
    situation = get_situation_key(yards_to_go)
    return -calculate_injury_modifier(injuries, situation, OFFENSE_WEIGHTS)

def calculate_net_injury_modifier(def_injuries, off_injuries, yards_to_go):
    def_mod = calculate_defensive_injury_modifier(def_injuries, yards_to_go)
    off_mod = calculate_offensive_injury_modifier(off_injuries, yards_to_go)
    return def_mod + off_mod
