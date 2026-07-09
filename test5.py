with open(r'C:\KAIHATSU\agentcli\src\uagent\uagent_llm.py', 'r', encoding='utf-8') as f:  
    lines = f.readlines()  
for i in range(55, 70):  
    print(f'{i}: {lines[i-1].rstrip()}')  
