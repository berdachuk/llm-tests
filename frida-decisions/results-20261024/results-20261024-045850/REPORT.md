# FRIDA-Decisions LAN report

- base: `http://192.168.0.175:8006`
- started: 2026-10-24T04:58:50-04:00

## Regression (:8002–8005, :8080)
- PASS: :8002 health 200
- PASS: :8003 health 200
- PASS: :8004 health 200
- PASS: :8005 health 200
- PASS: :8080 health 200

## Functional 4 types
- PASS: choice/score/noul/ranking JSON

## Latency (short ticket, 1 question, after warm-up)
- samples=20 p50=10.4 ms p95=10.9 ms
- PASS: p50 ≤ 80 ms

## Catalog (50 intents)
- wall=0.069s choice=i0
- PASS: catalog 50 intents < 2s

## VRAM
```
index, name, memory.used [MiB], memory.free [MiB]
0, NVIDIA GeForce RTX 4090, 23830 MiB, 254 MiB
1, NVIDIA GeForce RTX 5060 Ti, 8364 MiB, 7486 MiB
```


## Summary: pass=8 fail=0
index, name, memory.used [MiB], memory.free [MiB]
0, NVIDIA GeForce RTX 4090, 23830 MiB, 254 MiB
1, NVIDIA GeForce RTX 5060 Ti, 8364 MiB, 7486 MiB
