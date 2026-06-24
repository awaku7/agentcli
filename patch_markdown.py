import sys
with open("out/panel.js","rb") as f:
    d = f.read()

old = b"case 'done': {\r\n                        const el = document.getElementById('streaming');\r\n                        if (el) el.id = '';\r\n                        break;\r\n                    }"

new = b"case 'done': {\r\n                        const el = document.getElementById('streaming');\r\n                        if (el) {\r\n                            var txt = el.textContent || '';\r\n                            el.innerHTML = txt\r\n                                .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')\r\n                                .replace(/```(\\w*)\n([\\s\\S]*?)```/g,'<pre><code>$2</code></pre>')\r\n                                .replace(/```\n([\\s\\S]*?)```/g,'<pre><code>$1</code></pre>')\r\n                                .replace(/`([^`]+)`/g,'<code>$1</code>')\r\n                                .replace(/\\*\\*([^*]+)\\*\\*/g,'<b>$1</b>')\r\n                                .replace(/\\n/g,'<br>');\r\n                            el.id = '';\r\n                        }\r\n                        break;\r\n                    }"

if old in d:
    d = d.replace(old, new)
    with open("out/panel.js","wb") as f:
        f.write(d)
    print("patched")
else:
    print("skip (already patched or not found)")
 
