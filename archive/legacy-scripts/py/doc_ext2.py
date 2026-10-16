import re, html, os
D = r"C:\Users\jianm\Code\DeepseekHarness\docs"

def text_of(p):
    raw = open(p, encoding="utf-8", errors="replace").read()
    # 优先找 article / content 容器
    for pat in (r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
                r'<article[^>]*>(.*?)</article>',
                r'<main[^>]*>(.*?)</main>'):
        m = re.search(pat, raw, re.S)
        if m and len(m.group(1)) > 2000:
            body = m.group(1); break
    else:
        body = raw
    body = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", "", body, flags=re.S)
    body = re.sub(r"<pre[^>]*>", "\n```\n", body)
    body = re.sub(r"</pre>", "\n```\n", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = html.unescape(body)
    lines = [l.strip() for l in body.split("\n")]
    # 丢掉导航式短行
    out = []
    for l in lines:
        if len(l) < 3 and not l.startswith("```"):
            continue
        out.append(l)
    body = "\n".join(out)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()

for name in ("aifeaturereadyresult.html", "aifeaturereadyresultstate.html", "aifeaturereadystate.html"):
    p = os.path.join(D, name)
    t = text_of(p)
    print("=" * 80)
    print("### " + name + f"   ({len(t)} chars)")
    print("=" * 80)
    print(t[:3500])
    print()
