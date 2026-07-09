from uagent.uagent_llm import _TOTAL_ROUNDS, _TOOL_LAST_ROUND, _TOOL_AUTO_UNLOAD_ROUNDS  
import inspect  
print(inspect.getfile(_TOTAL_ROUNDS.__class__))  
