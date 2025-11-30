"""
Test local agentcore runtime
"""
import requests
import json

url = "http://localhost:8080/invocations"
headers = {"Content-Type": "application/json"}

print("Connected to agent at", url)
print("Type 'quit', 'exit', or 'bye' to exit\n")

while True:
    prompt = input("You: ")
    if prompt.lower() in ['quit', 'exit', 'bye']:
        break
    
    response = requests.post(url, headers=headers, json={"prompt": prompt}, stream=True)
    print("\nAgent: ", end="", flush=True)
    
    for line in response.iter_lines(decode_unicode=True):
        if line and line.startswith('data: '):
            try:
                json_str = line[6:]
                outer = json.loads(json_str)
                if isinstance(outer, str):
                    inner = json.loads(outer)
                    if "data" in inner:
                        print(inner["data"], end="", flush=True)
                elif isinstance(outer, dict) and "data" in outer:
                    print(outer["data"], end="", flush=True)
            except (json.JSONDecodeError, ValueError):
                pass
    
    print("\n")