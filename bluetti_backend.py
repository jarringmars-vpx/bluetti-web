from __future__ import annotations

import asyncio
import os
import time
from typing import Any


class BluettiCommunityService:
    """
    One persistent encrypted Community-library BLE session for BLUETTI Web.

    The browser never talks BLE directly. This service owns the BLE connection,
    polling, writes, verification, and normalized telemetry.
    """

    MODEL = "EL30V2"

    def __init__(self) -> None:
        self._stop = False
        self._revision = 0
        self._session = None
        self._control_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        self._pending_controls: dict[int, int] = {}
        self._control_holds: dict[int, dict[str, Any]] = {}
        self._control_hold_seconds = 2.0
        self._control_hold_required_matches = 2

        self._state: dict[str, Any] = {
            "connected": False,
            "model": self.MODEL,
            "soc": None,
            "ac_on": False,
            "dc_on": False,
            "ac_input_w": None,
            "ac_output_w": None,
            "dc_input_w": None,
            "dc_output_w": None,
            "temperature_c": None,
            "charging_mode": None,
            "battery_voltage_v": None,
            "battery_current_a": None,
            "battery_state": None,
            "pv_generation_kwh": None,
            "fan_state": None,
            "fault_active": False,
            "fault_summary": "Unknown",
            "status": "Starting Community BLE service…",
            "error": "",
            "updated_at": time.time(),
        }

    @property
    def revision(self) -> int:
        return self._revision

    def stop(self) -> None:
        self._stop = True

    def snapshot(self, version: str) -> dict[str, Any]:
        data = dict(self._state)
        data["version"] = version
        return data

    def _update(self, **changes: Any) -> None:
        changed = False
        for key, value in changes.items():
            if self._state.get(key) != value:
                self._state[key] = value
                changed = True
        self._state["updated_at"] = time.time()
        if changed:
            self._revision += 1

    async def queue_control(self, control: str, value: Any) -> None:
        if not self._state.get("connected"):
            raise RuntimeError("BLUETTI device is not connected.")

        if control == "ac":
            desired = 1 if int(value) else 0
            self._pending_controls[2011] = desired
            self._update(ac_on=bool(desired), status=f"Sending AC {'ON' if desired else 'OFF'}…")
        elif control == "dc":
            desired = 1 if int(value) else 0
            self._pending_controls[2012] = desired
            self._update(dc_on=bool(desired), status=f"Sending DC {'ON' if desired else 'OFF'}…")
        elif control == "mode":
            modes = {"Standard": 0, "Silent": 1, "Turbo": 2}
            if value not in modes:
                raise ValueError(f"Unsupported charging mode: {value}")
            desired = modes[value]
            self._pending_controls[2020] = desired
            self._update(charging_mode=value, status=f"Sending Charging Mode {value}…")
        else:
            raise ValueError(f"Unknown control: {control}")

        await self._control_queue.put((control, value))

    async def run(self) -> None:
        print("[BLUETTI] Community BLE service task started.")
        while not self._stop:
            session = None
            try:
                print("[BLUETTI] Searching for EL30V2...")
                device = await self._resolve_device()
                print("[BLUETTI] EL30V2 found.")
                self._update(status=f"Connecting to {self.MODEL} over Community BLE…", error="")
                print("[BLUETTI] Opening encrypted DeviceSession...")
                session = await self._open_session(device)
                print("[BLUETTI] DeviceSession ready.")
                self._session = session
                self._update(
                    connected=True,
                    status=f"Community BLE connected — live data from {self.MODEL}",
                    error="",
                )
                print("[BLUETTI] Polling started.")
                await self._poll_loop(session)
                print("[BLUETTI] Polling stopped.")
            except asyncio.CancelledError:
                print("[BLUETTI] Community BLE service task cancelled.")
                raise
            except Exception as exc:
                print(f"[BLUETTI] Service exception: {type(exc).__name__}: {exc}")
                self._update(
                    connected=False,
                    status=f"Community BLE disconnected — reconnecting to {self.MODEL}…",
                    error=str(exc),
                )
            finally:
                self._session = None
                if session is not None:
                    try:
                        print("[BLUETTI] Disconnecting DeviceSession...")
                        await session.disconnect()
                        print("[BLUETTI] DeviceSession disconnected.")
                    except asyncio.CancelledError:
                        print("[BLUETTI] Disconnect cancelled during shutdown.")
                        raise
                    except Exception as exc:
                        print(f"[BLUETTI] Disconnect exception: {type(exc).__name__}: {exc}")

            if not self._stop:
                await asyncio.sleep(2.0)

    async def _resolve_device(self):
        try:
            from bleak import BleakScanner
        except ImportError as exc:
            raise RuntimeError("bleak is not installed.") from exc

        configured = os.environ.get("BLUETTI_BLE_ADDRESS", "").strip()
        if configured:
            self._update(status=f"Finding {self.MODEL} at configured BLE address…")
            device = await BleakScanner.find_device_by_address(configured, timeout=8.0)
            if device is None:
                raise RuntimeError(f"{self.MODEL} was not found at the configured BLE address.")
            return device

        self._update(status=f"Searching for {self.MODEL} over Bluetooth…")
        discovered = await BleakScanner.discover(timeout=8.0, return_adv=True)
        target = self.MODEL.upper()
        candidates = []

        for device, adv in discovered.values():
            names = [
                (getattr(device, "name", None) or "").strip(),
                (getattr(adv, "local_name", None) or "").strip(),
            ]
            names = [name for name in names if name]
            if not names:
                continue
            exact = any(name.upper().startswith(target) for name in names)
            fuzzy = any(target in name.upper() for name in names)
            if exact or fuzzy:
                rssi = getattr(adv, "rssi", None)
                if not isinstance(rssi, (int, float)):
                    rssi = -9999
                candidates.append((1 if exact else 0, rssi, device))

        if not candidates:
            raise RuntimeError(f"No {self.MODEL} Bluetooth device found.")

        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidates[0][2]

    async def _open_session(self, device):
        try:
            from bluetti_bt_lib.bluetooth.device_session import DeviceSession, DeviceSessionConfig
            from bluetti_bt_lib.devices import EL30V2
        except ImportError as exc:
            raise RuntimeError(
                "The modified Community bluetti_bt_lib is not installed. "
                "Install the el30v2-enhancements checkout in editable mode."
            ) from exc

        loop = asyncio.get_running_loop()
        session = DeviceSession(
            getattr(device, "address", None),
            EL30V2(),
            loop.create_future,
            config=DeviceSessionConfig(
                timeout=60,
                use_encryption=True,
                command_timeout=0.5,
                command_retries=1,
                retry_delay=0.4,
            ),
        )
        await session.connect()
        return session

    async def _poll_loop(self, session) -> None:
        intervals = {
            "control": 0.35,
            "power": 0.75,
            "battery": 1.0,
            "temperature": 2.5,
            "fault": 2.0,
            "mode": 10.0,
            "pv_generation": 60.0,
        }
        next_due = {name: 0.0 for name in intervals}
        consecutive_failures = 0

        while not self._stop:
            if not session.is_connected:
                raise RuntimeError("Bluetooth connection was lost.")
            if not session.is_ready:
                raise RuntimeError("Encrypted Community BLE session is not ready.")

            await self._process_one_control(session)

            now = time.monotonic()
            due = [name for name, when in next_due.items() if now >= when]
            if not due:
                await asyncio.sleep(0.03)
                continue

            due.sort(key=lambda name: {
                "control": 0, "power": 1, "battery": 2, "temperature": 3,
                "fault": 4, "mode": 5, "pv_generation": 6,
            }[name])

            for group in due:
                if self._stop:
                    return
                try:
                    if group == "control":
                        values = await session.read_registers(2011, 2)
                        self._apply_control(values)
                    elif group == "power":
                        values = await session.read_registers(140, 10)
                        self._update(
                            dc_output_w=float(values[140]),
                            ac_output_w=float(values[142]),
                            dc_input_w=float(values[144]),
                            ac_input_w=float(values[146]),
                        )
                    elif group == "battery":
                        values = {}
                        values.update(await session.read_registers(102, 1))
                        values.update(await session.read_registers(6003, 2))
                        values.update(await session.read_registers(6009, 1))
                        self._update(
                            soc=max(0, min(100, int(values[102]))),
                            battery_voltage_v=round(float(values[6003]) / 100.0, 2),
                            battery_current_a=round(float(values[6004]) / 10.0, 1),
                            battery_state={0: "Idle", 1: "Charging", 2: "Discharging"}.get(
                                int(values[6009]), f"Unknown ({int(values[6009])})"
                            ),
                        )
                    elif group == "temperature":
                        values = {}
                        values.update(await session.read_registers(1153, 1))
                        values.update(await session.read_registers(6350, 1))
                        raw_fan = int(values[6350]) & 0xFFFF
                        self._update(
                            temperature_c=round(float(values[1153]) / 10.0, 1),
                            fan_state="Off" if raw_fan == 0 else "Active",
                        )
                    elif group == "fault":
                        values = {}
                        values.update(await session.read_registers(133, 1))
                        values.update(await session.read_registers(137, 1))
                        active = bool(int(values[133]) or int(values[137]))
                        self._update(
                            fault_active=active,
                            fault_summary="Fault Active" if active else "No Faults",
                        )
                    elif group == "mode":
                        values = await session.read_registers(2020, 1)
                        mode_value = self._filtered_control_value(2020, int(values[2020]))
                        if mode_value is not None:
                            self._update(charging_mode=self._mode_name(mode_value))
                    elif group == "pv_generation":
                        values = await session.read_registers(154, 1)
                        self._update(pv_generation_kwh=round(float(values[154]) / 10.0, 1))

                    consecutive_failures = 0
                    self._update(
                        connected=True,
                        status=f"Community BLE connected — live data from {self.MODEL}",
                        error="",
                    )
                except Exception as exc:
                    if not session.is_connected or not session.is_ready:
                        raise
                    consecutive_failures += 1
                    self._update(
                        connected=True,
                        status=f"Community BLE connected — retrying {group}",
                        error=f"Transient {group} read failure: {exc}",
                    )
                    if consecutive_failures >= 3:
                        raise RuntimeError(
                            f"{consecutive_failures} consecutive BLE read failures; "
                            f"last group={group}: {exc}"
                        ) from exc
                finally:
                    next_due[group] = time.monotonic() + intervals[group]

            await asyncio.sleep(0.01)

    def _filtered_control_value(self, register: int, polled_value: int):
        now = time.monotonic()
        if register in self._pending_controls:
            return None

        hold = self._control_holds.get(register)
        if hold is None:
            return int(polled_value)

        desired = int(hold["value"])
        if int(polled_value) == desired:
            hold["matches"] = int(hold.get("matches", 0)) + 1
            if hold["matches"] >= self._control_hold_required_matches:
                self._control_holds.pop(register, None)
                return desired
            return None

        if now < float(hold["expires"]):
            hold["matches"] = 0
            return None

        self._control_holds.pop(register, None)
        return int(polled_value)

    def _mark_verified(self, register: int, value: int) -> None:
        if self._pending_controls.get(register) == int(value):
            self._pending_controls.pop(register, None)
        self._control_holds[register] = {
            "value": int(value),
            "matches": 0,
            "expires": time.monotonic() + self._control_hold_seconds,
        }

    def _mark_failed(self, register: int) -> None:
        self._pending_controls.pop(register, None)
        self._control_holds.pop(register, None)

    def _apply_control(self, values: dict[int, int]) -> None:
        ac_value = self._filtered_control_value(2011, int(values[2011]))
        dc_value = self._filtered_control_value(2012, int(values[2012]))
        changes = {}
        if ac_value is not None:
            changes["ac_on"] = bool(ac_value)
        if dc_value is not None:
            changes["dc_on"] = bool(dc_value)
        if changes:
            self._update(**changes)

    async def _process_one_control(self, session) -> None:
        try:
            control, value = self._control_queue.get_nowait()
        except asyncio.QueueEmpty:
            return

        if control == "ac":
            field, requested, register, count = "ctrl_ac", bool(int(value)), 2011, 2
            label = "AC Output"
        elif control == "dc":
            field, requested, register, count = "ctrl_dc", bool(int(value)), 2012, 2
            label = "DC Output"
        elif control == "mode":
            field = "ctrl_charging_mode"
            requested = {"Standard": 0, "Silent": 1, "Turbo": 2}[value]
            register, count, label = 2020, 1, "Charging Mode"
        else:
            return

        try:
            await session.write(field, requested)
            readback = await session.read_registers(register if register == 2020 else 2011, count)

            actual_raw = int(readback[register])
            desired_raw = int(requested) if register == 2020 else (1 if bool(requested) else 0)
            if actual_raw != desired_raw:
                raise RuntimeError(
                    f"{label} readback mismatch: requested={desired_raw}, actual={actual_raw}"
                )

            if register == 2011:
                self._update(ac_on=bool(actual_raw))
            elif register == 2012:
                self._update(dc_on=bool(actual_raw))
            else:
                self._update(charging_mode=self._mode_name(actual_raw))

            self._mark_verified(register, actual_raw)
            self._update(status=f"{label} confirmed.", error="")
        except Exception as exc:
            self._mark_failed(register)
            self._update(
                status=f"{label} write failed; polling will verify current state.",
                error=str(exc),
            )
            if not session.is_connected or not session.is_ready:
                raise

    @staticmethod
    def _mode_name(value: int) -> str:
        return {0: "Standard", 1: "Silent", 2: "Turbo"}.get(int(value), f"Unknown ({int(value)})")
