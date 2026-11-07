# Temporary Gemma-4 31B QAT cutover (.175 :8080)

Replaces **Strata IQ3_S** on **GPU0 only**. GPU1 stacks (speaches `:8002`, gigaam `:8003`, embedding `:8004`, embeddinggemma-2 `:8005`, frida `:8006`) stay on nvidia-guard compose and were verified healthy after reboot.

## Live path

```
Client → https://llm.avroflex.ru/v1  (Bifrost)
       → llm-88 → https://llm-88.berdachuk.com/v1
       → nginx .51 → http://192.168.0.175:8080  (vLLM Gemma)
```

| Item | Value |
|---|---|
| Unit | `gemma4-31b-qat.service` (user, enabled, linger) |
| Strata | **masked** (`strata-iq3_s.service` → `/dev/null`; bak `…bak-gemma4-cutover`) |
| Firewall | `strata-open-8080.service` still enabled |
| Model path | `/mnt/data/berda-models/huggingface/google/gemma-4-31B-it-qat-w4a16-ct` |
| Served ids | `gemma-4-31b-it-qat` + alias `qwen3.8-flash-next-iq3_s` |
| Context | `max-model-len=2048`, `max-num-seqs=1`, `gpu-memory-utilization=0.95` |
| Auth | same Strata API key (nginx Bearer injection unchanged) |
| nvidia-guard | prefers Gemma if unit enabled; GPU1 compose loop untouched. Backup: `/usr/local/sbin/restart-gpu-services.sh.bak-pre-gemma4-*` |

## Bifrost note

`llm-88/qwen3.8-flash-next-iq3_s` works (allowlisted alias).  
`llm-88/gemma-4-31b-it-qat` may return **403** until Bifrost allowlist is updated — use the alias for `https://llm.avroflex.ru`.

## Restore Strata

```bash
ssh berda@192.168.0.175
systemctl --user disable --now gemma4-31b-qat.service
systemctl --user unmask strata-iq3_s.service
mv ~/.config/systemd/user/strata-iq3_s.service.bak-gemma4-cutover \
   ~/.config/systemd/user/strata-iq3_s.service
systemctl --user daemon-reload
systemctl --user enable --now strata-iq3_s.service
# optional: restore nvidia-guard from bak-pre-gemma4-*
```
