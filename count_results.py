p='C:\\Users\\nickk\\AppData\\Local\\Temp\\1788664078650-copilot-tool-output-10256-e972ea8f-5462-4edf-96a1-739b5fdeb6c4.txt'
with open(p,'r',encoding='utf-8') as f:
    s=f.read()
lines=[l for l in s.splitlines() if l.startswith('ATTEMPT')]
valid=sum(1 for l in lines if 'RESULT=valid tool_call' in l)
peg=sum(1 for l in lines if 'RESULT=peg-native-parse-error-handled' in l)
normal=sum(1 for l in lines if 'RESULT=normal content' in l)
unknown=sum(1 for l in lines if 'RESULT=empty/unknown' in l)
http500=sum(1 for l in lines if 'status=500' in l)
print({'valid':valid,'peg_handled':peg,'normal':normal,'unknown':unknown,'http500':http500,'total':len(lines)})
