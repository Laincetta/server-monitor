# server-monitor

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0-lightgrey.svg)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-informational.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

Real-time server monitoring via web dashboard. Tracks CPU, RAM, disk, network, processes and security events.

![dashboard preview](https://raw.githubusercontent.com/Laincetta/server-monitor/main/docs/preview.png)

## Features

- Live metrics — CPU, RAM, disk, network updated every second
- 60-second history charts
- Security tab — new connections, logins, suspicious processes
- Process table sorted by CPU usage
- Works on Linux and Windows

## Quick start

```sh
git clone https://github.com/Laincetta/server-monitor.git
cd server-monitor
pip3 install -r requirements.txt
python3 monitor.py
```

Open **http://localhost:5000**

## Download

Grab the latest release from the [Releases](https://github.com/Laincetta/server-monitor/releases) page — no git required.

## API

| Endpoint | Description |
|---|---|
| `GET /api/metrics` | CPU, RAM, disk, network + 60s history |
| `GET /api/alerts` | Performance alerts |
| `GET /api/security` | Connections, sessions, suspicious processes |
| `GET /api/processes` | Top 30 processes by CPU |

## Stack

- [Flask](https://flask.palletsprojects.com/) — backend
- [psutil](https://github.com/giampaolo/psutil) — system metrics
- [Chart.js](https://www.chartjs.org/) — charts

## License

[MIT](LICENSE)
