# Velojol Review

Дата ревью: 2026-04-10


// To do
- Главная
Список городов наполнить и сделать нормально


Проверка статуса: 2026-04-12

- По текущему состоянию кода пунктов, которые можно однозначно отметить как `Сделано`, не найдено.

## 1. Scope

Это ревью сделано по всему проекту в текущем workspace: Flask backend, SQLAlchemy models, admin/public/auth routes, шаблоны, JS/CSS, конфиг, зависимости, миграции и локальная SQLite база.

Что я реально проверил:

- структуру репозитория и git-состояние
- конфиг и точку входа
- все модели
- все основные роуты `auth`, `main`, `public`, `admin/*`
- ключевые шаблоны и JS
- локальную схему SQLite (`instance/velojol.db`)
- наличие тестов и миграций

Что не удалось полноценно проверить:

- запуск приложения через Flask в этом окружении, потому что зависимости не установлены (`ModuleNotFoundError: No module named 'flask'`)
- e2e-поведение в браузере

## 2. Что проект сейчас умеет

По коду проект пытается реализовать такие механики:

- публичный каталог городов
- страницу города с картой и списком велодорожек
- добавление велодорожки пользователем или анонимно
- модерацию велодорожек через admin
- регистрацию по email-коду
- восстановление пароля по email-коду
- профиль пользователя и список его велодорожек
- admin-управление городами
- admin-управление пользователями
- загрузку фото для велодорожек и аватаров
- вычисление длины велодорожки и агрегатов по городу

По факту часть механик реализована частично, часть расходится между backend, БД и frontend, часть небезопасна для production.

## 3. Снимок состояния проекта

- Стек: Flask, SQLAlchemy, Flask-Login, Flask-Migrate, Pillow, Mapbox GL JS, Leaflet.
- Локальная БД содержит: `3` users, `2` cities, `7` bikelanes, `0` notifications, `4` verification_codes.
- В репозитории есть tracked SQLite база `instance/velojol.db`, backup-файлы и временные скрипты.
- Тестов нет.
- Версионируемых миграций нет.

## 4. Критические проблемы

### CRITICAL-1. Код, модель и БД разъехались по полю `distance`

Файлы:

- `app/routes/main.py:137`
- `app/routes/main.py:141`
- `app/routes/main.py:216`
- `app/models/bikelane.py`
- `instance/velojol.db` schema

Проблема:

- В `main.add_bikelane()` используется `bikelane.distance`.
- В модели `BikeLane` поля `distance` нет.
- В локальной таблице `bikelanes` колонки `distance` тоже нет.

Последствия:

- значение дистанции не хранится как часть модели и не попадает в схему
- backend работает с фантомным атрибутом Python-объекта
- код вводит в заблуждение и ломает консистентность доменной модели

### CRITICAL-2. Валидация геометрии вызывает несуществующий метод

Файл:

- `app/routes/main.py:261`

Проблема:

- вызывается `temp_bikelane.calculate_distance()`
- такого метода в `BikeLane` нет, есть только `calculate_length()`

Последствия:

- часть серверной валидации фактически мертвая
- ошибки маскируются `except Exception: pass`
- невалидные данные могут пройти дальше без явного сигнала

### CRITICAL-3. Stored XSS через `|safe` и небезопасный `innerHTML`

Файлы:

- `app/templates/public/city.html:215`
- `app/templates/admin/view_bikelane.html:115`
- `app/templates/admin/edit_bikelane.html:92`
- `app/static/js/city_map_mapbox.js:662`
- `app/static/js/city_map_mapbox.js:342`
- `app/static/js/city_map.js:635`

Проблема:

- JSON и geometry вставляются в `<script>` через `|safe`
- данные из БД дальше рендерятся через `innerHTML`
- заголовок, описание и другие строки не санитизируются

Последствия:

- вредоносная строка в названии/описании велодорожки может превратиться в XSS
- это особенно опасно для публичной страницы города и админки

## 5. High severity

### HIGH-1. Во всем приложении отсутствует CSRF-защита

Файлы:

- `app/routes/auth.py`
- `app/routes/main.py`
- `app/routes/admin/*.py`
- формы в `app/templates/**`

Проблема:

- нет Flask-WTF, CSRF token и серверной CSRF-проверки
- все POST-формы и JSON endpoints уязвимы к cross-site request forgery

Риск:

- удаление велодорожек
- бан/разбан пользователей
- смена прав администратора
- отправка уведомлений
- регистрация и парольные сценарии

### HIGH-2. Open redirect в логине

Файл:

- `app/routes/auth.py:269`

Проблема:

- `next_page` редиректится без проверки домена и схемы

Последствие:

- можно использовать login flow для перенаправления пользователя на внешний вредоносный URL

### HIGH-3. Секреты и production-настройки небезопасны

Файлы:

- `config.py:13`
- `config.py:28`
- `run.py:28`
- `run.py:35`
- `run.py:70`
- `app/static/js/city_map_mapbox.js:6`

Проблема:

- fallback `SECRET_KEY` захардкожен
- `SESSION_COOKIE_SECURE = False`
- debug mode захардкожен в `app.run(debug=True)`
- deploy-команда создает админа `admin@velojol.com / admin123`
- Mapbox token хранится прямо в клиентском JS

Последствия:

- сессионная безопасность в production неготова
- дефолтный админ-креденшел может попасть в реальный контур
- утечки и misuse токенов вероятны

### HIGH-4. Конфликт маршрутов на `/`

Файлы:

- `app/routes/main.py:12`
- `app/routes/public.py:11`
- `app/__init__.py:37`
- `app/__init__.py:44`

Проблема:

- и `main.index`, и `public.cities` объявлены на `/`
- blueprints регистрируются оба

Последствия:

- поведение зависит от порядка регистрации
- часть публичного функционала может быть фактически недостижима
- архитектура URL не определена однозначно

### HIGH-5. Отсутствует нормальный migration workflow

Файлы:

- `.gitignore:17`
- `migrations/`
- `run.py:25`
- `run.py:43`

Проблема:

- весь каталог `migrations/` игнорируется git'ом
- versioned migration scripts не коммитятся
- при этом код одновременно использует и `upgrade()`, и `db.create_all()`

Последствия:

- схема БД не воспроизводима между окружениями
- drift между моделью и БД уже произошел
- новые разработчики не смогут надежно поднять проект

### HIGH-6. Валидация вынесена в отдельный модуль, но реально несовместима с приложением

Файлы:

- `app/utils/validators.py:14`
- `app/utils/validators.py:26`
- `app/utils/validators.py:34`
- `app/utils/validators.py:84`
- `config.py`

Проблема:

- валидатор читает `MIN_TITLE_LENGTH`, `MIN_DESCRIPTION_LENGTH`, `MAX_VIDEOS_PER_BIKELANE`
- этих ключей в `Config` нет
- типы дорожек в валидаторе (`separated_lane`, `bike_path`, `shared_lane`...) не совпадают с реальными (`lane`, `bollards`, `separated`, `shared`)

Последствия:

- валидатор нельзя считать source of truth
- при его полноценном использовании проект начнет падать

### HIGH-7. Email-подсистема не доведена до production-ready состояния

Файлы:

- `app/utils/email_sender.py:2`
- `requirements.txt:1`
- `requirements.txt:8`

Проблема:

- код использует `flask_mail`, но `Flask-Mail` отсутствует в `requirements.txt`
- `Flask-Migrate` продублирован дважды
- отправка почты идет через голые `Thread(...)` без очереди, retry, timeout policy и логирования уровня приложения
- ошибки печатаются в `print`, а не в logger

Последствия:

- окружение поднимается не детерминированно
- email-флоу нестабилен
- проблемы доставки трудно диагностировать

### HIGH-8. Доменные транзакции разорваны commit'ами внутри model methods

Файлы:

- `app/models/verification.py:59`
- `app/models/verification.py:69`
- `app/models/verification.py:78`
- `app/routes/auth.py:197`
- `app/routes/auth.py:356`

Проблема:

- `VerificationCode.increment_attempts()`, `increment_request_count()` и `verify()` сами делают `db.session.commit()`
- роуты вокруг них тоже коммитят

Последствия:

- теряется атомарность
- сложно управлять rollback
- состояния пользователя и verification code могут коммититься не как единая операция

## 6. Medium severity

### MEDIUM-1. Фронтенд страницы города содержит битую верстку

Файл:

- `app/templates/public/city.html:33`
- `app/templates/public/city.html:187`

Проблема:

- сломан атрибут `class="vstack >`
- у модалки не закрыт один из контейнеров

Последствия:

- unpredictable DOM
- возможные проблемы со стилями, overlay и JS-селекторами

### MEDIUM-2. `display_avatar` пишет DEBUG в stdout на каждый рендер

Файл:

- `app/models/user.py:55`
- `app/models/user.py:61`
- `app/models/user.py:72`

Проблема:

- property модели содержит `print(...)`

Последствия:

- шум в логах
- лишняя побочка в view layer

### MEDIUM-3. Обработка изображений портит соответствие формата и расширения

Файл:

- `app/utils/file_handler.py:23`
- `app/utils/file_handler.py:65`

Проблема:

- расширение файла сохраняется исходное
- при этом изображение всегда перезаписывается как JPEG

Пример:

- пользователь загрузил `.png`
- файл остается с расширением `.png`
- но содержимое становится JPEG

Последствия:

- неверный mime/format contract
- проблемы при отдаче файлов, кэшировании и повторной обработке

### MEDIUM-4. Админская редактура велодорожки содержит copy-paste ошибки

Файл:

- `app/routes/admin/bikelanes.py:69`
- `app/routes/admin/bikelanes.py:74`
- `app/routes/admin/bikelanes.py:79`
- `app/routes/admin/bikelanes.py:84`

Проблема:

- один и тот же блок обновления geometry продублирован 4 раза

Последствия:

- признак неаккуратного редактирования
- повышает риск регрессий и скрытых дефектов

### MEDIUM-5. Notifications-функционал не доведен до рабочего состояния

Файлы:

- `app/models/notification.py:51`
- `app/routes/admin/users.py:71`
- `app/routes/admin/bikelanes.py`

Проблема:

- есть только helper для approval, но он нигде не вызывается
- unread count помечен `TODO`
- локальная БД содержит `0` notifications
- reject/pending-сценарии как доменные события не доведены

Последствия:

- механика уведомлений существует номинально, но не как реальный продуктовый контур

### MEDIUM-6. Города хранятся одновременно в БД и в `cities.json`

Файлы:

- `app/routes/admin/cities.py:171`
- `app/models/bikelane.py:247`
- `app/static/data/cities.json`

Проблема:

- часть данных идет из БД
- часть отображения и fallback-логики идет через JSON-файл

Последствия:

- два источника правды
- возможны расхождения между admin-изменениями, API и frontend

### MEDIUM-7. В админке и страницах логина много inline JS/CSS

Файлы:

- `app/templates/auth/login.html`
- `app/templates/auth/verify_email.html`
- `app/templates/admin/edit_bikelane.html`
- `app/templates/admin/view_bikelane.html`

Проблема:

- логика и стили размазаны по шаблонам
- нет четкой границы между presentation и behavior

Последствия:

- хуже поддерживаемость
- сложнее тестировать и переиспользовать

### MEDIUM-8. Поиск и фильтры реализованы в двух местах сразу

Файлы:

- `app/routes/public.py`
- `app/static/js/city_map_mapbox.js`

Проблема:

- фильтрация есть и на сервере, и отдельно на клиенте
- клиентские фильтры работают уже по загруженному snapshot

Последствия:

- возможна разница между SSR-списком и client-side состоянием
- при росте данных фронтенд будет перегружаться лишним JSON

## 7. Low severity / hygiene

### LOW-1. Репозиторий захламлен backup и временными файлами

Найдено:

- `app/routes/main.py.backup`
- `app/routes/main.py.backup2`
- `app/__init__.py.backup`
- `app/static/js/city_map_mapbox.js.bak`
- `temp_finishLine.js`
- `temp_update.js`

Это снижает читаемость и повышает риск редактирования не того файла.

### LOW-2. `README.md` пустой

Файл:

- `README.md`

В проекте нет документации по запуску, зависимостям, миграциям, env, ролям и деплою.

### LOW-3. В коде много шумных `console.log`

Файлы:

- `app/static/js/add_bikelane.js`
- `app/static/js/city_map_mapbox.js`
- `app/static/js/city_map.js`
- `app/static/js/cities.js`

Для dev это терпимо, но в текущем объеме это уже шум, а не отладка.

## 8. Что не готово / недоделано

- Нет тестов вообще.
- Нет воспроизводимой схемы миграций.
- Нет production-ready security baseline.
- Нет законченного notification flow.
- Нет единого источника правды для городов.
- Нет цельной валидационной схемы для bikelane domain.
- Нет нормального error handling и observability policy.
- Нет завершенного dependency management.
- Нет нормального onboarding через `README.md`.
- Нет clean repository discipline.

## 9. Что сделано неправильно концептуально

- Доменная модель и схема БД развиваются несинхронно.
- Validation, persistence и presentation дублируют друг друга вместо единого контракта.
- Роуты содержат слишком много бизнес-логики.
- Model methods сами коммитят транзакции.
- Frontend получает сырые данные и рендерит их небезопасно.
- В проекте одновременно используются БД, JSON-файлы и шаблонные вычисления как конкурирующие источники состояния.
- Admin и public контуры не отделены по качеству кода: и там и там много ad-hoc решений.

## 10. Приоритетный порядок исправления

1. Остановить drift схемы: убрать фантомный `distance`, восстановить согласованность model <-> DB <-> forms <-> API.
2. Вырезать XSS и внедрить CSRF.
3. Убрать open redirect, debug mode, дефолтный secret/admin creds.
4. Нормализовать migrations: перестать игнорировать `migrations/`, зафиксировать version scripts.
5. Привести validation contract к одному источнику правды.
6. Разделить domain logic, persistence logic и template/JS rendering.
7. Завершить notifications как продуктовую механику, либо удалить мертвый код.
8. Привести uploads, images и static contract к корректной обработке форматов.
9. Почистить репозиторий и написать нормальный `README.md`.
10. После этого только запускать полноценное e2e и покрывать тестами.

## 11. Итог

Проект не выглядит как “готовый к продакшену” даже на уровне внутреннего alpha. Базовая идея и часть пользовательских сценариев уже собраны, но текущее состояние характеризуется как `prototype with working fragments`: есть полезный функционал, но фундаментально не хватает консистентности модели, безопасности, воспроизводимости схемы, тестового контура и инженерной дисциплины.

Если кратко: сначала надо чинить фундамент, а не косметику.