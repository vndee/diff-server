import requests

url = "http://localhost:5000/text_to_image/?prompt=tôi thấy hoa vàng trên cỏ xanh&lang=vi"

payload={}
headers = {}

response = requests.request("GET", url, headers=headers, data=payload)

print(response.text)

