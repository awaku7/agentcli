import ast  
with open(r'C:\KAIHATSU\agentcli\src\uagent\uagent_llm.py', 'r', encoding='utf-8') as f:  
    lines = f.readlines()  
print(f'File has {len(lines)} lines')  
for i, l in enumerate(lines, 1):  
    if l.startswith('from ') or l.startswith('import '):  
        print(f'{i}: {l.rstrip()}')  
