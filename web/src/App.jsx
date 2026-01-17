import { useState, useEffect, useMemo } from 'react'
import './App.css'

// Load wallet data from JSON
const loadWalletData = async () => {
  try {
    // Try to load from the data folder
    const response = await fetch('/data/smart_wallets.json')
    if (!response.ok) throw new Error('Failed to load')
    return await response.json()
  } catch {
    // Return demo data if file not found
    return []
  }
}

// Score badge component
function ScoreBadge({ score }) {
  const level = score >= 80 ? 'high' : score >= 50 ? 'medium' : 'low'
  return (
    <span className={`score-${level} px-3 py-1 rounded-full text-sm font-bold text-white`}>
      {score.toFixed(1)}
    </span>
  )
}

// Token badge with DexScreener link
function TokenBadge({ token }) {
  // Handle both string (legacy) and object formats
  const isObject = typeof token === 'object' && token !== null
  const address = isObject ? token.address : token
  const label = isObject ? token.symbol : (address.slice(0, 4) + '...')

  // Use dex_url from data if available, otherwise construct from address
  const url = isObject && token.dex_url
    ? token.dex_url
    : `https://dexscreener.com/solana/${address}`

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="token-badge inline-block px-2 py-1 bg-blue-900/50 text-blue-400 rounded text-xs font-mono hover:bg-blue-800/60 transition-colors"
      title={address}
    >
      {label}
    </a>
  )
}

// Metric display component
function Metric({ label, value, highlight }) {
  const colorClass = highlight === 'positive' ? 'text-green-400'
    : highlight === 'negative' ? 'text-red-400'
      : 'text-white'
  return (
    <div className="flex justify-between py-1 border-b border-gray-700/30">
      <span className="text-gray-400 text-sm">{label}</span>
      <span className={`font-medium ${colorClass}`}>{value}</span>
    </div>
  )
}

// Wallet card component
function WalletCard({ wallet }) {
  const shortAddress = wallet.wallet_address.slice(0, 8) + '...' + wallet.wallet_address.slice(-6)
  const birdeyeUrl = `https://birdeye.so/solana/wallet-analyzer/${wallet.wallet_address}`

  // Parse tokens list if it's a string (legacy/csv compat) or use as is
  let tokens = []
  if (Array.isArray(wallet.tokens_list)) {
    tokens = wallet.tokens_list
  } else if (typeof wallet.tokens_list === 'string') {
    tokens = wallet.tokens_list.split(',').map(t => t.trim())
  }

  // Determine PnL highlight
  const pnlNum = parseInt(wallet.realized_pnl_7d) || 0
  const pnlHighlight = pnlNum > 0 ? 'positive' : pnlNum < 0 ? 'negative' : null

  return (
    <div className="wallet-card bg-gray-800/80 rounded-xl p-5 border border-gray-700/50 backdrop-blur">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <span className="text-gray-400 text-xs">#{wallet.rank}</span>
          <h3 className="font-mono text-lg text-white">🦅 {shortAddress}</h3>
        </div>
        <ScoreBadge score={parseFloat(wallet.score)} />
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* 7D Stats */}
        <div className="bg-gray-900/50 rounded-lg p-3">
          <h4 className="text-xs text-blue-400 font-bold mb-2">📅 7 Day</h4>
          <Metric label="Win Rate" value={wallet.win_rate_7d} />
          <Metric label="Realized" value={`$${wallet.realized_pnl_7d}`} highlight={pnlHighlight} />
          <Metric label="Hold Time" value={wallet.avg_holding_time_7d} />
        </div>

        {/* 30D Stats */}
        <div className="bg-gray-900/50 rounded-lg p-3">
          <h4 className="text-xs text-purple-400 font-bold mb-2">📆 30 Day</h4>
          <Metric label="Win Rate" value={wallet.win_rate_30d} />
          <Metric label="Realized" value={`$${wallet.realized_pnl_30d}`} />
          <Metric label="Hold Time" value={wallet.avg_holding_time_30d} />
        </div>
      </div>

      {/* Additional Stats */}
      <div className="flex gap-4 text-sm text-gray-400 mb-4">
        <span>👁 {wallet.appearances} appearances</span>
        <span>💰 ${wallet.total_pnl} total PnL</span>
      </div>

      {/* Token Appearances */}
      <div className="mb-4">
        <span className="text-xs text-gray-500 block mb-2">Token Appearances ({tokens.length}):</span>
        <div className="flex flex-wrap gap-2">
          {tokens.map((token, i) => (
            <TokenBadge key={i} token={token} />
          ))}
        </div>
      </div>

      {/* Actions */}
      <a
        href={birdeyeUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="block w-full text-center py-2 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg text-white font-medium hover:from-blue-500 hover:to-purple-500 transition-all"
      >
        📊 View on Birdeye
      </a>
    </div>
  )
}

// Filter panel component
function FilterPanel({ filters, setFilters }) {
  return (
    <div className="bg-gray-800/60 rounded-xl p-4 mb-6 border border-gray-700/50">
      <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
        🔍 Filters
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <label className="text-xs text-gray-400 block mb-1">Min Score</label>
          <input
            type="number"
            value={filters.minScore}
            onChange={(e) => setFilters({ ...filters, minScore: parseFloat(e.target.value) || 0 })}
            className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white"
          />
        </div>
        <div>
          <label className="text-xs text-gray-400 block mb-1">Min Appearances</label>
          <input
            type="number"
            value={filters.minAppearances}
            onChange={(e) => setFilters({ ...filters, minAppearances: parseInt(e.target.value) || 0 })}
            className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white"
          />
        </div>
        <div>
          <label className="text-xs text-gray-400 block mb-1">Min Total PnL</label>
          <input
            type="number"
            value={filters.minPnl}
            onChange={(e) => setFilters({ ...filters, minPnl: parseInt(e.target.value) || 0 })}
            className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white"
          />
        </div>
        <div>
          <label className="text-xs text-gray-400 block mb-1">Search Address</label>
          <input
            type="text"
            placeholder="Enter wallet..."
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white"
          />
        </div>
      </div>
    </div>
  )
}

// Sort options
const SORT_OPTIONS = [
  { value: 'score', label: 'Score' },
  { value: 'total_pnl', label: 'Total PnL' },
  { value: 'appearances', label: 'Appearances' },
  { value: 'win_rate_7d', label: 'Win Rate (7D)' },
]

// Main App
function App() {
  const [wallets, setWallets] = useState([])
  const [loading, setLoading] = useState(true)
  const [sortBy, setSortBy] = useState('score')
  const [sortDir, setSortDir] = useState('desc')
  const [filters, setFilters] = useState(() => {
    // Load filters from localStorage
    const saved = localStorage.getItem('walletFilters')
    return saved ? JSON.parse(saved) : {
      minScore: 0,
      minAppearances: 0,
      minPnl: 0,
      search: ''
    }
  })

  // Save filters to localStorage
  useEffect(() => {
    localStorage.setItem('walletFilters', JSON.stringify(filters))
  }, [filters])

  // Load data
  useEffect(() => {
    loadWalletData().then(data => {
      setWallets(data)
      setLoading(false)
    })
  }, [])

  // Refresh data
  const refreshData = () => {
    setLoading(true)
    loadWalletData().then(data => {
      setWallets(data)
      setLoading(false)
    })
  }

  // Filter and sort wallets
  const filteredWallets = useMemo(() => {
    let result = wallets.filter(w => {
      if (parseFloat(w.score) < filters.minScore) return false
      if (w.appearances < filters.minAppearances) return false
      if (parseInt(w.total_pnl) < filters.minPnl) return false
      if (filters.search && !w.wallet_address.toLowerCase().includes(filters.search.toLowerCase())) return false
      return true
    })

    // Sort
    result.sort((a, b) => {
      let aVal, bVal
      switch (sortBy) {
        case 'score':
          aVal = parseFloat(a.score)
          bVal = parseFloat(b.score)
          break
        case 'total_pnl':
          aVal = parseInt(a.total_pnl)
          bVal = parseInt(b.total_pnl)
          break
        case 'appearances':
          aVal = a.appearances
          bVal = b.appearances
          break
        case 'win_rate_7d':
          aVal = parseFloat(a.win_rate_7d) || 0
          bVal = parseFloat(b.win_rate_7d) || 0
          break
        default:
          aVal = 0
          bVal = 0
      }
      return sortDir === 'desc' ? bVal - aVal : aVal - bVal
    })

    return result
  }, [wallets, filters, sortBy, sortDir])

  return (
    <div className="min-h-screen p-6">
      {/* Header */}
      <header className="max-w-7xl mx-auto mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
              🧠 Smart Wallet Tracker
            </h1>
            <p className="text-gray-400 mt-1">
              Solana Memecoin Analysis Dashboard
            </p>
          </div>
          <button
            onClick={refreshData}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-white transition-colors"
          >
            🔄 Refresh Data
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto">
        {/* Filters */}
        <FilterPanel filters={filters} setFilters={setFilters} />

        {/* Sort Controls */}
        <div className="flex items-center gap-4 mb-6">
          <span className="text-gray-400">Sort by:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
          >
            {SORT_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <button
            onClick={() => setSortDir(d => d === 'desc' ? 'asc' : 'desc')}
            className="px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white"
          >
            {sortDir === 'desc' ? '↓ High to Low' : '↑ Low to High'}
          </button>
          <span className="text-gray-500 ml-auto">
            Showing {filteredWallets.length} of {wallets.length} wallets
          </span>
        </div>

        {/* Wallet Grid */}
        {loading ? (
          <div className="text-center py-12">
            <div className="text-4xl mb-4">⏳</div>
            <p className="text-gray-400">Loading wallet data...</p>
          </div>
        ) : filteredWallets.length === 0 ? (
          <div className="text-center py-12 bg-gray-800/50 rounded-xl">
            <div className="text-4xl mb-4">🔍</div>
            <p className="text-gray-400">No wallets match your filters</p>
            <button
              onClick={() => setFilters({ minScore: 0, minAppearances: 0, minPnl: 0, search: '' })}
              className="mt-4 text-blue-400 hover:underline"
            >
              Clear filters
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredWallets.map(wallet => (
              <WalletCard key={wallet.wallet_address} wallet={wallet} />
            ))}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto mt-12 py-6 border-t border-gray-800 text-center text-gray-500 text-sm">
        Smart Wallet Tracker • Data from DexScreener & Birdeye
      </footer>
    </div>
  )
}

export default App
