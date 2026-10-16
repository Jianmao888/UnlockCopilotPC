import re, html, os
D = r"C:\Users\jianm\Code\DeepseekHarness\docs"

def article(p):
    raw = open(p, encoding="utf-8", errors="replace").read()
    # 从第一个 anchor-headings 到 "Applies to" 或 feedback
    m = re.search(r'<div data-no-chunk="" class="anchor-headings">(.*?)(?:<h2>Applies to</h2>|id="site-user-feedback-footer")', raw, re.S)
    body = m.group(1) if m else raw
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", body, flags=re.S)
    body = re.sub(r"<pre[^>]*>", "\n```\n", body)
    body = re.sub(r"</pre>", "\n```\n", body)
    body = re.sub(r"<h2[^>]*>", "\n## ", body)
    body = re.sub(r"<h3[^>]*>", "\n### ", body)
    body = re.sub(r"<tr[^>]*>", "\n| ", body)
    body = re.sub(r"</t[dh]>", " | ", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = html.unescape(body)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()

for name in ("aifeaturereadyresultstate.html", "aifeaturereadystate.html"):
    p = os.path.join(D, name)
    print("=" * 78)
    print("### " + name)
    print("=" * 78)
    print(article(p)[:2600])
    print()

# get-started 里的代码示例
p = os.path.join(D, "get-started.html")
t = article(p)
print("=" * 78)
print("### get-started.html  （含 EnsureReadyAsync 的段落）")
print("=" * 78)
lines = t.split("\n")
for i, l in enumerate(lines):
    if "EnsureReady" in l or "GetReadyState" in l or "AIFeatureReady" in l:
        lo = max(0, i - 6); hi = min(len(lines), i + 14)
        print("  ---- 附近 ----")
        for x in lines[lo:hi]:
            print("   " + x)
        print()
