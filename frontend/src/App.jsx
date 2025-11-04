import { useState, useEffect } from 'react';
import { Search, ChevronDown } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const API_URL = 'http://http://localhost:5001';

export default function EldenRingHelper() {
  const [searchQuery, setSearchQuery] = useState('');
  const [ngLevel, setNgLevel] = useState('NG');
  const [currentView, setCurrentView] = useState('landing');
  const [searchResults, setSearchResults] = useState([]);
  const [enemyData, setEnemyData] = useState(null);
  const [regionData, setRegionData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [ngDropdownOpen, setNgDropdownOpen] = useState(false);
  const [cacheStats, setCacheStats] = useState({ total_enemies: 0, cached_enemies: 0, percentage: 0 });
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const ngLevels = ['NG', 'NG+', 'NG+2', 'NG+3', 'NG+4', 'NG+5', 'NG+6', 'NG+7'];

  // Fetch cache stats on mount and when NG level changes
  useEffect(() => {
    fetchCacheStats();
  }, [ngLevel]);

  const fetchCacheStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/cache/stats?ng=${encodeURIComponent(ngLevel)}`);
      const data = await response.json();
      setCacheStats(data);
    } catch (error) {
      console.error('Error fetching cache stats:', error);
    }
  };

  const handleSearch = async () => {
  if (!searchQuery.trim()) return;
  setLoading(true);

  try {
    const response = await fetch(`${API_URL}/api/search?q=${encodeURIComponent(searchQuery)}&ng=${encodeURIComponent(ngLevel)}`);
    const data = await response.json();
    
    if (data.results && data.results.length > 0) {
      const uniqueEnemies = [];
      const seenNames = new Set();
      
      data.results.forEach(enemy => {
        if (!seenNames.has(enemy.name)) {
          seenNames.add(enemy.name);
          uniqueEnemies.push(enemy);
        }
      });
      
      setSearchResults(uniqueEnemies);
      setCurrentView('search-results');
    } else {
      // Check if it's actually a valid region by trying to fetch region data
      const regionResponse = await fetch(`${API_URL}/api/region/${encodeURIComponent(searchQuery)}/enemies?ng=${encodeURIComponent(ngLevel)}`);
      const regionData = await regionResponse.json();
      
      if (regionData.enemies && regionData.enemies.length > 0) {
        // Valid region with enemies
        setRegionData({ name: searchQuery });
        setCurrentView('region-choice');
      } else {
        // No enemies found and not a valid region - show error
        setSearchResults([]);
        setCurrentView('no-results');
      }
    }
  } catch (error) {
    console.error('Search error:', error);
  } finally {
    setLoading(false);
  }
};

  const handleEnemySelect = async (enemyName, specificNG = null) => {
  setLoading(true);
  try {
    const ngToUse = specificNG || ngLevel;
    const response = await fetch(`${API_URL}/api/enemy/${encodeURIComponent(enemyName)}?ng=${encodeURIComponent(ngToUse)}`);
    const data = await response.json();
    console.timeEnd('Enemy fetch');
    setEnemyData(data);
    setCurrentView('enemy');
    fetchCacheStats();
  } catch (error) {
    console.error('Error fetching enemy:', error);
  } finally {
    setLoading(false);
  }
};

  const handleLocationChange = async (location) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/enemy/${encodeURIComponent(enemyData.name)}?ng=${encodeURIComponent(ngLevel)}&location=${encodeURIComponent(location)}`);
      const data = await response.json();
      setEnemyData({...data, all_instances: enemyData.all_instances || data.all_instances});
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRegionAverage = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/region/${encodeURIComponent(regionData.name)}?ng=${encodeURIComponent(ngLevel)}`);
      const data = await response.json();
      const regionAsEnemy = {
  name: `${data.region} (Average)`,
  location: `${data.enemy_count} enemies`,
  hp: data.avg_hp,
  damage_negation: data.avg_damage_negation,
  resistances: data.avg_resistances,  // ← Changed from hardcoded values
  poise: data.avg_poise,  // ← Now includes all poise data
  ai_strategy: data.ai_strategy,
  all_instances: []
};
      setEnemyData(regionAsEnemy);
      setCurrentView('enemy');
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRegionEnemies = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/region/${encodeURIComponent(regionData.name)}/enemies?ng=${encodeURIComponent(ngLevel)}`);
      const data = await response.json();
      setRegionData({ ...regionData, enemies: data.enemies });
      setCurrentView('region-enemies');
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  const getDefenseChartData = (dn) => {
    if (!dn) return [];
    return [
      { name: 'Physical', value: dn.physical },
      { name: 'Strike', value: dn.strike },
      { name: 'Slash', value: dn.slash },
      { name: 'Pierce', value: dn.pierce },
      { name: 'Magic', value: dn.magic },
      { name: 'Fire', value: dn.fire },
      { name: 'Lightning', value: dn.lightning },
      { name: 'Holy', value: dn.holy }
    ];
  };

  const getResistanceChartData = (r) => {
    if (!r) return [];
    return [
      { name: 'Poison', value: r.poison === 'Immune' ? 0 : r.poison, label: r.poison === 'Immune' ? 'Immune' : r.poison },
      { name: 'Rot', value: r.scarlet_rot === 'Immune' ? 0 : r.scarlet_rot, label: r.scarlet_rot === 'Immune' ? 'Immune' : r.scarlet_rot },
      { name: 'Bleed', value: r.bleed === 'Immune' ? 0 : r.bleed, label: r.bleed === 'Immune' ? 'Immune' : r.bleed },
      { name: 'Frost', value: r.frost === 'Immune' ? 0 : r.frost, label: r.frost === 'Immune' ? 'Immune' : r.frost },
      { name: 'Sleep', value: r.sleep === 'Immune' ? 0 : r.sleep, label: r.sleep === 'Immune' ? 'Immune' : r.sleep },
      { name: 'Madness', value: r.madness === 'Immune' ? 0 : r.madness, label: r.madness === 'Immune' ? 'Immune' : r.madness },
      { name: 'Deathblight', value: r.deathblight === 'Immune' ? 0 : r.deathblight, label: r.deathblight === 'Immune' ? 'Immune' : r.deathblight }
    ];
  };

  const getDefenseColor = (v) => {
    if (v < -10) return '#18b181ff';
    if (v < 0) return '#00b106ff';
    if (v < 20) return '#31b808ff';
    if (v < 40) return '#e6e329ff';
    if (v < 60) return '#ea8621ff';
    if (v < 80) return '#e9452aff';
    return '#22c55e';
  };

  const getResistanceColor = (v) => {
    if (v === 0) return '#35ebdbff';
    if (v < 300) return '#19d25dff';
    if (v < 600) return '#e6c80aff';
    if (v < 900) return '#e66925ff';
    if (v < 1200) return '#e62525ff';
    return '#22c55e';
  };

  const formatAIText = (text) => {
    if (!text) return '';
    let formatted = text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^### (.*$)/gim, '<h3 class="text-lg font-bold text-amber-400 mt-4 mb-2">$1</h3>')
      .replace(/^## (.*$)/gim, '<h2 class="text-xl font-bold text-amber-400 mt-4 mb-2">$1</h2>')
      .replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold text-amber-400 mt-4 mb-2">$1</h1>')
      .replace(/^\d+\.\s(.*$)/gim, '<li class="ml-4 mb-1">$1</li>')
      .replace(/^-\s(.*$)/gim, '<li class="ml-4 mb-1">$1</li>');
    return formatted;
  };

  if (currentView === 'no-results') {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black text-gray-100 flex flex-col items-center justify-center p-8">
      <button
        onClick={() => setCurrentView('landing')}
        className="absolute top-8 left-8 px-6 py-3 bg-gray-800 border border-amber-500/30 rounded-lg hover:border-amber-500 transition-all"
      >
        ← Back
      </button>
      
      <div className="text-center">
        <h2 className="text-4xl font-bold text-red-400 mb-4">No Results</h2>
        <p className="text-gray-400 text-lg">
          No enemies or regions found matching "<span className="text-amber-400">{searchQuery}</span>"
        </p>
      </div>
    </div>
  );
}

  const extractRecommendations = (aiStrategy, damageNegation, resistances) => {
  const recommendations = [];

  // --- DAMAGE TYPES ---
  if (damageNegation) {
    const damageTypes = [
      { name: 'Physical', value: damageNegation.physical },
      { name: 'Strike', value: damageNegation.strike },
      { name: 'Slash', value: damageNegation.slash },
      { name: 'Pierce', value: damageNegation.pierce },
      { name: 'Magic', value: damageNegation.magic },
      { name: 'Fire', value: damageNegation.fire },
      { name: 'Lightning', value: damageNegation.lightning },
      { name: 'Holy', value: damageNegation.holy }
    ];

    const values = damageTypes.map(d => d.value);
    const min = Math.min(...values);
    const max = Math.max(...values);

    // If all values are very close, no true weakness
    if (max - min >= 15) {
      const avg = values.reduce((a, b) => a + b, 0) / values.length;
      const threshold = min + (avg - min) * 0.5; // halfway between min and average

      const best = damageTypes.filter(d => d.value <= threshold);
      best.sort((a, b) => a.value - b.value);
      best.forEach(d => recommendations.push(d.name));
    }
  }

  // --- STATUS EFFECTS ---
  if (resistances) {
    const statusEffects = [
      { name: 'Poison', value: resistances.poison },
      { name: 'Rot', value: resistances.scarlet_rot },
      { name: 'Bleed', value: resistances.bleed },
      { name: 'Frost', value: resistances.frost },
      { name: 'Sleep', value: resistances.sleep },
      { name: 'Madness', value: resistances.madness },
      { name: 'Deathblight', value: resistances.deathblight }
    ]
      .filter(s => s.value !== 'Immune' && s.value != null && s.value !== '')
      .map(s => ({ ...s, value: Number(s.value) }))
      .filter(s => !isNaN(s.value) && s.value > 0); // ignore nulls, NaN, or 0


    if (statusEffects.length > 0) {
      const values = statusEffects.map(s => s.value);
      const min = Math.min(...values);
      const avg = values.reduce((a, b) => a + b, 0) / values.length;
      const threshold = min + (avg - min) * 0.5; // dynamic threshold

      const bestStatuses = statusEffects.filter(s => s.value <= threshold && s.value < 400);
      bestStatuses.sort((a, b) => a.value - b.value);
      bestStatuses.forEach(s => recommendations.push(s.name));
    }
  }

  return recommendations.length > 0 ? recommendations : ['Balanced approach'];
};



  if (currentView === 'landing') {
    return (
      <div className="min-h-screen w-full overflow-x-hidden bg-gradient-to-br from-slate-900 to-slate-800 flex flex-col items-center justify-center px-4">
        {(loading || isAnalyzing) && (
  <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center">
    <div className="bg-gray-800 border-2 border-amber-500 rounded-xl p-8 flex flex-col items-center gap-4">
      <div className="w-16 h-16 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
      <div className="text-xl font-bold text-amber-400">
        {currentView === 'enemy' ? 'Analyzing enemy...' : 'Loading...'}
      </div>
    </div>
  </div>
)}
        <div className="absolute top-8 right-8">
          <div className="relative">
            <button
              onClick={() => setNgDropdownOpen(!ngDropdownOpen)}
              className="px-6 py-3 bg-gray-800 border-2 border-amber-500/30 rounded-lg text-white font-bold hover:border-amber-500 transition-all flex items-center gap-2"
            >
              {ngLevel}
              <ChevronDown size={20} className={`transition-transform ${ngDropdownOpen ? 'rotate-180' : ''}`} />
            </button>
            
            {ngDropdownOpen && (
              <div className="absolute top-full mt-2 right-0 bg-gray-800 border-2 border-amber-500/30 rounded-lg overflow-hidden z-50 min-w-[120px]">
                {ngLevels.map(ng => (
                  <button
                    key={ng}
                    onClick={() => {
                      setNgLevel(ng);
                      setNgDropdownOpen(false);
                    }}
                    className="w-full px-6 py-3 text-left hover:bg-amber-500/20 transition-colors text-white font-medium"
                  >
                    {ng}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="w-full max-w-2xl px-4">
          <h1 className="text-6xl font-bold text-center mb-12 bg-gradient-to-r from-amber-400 to-yellow-600 bg-clip-text text-transparent">
            ELDEN RING HELPER
          </h1>
          
          <div className="mb-8 bg-gray-800/50 border border-amber-500/30 rounded-lg p-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm text-gray-400">Enemy Database</span>
              <span className="text-sm font-bold text-amber-400">
                {cacheStats.cached_enemies}/{cacheStats.total_enemies} Analyzed
              </span>
            </div>
            <div className="w-full h-3 bg-gray-900 rounded-full overflow-hidden border border-amber-500/30">
              <div 
                className="h-full bg-gradient-to-r from-amber-500 to-yellow-600 transition-all duration-500"
                style={{ width: `${cacheStats.percentage}%` }}
              />
            </div>
            <div className="text-center mt-2 text-xs text-gray-500">
              {cacheStats.percentage}% Complete
            </div>
          </div>
          
          <div className="relative flex flex-col sm:flex-row gap-4">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder="Search enemy or region..."
              className={`flex-1 px-8 py-6 bg-gray-800/80 border-2 border-amber-500/30 rounded-xl text-white text-lg placeholder-gray-500 focus:border-amber-500 focus:outline-none transition-all duration-300 ${isFocused ? 'scale-105' : 'scale-100'}`}
            />
            <button
              onClick={handleSearch}
              disabled={loading}
              className="px-8 py-6 bg-gradient-to-r from-amber-500 to-yellow-600 text-black font-bold rounded-xl hover:from-amber-400 hover:to-yellow-500 transition-all disabled:opacity-50 flex items-center gap-2 justify-center"
            >
              {loading ? 'Searching...' : <><Search size={24} /> Search</>}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (currentView === 'search-results') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black text-gray-100 p-8">
      {loading && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-gray-800 border-2 border-amber-500 rounded-xl p-8 flex flex-col items-center gap-4">
            <div className="w-16 h-16 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
            <div className="text-xl font-bold text-amber-400">Analyzing enemy...</div>
          </div>
        </div>
      )}
        <button
          onClick={() => setCurrentView('landing')}
          className="mb-6 px-6 py-3 bg-gray-800 border border-amber-500/30 rounded-lg hover:border-amber-500 transition-all"
        >
          ← Back
        </button>
        
        <h2 className="text-3xl font-bold text-amber-400 mb-6">Search Results</h2>
        
        <div className="grid gap-4 max-w-2xl">
          {searchResults.map((enemy, idx) => (
            <button
              key={idx}
              onClick={() => handleEnemySelect(enemy.name)}
              className="text-left p-6 bg-gray-800/70 backdrop-blur border-2 border-amber-500/20 rounded-lg hover:border-amber-500 hover:scale-[1.02] transition-all"
            >
              <div className="text-2xl font-bold text-white mb-2">{enemy.name}</div>
              <div className="text-gray-400">{enemy.location}</div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (currentView === 'region-choice') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black text-gray-100 flex flex-col items-center justify-center p-8">
        {loading && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-gray-800 border-2 border-amber-500 rounded-xl p-8 flex flex-col items-center gap-4">
            <div className="w-16 h-16 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
            <div className="text-xl font-bold text-amber-400">Analyzing region...</div>
          </div>
        </div>
      )}
        <button
          onClick={() => setCurrentView('landing')}
          className="absolute top-8 left-8 px-6 py-3 bg-gray-800 border border-amber-500/30 rounded-lg hover:border-amber-500 transition-all"
        >
          ← Back
        </button>
        
        <h2 className="text-4xl font-bold text-amber-400 mb-12">{regionData.name}</h2>
        
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-4">
          <button
            onClick={handleRegionAverage}
            className="w-64 h-64 rounded-full bg-gradient-to-br from-amber-500 to-yellow-600 hover:from-amber-400 hover:to-yellow-500 text-black font-bold text-xl shadow-2xl hover:scale-105 transition-all flex items-center justify-center"
          >
            {regionData.name}<br/>Average
          </button>
          
          <button
            onClick={handleRegionEnemies}
            className="w-64 h-64 rounded-full bg-gradient-to-br from-red-600 to-red-800 hover:from-red-500 hover:to-red-700 text-white font-bold text-xl shadow-2xl hover:scale-105 transition-all flex items-center justify-center"
          >
            All Enemies in<br/>{regionData.name}
          </button>
        </div>
      </div>
    );
  }

  if (currentView === 'region-enemies') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black text-gray-100 p-8">
        {loading && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-gray-800 border-2 border-amber-500 rounded-xl p-8 flex flex-col items-center gap-4">
            <div className="w-16 h-16 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
            <div className="text-xl font-bold text-amber-400">Analyzing enemy...</div>
          </div>
        </div>
      )}
        <button
          onClick={() => setCurrentView('region-choice')}
          className="mb-6 px-6 py-3 bg-gray-800 border border-amber-500/30 rounded-lg hover:border-amber-500 transition-all"
        >
          ← Back
        </button>
        
        <h2 className="text-3xl font-bold text-amber-400 mb-6">Enemies in {regionData.name}</h2>
        
        <div className="grid gap-4 max-w-2xl">
          {regionData.enemies?.map((enemy, idx) => (
  <button
    key={idx}
    onClick={async () => {
      setLoading(true);
      try {
        const response = await fetch(`${API_URL}/api/enemy/${encodeURIComponent(enemy.name)}?ng=${encodeURIComponent(ngLevel)}&location=${encodeURIComponent(enemy.location)}`);
        const data = await response.json();
        setEnemyData(data);
        setCurrentView('enemy');
        fetchCacheStats();
      } catch (error) {
        console.error('Error:', error);
      } finally {
        setLoading(false);
      }
    }}
    className="text-left p-6 bg-gray-800/70 backdrop-blur border-2 border-amber-500/20 rounded-lg hover:border-amber-500 hover:scale-[1.02] transition-all"
  >
    <div className="text-2xl font-bold text-white">{enemy.name}</div>
    <div className="text-sm text-gray-400 mt-1">{enemy.location}</div>
  </button>
))}
        </div>
      </div>
    );
  }

  if (currentView === 'enemy' && enemyData) {
    const recommendations = extractRecommendations(enemyData.ai_strategy, enemyData.damage_negation, enemyData.resistances);
    
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black text-gray-100 p-8">
        {(loading || isAnalyzing) && (
  <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center">
    <div className="bg-gray-800 border-2 border-amber-500 rounded-xl p-8 flex flex-col items-center gap-4">
      <div className="w-16 h-16 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
      <div className="text-xl font-bold text-amber-400">
        {currentView === 'enemy' ? 'Analyzing enemy...' : 'Loading...'}
      </div>
    </div>
  </div>
)}
        <div className="flex justify-between items-center mb-6">
          <button
            onClick={() => setCurrentView('search-results')}
            className="px-6 py-3 bg-gray-800 border border-amber-500/30 rounded-lg hover:border-amber-500 transition-all"
          >
            ← Back
          </button>
          
          {/* NG Selector */}
          <div className="relative">
            <button
              onClick={() => setNgDropdownOpen(!ngDropdownOpen)}
              className="px-6 py-3 bg-gray-800 border-2 border-amber-500/30 rounded-lg text-white font-bold hover:border-amber-500 transition-all flex items-center gap-2"
            >
              {ngLevel}
              <ChevronDown size={20} className={`transition-transform ${ngDropdownOpen ? 'rotate-180' : ''}`} />
            </button>
            
            {ngDropdownOpen && (
  <div className="absolute top-full mt-2 right-0 bg-gray-800 border-2 border-amber-500/30 rounded-lg overflow-hidden z-50 min-w-[120px]">
    {ngLevels.map(ng => (
      <button
        key={ng}
        onClick={() => {
          setNgLevel(ng);
          setNgDropdownOpen(false);
          handleEnemySelect(enemyData.name, ng);  // ← Pass ng directly!
        }}
        className="w-full px-6 py-3 text-left hover:bg-amber-500/20 transition-colors text-white font-medium"
      >
        {ng}
      </button>
    ))}
  </div>
)}
          </div>
        </div>

        <div className="mb-8 bg-gray-800/50 border-2 border-red-500/30 rounded-lg p-6">
          <div className="flex justify-between items-center mb-3">
            <span className="text-2xl font-bold text-white">{enemyData.name}</span>
            <span className="text-3xl font-bold text-red-400">{enemyData.hp?.toLocaleString()} HP</span>
          </div>
          <div className="w-full h-8 bg-gray-900 rounded-full overflow-hidden border-2 border-red-500/50">
            <div className="h-full bg-gradient-to-r from-red-600 to-red-400 w-full"></div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="space-y-6">
            {enemyData.all_instances?.length > 1 && (
              <div className="bg-gray-800/70 backdrop-blur border border-amber-500/20 rounded-lg p-4">
                <h3 className="text-lg font-bold text-amber-400 mb-3">Location</h3>
                <select
                  value={enemyData.location}
                  onChange={(e) => handleLocationChange(e.target.value)}
                  className="w-full p-3 bg-gray-700 border border-amber-500/30 rounded-lg text-white hover:border-amber-500 transition-all cursor-pointer"
                >
                  {enemyData.all_instances.map((inst, idx) => (
                    <option key={idx} value={inst.location}>
                      {inst.location}
                    </option>
                  ))}
                </select>
              </div>
            )}
            
            <div className="bg-gray-800/70 backdrop-blur border border-amber-500/20 rounded-lg p-6">
              <div 
                className="text-gray-300 text-sm leading-relaxed"
                dangerouslySetInnerHTML={{ __html: formatAIText(enemyData.ai_strategy) }}
              />
            </div>
          </div>

          <div className="flex flex-col items-center pt-0">
            <div className="bg-gradient-to-br from-amber-500/20 to-yellow-600/20 border-2 border-amber-500 rounded-xl p-8 text-center w-full">
              <h3 className="text-2xl font-bold text-amber-400 mb-6">Recommended Strategy</h3>
              <div className="flex flex-col gap-8">
                {recommendations.length > 0 ? (
                  recommendations.map((rec, idx) => (
                    <div key={idx} className="text-3xl font-bold text-white bg-gray-800/50 rounded-lg py-3 px-6">
                      {rec}
                    </div>
                  ))
                ) : (
                  <div className="text-3xl font-bold text-white">Balanced approach</div>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-gray-800/70 backdrop-blur border border-amber-500/20 rounded-lg p-6">
              <h3 className="text-lg font-bold text-amber-400 mb-4">Damage Negation (%)</h3>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={getDefenseChartData(enemyData.damage_negation)} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis type="number" domain={[-50, 100]} stroke="#9ca3af" />
                  <YAxis type="category" dataKey="name" width={80} stroke="#9ca3af" tick={{ fontSize: 12 }} />
                  <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #fbbf24', borderRadius: '8px' }}
                  itemStyle={{color: '#fff'}} cursor={{fill: '#9494945c'}}/>
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} activeBar>
                    {getDefenseChartData(enemyData.damage_negation).map((entry, i) => (
                      <Cell key={i} fill={getDefenseColor(entry.value)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-gray-800/70 backdrop-blur border border-amber-500/20 rounded-lg p-6">
              <h3 className="text-lg font-bold text-amber-400 mb-4">Status Resistances</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={getResistanceChartData(enemyData.resistances)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="name" stroke="#9ca3af" angle={-45} textAnchor="end" height={80} />
                  <YAxis stroke="#9ca3af" />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #fbbf24', borderRadius: '8px' }}
                    formatter={(value, name, props) => props.payload.label}
                    itemStyle={{color: '#fff'}}
                    cursor={{fill: '#9494945c'}}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {getResistanceChartData(enemyData.resistances).map((entry, i) => (
                      <Cell key={i} fill={getResistanceColor(entry.value)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-gray-800/70 backdrop-blur border border-amber-500/20 rounded-lg p-6">
              <h3 className="text-lg font-bold text-amber-400 mb-3">Stance</h3>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-lg text-gray-400">Regen: {enemyData.poise?.regen_delay?.toFixed(1)}s</div>
                </div>
                <div className="flex gap-4">
                  {/* Base Poise */}
                  <div className="text-center">
                    <div className="w-24 h-24 rounded-full border-4 border-amber-500 flex items-center justify-center bg-amber-500/10">
                      <span className="text-2xl font-bold text-amber-400">{enemyData.poise?.base || 0}</span>
                    </div>
                    <div className="text-xs text-gray-400 mt-2">Base</div>
                  </div>
                  
                  {/* Effective Poise */}
                  <div className="text-center">
                    <div className="w-24 h-24 rounded-full border-4 border-green-500 flex items-center justify-center bg-green-500/10">
                      <span className="text-2xl font-bold text-green-400">
                        {enemyData.poise?.effective === 999999 ? '∞' : (enemyData.poise?.effective || 0)}
                      </span>
                    </div>
                    <div className="text-xs text-gray-400 mt-2">Effective</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
