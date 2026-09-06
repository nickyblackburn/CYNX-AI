import re
path = r'C:\Users\nickk\AppData\Local\Temp\1788654768004-copilot-tool-output-10256-01d7f6a8-cfe3-4c29-9f85-ec9aad72204f.txt'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
res = []
for i,l in enumerate(lines):
    if '[CURRENT JSON]' in l:
        # next non-empty line
        j=i+1
        while j < len(lines) and lines[j].strip()=='' : j+=1
        if j < len(lines):
            res.append(lines[j].strip())
for idx, r in enumerate(res,1):
    print(f'-- SNAPSHOT {idx} --')
    print(r)
    print()
