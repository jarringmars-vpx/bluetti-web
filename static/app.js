let state = null;
let ws = null;
let keepaliveTimer = null;

function fToDisplay(c) {
  return ((c * 9 / 5) + 32).toFixed(1) + " °F";
}

function render(s) {
  state = s;
  document.getElementById("model").textContent = s.model || "BLUETTI";
  document.getElementById("status").textContent = s.connected ? "Connected" : "Disconnected";
  document.getElementById("soc").textContent = `${s.soc ?? "--"}%`;
  document.getElementById("socBar").style.width = `${Math.max(0, Math.min(100, s.soc || 0))}%`;
  document.getElementById("acInput").textContent = `${s.ac_input_w ?? "--"} W`;
  document.getElementById("acOutput").textContent = `${s.ac_output_w ?? "--"} W`;
  document.getElementById("dcInput").textContent = `${s.dc_input_w ?? "--"} W`;
  document.getElementById("dcOutput").textContent = `${s.dc_output_w ?? "--"} W`;
  document.getElementById("batteryVoltage").textContent = `${s.battery_voltage_v ?? "--"} V`;
  document.getElementById("batteryCurrent").textContent = `${s.battery_current_a ?? "--"} A`;
  document.getElementById("batteryState").textContent = s.battery_state || "--";
  document.getElementById("pvGeneration").textContent = `${s.pv_generation_kwh ?? "--"} kWh`;
  document.getElementById("temperature").textContent =
    typeof s.temperature_c === "number" ? fToDisplay(s.temperature_c) : "-- °F";
  document.getElementById("chargingMode").textContent = s.charging_mode || "--";

  const ac = document.getElementById("acBtn");
  ac.textContent = s.ac_on ? "AC ON" : "AC OFF";
  ac.classList.toggle("on", !!s.ac_on);

  const dc = document.getElementById("dcBtn");
  dc.textContent = s.dc_on ? "DC ON" : "DC OFF";
  dc.classList.toggle("on", !!s.dc_on);
}

async function post(url) {
  const r = await fetch(url, {method:"POST"});
  const data = await r.json();
  if (data.state) render(data.state);
}

function toggleAC() {
  if (!state) return;
  post(`/api/control/ac/${state.ac_on ? 0 : 1}`);
}

function toggleDC() {
  if (!state) return;
  post(`/api/control/dc/${state.dc_on ? 0 : 1}`);
}

function setMode(mode) {
  post(`/api/control/mode/${mode}`);
}

async function loadInitial() {
  try {
    const r = await fetch("/api/state");
    render(await r.json());
  } catch (_) {
    document.getElementById("status").textContent = "Offline";
  }
}

function connectWebSocket() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws`);
  ws.onmessage = ev => render(JSON.parse(ev.data));
  ws.onopen = () => {
    document.getElementById("status").textContent = "Connected";
    if (keepaliveTimer) clearInterval(keepaliveTimer);
    keepaliveTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 15000);
  };
  ws.onclose = () => {
    document.getElementById("status").textContent = "Reconnecting…";
    setTimeout(connectWebSocket, 1500);
  };
}

loadInitial();
connectWebSocket();
