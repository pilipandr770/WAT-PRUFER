from app.adapters.vies_adapter import ViesAdapter
import json

v = ViesAdapter()
for vat in ["DE136705981", "DE811220642"]:
    res = v.fetch({"vat_number": vat})
    print(vat)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print('-' * 40)
