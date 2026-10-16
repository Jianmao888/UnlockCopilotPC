import re, html, os, glob
D = r"C:\Users\jianm\Code\DeepseekHarness\docs"

def text_of(p):
    raw = open(p, encoding="utf-8", errors="replace").read()
    # 取 <main>
    m = re.search(r"<main[^>]*>(.*?)</main>", raw, re.S)
    body = m.group(1) if m else raw
    # 去脚本/样式
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", body, flags=re.S)
    # code 块标记
    body = re.sub(r"<pre[^>]*>", "\n```\n", body)
    body = re.sub(r"</pre>", "\n```\n", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = html.unescape(body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()

for name in ("aifeaturereadyresult.html", "aifeaturereadyresultstate.html"):
    p = os.path.join(D, name)
    print("=" * 80)
    print("### " + name)
    print("=" * 80)
    t = text_of(p)
    print(t[:4000])
    print()
