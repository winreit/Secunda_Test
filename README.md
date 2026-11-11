# Async Payment Processing Service

Асинхронный микросервис создания и обработки платежей. Стек: FastAPI, Pydantic v2, SQLAlchemy Async, PostgreSQL, RabbitMQ/FastStream, Alembic, Docker Compose.

## Возможности

- `POST /api/v1/payments` создаёт платёж со статусом `pending` и возвращает HTTP 202.
- `GET /api/v1/payments/{payment_id}` возвращает состояние платежа.
- Авторизация через `X-API-Key`.
- Идемпотентность через обязательный `Idempotency-Key`: повтор с тем же ключом и тем же телом возвращает существующий платёж; другое тело с тем же ключом — HTTP 409.
- Создание платежа и запись события Outbox выполняются в одной транзакции PostgreSQL.
- Outbox Worker публикует события в RabbitMQ; блокировки строк `SKIP LOCKED` позволяют запускать несколько worker.
- Consumer имитирует обработку 2–5 секунд с вероятностью успеха 90%, меняет статус на `succeeded` или `failed` и заполняет `processed_at`.
- Webhook отправляется с повторными попытками и экспоненциальной задержкой; после исчерпания попыток событие публикуется в `payments.dlq`.

## Запуск через Docker Compose

1. Скопируйте `.env.example` в `.env` и задайте длинный случайный `API_KEY`. Compose остановится с ошибкой, если переменная не задана.
2. Убедитесь, что порты `5433`, `5672`, `15672` и `8000` свободны. PostgreSQL контейнера доступен на хосте через `localhost:5433` (внутри Docker-сети — `postgres:5432`).
3. Запустите:

```bash
docker compose up --build
```

Compose поднимет PostgreSQL и RabbitMQ, выполнит `alembic upgrade head`, затем запустит API, Outbox Worker и Consumer.

- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health
- RabbitMQ Management: http://localhost:15672 (guest/guest; только локальная разработка)

## Примеры запросов

Создание:

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: change-me-before-deploying' \
  -H 'Idempotency-Key: order-10001' \
  -d '{"amount":"1250.50","currency":"RUB","description":"Test payment","metadata":{"order_id":10001}}'
```

Получение:

```bash
curl http://localhost:8000/api/v1/payments/1 \
  -H 'X-API-Key: change-me-before-deploying'
```

Webhook endpoint должен принимать POST с JSON: `payment_id`, `status`, `amount` (десятичная строка), `currency`. Для дедупликации повторных уведомлений получатель может использовать заголовок `Idempotency-Key`.

## Локальный запуск без Docker

Нужны PostgreSQL и RabbitMQ. Создайте виртуальное окружение, установите зависимости и настройте `.env`:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

В отдельных терминалах запустите worker и consumer:

```bash
python -m app.workers.outbox_worker
faststream run app.messaging.consumer:broker
```

## Миграции

```bash
alembic upgrade head
alembic downgrade -1
```

## Тесты

```bash
pytest -q
```

Тесты в `tests/` проверяют валидацию схем и бизнес-правила, не требуя поднятого PostgreSQL/RabbitMQ. Для полной проверки интеграции запустите Compose и выполните запросы из раздела выше.

## Примечания по надёжности

- Доставка из Outbox в RabbitMQ — at-least-once: при аварии после публикации, но до отметки `published_at`, возможна повторная доставка. Consumer защищает обработку платежа атомарным захватом записи; webhook-получатель должен дедуплицировать повторные уведомления по `Idempotency-Key`.
- Блокировка строки платежа через `SELECT FOR UPDATE` защищает от одновременной обработки повторно доставленного сообщения; при аварии незавершённая транзакция откатывается.
- DLQ consumer сейчас фиксирует сообщения в логах. В production следует подключить постоянное хранилище/алертинг для DLQ и отдельный контролируемый механизм replay.
- Замените демонстрационные пароли и API key перед любым публичным развёртыванием. 
