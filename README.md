# server-monitor

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0-lightgrey.svg)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-informational.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

Мониторинг сервера через браузер. CPU, RAM, диск, сеть и процессы в реальном времени.

## Запуск

```sh
git clone https://github.com/Laincetta/server-monitor.git
cd server-monitor
pip3 install -r requirements.txt
python3 monitor.py
```

Открыть http://localhost:5000

## Что показывает

- CPU, RAM, диск, сеть - обновляется раз в секунду
- Графики нагрузки за последние 60 секунд
- Процессы отсортированы по CPU
- Новые подключения, сессии пользователей, подозрительные процессы

## Скачать

Архив без git - на странице [Releases](https://github.com/Laincetta/server-monitor/releases).

## API

| Endpoint | Что возвращает |
|---|---|
| `GET /api/metrics` | CPU, RAM, диск, сеть + история 60с |
| `GET /api/alerts` | Оповещения |
| `GET /api/security` | Подключения и сессии |
| `GET /api/processes` | Топ 30 процессов по CPU |

## Стек

flask, psutil, chart.js

## Лицензия

[MIT](LICENSE)
