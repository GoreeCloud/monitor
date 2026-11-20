import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';

type State = 'up' | 'down' | 'pending';
type Monitor = { id: string; name: string; target?: string; kind?: string; state: State; interval_s: number; last_checked: number | null; last_latency_ms: number | null; public: number };
type Incident = { id: number; monitor_name: string; started_at: number };
type PublicStatus = { service: string; summary: { total: number; up: number; down: number; pending: number }; monitors: Monitor[]; incidents: Incident[]; updated_at: number };

function timestamp(epoch: number | null): string {
  return epoch ? new Date(epoch * 1000).toLocaleString() : 'Not yet checked';
}

async function request<T>(path: string, token = '', options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...options,
    cache: 'no-store',
    headers: {
      ...(options?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: 'Bearer ' + token } : {}),
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { error?: string };
    throw new Error(body.error || 'Request failed (' + response.status + ')');
  }
  return response.json() as Promise<T>;
}

export default function App() {
  const [publicData, setPublicData] = useState<PublicStatus | null>(null);
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [token, setToken] = useState('');
  const [admin, setAdmin] = useState(false);
  const [name, setName] = useState('');
  const [target, setTarget] = useState('');
  const [interval, setInterval] = useState('60');
  const [isPublic, setIsPublic] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    try {
      const status = await request<PublicStatus>('/api/v1/status');
      setPublicData(status);
      if (token && admin) {
        const all = await request<{ monitors: Monitor[] }>('/api/v1/monitors', token);
        setMonitors(all.monitors);
      } else {
        setMonitors(status.monitors);
      }
      setLastRefreshed(new Date());
      setError('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to connect to the monitor API');
    }
  }, [token, admin]);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 20000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const counts = useMemo(() => ({
    total: monitors.length,
    up: monitors.filter(m => m.state === 'up').length,
    down: monitors.filter(m => m.state === 'down').length,
    pending: monitors.filter(m => m.state === 'pending').length,
  }), [monitors]);

  async function authorize(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const value = await request<{ monitors: Monitor[] }>('/api/v1/monitors', token);
      setMonitors(value.monitors);
      setAdmin(true);
      setError('');
    } catch (reason) {
      setAdmin(false);
      setError(reason instanceof Error ? reason.message : 'Authentication failed');
    } finally {
      setBusy(false);
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await request('/api/v1/monitors', token, {
        method: 'POST',
        body: JSON.stringify({ name, target, interval_s: Number(interval), public: isPublic }),
      });
      setName('');
      setTarget('');
      setIsPublic(false);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not add monitor');
    } finally {
      setBusy(false);
    }
  }

  async function execute(id: string, method: 'check' | 'delete') {
    setBusy(true);
    try {
      await request('/api/v1/monitors/' + id + (method === 'check' ? '/check' : ''), token, {
        method: method === 'check' ? 'POST' : 'DELETE',
      });
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Action failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand"><div className="brand-mark" aria-hidden="true">◈</div><div><strong>GoreeCloud</strong><small>MONITOR</small></div></div>
        <div className="side-label">WORKSPACE</div>
        <a className="nav active" href="#overview">◉ <span>Overview</span></a>
        <a className="nav" href="#monitors">▤ <span>Monitors</span></a>
        <a className="nav" href="#incidents">◷ <span>Incidents</span></a>
        <div className="sidebar-bottom">Self-hosted · Development preview<br />No telemetry by default</div>
      </aside>
      <main id="overview" className="content">
        <header className="topbar"><span className="eyebrow">GOREESHIELD PRIVACY-FIRST MONITORING</span><span className="live"><i /> API: {publicData ? 'Connected' : 'Unavailable'}</span></header>
        <section className="hero">
          <div><p className="kicker">SERVICE HEALTH / OVERVIEW</p><h1>Every service.<br /><em>One clear picture.</em></h1>
          <p className="intro">A private, self-hosted view of uptime, response time, and ongoing incidents.</p></div>
          <button type="button" className="button secondary" onClick={() => void refresh()}>↻ Refresh status</button>
        </section>
        {error && <div role="alert" className="error">{error}</div>}
        <section className="stats" aria-label="Monitoring summary">
          {([['Services', counts.total, 'All visible monitors'], ['Operational', counts.up, 'Currently responding'], ['Incidents', counts.down, 'Require attention'], ['Pending', counts.pending, 'Awaiting first result']] as const).map(([label,value,sub]) =>
            <div className="stat" key={label}><p>{label}</p><strong>{value}</strong><span>{sub}</span></div>)}
        </section>
        <section className="section" id="monitors">
          <div className="section-header"><div><span className="kicker">LIVE MONITORING</span><h2>Service overview</h2></div><div className="muted">Last refreshed {lastRefreshed?.toLocaleTimeString() || '—'}</div></div>
          {monitors.length === 0 ? <div className="empty">No visible monitors yet. {admin ? 'Add your first monitor below.' : 'Sign in to manage monitors or publish a status view.'}</div> :
          <div className="monitor-list">{monitors.map(m => <article className="monitor" key={m.id}>
            <div className={'status-dot '+m.state} aria-label={m.state} />
            <div className="monitor-info"><h3>{m.name}</h3><p>{admin && m.target ? m.target : 'Published status'} · {timestamp(m.last_checked)}</p></div>
            <div className="latency">{m.last_latency_ms === null ? '—' : m.last_latency_ms + ' ms'}<small>Latency</small></div>
            <span className={'state-pill '+m.state}>{m.state}</span>
            {admin && <div className="actions"><button type="button" disabled={busy} onClick={() => void execute(m.id,'check')}>Check</button>
              <button type="button" disabled={busy} onClick={() => { if(window.confirm('Delete this monitor and its history?')) void execute(m.id,'delete'); }}>Delete</button></div>}
          </article>)}</div>}
        </section>
        <div className="columns">
          <section className="section compact" id="incidents"><span className="kicker">INCIDENT FEED</span><h2>Active incidents</h2>
            {!publicData?.incidents.length ? <p className="muted">No published active incidents.</p> :
            <ul className="incidents">{publicData.incidents.map(i => <li key={i.id}><strong>{i.monitor_name}</strong><span>Started {timestamp(i.started_at)}</span></li>)}</ul>}
          </section>
          <section className="section compact" id="settings"><span className="kicker">ACCESS & CONTROL</span><h2>{admin ? 'Add a monitor' : 'Administrator access'}</h2>
            {!admin ? <form onSubmit={authorize} className="form">
              <label htmlFor="token">API token (kept in memory only)</label><input id="token" type="password" autoComplete="off" value={token} onChange={e=>setToken(e.target.value)} minLength={32} required placeholder="Paste MONITOR_API_TOKEN"/>
              <button className="button primary" disabled={busy}>Unlock controls</button>
            </form> :
            <form onSubmit={add} className="form">
              <label htmlFor="serviceName">Service name</label><input id="serviceName" value={name} onChange={e=>setName(e.target.value)} maxLength={100} required placeholder="Example: Family Cloud"/>
              <label htmlFor="target">Probe URL</label><input id="target" value={target} onChange={e=>setTarget(e.target.value)} required placeholder="https://example.org/health"/>
              <label htmlFor="interval">Interval in seconds</label><input id="interval" value={interval} onChange={e=>setInterval(e.target.value)} type="number" min="15" max="86400" required/>
              <label className="check"><input type="checkbox" checked={isPublic} onChange={e=>setIsPublic(e.target.checked)}/> Publish this monitor's state</label>
              <div className="form-row"><button className="button primary" disabled={busy}>Add monitor</button><button className="button secondary" type="button" onClick={()=>{ setAdmin(false);setToken('');setMonitors(publicData?.monitors || []);}}>Lock</button></div>
            </form>}
          </section>
        </div>
        <footer>GoreeCloud Monitor · Development preview · GoreeShield privacy · Wardveil security · GoreeCloud Mesh interoperability</footer>
      </main>
    </div>
  );
}
