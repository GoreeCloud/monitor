const columns = ["Service", "Group", "Status", "24h uptime (%)", "Latency (ms)", "Last observation UTC"];
function csvCell(value) {
  let text = value === null || value === undefined ? "" : String(value);
  // Spreadsheet apps interpret untrusted values starting with these characters as formulas.
  if (/^[\s]*[=+\-@\t\r]/.test(text)) text = "'" + text;
  return '"' + text.replaceAll('"','""') + '"';
}
export function buildMonitorCsv(monitors) {
  if (!Array.isArray(monitors)) throw new TypeError("Monitors must be an array");
  const rows = [columns,...monitors.map(m=>[
    m.name, m.group, m.state, m.uptime24, m.ping, m.observedAt
  ])];
  return "\uFEFF" + rows.map(row=>row.map(csvCell).join(",")).join("\r\n") + "\r\n";
}
