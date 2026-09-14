let state = null;
let ws = null;
let keepaliveTimer = null;
const TEMP_PREF_KEY = "bluettiWeb.temperatureDisplay";
const RUNTIME_PREF_KEY = "bluettiWeb.runtimeCalculation";
const BATTERY_CAPACITY_WH = 288;
const BATTERY_AVERAGE_WINDOW_MS = 30000;

let temperaturePreference = localStorage.getItem(TEMP_PREF_KEY) || "F";
let runtimePreference = localStorage.getItem(RUNTIME_PREF_KEY) || "Averaged";
let batteryPowerSamples = [];
let lastBatteryState = null;

function valueOrDash(v, suffix = "") {
  return (v === null || v === undefined) ? `--${suffix}` : `${v}${suffix}`;
}

function formatTemperature(c) {
  if (typeof c !== "number" || !Number.isFinite(c)) {
    if (temperaturePreference === "C") return "-- °C";
    if (temperaturePreference === "Both") return "-- °F / -- °C";
    return "-- °F";
  }

  const f = ((c * 9 / 5) + 32).toFixed(1);
  const cText = c.toFixed(1);

  if (temperaturePreference === "C") return `${cText} °C`;
  if (temperaturePreference === "Both") return `${f} °F / ${cText} °C`;
  return `${f} °F`;
}

function updateTemperatureSettingButtons() {
  const mapping = {
    F: "tempUnitF",
    C: "tempUnitC",
    Both: "tempUnitBoth",
  };
  Object.entries(mapping).forEach(([value, id]) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle("active", temperaturePreference === value);
  });
}

function setTemperaturePreference(value) {
  if (!["F", "C", "Both"].includes(value)) return;
  temperaturePreference = value;
  localStorage.setItem(TEMP_PREF_KEY, value);
  updateTemperatureSettingButtons();
  if (state) render(state);
}

function updateRuntimeSettingButtons() {
  const mapping = {
    Instantaneous: "runtimeInstant",
    Averaged: "runtimeAverage",
  };
  Object.entries(mapping).forEach(([value, id]) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle("active", runtimePreference === value);
  });
}

function setRuntimePreference(value) {
  if (!["Instantaneous", "Averaged"].includes(value)) return;
  runtimePreference = value;
  localStorage.setItem(RUNTIME_PREF_KEY, value);
  updateRuntimeSettingButtons();
  if (state) render(state);
}

function batteryPowerWatts(s) {
  if (
    typeof s.battery_voltage_v !== "number" ||
    !Number.isFinite(s.battery_voltage_v) ||
    typeof s.battery_current_a !== "number" ||
    !Number.isFinite(s.battery_current_a)
  ) {
    return null;
  }

  const watts = Math.abs(s.battery_voltage_v * s.battery_current_a);
  return Number.isFinite(watts) ? watts : null;
}

function recordBatteryPowerSample(s) {
  const direction = s.battery_state || null;
  const watts = batteryPowerWatts(s);
  const now = Date.now();

  if (direction !== lastBatteryState) {
    batteryPowerSamples = [];
    lastBatteryState = direction;
  }

  if (
    (direction === "Charging" || direction === "Discharging") &&
    watts !== null &&
    watts >= 1
  ) {
    batteryPowerSamples.push({time: now, watts});
  }

  const cutoff = now - BATTERY_AVERAGE_WINDOW_MS;
  batteryPowerSamples = batteryPowerSamples.filter(sample => sample.time >= cutoff);
}

function averagedBatteryPowerWatts() {
  if (!batteryPowerSamples.length) return null;
  return batteryPowerSamples.reduce((sum, sample) => sum + sample.watts, 0) / batteryPowerSamples.length;
}

function formatRuntimeHours(hours) {
  if (!Number.isFinite(hours) || hours < 0) return "--";
  const totalMinutes = Math.max(0, Math.round(hours * 60));
  if (totalMinutes < 1) return "<1 min";

  const days = Math.floor(totalMinutes / 1440);
  const hoursPart = Math.floor((totalMinutes % 1440) / 60);
  const minutesPart = totalMinutes % 60;

  if (days > 0) {
    return hoursPart > 0 ? `${days}d ${hoursPart}h` : `${days}d`;
  }
  if (hoursPart > 0) {
    return minutesPart > 0 ? `${hoursPart}h ${minutesPart}m` : `${hoursPart}h`;
  }
  return `${minutesPart}m`;
}

function calculateTimeRemaining(s) {
  const soc = typeof s.soc === "number" && Number.isFinite(s.soc)
    ? Math.max(0, Math.min(100, s.soc))
    : null;

  if (soc === null) {
    return {text: "--", label: "Time Remaining"};
  }

  if (s.battery_state === "Idle") {
    return {text: "--", label: "Time Remaining · Idle"};
  }

  const instantaneous = batteryPowerWatts(s);
  const averaged = averagedBatteryPowerWatts();
  const watts = runtimePreference === "Averaged"
    ? (averaged ?? instantaneous)
    : instantaneous;

  if (watts === null || watts < 1) {
    return {
      text: "--",
      label: runtimePreference === "Averaged"
        ? "Time Remaining · Averaged"
        : "Time Remaining · Instantaneous"
    };
  }

  let hours;
  let directionLabel;

  if (s.battery_state === "Charging") {
    const missingWh = BATTERY_CAPACITY_WH * ((100 - soc) / 100);
    hours = missingWh / watts;
    directionLabel = "To Full";
  } else if (s.battery_state === "Discharging") {
    const remainingWh = BATTERY_CAPACITY_WH * (soc / 100);
    hours = remainingWh / watts;
    directionLabel = "Time Remaining";
  } else {
    return {text: "--", label: "Time Remaining"};
  }

  const methodLabel = runtimePreference === "Averaged" ? "Averaged" : "Instantaneous";
  return {
    text: formatRuntimeHours(hours),
    label: `${directionLabel} · ${methodLabel}`
  };
}

function openSettings() {
  updateTemperatureSettingButtons();
  updateRuntimeSettingButtons();
  document.getElementById("settingsBackdrop").hidden = false;
  document.body.classList.add("settings-open");
}

function closeSettings() {
  document.getElementById("settingsBackdrop").hidden = true;
  document.body.classList.remove("settings-open");
}

function closeSettingsFromBackdrop(event) {
  if (event.target === event.currentTarget) closeSettings();
}

function summedWatts(a, b) {
  const values = [a, b].filter(v => typeof v === "number" && Number.isFinite(v));
  if (!values.length) return null;
  return Math.round(values.reduce((sum, v) => sum + v, 0));
}

function setControlsEnabled(enabled) {
  ["acBtn", "dcBtn", "imageAcBtn", "imageDcBtn", "modeStandard", "modeSilent", "modeTurbo"].forEach(id => {
    document.getElementById(id).disabled = !enabled;
  });
}

function render(s) {
  state = s;
  document.getElementById("model").textContent = s.model || "BLUETTI";
  document.getElementById("status").textContent = s.status || (s.connected ? "Connected" : "Disconnected");
  document.getElementById("error").textContent = s.error || "";
  document.getElementById("soc").textContent = s.soc === null || s.soc === undefined ? "--%" : `${s.soc}%`;
  document.getElementById("socBar").style.width = `${Math.max(0, Math.min(100, s.soc || 0))}%`;

  recordBatteryPowerSample(s);
  const runtime = calculateTimeRemaining(s);
  document.getElementById("timeRemaining").textContent = runtime.text;
  document.getElementById("timeRemainingLabel").textContent = runtime.label;
  const imageInput = summedWatts(s.ac_input_w, s.dc_input_w);
  const imageOutput = summedWatts(s.ac_output_w, s.dc_output_w);
  document.getElementById("imageInputWatts").textContent =
    imageInput === null ? "--" : `${imageInput}`;
  document.getElementById("imageSocValue").textContent =
    s.soc === null || s.soc === undefined ? "--" : `${s.soc}`;
  document.getElementById("imageOutputWatts").textContent =
    imageOutput === null ? "--" : `${imageOutput}`;
  document.getElementById("acInput").textContent = valueOrDash(s.ac_input_w, " W");
  document.getElementById("acOutput").textContent = valueOrDash(s.ac_output_w, " W");
  document.getElementById("dcInput").textContent = valueOrDash(s.dc_input_w, " W");
  document.getElementById("dcOutput").textContent = valueOrDash(s.dc_output_w, " W");
  document.getElementById("batteryVoltage").textContent = valueOrDash(s.battery_voltage_v, " V");
  document.getElementById("batteryCurrent").textContent = valueOrDash(s.battery_current_a, " A");
  document.getElementById("batteryState").textContent = s.battery_state || "--";
  document.getElementById("pvGeneration").textContent = valueOrDash(s.pv_generation_kwh, " kWh");
  document.getElementById("temperature").textContent = formatTemperature(s.temperature_c);
  document.getElementById("chargingMode").textContent = s.charging_mode || "--";
  document.getElementById("fan").textContent = `Fan ${s.fan_state || "--"}`;

  const fault = document.getElementById("fault");
  fault.textContent = s.fault_summary || "Fault status unavailable";
  fault.classList.toggle("fault-active", !!s.fault_active);

  const ac = document.getElementById("acBtn");
  ac.textContent = s.ac_on ? "AC ON" : "AC OFF";
  ac.classList.toggle("on", !!s.ac_on);
  document.getElementById("imageAcBtn").classList.toggle("on", !!s.ac_on);

  const dc = document.getElementById("dcBtn");
  dc.textContent = s.dc_on ? "DC ON" : "DC OFF";
  dc.classList.toggle("on", !!s.dc_on);
  document.getElementById("imageDcBtn").classList.toggle("on", !!s.dc_on);

  ["Standard", "Silent", "Turbo"].forEach(mode => {
    const id = "mode" + mode;
    document.getElementById(id).classList.toggle("active", s.charging_mode === mode);
  });

  setControlsEnabled(!!s.connected);
  document.getElementById("footer").textContent =
    `BLUETTI Web v${s.version || "?"} · Community BLE backend`;
}

async function post(url) {
  try {
    const r = await fetch(url, {method:"POST"});
    const data = await r.json();
    if (!r.ok) {
      throw new Error(data.detail || "Control request failed");
    }
    if (data.state) render(data.state);
  } catch (err) {
    document.getElementById("error").textContent = err.message || String(err);
  }
}

function refreshApp() {
  window.location.reload();
}

function toggleAC() {
  if (!state || !state.connected) return;
  post(`/api/control/ac/${state.ac_on ? 0 : 1}`);
}

function toggleDC() {
  if (!state || !state.connected) return;
  post(`/api/control/dc/${state.dc_on ? 0 : 1}`);
}

function setMode(mode) {
  if (!state || !state.connected) return;
  post(`/api/control/mode/${mode}`);
}

async function loadInitial() {
  try {
    const r = await fetch("/api/state");
    render(await r.json());
  } catch (_) {
    document.getElementById("status").textContent = "Web server offline";
  }
}

function connectWebSocket() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws`);
  ws.onmessage = ev => render(JSON.parse(ev.data));
  ws.onopen = () => {
    if (keepaliveTimer) clearInterval(keepaliveTimer);
    keepaliveTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 15000);
  };
  ws.onclose = () => {
    document.getElementById("status").textContent = "WebSocket reconnecting…";
    setTimeout(connectWebSocket, 1500);
  };
}

loadInitial();
connectWebSocket();


document.addEventListener("keydown", event => {
  if (event.key === "Escape") closeSettings();
});

updateTemperatureSettingButtons();
updateRuntimeSettingButtons();
