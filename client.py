import requests

BASE = "http://127.0.0.1:5000/"

response = requests.put(BASE + "route/petah tikva, asirei tsiyon 13/tel aviv, j.l. gordon 61")

print(response.json())
