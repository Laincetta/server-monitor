# server-monitor

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0-lightgrey.svg)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-informational.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

Веб-дашборд для мониторинга сервера в реальном времени. Отслеживает CPU, RAM, диск, сеть, процессы и события безопасности.

## Возможности

- Живые метрики — CPU, RAM, диск, сеть обновляются каждую секунду
- Графики истории за последние 60 секунд
- Вкладка безопасности — новые подключения, входы пользователей, подозрительные процессы
- Таблица процессов, отсортированная по загрузке CPU
- Работает на Linux и Windows

## Быстрый старт

```sh
git clone https://github.com/Laincetta/server-monitor.git
cd server-monitor
pip3 install -r requirements.txt
python3 monitor.py
```

Открыть **http://localhost:5000**

## Скачать

Готовый архив без git — на странице [Releases](https://github.com/Laincetta/server-monitor/releases).

## API

| Endpoint | Описание |
|---|---|
| `GET /api/metrics` | CPU, RAM, диск, сеть + история 60с |
| `GET /api/alerts` | Оповещения о производительности |
| `GET /api/security` | Подключения, сессии, подозрительные процессы |
| `GET /api/processes` | Топ 30 процессов по CPU |

## Стек

- [Flask](https://flask.palletsprojects.com/) — бэкенд
- [psutil](https://github.com/giampaolo/psutil) — системные метрики
- [Chart.js](https://www.chartjs.org/) — графики

## Лицензия

[MIT](LICENSE)
