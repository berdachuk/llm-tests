#!/usr/bin/env bash
# FRIDA-Decisions LAN test suite (4 types, latency, catalog, regression).
set -euo pipefail

BASE="${FRIDA_BASE:-http://192.168.0.175:8006}"
OUT_DIR="${OUT_DIR:-$(cd "$(dirname "$0")" && pwd)/results-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT_DIR"
REPORT="$OUT_DIR/REPORT.md"

pass=0
fail=0
note() { echo "$*" | tee -a "$REPORT"; }
ok() { note "- PASS: $*"; pass=$((pass + 1)); }
bad() { note "- FAIL: $*"; fail=$((fail + 1)); }

note "# FRIDA-Decisions LAN report"
note ""
note "- base: \`$BASE\`"
note "- started: $(date -Is)"
note ""

note "## Regression (:8002–8005, :8080)"
for spec in \
  "8002|http://192.168.0.175:8002/health" \
  "8003|http://192.168.0.175:8003/health" \
  "8004|http://192.168.0.175:8004/health" \
  "8005|http://192.168.0.175:8005/health" \
  "8080|http://192.168.0.175:8080/health"; do
  port="${spec%%|*}"; url="${spec#*|}"
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" || echo 000)
  if [[ "$code" == "200" ]]; then ok ":$port health $code"; else bad ":$port health $code"; fi
done
note ""

note "## Functional 4 types"
TICKET='{"data":{"state":"Здравствуйте, у меня не приходит код подтверждения уже час.","questions":{"topic":{"type":"choice","instructions":"К какой теме относится обращение?","criteria":{"login":"вход, коды, пароли","payment":"оплата, возвраты","delivery":"доставка"}},"urgency":{"type":"score","instructions":"Оцени срочность.","criteria":["низкая","средняя","высокая"]},"spam":{"type":"noul","instructions":"Является ли сообщение спамом?"},"passages":{"type":"ranking","instructions":"Релевантность пассажа.","criteria":["Код приходит в SMS за 2 минуты.","Доставка 3–5 дней."]}}}}'
resp=$(curl -fsS -H 'Content-Type: application/json' -d "$TICKET" "$BASE/pooling")
printf '%s' "$resp" >"$OUT_DIR/functional.json"
python3 - "$OUT_DIR/functional.json" <<'PY' && ok "choice/score/noul/ranking JSON" || bad "functional parse"
import json,sys
p=json.load(open(sys.argv[1]))
a=(p.get("data") or p).get("answers") or p
assert a["topic"]["type"]=="choice" and "choice" in a["topic"]
assert a["urgency"]["type"]=="score" and "score" in a["urgency"]
assert a["spam"]["type"]=="noul" and "noul" in a["spam"]
assert a["passages"]["type"]=="ranking"
print("topic=", a["topic"].get("choice"), "urgency=", a["urgency"].get("score"), "spam=", a["spam"].get("noul"))
PY
note ""

note "## Latency (short ticket, 1 question, after warm-up)"
WARM='{"data":{"state":"Проверьте статус заказа 12345.","questions":{"spam":{"type":"noul","instructions":"Спам?"}}}}'
for i in 1 2 3; do curl -fsS -H 'Content-Type: application/json' -d "$WARM" "$BASE/pooling" >/dev/null; done
times=()
for i in $(seq 1 20); do
  t=$(curl -fsS -o /dev/null -w "%{time_total}" -H 'Content-Type: application/json' -d "$WARM" "$BASE/pooling")
  times+=("$t")
done
printf '%s\n' "${times[@]}" >"$OUT_DIR/latency_samples.txt"
python3 - "$OUT_DIR/latency_samples.txt" <<'PY' | tee -a "$REPORT"
import sys
xs=sorted(float(x) for x in open(sys.argv[1]) if x.strip())
def pct(p):
    if not xs: return None
    k=int(round((p/100)*(len(xs)-1)))
    return xs[k]
p50,p95=pct(50),pct(95)
print(f"- samples={len(xs)} p50={p50*1000:.1f} ms p95={p95*1000:.1f} ms")
open(sys.argv[1]+".summary","w").write(f"p50_ms={p50*1000:.1f}\np95_ms={p95*1000:.1f}\n")
raise SystemExit(0 if p50<=0.080 else 1)
PY
if [[ $? -eq 0 ]]; then ok "p50 ≤ 80 ms"; else bad "p50 > 80 ms"; fi
note ""

note "## Catalog (50 intents)"
python3 - <<'PY' >"$OUT_DIR/catalog_req.json"
import json
crit={f"i{i}": f"намерение номер {i}: типовой сценарий поддержки {i}" for i in range(50)}
print(json.dumps({"data":{"state":"Не могу войти в личный кабинет, пароль не подходит.","questions":{"intent":{"type":"choice","instructions":"Какой интент?","criteria":crit}}}}, ensure_ascii=False))
PY
t0=$(date +%s.%N)
curl -fsS -H 'Content-Type: application/json' -d @"$OUT_DIR/catalog_req.json" "$BASE/pooling" >"$OUT_DIR/catalog_resp.json"
t1=$(date +%s.%N)
python3 - "$OUT_DIR/catalog_resp.json" "$t0" "$t1" <<'PY' | tee -a "$REPORT"
import json,sys
p=json.load(open(sys.argv[1]))
a=(p.get("data") or p).get("answers") or p
wall=float(sys.argv[3])-float(sys.argv[2])
choice=a["intent"].get("choice")
print(f"- wall={wall:.3f}s choice={choice}")
open(sys.argv[1]+".wall","w").write(f"{wall}\n")
raise SystemExit(0 if wall<2.0 and choice else 1)
PY
if [[ $? -eq 0 ]]; then ok "catalog 50 intents < 2s"; else bad "catalog"; fi
note ""

note "## Capability suite (RU/EN, software-dev)"
HERE="$(cd "$(dirname "$0")" && pwd)"
CAP_OUT="$OUT_DIR/capability"
if python3 "$HERE/run_capability_suite.py" --base "$BASE" --out "$CAP_OUT" | tee -a "$REPORT"; then
  ok "capability suite gates"
else
  bad "capability suite gates"
fi
note ""

note "## VRAM"
vram_cmd=(nvidia-smi --query-gpu=index,name,memory.used,memory.free --format=csv)
if command -v nvidia-smi >/dev/null 2>&1; then
  "${vram_cmd[@]}" | tee -a "$REPORT" || note "(nvidia-smi failed)"
else
  ssh -o BatchMode=yes -o ConnectTimeout=5 berda@192.168.0.175 \
    "${vram_cmd[*]}" | tee -a "$REPORT" \
    || note "(nvidia-smi unavailable locally and via ssh)"
fi
note ""
note "## Summary: pass=$pass fail=$fail"
echo "REPORT=$REPORT"
[[ "$fail" -eq 0 ]]
