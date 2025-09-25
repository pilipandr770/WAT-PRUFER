import json, requests

BASE = "http://127.0.0.1:5000"

def main():
    payload = {
        "vat_number": "DE811220642",
        # опційно для тесту санкцій без approx:
        # "name": "BMW AG",
        # "website": "https://www.bmw.de",
        "requester": {
            "country_code": "DE",
            "vat_number":  "DE456902445"  # <-- той самий з .env, реальний VAT запитувача
        }
    }
    r = requests.post(f"{BASE}/api/companies/lookup", json=payload, timeout=90)
    print("POST /api/companies/lookup status:", r.status_code)
    print(r.text)

if __name__ == "__main__":
    main()
