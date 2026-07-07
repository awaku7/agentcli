import pathlib
p = pathlib.Path("src/uagent/tools/generate_zai.py")
p.write_text(open("_zai_content.txt", encoding="utf-8").read(), encoding="utf-8")
print("written", p.stat().st_size)
