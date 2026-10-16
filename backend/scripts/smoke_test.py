"""Live smoke test using a pre-created, assigned dashboard user.

Set SMOKE_EMAIL, SMOKE_PASSWORD and SMOKE_QUESTION. Never put passwords in source.
"""
import http.cookiejar
import json
import os
import urllib.error
import urllib.request

API = os.environ.get("API", "http://localhost:8000/api")
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{API}{path}", data=data,
        method="POST" if body is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    try:
        with opener.open(req, timeout=180) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()


def main():
    email, password = os.getenv("SMOKE_EMAIL"), os.getenv("SMOKE_PASSWORD")
    if not email or not password:
        raise SystemExit("Set SMOKE_EMAIL and SMOKE_PASSWORD for a pre-created assigned user")
    status, body = call("/auth/login", {"email": email, "password": password})
    if status != 200:
        raise SystemExit(f"Login failed: {status} {body}")
    status, clients = call("/analysis/clients")
    if status != 200 or not clients:
        raise SystemExit(f"No assigned clients: {status} {clients}")
    client = clients[0]
    question = os.getenv("SMOKE_QUESTION", "Show the first rows in the data")
    status, body = call("/analysis/query", {
        "question": question, "client_id": client["id"]
    })
    if status != 200:
        raise SystemExit(f"Query failed: {status} {body}")
    if body["database"] != client["database_name"]:
        raise SystemExit("Wrong analysis database selected")
    status, page = call("/analysis/rows", {"token": body["token"], "page": 0})
    if status != 200:
        raise SystemExit(f"Pagination failed: {status} {page}")
    print(f"OK: {client['code']} -> {body['database']}, {len(page['rows'])} rows")


if __name__ == "__main__":
    main()