# Снимок настроек Strata IQ3_S (восстановление)

Дата снимка: **2026-10-16** (прод на `192.168.0.175`, ethernet).  
Артефакты (без секретов): [`strata-restore/iq3_s-20261016/`](strata-restore/iq3_s-20261016/).  
Копия на сервере: `/mnt/data/strata/runs/production/restore-iq3_s-20261016/`.

> Секреты **не** в git. Ключ: `/mnt/data/strata/runs/production/api-key.txt`  
> (локальные копии: `avroflex-infra/k8s/secrets/strata-api-key*.txt`, OpenCode `~/.config/opencode/secrets/strata-api-key.token`).

## 1. Целевое состояние прода

| Параметр | Значение |
|---|---|
| Host | `berda@192.168.0.175` (`llm-server`), primary LAN **`.175`** |
| Engine | Strata **v0.1.44.1** (`296b59d2`, tag `v0.1.44.1`) |
| Quant | GSQ-RCO **IQ3_S** |
| Served id | `qwen3.8-flash-next-iq3_s` |
| Bifrost | `llm-88/qwen3.8-flash-next-iq3_s` |
| Bind | `0.0.0.0:8080` |
| GPU | **0 only** (нет `layer_split`) |
| Context | `--max-context 262144`, KV `int8`, `--kv-resident 32768` |
| Vision | mmproj BF16 + vision worker |
| Units | `strata-iq3_s.service` + `strata-open-8080.service` (user, **enabled**, linger=yes) |
| FreeToken | выключен |

## 2. Пути артефактов на диске

| Что | Путь | Размер / SHA-256 |
|---|---|---|
| Config | `/mnt/data/strata/Strata/strata-iq3_s.json` | см. артефакт |
| Pack | `/mnt/data/strata-data/packs/iq3_s/` | ~1.5 G; `dense.bin` `d2af3d8331e5c7a1985d1d589747230f9d56719a6d33c7cddc9ee6b81cde6b13` |
| GGUF 00001 | `…/models/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf` | ~52 G; `4c1eb2ceb4915e1192f4f386021897bde56a97f40a0bb78bb86465e0f7d2aca3` |
| GGUF 00002 (PLE) | `…/models/IQ3_S/…-00002-of-00002.gguf` | ~27 G; `316b46f3a2dbd68c900f43136ab9449f9dcc3725dfd8c794847c204bc161e113` |
| mmproj | `/mnt/data/strata-data/models/mmproj-Qwen3.8-Flash-Next-BF16.gguf` | ~866 M; `b1a82259702816a5330d7bd7607cd9676b11780e79ff7348c21103ff3ce49bd0` |
| MTP | `/mnt/data/strata-data/mtp/rt` | ~787 M |
| Expert profile | `/mnt/data/strata/Strata/data/expert-profile.bin` | ~193 K |
| API key | `/mnt/data/strata/runs/production/api-key.txt` | mode 600 |
| Logs | `/mnt/data/strata/runs/production/server.out`, `strata-iq3_s.log` | |

## 3. Engine args (из live config)

```text
--pack /mnt/data/strata-data/packs/iq3_s
--native …/IQ3_S/…-00001-of-00002.gguf
--ple-gguf …/IQ3_S/…-00002-of-00002.gguf
--expert-profile /mnt/data/strata/Strata/data/expert-profile.bin
--expert-cache auto
--prefill auto
--spec 4 --spec-min-p 0.5
--mtp /mnt/data/strata-data/mtp/rt
--max-context 262144
--kv int8 --kv-resident 32768
--vision
--vram-reserve-mib 700
--pool-workers 15
gpu: 0
host: 0.0.0.0  port: 8080
model_name: qwen3.8-flash-next-iq3_s
```

Полный JSON: [`strata-restore/iq3_s-20261016/strata-iq3_s.json`](strata-restore/iq3_s-20261016/strata-iq3_s.json)  
(`api_key` — плейсхолдер; подставить из `api-key.txt`).

## 4. systemd

Файлы: `~/.config/systemd/user/strata-iq3_s.service`, `strata-open-8080.service`  
(копии в `strata-restore/iq3_s-20261016/`).

Ключевые свойства `strata-iq3_s`:

- `ExecStart=…/python …/serve/server.py --engine strata --config …/strata-iq3_s.json --port 8080`
- CUDA 13.0 в `PATH` / `LD_LIBRARY_PATH`
- `TimeoutStartSec=900`, `Restart=on-failure`
- `Wants=strata-open-8080` (не `Requires`, не `Before` у firewall)

Firewall oneshot → `sudo /usr/local/sbin/open-strata-8080.sh` (скрипт в артефактах).  
После GPU recovery: `/usr/local/sbin/restart-gpu-services.sh` стартует `strata-open-8080` и рестартит `strata-iq3_s`.

## 5. nginx / Bifrost (`.51`)

- Site: `/etc/nginx/sites-enabled/llm-88.berdachuk.com`
- `location /v1/` → `proxy_pass http://192.168.0.175:8080;`
- Auth upstream: `include /etc/nginx/snippets/strata-upstream-auth.conf;` (Bearer Strata, mode 600)
- Сниппеты: `nginx-v1-location.snippet`, `strata-upstream-auth.conf.example`

## 6. Процедура восстановления после теста Q4 / другого quant

На `.175`:

```bash
# 1) Остановить тестовый движок на :8081 (если был) — не трогая ключи.
# 2) Вернуть конфиг
cp -a /mnt/data/strata/runs/production/restore-iq3_s-20261016/strata-iq3_s.json \
      /mnt/data/strata/Strata/strata-iq3_s.json
# Вставить api_key из production/api-key.txt в JSON (или оставить уже живой файл)

# 3) Юниты (если перезаписывали)
cp -a /mnt/data/strata/runs/production/restore-iq3_s-20261016/strata-iq3_s.service \
      ~/.config/systemd/user/strata-iq3_s.service
cp -a /mnt/data/strata/runs/production/restore-iq3_s-20261016/strata-open-8080.service \
      ~/.config/systemd/user/strata-open-8080.service
systemctl --user daemon-reload
systemctl --user enable --now strata-open-8080.service strata-iq3_s.service

# 4) Smoke
KEY=$(cat /mnt/data/strata/runs/production/api-key.txt)
curl -fsS -H "Authorization: Bearer $KEY" http://127.0.0.1:8080/v1/models
```

На `.51` (если меняли upstream):

```bash
# location /v1/ снова на http://192.168.0.175:8080 + strata-upstream-auth.conf
sudo nginx -t && sudo systemctl reload nginx
```

Клиенты: Bifrost model `llm-88/qwen3.8-flash-next-iq3_s`; OpenCode `llm-88-local` → `.175:8080/v1`.

## 7. Чего не делать при restore

- Не ставить `"gpu": [0,1]` / `layer_split` (это был dual-GPU тест, не прод).
- Не указывать Wi‑Fi IP вместо `.175`.
- Не коммитить `api_key` / `strata-upstream-auth.conf` с живым Bearer.
