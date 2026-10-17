# Как пользоваться LLM-сервисами на `llm-server` (`.175`)

> **Дата:** 2026-10-15  
> Хост: `llm-server`, основной LAN IP — ethernet **`192.168.0.175`**.  
> Wi‑Fi может быть поднят как backup, но **nginx и Docker publish смотрят только на `.175`**.  
> Секреты в эту инструкцию не входят — ключи только на хосте / в менеджере паролей / в локальных `~/.config/…` вне git.

Связанные runbook’и: [`STRATA_88_PRODUCTION.md`](STRATA_88_PRODUCTION.md), [`STRATA_88_ACTIVE_STACK.md`](STRATA_88_ACTIVE_STACK.md), [`EMBEDDINGS_88.md`](EMBEDDINGS_88.md), `avroflex-infra/docs/bifrost-llm88-asr-stack.md`.

---

## 1. Что где слушает

| Сервис | LAN | Публично (через nginx `.51`) | Model id |
|---|---|---|---|
| **Strata** (chat) | `http://192.168.0.175:8080` | `https://llm-88.berdachuk.com/v1` | `qwen3.8-flash-next-ud-q4_k_xl` |
| Speaches ASR | `http://192.168.0.175:8002` | `https://llm-88.berdachuk.com/speaches/v1` | (см. `/v1/models` Speaches) |
| GigaAM ASR | `http://192.168.0.175:8003` | `https://llm-88.berdachuk.com/gigaam/v1` | `gigaam-v3` |
| TEI embeddings | `http://192.168.0.175:8004` | `https://llm-88.berdachuk.com/embedding/v1` | `Qwen/Qwen3-Embedding-0.6B` |
| EmbeddingGemma-2 | `http://192.168.0.175:8005` | `https://llm-88.berdachuk.com/embedding-gemma2/v1` | `google/embeddinggemma-2` |

Через Bifrost (`https://llm.avroflex.ru/v1`) те же backend’ы с префиксами провайдера:

| Назначение | Bifrost model id |
|---|---|
| Chat | `llm-88/qwen3.8-flash-next-ud-q4_k_xl` |
| ASR RU | `gigaam-88/gigaam-v3` |
| ASR multilingual | `audio-88/…` (faster-whisper) |
| Embeddings text | `embedding-88/Qwen/Qwen3-Embedding-0.6B` |
| Embeddings Gemma (text via Bifrost) | `embedding-gemma2-88/google/embeddinggemma-2` |

Практический потолок промпта Strata: **~248K** токенов (advertised `n_ctx=262144`).  
Concurrency Strata по умолчанию **1**.

---

## 2. Какой путь выбрать

| Сценарий | Куда бить |
|---|---|
| Домашняя LAN, минимальная задержка | напрямую `http://192.168.0.175:8080` |
| Из интернета / с телефона | `https://llm-88.berdachuk.com/v1` |
| Приложения Avroflex / VK | `https://llm.avroflex.ru/v1` + Virtual Key |
| OpenCode на этой машине | провайдер `llm-88-local` → `.175:8080` (см. §5) |

Не используйте старый Wi‑Fi IP `192.168.0.88` для сервисов: он нестабилен и больше не в nginx/Docker.

SSH: `ssh llm-server` или `ssh berda@192.168.0.175`.

---

## 3. Аутентификация (без значений ключей)

| Путь | Что нужно |
|---|---|
| LAN Strata `:8080` | Bearer = Strata API key |
| `llm-88.berdachuk.com` | Bearer = `LLM_88_API_KEY` (nginx map / Bifrost provider key) |
| `llm.avroflex.ru` | Bearer = Virtual Key Bifrost (например VK coding) |
| LAN TEI/Gemma/ASR `:8002–8005` | без auth |

Ключи **не коммитить** (`k8s/secrets/` в `.gitignore`). Локальный склад на станции оператора:

| Назначение | Файл в `avroflex-infra/k8s/secrets/` |
|---|---|
| Strata LAN Bearer | `strata-api-key.txt` |
| llm-88 HTTPS Bearer | `llm-88-api-key.txt` |
| Bifrost VK coding → llm-88 | `vk9-code-llm88.txt` |

OpenCode читает копии из `~/.config/opencode/secrets/*.token` (синхронизировать вручную при ротации).

---

## 4. Примеры (плейсхолдеры)

Подставьте свои значения окружения; в git/доках секретов нет.

### 4.1. Strata — список моделей (LAN)

```bash
KEY=$(tr -d '\n' < ~/projects-avroflex/avroflex-infra/k8s/secrets/strata-api-key.txt)
# или с хоста: ssh berda@192.168.0.175 'tr -d "\n" </mnt/data/strata/runs/production/api-key.txt'
curl -fsS -H "Authorization: Bearer $KEY" \
  http://192.168.0.175:8080/v1/models
```

### 4.2. Strata — chat (LAN)

```bash
curl -fsS http://192.168.0.175:8080/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3.8-flash-next-ud-q4_k_xl",
    "temperature": 0,
    "max_tokens": 64,
    "messages": [{"role": "user", "content": "Reply with exactly: pong"}]
  }'
```

### 4.3. Публичный llm-88 (через nginx)

```bash
LLM_88_API_KEY=$(tr -d '\n' < ~/projects-avroflex/avroflex-infra/k8s/secrets/llm-88-api-key.txt)
curl -fsS https://llm-88.berdachuk.com/v1/models \
  -H "Authorization: Bearer $LLM_88_API_KEY"
```

### 4.4. Bifrost

```bash
curl -fsS https://llm.avroflex.ru/v1/chat/completions \
  -H "Authorization: Bearer $VK" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "llm-88/qwen3.8-flash-next-ud-q4_k_xl",
    "temperature": 0,
    "max_tokens": 64,
    "messages": [{"role": "user", "content": "Reply with exactly: pong"}]
  }'
```

### 4.5. Embeddings (LAN, без auth)

```bash
curl -fsS http://192.168.0.175:8004/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3-Embedding-0.6B","input":["hello"]}'

curl -fsS http://192.168.0.175:8005/health
```

### 4.6. Monitor UI

Открыть: **http://192.168.0.175:8080/#monitor**  
Вставить Strata Bearer в настройках Monitor (без ключа UI/метрики не заработают).

---

## 5. OpenCode

Конфиг: `~/.config/opencode/opencode.jsonc` (не в git).

| Поле | Значение |
|---|---|
| Default model | `llm-88-local/qwen3.8-flash-next-ud-q4_k_xl` |
| LAN baseURL | `http://192.168.0.175:8080/v1` |
| Context limit | `248000` |
| Запасные провайдеры | `llm-88` (HTTPS), `avroflex-llm88` (Bifrost) |

Ключи — только в `~/.config/opencode/secrets/*.token`.

---

## 6. Быстрая проверка «всё живо»

```bash
# LAN
curl -fsS -o /dev/null -w 'strata=%{http_code}\n' http://192.168.0.175:8080/
curl -fsS -o /dev/null -w 'speaches=%{http_code}\n' http://192.168.0.175:8002/v1/models
curl -fsS -o /dev/null -w 'gigaam=%{http_code}\n' http://192.168.0.175:8003/health
curl -fsS -o /dev/null -w 'tei=%{http_code}\n' http://192.168.0.175:8004/health
curl -fsS -o /dev/null -w 'gemma=%{http_code}\n' http://192.168.0.175:8005/health

# SSH / unit
ssh berda@192.168.0.175 'systemctl --user is-active strata-ud-q4_k_xl.service'
```

Ожидаемо: HTTP **200** (для Strata root без ключа UI отдаётся; `/v1/*` без Bearer — **401**).

---

## 7. Типичные проблемы

| Симптом | Что проверить |
|---|---|
| Не открывается `…88:8080` | Это Wi‑Fi IP; используйте **`.175`** |
| Monitor пустой / 401 на API | Нет Bearer в Settings / неверный Strata key |
| Bifrost 502/timeout на chat | nginx `.51` → `192.168.0.175:8080`; `strata-ud-q4_k_xl` active |
| TEI/Gemma недоступны с LAN | Publish только на `.175`, не на `0.0.0.0` и не на Wi‑Fi IP |
| Prefill «медленный» на коротком промпте в Monitor | Нормально; на длинном контексте matrix ~1.9–2.1k t/s |

Операторский restart Strata: см. [`STRATA_88_PRODUCTION.md`](STRATA_88_PRODUCTION.md).
