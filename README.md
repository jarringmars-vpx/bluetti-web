BLUETTI Web v0.1.0
==================

Purpose
-------
This first prototype validates the local-web architecture from an iPhone
before connecting it to the real BLUETTI Community backend.

It currently uses MOCK telemetry and MOCK controls only.
It DOES NOT send BLE commands to the EL30V2.

Install
-------
1. Extract this folder on the Windows PC, for example:
   C:\Users\clay\bluetti-web

2. Run:
   install_dependencies.bat

3. Run:
   run_web_app.bat

4. If Windows Firewall asks, allow Python/Uvicorn on PRIVATE networks only.

5. On the Windows PC:
   ipconfig

   Find the IPv4 address of the Wi-Fi/Ethernet adapter used by the iPhone.

6. With the iPhone on the same Wi-Fi network, open Safari:
   http://<PC-IP>:8080

What to test
------------
- Page loads on iPhone.
- SOC and cards fit the phone screen.
- AC/DC buttons change immediately.
- Charging Mode changes.
- PV input and temperature drift slightly every 2 seconds without page reload.
  That proves WebSocket push updates from Windows to Safari.

Security
--------
Private LAN only. Do not expose TCP port 8080 directly to the Internet.

Next version
------------
Replace mock state/control functions with the existing Community DeviceSession:
- R102 SOC
- R140/R142/R144/R146 power flow
- R1153 temperature
- R154 PV generation
- R6003/R6004/R6009 battery details
- R2011/R2012/R2020 state + controls
