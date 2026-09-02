Defect: insecure deserialization -- Python `pickle.loads()` is applied
directly to untrusted, attacker-controlled input from an HTTP request,
allowing arbitrary code execution via a crafted pickle payload.
