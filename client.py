import requests

BASE = "http://127.0.0.1:5000/"

response = requests.get(BASE + "route/haifa, ilanot st 19/tel aviv, j.l. gordon 61")

print(response.json())
