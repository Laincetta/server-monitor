# Система мониторинга сервера

Веб-приложение для мониторинга ресурсов сервера в реальном времени.

## Стек

- **Backend**: Python 3, Flask, psutil
- **Frontend**: HTML/CSS/JS, Chart.js 4.4, Geist font

## Возможности

- Мониторинг CPU, RAM, диска, сети в реальном времени
- Графики нагрузки за последние 60 секунд
- Система оповещений (warning / critical пороги)
- Вкладка безопасности: новые подключения, подозрительные процессы, сессии
- Таблица процессов с сортировкой по CPU/RAM

## Запуск

### Linux

```bash
pip install -r requirements.txt
python monitor.py
```

Открыть браузер: `http://localhost:5000`

### Windows

```bat
run.bat
```

## API

| Endpoint | Описание |
|----------|----------|
| `GET /api/metrics` | CPU, RAM, диск, сеть |
| `GET /api/alerts` | Активные оповещения |
| `GET /api/security` | Подключения, процессы, сессии |
| `GET /api/processes` | Список процессов |

## Структура

```
monitor/
├── monitor.py          # Flask-приложение
├── requirements.txt    # Зависимости
├── run.sh              # Запуск на Linux
├── run.bat             # Запуск на Windows
└── templates/
    └── dashboard.html  # Фронтенд
```
