"""
Test local agentcore runtime
"""
import requests
import json

url = "http://localhost:8080/invocations"
headers = {"Content-Type": "application/json"}

while True:
    prompt = input("You: ")
    if prompt.lower() in ['quit', 'exit', 'bye']:
        break
    
    response = requests.post(url, headers=headers, json={"prompt": prompt})
    print(f"\nAgent: {response.json()}\n")