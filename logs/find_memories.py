import httpx
import re

r = httpx.get('http://localhost:3000/main.js')
content = r.text

# find where photo-wall is mentioned, and get the surrounding text
matches = re.finditer(r'photo-wall', content)
for m in matches:
    start = max(0, m.start() - 200)
    end = min(len(content), m.end() + 200)
    print("---")
    print(content[start:end])
