import pathlib
p = pathlib.Path("src/uagent/tools/generate_zai.py")
p.write_text(open("_generate_zai_content.py", encoding="utf-8").read(), encoding="utf-8")
print("OK")
