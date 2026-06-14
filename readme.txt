Локальный запуск Velojol
=======================

Команды выполнять из папки проекта:

cd /Users/ruslanfatihov/Desktop/Projects/velojol-4.0

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt

mkdir -p instance

flask --app run.py setup-local

python3 run.py

После запуска сайт будет доступен по адресу:
http://127.0.0.1:5500

Если нужен администратор, после инициализации базы можно выполнить:
flask --app run.py create-admin

Если установка раньше упала с ошибкой по зависимостям, выполните заново:
pip install -r requirements.txt

Отдельные команды Flask, если нужны вручную:
flask --app run.py init-db
flask --app run.py seed-cities
