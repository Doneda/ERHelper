from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
from anthropic import Anthropic
from dotenv import load_dotenv
import os
import warnings
import pickle
from pathlib import Path

# Load environment variables
load_dotenv()

# Suppress warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)
CORS(app)

# Initialize Claude
anthropic_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')

# Global data storage
elden_data = {}
ai_cache = {}

# Cache settings
CACHE_DIR = Path('../data')  # Go up one level from backend/
CACHE_FILE = CACHE_DIR / 'elden_cache.pkl'
DATA_FILE = CACHE_DIR / 'elden_ring_data.xlsx'
AI_CACHE_FILE = CACHE_DIR / 'ai_cache.pkl'

def load_elden_ring_data(force_reload=False):
    """Load all NG tabs from Excel file with caching support"""
    global elden_data
    
    # Create data directory if it doesn't exist
    CACHE_DIR.mkdir(exist_ok=True)
    
    # Try to load from cache first (only if not forcing reload)
    if not force_reload and CACHE_FILE.exists():
        try:
            print("📦 Loading from cache...")
            with open(CACHE_FILE, 'rb') as f:
                elden_data = pickle.load(f)
            print(f"✅ Loaded {sum(len(df) for df in elden_data.values())} enemies from cache")
            return  # Exit early if cache loaded successfully
        except Exception as e:
            print(f"⚠️  Cache load failed: {e}")
            print("📚 Falling back to Excel...")
    
    print("📚 Loading Elden Ring data from Excel...")
    
    # Check if data file exists
    if not DATA_FILE.exists():
        print(f"❌ ERROR: {DATA_FILE} not found!")
        print(f"   Current directory: {Path.cwd()}")
        print(f"   Looking for: {DATA_FILE.absolute()}")
        return
    
    ng_levels = ['NG', 'NG+', 'NG+2', 'NG+3', 'NG+4', 'NG+5', 'NG+6', 'NG+7']
    
    for ng in ng_levels:
        try:
            df = None
            # Try header rows 0,1,2 to handle files where column names start on row 2
            for header_row in (1, 0, 2):  # Try 1 first (most common)
                try:
                    tmp = pd.read_excel(DATA_FILE, sheet_name=ng, header=header_row, dtype=object)
                    tmp.columns = [str(c).strip() for c in tmp.columns]
                    if 'Name' in tmp.columns:
                        df = tmp
                        if header_row != 0:
                            print(f"   {ng}: Using header row {header_row}")
                        break
                except Exception:
                    continue
            
            if df is None:
                print(f"❌ Could not find 'Name' column in {ng}")
                continue
            
            # Drop rows without a name or placeholder rows
            df = df[df['Name'].notna()]
            df = df[df['Name'] != '???']
            
            # Robust HP handling - only use dlcClear if it's a valid number
            df['HP'] = df.apply(lambda row: (
                pd.to_numeric(row.get('dlcClear'), errors='coerce') 
                if pd.notna(row.get('dlcClear')) and row.get('dlcClear') != '-' 
                else pd.to_numeric(row.get('Health'), errors='coerce')
            ), axis=1)
            
            # Fill remaining NaN with 0
            df['HP'] = df['HP'].fillna(0)
            
            # Coerce numeric columns - including both Defense and Damage Negation
            numeric_cols = [
                # Defense columns (H-O) - keep for backend
                'Phys','Strike','Slash','Pierce','Magic','Fire','Ltng','Holy',
                # Damage Negation columns (Q-X) - pandas might add .1 suffix
                'Phys.1','Strike.1','Slash.1','Pierce.1','Magic.1','Fire.1','Ltng.1','Holy.1',
                # Poise
                'Base','Effective','Regen Delay',
                # Status multipliers
                'Bleed.1','Frost.1','HP Burn Effect'
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Ensure ID exists
            if 'ID' not in df.columns:
                df['ID'] = range(1, len(df) + 1)
            
            elden_data[ng] = df
            print(f"✅ {ng}: {len(df)} enemies")
            
        except Exception as e:
            print(f"❌ Error loading {ng}: {e}")
    
    # Save to cache
    if elden_data:
        try:
            print("💾 Saving to cache...")
            with open(CACHE_FILE, 'wb') as f:
                pickle.dump(elden_data, f)
            print(f"✅ Cache saved")
        except Exception as e:
            print(f"⚠️  Could not save cache: {e}")
    
    print(f"🎮 Total: {sum(len(df) for df in elden_data.values())} enemies")

def load_ai_cache():
    """Load AI analysis cache from disk"""
    if AI_CACHE_FILE.exists():
        try:
            with open(AI_CACHE_FILE, 'rb') as f:
                cache = pickle.load(f)
                print(f"🤖 Loaded {len(cache)} cached AI analyses")
                return cache
        except Exception as e:
            print(f"⚠️  AI cache load failed: {e}")
    return {}

def save_ai_cache(cache):
    """Save AI analysis cache to disk"""
    try:
        with open(AI_CACHE_FILE, 'wb') as f:
            pickle.dump(cache, f)
        print(f"💾 AI cache saved ({len(cache)} entries)")
    except Exception as e:
        print(f"⚠️  Could not save AI cache: {e}")

def search_enemies(query, ng_level='NG'):
    """Search for enemies by name - returns ALL instances with their locations and HP"""
    if ng_level not in elden_data:
        return []
    
    df = elden_data[ng_level]
    
    # Case-insensitive search
    mask = df['Name'].str.contains(query, case=False, na=False)
    results = df[mask]
    
    # Return ALL matching enemies with their unique stats
    enemies = []
    for _, row in results.iterrows():
        enemies.append({
            'name': row['Name'],
            'location': row['Location'],
            'hp': int(row['HP']) if pd.notna(row['HP']) and row['HP'] > 0 else 0,
            'id': row['ID']
        })
    
    return enemies

def get_enemy_details(enemy_name, location=None, ng_level='NG'):
    """Get full details for a specific enemy, optionally filtered by location"""
    if ng_level not in elden_data:
        return None
    
    df = elden_data[ng_level]
    
    # Find matches by name
    matches = df[df['Name'] == enemy_name]
    
    # If location specified, filter by location too
    if location and len(matches) > 0:
        location_matches = matches[matches['Location'] == location]
        if len(location_matches) > 0:
            matches = location_matches
    
    if len(matches) == 0:
        return None
    
    # Take first match (or the location-specific one)
    enemy = matches.iloc[0]
    
    # Safe numeric extraction with defaults
    def safe_int(value, default=0):
        try:
            if pd.isna(value) or value == '-':
                return default
            return int(float(value))
        except:
            return default
    
    def safe_float(value, default=0.0):
        try:
            if pd.isna(value) or value == '-':
                return default
            return float(value)
        except:
            return default
    
    # Extract relevant data
    details = {
        'name': enemy['Name'],
        'location': enemy.get('Location', 'Unknown'),
        'hp': safe_int(enemy['HP']),
        'damage_negation': {
            # These are the actual damage negation % columns (Q-X in your sheet)
            'physical': safe_float(enemy.get('Phys.1', 0)),      # Column Q
            'strike': safe_float(enemy.get('Strike.1', 0)),      # Column R
            'slash': safe_float(enemy.get('Slash.1', 0)),        # Column S
            'pierce': safe_float(enemy.get('Pierce.1', 0)),      # Column T
            'magic': safe_float(enemy.get('Magic.1', 0)),        # Column U
            'fire': safe_float(enemy.get('Fire.1', 0)),          # Column V
            'lightning': safe_float(enemy.get('Ltng.1', 0)),     # Column W
            'holy': safe_float(enemy.get('Holy.1', 0))           # Column X
        },
        'resistances': {
            'poison': _format_resistance(enemy.get('Poison', 999999)),
            'scarlet_rot': _format_resistance(enemy.get('Scarlet Rot', 999999)),
            'bleed': _format_resistance(enemy.get('Bleed', 999999)),
            'frost': _format_resistance(enemy.get('Frost', 999999)),
            'sleep': _format_resistance(enemy.get('Sleep', 999999)),
            'madness': _format_resistance(enemy.get('Madness', 999999)),
            'deathblight': _format_resistance(enemy.get('Deathblight', 999999))
        },
        'poise': {
            'base': safe_int(enemy.get('Base', 0)),
            'effective': _parse_poise(enemy.get('Effective', 0)),
            'regen_delay': safe_float(enemy.get('Regen Delay', 0))
        },
        'status_multipliers': {
            'bleed': safe_float(enemy.get('Bleed.1', 1)),
            'frost': safe_float(enemy.get('Frost.1', 1)),
            'black_flame': safe_float(enemy.get('HP Burn Effect', 1))
        },
        'has_weak_spots': bool(safe_int(enemy.get('Weak Part', 0))),
        'all_instances': []  # Will add info about other instances
    }
    
    # Add info about all instances of this enemy
    all_enemy_instances = df[df['Name'] == enemy_name]
    for _, instance in all_enemy_instances.iterrows():
        details['all_instances'].append({
            'location': instance.get('Location', 'Unknown'),
            'hp': safe_int(instance['HP'])
        })
    
    return details

def _format_resistance(value):
    """Format resistance value (handle 'Immune')"""
    if pd.isna(value):
        return 999999
    if str(value).lower() == 'immune':
        return 'Immune'
    try:
        return int(value)
    except:
        return 999999

def _parse_poise(value):
    """Parse effective poise (handle ∞)"""
    if pd.isna(value):
        return 0
    if str(value) == '∞' or str(value).lower() == 'inf':
        return 999999
    try:
        return int(float(value))
    except:
        return 0

def search_by_region(region, ng_level='NG'):
    """Get all enemies in a region"""
    if ng_level not in elden_data:
        return []
    
    df = elden_data[ng_level]
    
    # Case-insensitive region search
    mask = df['Location'].str.contains(region, case=False, na=False)
    results = df[mask]
    
    enemies = []
    for _, row in results.iterrows():
        enemies.append({
            'name': row['Name'],
            'location': row['Location']
        })
    
    return enemies

def calculate_region_average(region, ng_level='NG'):
    """Calculate average stats for all enemies in a region (immune ignored)"""
    if ng_level not in elden_data:
        return None

    df = elden_data[ng_level]

    # Filter by region
    mask = df['Location'].str.contains(region, case=False, na=False)
    region_df = df[mask]

    if len(region_df) == 0:
        return None

    # Helper: safely average only numeric resistances (ignore immune/NaN)
    def avg_resistance(column_name):
        values = []
        for val in region_df[column_name]:
            if pd.isna(val) or str(val).strip().lower() == 'immune':
                continue
            try:
                values.append(float(val))
            except:
                continue
        return int(np.mean(values)) if values else None

    # Helper: safely average numeric columns
    def safe_avg(col_name):
        if col_name in region_df.columns:
            numeric_vals = pd.to_numeric(region_df[col_name], errors='coerce')
            numeric_vals = numeric_vals.dropna()
            return round(numeric_vals.mean(), 1) if len(numeric_vals) > 0 else 0
        return 0

    # Calculate averages
    avg_stats = {
        'region': region,
        'enemy_count': len(region_df),
        'avg_hp': int(region_df['HP'].mean()) if region_df['HP'].notna().any() else 0,

        'avg_damage_negation': {
            k: safe_avg(col)
            for k, col in {
                'physical': 'Phys.1', 'strike': 'Strike.1', 'slash': 'Slash.1', 'pierce': 'Pierce.1',
                'magic': 'Magic.1', 'fire': 'Fire.1', 'lightning': 'Ltng.1', 'holy': 'Holy.1'
            }.items()
        },

        'avg_resistances': {
            k: avg_resistance(col)
            for k, col in {
                'poison': 'Poison', 'scarlet_rot': 'Scarlet Rot', 'bleed': 'Bleed',
                'frost': 'Frost', 'sleep': 'Sleep', 'madness': 'Madness', 'deathblight': 'Deathblight'
            }.items()
        },

        'avg_poise': {
            'base': safe_avg('Base'),
            'effective': safe_avg('Effective'),
            'regen_delay': safe_avg('Regen Delay')
        },

        # Include status multipliers (optional but useful)
        'avg_status_multipliers': {
            'bleed': safe_avg('Bleed.1'),
            'frost': safe_avg('Frost.1'),
            'black_flame': safe_avg('HP Burn Effect')
        }
    }

    return avg_stats

# Game-specific knowledge base (you can customize this)
GAME_KNOWLEDGE = """
Game Mechanics Context:
- Damage Negation: Negative values = weakness (takes MORE damage), Positive = resistance (takes LESS damage)
- Status Resistance: Lower values = easier to proc status, Higher = harder, "Immune" = cannot be affected
- Poise: Damage must exceed poise to break enemy's posture and give opportunity for high DPS window
- Poise Values: < 40 = Very low poise; < 60 = Low poise, easy to stagger; 60-70 = Medium poise; 80-90 = High poise; > 100 = Very high poise, hard to stagger
- Weak Spots: Some enemies have parts that take extra damage (indicated by has_weak_spots flag),

Status Effect Viability:
- Bleed: Effective if resistance < 400; very effective if resistance < 300; Not so reliable if resistance > 600
- Poison: Effective if resistance < 400; very effective if resistance < 300; Not so reliable if resistance > 600
- Frost: Effective if resistance < 400; very effective if resistance < 300; Not so reliable if resistance > 600
- Sleep: Very effective if resistance < 200; Not reliable if resistance > 250
- Scarlet Rot: Effective if resistance < 300; very effective if resistance < 200; Not so reliable if resistance > 500
- Madness: Does not work on PvE enemies
- Deathblight: Does not work on PvE enemies

Combat Tips:
- Fire is less effective in rain/water areas, those include Liurnia of the Lakes, Agheel's Lake, etc.
- Lightning more effective in rain/water areas, those include Liurnia of the Lakes, Agheel's Lake, etc.
- Strike damage good against armored enemies, specially effective against Cristallians.
- Slash good against unarmored/flesh enemies, and any "beast" type enemies.
- Pierce good against Dragons and large enemies, specially those in heavy armor.

Special knowladge:
- "Mechanical" type enemies are only: Golem, Imps (all variants), Burial Watchdog (both).
- "Mechanical" type enemies are EXTREMELY vulnerable to the item "Crystal dart", which makes them go mad and attack allies.
- The "Abductor Virgin" enemy has a different poise mechanic, it's staggered by number of hits rather than poise damage.
- The "Abductor Virgin" enemy is poise-broken after 25 hits, (lightning damage counts as 5 hits).
- Both versions of the "Fallinsgstar Beast" can be stunned instantly if hit in the head while it's charging in the player's direction.
- "Night's Cavalry" enemy variant with Halberd weapon can be parried, falling from his horse.
- The boss "Maliketh, the Black Blade" can be parried with the item "Blasphemous Claw" when his sword glows white.
- Malenia can be thrown out of waterflowl dance if hitted by a Frost pot (only effective in normal NG).
- Despite Dragons having high poise, they take double poise damage in the head, making it's effective poise much lower when aiming for the head.
- The Ancient Dragons have praticaly infinite poise, tell the player "I dare you to try to poise-break one of those".
- The "Frostbite" status effect reduce enemies' damage negation against all damage types by 20% while active.
- The spell "Ranni's Dark Moon" reduces target's magic damage negation by 10%, and it's multiplicative with frostbite.
- Oil pots increase enemies' fire damage negation by 50%, for the next fire damage instance.
- Lightning-damage projectiles spread in water, dealing more damage in area.
- If an enemy has low poison resistance, recommend the player to use "Poisoned stone clump" item, sold by "Nomadic Merchant Caelid Highway North".
- The "land squirt" enemy gets instantly killed if poisoned, exploding and poisoning nearby enemies.
- Once poise-broken, Cristallians become extremely easy to stagger.
- Trolls get staggered if hit in the head with any type of damage.
- Margit the Fell Omen, and Morgott the Omen King are staggered by the item "Margit's Shackle".
- Mohg, Lord of Blood is staggered by the item "Mohg's Shackle".
- Always recommend players to use "Purifying Crystal Tear" when fighting "Mohg, Lord of Blood", as it's almost mandatory.
- All enemies with "dog" in their name get scared by the "beast-repellent torch" item.
- When fighting "Skeleton" type enemies, recommend using "Holy water pot" item, as it makes them not revive upon death.
- The dragon "Decaying Ekzykes" is the only dragon in the game weak to fire damage.
- When facing "Commander Niall" and "Commander O'Neil", recommend using the item "Bewitching Branch" to turn their allies against them.
- Some enemies take extreme extra damage from backstabs, those include: Vulgar Militia, and Albinauric archers.
- The enemies "Giant Miranda Sprout" and "Large Fingercreeper" get stunned if hit with fire damage.
- When fighting "Dragon" type enemies, recommend using the "Anti-Dragon grease" or "Dragon Communion grease" items.
- The enemy "Revenant" takes HUGE damage when near Healing spells.
- Scarlet Rot does extreme damage over time, recommend using it when the resistance is lower than 300.
- Heavy charged attacks always deal more poise damage than jump attacks.
- "Guard-counters" tend to do even more poise damage than charged heavy attacks.
"""

def analyze_with_ai(enemy_data, context="enemy"):
    """Use Claude AI to generate strategy recommendations with caching"""
    
    # Create cache key - USE NAME ONLY for enemies (stats are identical, only HP differs)
    if context == "enemy":
        cache_key = f"enemy_{enemy_data['name']}_{enemy_data['location']}"
    else:  # region
        cache_key = f"region_{enemy_data['region']}"
    
    # Check cache first
    if cache_key in ai_cache:
        print(f"✅ Using cached AI analysis for: {cache_key}")
        return ai_cache[cache_key]
    
    print(f"Generating NEW AI analysis for: {cache_key}")
    
    # If not in cache, generate new analysis
    try:
        if context == "enemy":
            prompt = f"""You are an expert Elden Ring strategy guide. Analyze this enemy and provide tactical combat advice.

{GAME_KNOWLEDGE}

Enemy: {enemy_data['name']}
HP: {enemy_data['hp']:,}
Location: {enemy_data['location']}

Damage Negation (LOWER is better for player, NEGATIVE means weakness):
- Physical: {enemy_data['damage_negation']['physical']}%
- Strike: {enemy_data['damage_negation']['strike']}%
- Slash: {enemy_data['damage_negation']['slash']}%
- Pierce: {enemy_data['damage_negation']['pierce']}%
- Magic: {enemy_data['damage_negation']['magic']}%
- Fire: {enemy_data['damage_negation']['fire']}%
- Lightning: {enemy_data['damage_negation']['lightning']}%
- Holy: {enemy_data['damage_negation']['holy']}%

Status Resistances (LOWER is better for player):
- Poison: {enemy_data['resistances']['poison']}
- Bleed: {enemy_data['resistances']['bleed']}
- Frost: {enemy_data['resistances']['frost']}
- Sleep: {enemy_data['resistances']['sleep']}

Poise: {enemy_data['poise']['base']} (higher = harder to stagger)
Has Weak Spots: {enemy_data['has_weak_spots']}

Provide:
1. **Best Damage Types:** List top 2-3 damage types (lowest/most negative negation values)
2. **Viable Status Effects:** Only list if resistance is actually low enough to be practical
3. **Combat Strategy:** Brief tactical tips (2-3 sentences)

Keep response under 150 words, focused and actionable."""

        else:  # region
            prompt = f"""Analyze this Elden Ring region and provide general strategy:

Region: {enemy_data['region']}
Enemy Count: {enemy_data['enemy_count']}
Average HP: {enemy_data['avg_hp']:,}

Average Damage Negation:
- Physical: {enemy_data['avg_damage_negation']['physical']}%
- Strike: {enemy_data['avg_damage_negation']['strike']}%
- Slash: {enemy_data['avg_damage_negation']['slash']}%
- Pierce: {enemy_data['avg_damage_negation']['pierce']}%
- Magic: {enemy_data['avg_damage_negation']['magic']}%
- Fire: {enemy_data['avg_damage_negation']['fire']}%
- Lightning: {enemy_data['avg_damage_negation']['lightning']}%
- Holy: {enemy_data['avg_damage_negation']['holy']}%

Provide:
1. Best general damage types for this region
2. General combat approach
3. Any notable patterns

Keep it brief (3-4 sentences)."""

        message = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        
        # Save to cache
        ai_cache[cache_key] = response_text
        save_ai_cache(ai_cache)
        
        return response_text
        
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return "Strategy analysis unavailable. Check enemy weaknesses in the stats."

@app.route('/api/debug/columns', methods=['GET'])
def debug_columns():
    """Debug endpoint to see all column names"""
    ng_level = request.args.get('ng', 'NG')
    ng_level = ng_level.replace(' ', '+')
    if ng_level not in elden_data:
        return jsonify({'error': 'NG level not found'}), 404
    
    df = elden_data[ng_level]
    return jsonify({
        'ng_level': ng_level,
        'columns': list(df.columns),
        'total_columns': len(df.columns),
        'sample_row': df.iloc[0].to_dict() if len(df) > 0 else {}
    })

@app.route('/')
def index():
    """Simple landing page with API info"""
    status = "✅ Loaded" if elden_data else "❌ Not loaded"
    enemy_count = sum(len(df) for df in elden_data.values()) if elden_data else 0
    
    return f"""
    <html>
    <head>
        <title>Elden Ring Helper API</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #1a1a1a; color: #fff; }}
            h1 {{ color: #ffd700; }}
            .status {{ padding: 10px; background: #2a2a2a; border-radius: 5px; margin: 20px 0; }}
            a {{ color: #4a9eff; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            code {{ background: #333; padding: 2px 6px; border-radius: 3px; color: #0f0; }}
        </style>
    </head>
    <body>
        <h1>🎮 Elden Ring Helper API</h1>
        <div class="status">
            <strong>Status:</strong> {status}<br>
            <strong>Enemies:</strong> {enemy_count:,}<br>
            <strong>NG Levels:</strong> {len(elden_data)}
        </div>
        
        <h2>📡 Endpoints:</h2>
        <ul>
            <li><a href="/api/health">/api/health</a></li>
            <li><a href="/api/search?q=bear&ng=NG">/api/search?q=bear&ng=NG</a></li>
            <li><a href="/api/enemy/Runebear?ng=NG">/api/enemy/Runebear?ng=NG</a></li>
            <li><a href="/api/debug/columns?ng=NG">/api/debug/columns?ng=NG</a> (debug)</li>
        </ul>
        
        <h2>🧪 Test:</h2>
        <form action="/api/search" method="get" style="margin: 20px 0;">
            <input type="text" name="q" placeholder="Search..." value="bear" 
                   style="padding: 8px; background: #333; border: 1px solid #555; color: #fff; width: 200px;">
            <input type="hidden" name="ng" value="NG">
            <button type="submit" style="padding: 8px 16px; background: #4a9eff; border: none; color: #fff; cursor: pointer;">Search</button>
        </form>
        
        <p><small>Cache: {'✅' if CACHE_FILE.exists() else '❌'} | 
        Columns loaded: {len(elden_data['NG'].columns) if 'NG' in elden_data else 0}</small></p>
    </body>
    </html>
    """, 200

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/api/reload', methods=['POST'])
def reload_data():
    """Force reload data from Excel (bypass cache)"""
    load_elden_ring_data(force_reload=True)
    return jsonify({
        'status': 'reloaded',
        'enemies_loaded': sum(len(df) for df in elden_data.values()),
        'ng_levels': list(elden_data.keys())
    })
@app.route('/api/enemy/<path:enemy_name>', methods=['GET'])
def api_get_enemy(enemy_name):
    """Get full enemy details with AI analysis"""
    ng_level = request.args.get('ng', 'NG')
    ng_level = ng_level.replace(' ', '+')
    location = request.args.get('location', None)  # Optional location filter
    
    details = get_enemy_details(enemy_name, location, ng_level)
    
    if not details:
        return jsonify({'error': 'Enemy not found'}), 404
    
    # Generate AI strategy
    strategy = analyze_with_ai(details, context="enemy")
    details['ai_strategy'] = strategy
    
    return jsonify(details)

@app.route('/api/region/<region_name>', methods=['GET'])
def api_get_region(region_name):
    """Get region average stats with AI analysis"""
    ng_level = request.args.get('ng', 'NG')
    ng_level = ng_level.replace(' ', '+')
    
    avg_stats = calculate_region_average(region_name, ng_level)
    
    if not avg_stats:
        return jsonify({'error': 'Region not found'}), 404
    
    # Generate AI strategy
    strategy = analyze_with_ai(avg_stats, context="region")
    avg_stats['ai_strategy'] = strategy
    
    return jsonify(avg_stats)

@app.route('/api/region/<region_name>/enemies', methods=['GET'])
def api_get_region_enemies(region_name):
    """Get list of all enemies in a region"""
    ng_level = request.args.get('ng', 'NG')
    ng_level = ng_level.replace(' ', '+')
    
    enemies = search_by_region(region_name, ng_level)
    
    return jsonify({
        'region': region_name,
        'ng_level': ng_level,
        'count': len(enemies),
        'enemies': enemies
    })

@app.route('/api/search', methods=['GET'])
def api_search():
    """Search for enemies by name"""
    query = request.args.get('q', '')
    ng_level = request.args.get('ng', 'NG')
    ng_level = ng_level.replace(' ', '+')
    
    # Debug: print what we're receiving
    print(f"🔍 Search request: query='{query}', ng='{ng_level}'")
    
    if not query:
        return jsonify({'results': []})
    
    # Verify NG level exists
    if ng_level not in elden_data:
        print(f"⚠️  NG level '{ng_level}' not found in data. Available: {list(elden_data.keys())}")
        return jsonify({'results': []})
    
    results = search_enemies(query, ng_level)
    
    return jsonify({
        'query': query,
        'ng_level': ng_level,
        'results': results
    })

@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'data_loaded': len(elden_data) > 0,
        'ng_levels': list(elden_data.keys()),
        'total_enemies': sum(len(df) for df in elden_data.values())
    })

@app.route('/api/cache/stats', methods=['GET'])
def cache_stats():
    """Get AI cache statistics (unique enemy-based)"""
    ng_level = request.args.get('ng', 'NG')
    ng_level = ng_level.replace(' ', '+')  # Prevent breakage if spaces are used

    if ng_level not in elden_data:
        return jsonify({'error': 'NG level not found'}), 404

    # Get dataframe for this NG level
    df = elden_data[ng_level]

    # --- UNIQUE ENEMIES ---
    unique_enemy_names = df['Name'].unique().tolist()
    total_enemies = len(unique_enemy_names)

    # --- CACHED UNIQUE ENEMIES ---
    cached_names = set()

    # We still use location-level cache keys, but only count name once if *any* variation is cached
    for _, row in df.iterrows():
        cache_key = f"enemy_{row['Name']}_{row['Location']}"
        if cache_key in ai_cache:
            cached_names.add(row['Name'])

    cached_count = len(cached_names)

    return jsonify({
        'total_enemies': total_enemies,
        'cached_enemies': cached_count,
        'percentage': round((cached_count / total_enemies * 100), 1) if total_enemies > 0 else 0
    })

@app.route('/api/cache/update', methods=['POST'])
def update_ai_cache():
    """Manually update AI cache entry (admin function)"""
    data = request.get_json()
    
    enemy_name = data.get('enemy_name')
    new_strategy = data.get('strategy')
    
    if not enemy_name or not new_strategy:
        return jsonify({'error': 'Missing enemy_name or strategy'}), 400
    
    # Create cache key (same format as analyze_with_ai)
    cache_key = f"enemy_{enemy_name}"
    
    # Update cache
    ai_cache[cache_key] = new_strategy
    save_ai_cache(ai_cache)
    
    print(f"✏️  Updated AI cache for: {cache_key}")
    
    return jsonify({
        'status': 'updated',
        'cache_key': cache_key,
        'message': f'AI strategy updated for {enemy_name}'
    })

@app.route('/api/cache/debug', methods=['GET'])
def cache_debug():
    """Debug: Show what's in the AI cache"""
    return jsonify({
        'cache_size': len(ai_cache),
        'sample_keys': list(ai_cache.keys())[:10]  # Show first 10 keys
    })

@app.route('/api/cache/view/<enemy_name>', methods=['GET'])
def view_ai_cache(enemy_name):
    """View cached AI strategy for an enemy"""
    cache_key = f"enemy_{enemy_name}"
    
    if cache_key in ai_cache:
        return jsonify({
            'enemy_name': enemy_name,
            'cache_key': cache_key,
            'strategy': ai_cache[cache_key]
        })
    else:
        return jsonify({'error': 'Not found in cache'}), 404
        
import os
if __name__ == '__main__':
    # Load data on startup (uses cache if available)
    load_elden_ring_data()
    ai_cache = load_ai_cache() 
    
    if not elden_data:
        print("\n⚠️  WARNING: No data loaded!")
        print(f"   Looking for: {DATA_FILE.absolute()}")
    
    print("\n🎮 Elden Ring Helper API")
    print("🔗 http://localhost:5001\n")
    
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
