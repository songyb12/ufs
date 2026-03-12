import { useState, useEffect, useCallback } from 'react'
import { MapContainer, TileLayer, CircleMarker, Tooltip, Polyline } from 'react-leaflet'
import { getForexMap, backfillForex } from '../api'
import { useToast } from '../components/Toast'
import 'leaflet/dist/leaflet.css'

const STRENGTH_COLORS = {
  Strong: '#22c55e',
  'Mild Strong': '#86efac',
  Neutral: '#6b7280',
  'Mild Weak': '#fca5a5',
  Weak: '#ef4444',
  Base: '#3b82f6',
}

function DxyPanel({ analysis }) {
  if (!analysis) return null
  return (
    <div className="card" style={{ padding: '1rem', borderLeft: `3px solid ${analysis.color}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <span style={{ fontWeight: 700 }}>Dollar Index (DXY)</span>
        <span style={{ fontSize: '1.5rem', fontWeight: 700, color: analysis.color }}>{analysis.value}</span>
      </div>
      <div style={{ fontSize: '0.8rem', color: analysis.color, fontWeight: 600, marginBottom: '0.35rem' }}>{analysis.level_kr}</div>
      <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{analysis.impact_kr}</div>
    </div>
  )
}

function FlowTable({ flows }) {
  if (!flows || flows.length === 0) return null
  return (
    <div className="card" style={{ padding: '1rem' }}>
      <h3 style={{ fontSize: '0.95rem', marginBottom: '0.75rem' }}>자본 흐름 (캐리 트레이드 방향)</h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th style={thStyle}>흐름</th>
              <th style={thStyle}>금리차</th>
              <th style={thStyle}>강도</th>
            </tr>
          </thead>
          <tbody>
            {flows.map((f, i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={tdStyle}>{f.label_kr}</td>
                <td style={{ ...tdStyle, color: '#3b82f6', fontWeight: 600 }}>{f.rate_diff}%p</td>
                <td style={tdStyle}>
                  <div style={{ width: '100%', maxWidth: '80px', height: '6px', background: 'var(--border)', borderRadius: '3px' }}>
                    <div style={{ width: `${f.intensity * 100}%`, height: '100%', background: '#3b82f6', borderRadius: '3px' }} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const thStyle = { textAlign: 'left', padding: '0.4rem 0.5rem', color: 'var(--text-muted)', fontWeight: 600 }
const tdStyle = { padding: '0.4rem 0.5rem' }

function CountryTable({ countries }) {
  if (!countries || countries.length === 0) return null
  const sorted = [...countries].sort((a, b) => (b.interest_rate || 0) - (a.interest_rate || 0))
  return (
    <div className="card" style={{ padding: '1rem' }}>
      <h3 style={{ fontSize: '0.95rem', marginBottom: '0.75rem' }}>통화별 상세</h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th style={thStyle}>통화</th>
              <th style={thStyle}>국가</th>
              <th style={thStyle}>금리</th>
              <th style={thStyle}>환율</th>
              <th style={thStyle}>1D</th>
              <th style={thStyle}>1W</th>
              <th style={thStyle}>1M</th>
              <th style={thStyle}>강도</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((c) => {
              const sColor = c.strength?.color || '#6b7280'
              return (
                <tr key={c.currency} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ ...tdStyle, fontWeight: 700 }}>{c.flag} {c.currency}</td>
                  <td style={tdStyle}>{c.country}</td>
                  <td style={{ ...tdStyle, color: '#3b82f6', fontWeight: 600 }}>
                    {c.interest_rate != null ? `${c.interest_rate.toFixed(2)}%` : 'N/A'}
                  </td>
                  <td style={tdStyle}>{c.fx_current ? c.fx_current.toLocaleString() : '-'}</td>
                  <td style={{ ...tdStyle, ...changeStyle(c.fx_change_1d) }}>{fmtChange(c.fx_change_1d)}</td>
                  <td style={{ ...tdStyle, ...changeStyle(c.fx_change_1w) }}>{fmtChange(c.fx_change_1w)}</td>
                  <td style={{ ...tdStyle, ...changeStyle(c.fx_change_1m) }}>{fmtChange(c.fx_change_1m)}</td>
                  <td style={{ ...tdStyle, color: sColor, fontWeight: 600 }}>{c.strength?.label || '-'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function changeStyle(v) {
  if (!v) return { color: 'var(--text-muted)' }
  return { color: v > 0 ? '#ef4444' : v < 0 ? '#22c55e' : 'var(--text-muted)' }
}

function fmtChange(v) {
  if (v == null || v === 0) return '-'
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
}

function ForexWorldMap({ countries, flows }) {
  if (!countries || countries.length === 0) return null

  return (
    <div className="card" style={{ padding: '0.5rem', marginBottom: '1rem' }}>
      <MapContainer
        center={[20, 30]}
        zoom={2}
        minZoom={2}
        maxZoom={6}
        style={{ height: '500px', borderRadius: '0.5rem', background: '#1a1a2e' }}
        scrollWheelZoom={true}
        worldCopyJump={true}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        />

        {/* Capital flow lines */}
        {flows && flows.map((f, i) => (
          <Polyline
            key={`flow-${i}`}
            positions={[[f.from_lat, f.from_lon], [f.to_lat, f.to_lon]]}
            pathOptions={{
              color: '#3b82f6',
              weight: 1 + f.intensity * 3,
              opacity: 0.4 + f.intensity * 0.4,
              dashArray: '8 4',
            }}
          >
            <Tooltip sticky>{f.label_kr}</Tooltip>
          </Polyline>
        ))}

        {/* Country markers */}
        {countries.map((c) => {
          const color = c.strength?.color || '#6b7280'
          const radius = c.currency === 'USD' ? 10 : c.interest_rate != null ? 6 + Math.min(c.interest_rate, 10) * 0.5 : 5
          return (
            <CircleMarker
              key={c.currency}
              center={[c.lat, c.lon]}
              radius={radius}
              pathOptions={{
                fillColor: color,
                fillOpacity: 0.85,
                color: '#fff',
                weight: 1.5,
              }}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                <div style={{ fontSize: '0.8rem', lineHeight: 1.4 }}>
                  <strong>{c.flag} {c.currency} ({c.name})</strong><br />
                  {c.interest_rate != null && <>금리: {c.interest_rate.toFixed(2)}%<br /></>}
                  {c.fx_pair && <>환율: {c.fx_current?.toLocaleString()} ({c.fx_pair})<br /></>}
                  강도: <span style={{ color }}>{c.strength?.label}</span><br />
                  {c.fx_change_1d ? <>1D: {fmtChange(c.fx_change_1d)}</> : null}
                </div>
              </Tooltip>
            </CircleMarker>
          )
        })}
      </MapContainer>
    </div>
  )
}

export default function ForexMap({ refreshKey, onNavigate }) {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [backfilling, setBackfilling] = useState(false)

  const loadData = useCallback(() => {
    setLoading(true)
    getForexMap()
      .then(d => setData(d))
      .catch(err => toast.error('Load failed: ' + err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData() }, [loadData, refreshKey])

  const handleBackfill = async () => {
    setBackfilling(true)
    try {
      const res = await backfillForex(30)
      toast.success(`환율 데이터 ${res.saved || 0}건 수집 완료`)
      loadData()
    } catch (err) {
      toast.error('Backfill failed: ' + err.message)
    } finally {
      setBackfilling(false)
    }
  }

  if (loading) {
    return <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading forex map...</div>
  }

  const countries = data?.countries || []
  const flows = data?.flows || []

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h2>Global Forex Map</h2>
        <button
          className="btn btn-primary"
          onClick={handleBackfill}
          disabled={backfilling}
          style={{ fontSize: '0.75rem', padding: '0.3rem 0.75rem' }}
        >
          {backfilling ? 'Collecting...' : 'Backfill Forex Data'}
        </button>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', margin: 0 }}>
          세계 환율 현황, 통화 강도, 금리 기반 자본 흐름 시각화
        </p>
        {onNavigate && (
          <button
            className="btn btn-outline"
            onClick={() => onNavigate('carry-trade')}
            style={{ fontSize: '0.72rem', padding: '0.25rem 0.6rem' }}
          >
            {'💱'} 캐리트레이드
          </button>
        )}
      </div>

      {/* DXY + VIX Panel */}
      <div style={{ display: 'grid', gridTemplateColumns: data?.dxy_analysis ? '2fr 1fr' : '1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
        <DxyPanel analysis={data?.dxy_analysis} />
        {data?.vix != null && (
          <div className="card" style={{ padding: '1rem', borderLeft: `3px solid ${data.vix > 25 ? '#ef4444' : data.vix > 20 ? '#eab308' : '#22c55e'}` }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>VIX (공포지수)</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: data.vix > 25 ? '#ef4444' : data.vix > 20 ? '#eab308' : '#22c55e' }}>
              {data.vix.toFixed(1)}
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
              {data.vix > 30 ? '극단적 공포' : data.vix > 25 ? '높은 불안' : data.vix > 20 ? '불안 확대' : '안정'}
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', margin: '0.75rem 0', fontSize: '0.72rem' }}>
        {Object.entries(STRENGTH_COLORS).map(([label, color]) => (
          <span key={label} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: color, display: 'inline-block' }} />
            {label === 'Base' ? '기준통화' : label === 'Strong' ? '강세' : label === 'Mild Strong' ? '소폭강세' : label === 'Neutral' ? '보합' : label === 'Mild Weak' ? '소폭약세' : '약세'}
          </span>
        ))}
      </div>

      {/* World Map */}
      <ForexWorldMap countries={countries} flows={flows} />

      {/* Strength Summary */}
      {countries.length > 0 && (
        <div className="card" style={{ padding: '1rem', marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '0.95rem', marginBottom: '0.75rem' }}>통화 강도 요약</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {[...countries]
              .filter(c => c.currency !== 'USD' && c.strength?.score != null)
              .sort((a, b) => (b.strength?.score || 0) - (a.strength?.score || 0))
              .slice(0, 12)
              .map(c => (
                <div key={c.currency} style={{
                  display: 'flex', alignItems: 'center', gap: '0.35rem',
                  padding: '0.3rem 0.6rem', borderRadius: '0.25rem',
                  background: 'var(--bg-secondary)', border: '1px solid var(--border)',
                  fontSize: '0.75rem',
                }}>
                  <span>{c.flag}</span>
                  <span style={{ fontWeight: 700 }}>{c.currency}</span>
                  <span style={{ color: c.strength?.color || '#6b7280', fontWeight: 600 }}>{c.strength?.label}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Flow Table and Country Table */}
      <div style={{ display: 'grid', gridTemplateColumns: flows.length > 0 ? '1fr 2fr' : '1fr', gap: '1rem' }}>
        <FlowTable flows={flows} />
        <CountryTable countries={countries} />
      </div>
    </div>
  )
}
