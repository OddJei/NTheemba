import json
import re
import uuid
from pathlib import Path
import httpx
import os


BASE = "http://127.0.0.1:8500"
# climb to workspace soft-launch root then contracts
HERE = Path(__file__).resolve().parents[4] / "contracts" / "msme-engine"
OPENAPI = HERE / "openapi.json"


def sample_for_name(name):
    n = name.lower()
    if "email" in n:
        # produce a unique email per run to avoid conflicts
        return f"test+{uuid.uuid4().hex[:8]}@example.com"
    if "password" in n:
        return "secret123"
    if "phone" in n:
        return "+260971000000"
    if "amount" in n or "price" in n:
        return 1000
    if "currency" in n:
        return "ZMW"
    # datetime-like fields (check before generic id handling because 'id' appears in 'paid')
    if "paid_until" in n or "until" in n or n.endswith("date") or "expiry" in n or "paid" in n:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()
    # plural ids should be a list
    if n == "ids" or n.endswith("ids"):
        return ["id_test"]
    if "id" in n and not n.endswith("id"):
        return "id_test"
    if n.endswith("id") or "business_id" in n:
        return "biz_test"
    # delivery locations dicts
    if "delivery" in n and "location" in n:
        return {"main": {"address": "unknown"}}
    if "username" in n:
        # unique username per run to avoid duplicate-registration 409s
        return f"tester_{uuid.uuid4().hex[:8]}"
    if "plan" in n:
        return "free"
    if "role" in n:
        return "default"
    return "test"


def build_body(schema: dict):
    if not schema:
        return {}
    # If properties exist, fill required with heuristics
    props = schema.get("properties", {})
    required = schema.get("required", [])
    body = {}
    for k in required:
        if k in props:
            body[k] = sample_for_name(k)
        else:
            body[k] = "test"
    # Fill at least one property if none required
    if not body and props:
        first = next(iter(props.keys()))
        body[first] = sample_for_name(first)
    # Ensure `delivery_locations` is a dict when present
    if "delivery_locations" in props and "delivery_locations" not in body:
        body["delivery_locations"] = {"main": {"address": "unknown"}}
    return body


def fill_path(path: str):
    # replace {param} with sample values
    def repl(m):
        key = m.group(1)
        return sample_for_name(key)

    return re.sub(r"\{([^}]+)\}", repl, path)


def resolve_ref(ref: str, doc: dict):
    if not ref.startswith("#/components/schemas/"):
        return None
    name = ref.split("/")[-1]
    return doc.get("components", {}).get("schemas", {}).get(name)


def main():
    doc = json.loads(OPENAPI.read_text())
    paths = doc.get("paths", {})
    results = []
    client = httpx.Client(timeout=10)

    # --- perform register/login flow to obtain Authorization token ---
    access_token = None
    refresh_token = None
    try:
        # build register body from openapi if present
        reg_spec = paths.get("/auth/register", {}).get("post")
        if reg_spec:
            rb = reg_spec.get("requestBody")
            js = (rb.get("content") or {}).get("application/json") if rb else None
            schema = js.get("schema") if js else None
            if isinstance(schema, dict) and "$ref" in schema:
                schema = resolve_ref(schema["$ref"], doc) or schema
            reg_body = build_body(schema) if schema else {"username": f"tester_{uuid.uuid4().hex[:6]}", "email": f"test+{uuid.uuid4().hex[:6]}@example.com", "password": "secret123"}
        else:
            reg_body = {"username": f"tester_{uuid.uuid4().hex[:6]}", "email": f"test+{uuid.uuid4().hex[:6]}@example.com", "password": "secret123"}

        r = client.post(BASE + "/auth/register", json=reg_body)
        print("[tester] register payload:", reg_body)
        print("[tester] register response:", r.status_code, r.text[:400])
        # ignore non-2xx (may already exist)
        login_body = {"identifier": reg_body.get("email") or reg_body.get("username"), "password": reg_body.get("password")}
        print("[tester] login payload:", login_body)
        r2 = client.post(BASE + "/auth/login", json=login_body)
        print("[tester] login response:", r2.status_code, r2.text[:400])
        if r2.status_code == 200:
            j = r2.json()
            access_token = j.get("access_token") or (j.get("token") if isinstance(j, dict) else None)
            refresh_token = j.get("refresh_token")
            # immediately verify refresh endpoint with the obtained refresh token
            if refresh_token:
                rr = client.post(BASE + "/auth/refresh", json={"refresh_token": refresh_token})
                print("[tester] immediate refresh response:", rr.status_code, rr.text[:400])
                if rr.status_code == 200:
                    rrj = rr.json()
                    # update tokens to the latest rotated values
                    access_token = rrj.get("access_token") or access_token
                    refresh_token = rrj.get("refresh_token") or refresh_token
    except Exception:
        access_token = None

    for path, methods in paths.items():
        for method, spec in methods.items():
            url_path = fill_path(path)
            url = BASE + url_path
            body = None
            headers = {}
            # send internal secret for internal/outbox endpoints
            desc = (spec.get("description") or "").lower()
            if path.startswith("/outbox") or path.startswith("/internal") or "internal secret" in desc:
                headers["X-Internal-Secret"] = os.environ.get("OUTBOX_INTERNAL_SECRET", "test-internal-secret")
            # attach auth header for endpoints that declare security
            sec = spec.get("security")
            if sec and access_token:
                headers["Authorization"] = f"Bearer {access_token}"
            # if requestBody present, attempt to build a minimal body
            rb = spec.get("requestBody")
            if rb:
                content = rb.get("content", {})
                # prefer application/json
                js = content.get("application/json") or (next(iter(content.values())) if content else None)
                schema = js.get("schema") if js else None
                if isinstance(schema, dict) and "$ref" in schema:
                    resolved = resolve_ref(schema["$ref"], doc)
                    schema = resolved or schema
                if isinstance(schema, dict):
                    # reuse known login/refresh tokens when iterating endpoints
                    if url_path == "/auth/refresh" and refresh_token:
                        body = {"refresh_token": refresh_token}
                    elif url_path == "/auth/login" and 'login_body' in locals():
                        body = login_body
                    else:
                        body = build_body(schema)
                else:
                    body = {}

            try:
                if method.lower() == "get":
                    r = client.get(url, headers=headers)
                else:
                    r = client.request(method.upper(), url, json=body or {}, headers=headers)
                ok = 200 <= r.status_code < 400
                # capture response headers for debugging (tokens may be returned in headers)
                hdrs = dict(r.headers)
                # if this response returns rotated tokens, update our stored values
                try:
                    jr = r.json()
                except Exception:
                    jr = None
                # update tokens when present in any successful response
                if jr and isinstance(jr, dict):
                    if jr.get("access_token"):
                        access_token = jr.get("access_token") or access_token
                    if jr.get("refresh_token"):
                        refresh_token = jr.get("refresh_token") or refresh_token

                # handle session_revoked on refresh: try to re-login once and retry the request
                if r.status_code == 401 and jr and isinstance(jr, dict) and jr.get("detail") == "session_revoked":
                    if 'login_body' in locals():
                        lr = client.post(BASE + "/auth/login", json=login_body)
                        print("[tester] re-login response:", lr.status_code, (lr.text[:400] if lr is not None else None))
                        if lr.status_code == 200:
                            try:
                                lj = lr.json()
                            except Exception:
                                lj = None
                            if lj and isinstance(lj, dict):
                                access_token = lj.get("access_token") or access_token
                                refresh_token = lj.get("refresh_token") or refresh_token
                            # retry the original call once with refreshed tokens
                            if headers and access_token:
                                headers["Authorization"] = f"Bearer {access_token}"
                            try:
                                if method.lower() == "get":
                                    r = client.get(url, headers=headers)
                                else:
                                    r = client.request(method.upper(), url, json=body or {}, headers=headers)
                                hdrs = dict(r.headers)
                            except Exception:
                                pass

                results.append((method.upper(), url_path, r.status_code, r.text[:200], hdrs))
                print(f"{method.upper()} {url_path} -> {r.status_code}")
                if not ok:
                    print("  Response:", r.text[:1000])
                    if hdrs:
                        print("  Headers:", {k: hdrs.get(k) for k in list(hdrs)[:6]})
            except Exception as e:
                results.append((method.upper(), url_path, "ERROR", str(e)))
                print(f"{method.upper()} {url_path} -> ERROR: {e}")

    # summary
    print("\nSummary:\n")
    for m, p, s, t, h in results:
        # show first few headers in summary for quick inspection
        header_preview = None
        if isinstance(h, dict) and h:
            header_preview = {k: h.get(k) for k in list(h)[:4]}
        print(f"{s}\t{m}\t{p}\t{header_preview}")


if __name__ == "__main__":
    main()
