Defect: server-side request forgery (SSRF) -- the server fetches a
user-supplied URL with no validation/allowlisting, letting an attacker
make the server issue requests to internal-only endpoints (e.g. cloud
metadata services, internal admin APIs, localhost services).
