#!/usr/bin/env python3
"""Regenerate sitemap.xml and feed.xml from blog post metadata.

Each post's <meta property="article:published_time"> is the source of truth
for dates. Run with no arguments to write the files; run with --check to
verify they are up to date (used by CI) without writing anything.

Also fails loudly if a post is missing required metadata or isn't linked
from the blog index and the homepage.
"""
import html
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://wescastle.com"


def meta(source, pattern, path):
    m = re.search(pattern, source)
    if not m:
        sys.exit(f"error: {path}: missing required metadata ({pattern})")
    return m.group(1)


def load_posts():
    posts = []
    for path in sorted((ROOT / "blog").glob("*.html")):
        if path.name == "index.html":
            continue
        source = path.read_text()
        title = meta(source, r"<title>([^<]+?)(?: \| WesCastle Blog)?</title>", path)
        description = meta(source, r'<meta name="description" content="([^"]+)"', path)
        date = meta(source, r'<meta property="article:published_time" content="(\d{4}-\d{2}-\d{2})"', path)
        posts.append({
            "file": path.name,
            "url": f"{SITE}/blog/{path.name}",
            "title": title,
            "description": description,
            "date": date,
        })
    posts.sort(key=lambda p: (p["date"], p["file"]), reverse=True)
    return posts


def check_linked(posts):
    blog_index = (ROOT / "blog" / "index.html").read_text()
    homepage = (ROOT / "index.html").read_text()
    missing = []
    for p in posts:
        if f'href="{p["file"]}"' not in blog_index:
            missing.append(f'blog/index.html has no link to {p["file"]}')
        if f'/blog/{p["file"]}' not in homepage:
            missing.append(f'index.html (homepage blog section) has no link to {p["file"]}')
    if missing:
        sys.exit("error: unlinked posts:\n  " + "\n  ".join(missing))


def build_sitemap(posts):
    newest = posts[0]["date"]
    entries = [
        (f"{SITE}/", newest, "monthly", "1.0"),
        (f"{SITE}/blog/", newest, "weekly", "0.9"),
    ] + [(p["url"], p["date"], "monthly", "0.8") for p in posts]

    urls = "\n".join(
        "  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        f"    <changefreq>{freq}</changefreq>\n"
        f"    <priority>{prio}</priority>\n"
        "  </url>"
        for loc, lastmod, freq, prio in entries
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )


def rfc822(date):
    dt = datetime.strptime(date, "%Y-%m-%d").replace(hour=8, tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def build_feed(posts):
    items = "\n".join(
        "    <item>\n"
        f"      <title>{html.escape(p['title'])}</title>\n"
        f"      <link>{p['url']}</link>\n"
        f"      <guid>{p['url']}</guid>\n"
        f"      <pubDate>{rfc822(p['date'])}</pubDate>\n"
        f"      <description>{html.escape(p['description'])}</description>\n"
        "    </item>"
        for p in posts
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        "    <title>WesCastle Blog</title>\n"
        f"    <link>{SITE}/blog/</link>\n"
        f'    <atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>\n'
        "    <description>Field notes from offensive security engagements, developer tooling, and infrastructure ownership. By Wes Hardcastle.</description>\n"
        "    <language>en</language>\n"
        f"    <lastBuildDate>{rfc822(posts[0]['date'])}</lastBuildDate>\n"
        f"{items}\n"
        "  </channel>\n"
        "</rss>\n"
    )


def main():
    check = "--check" in sys.argv
    posts = load_posts()
    if not posts:
        sys.exit("error: no posts found in blog/")
    check_linked(posts)

    outputs = {
        ROOT / "sitemap.xml": build_sitemap(posts),
        ROOT / "feed.xml": build_feed(posts),
    }
    stale = []
    for path, content in outputs.items():
        if check:
            if not path.exists() or path.read_text() != content:
                stale.append(path.name)
        else:
            path.write_text(content)
            print(f"wrote {path.relative_to(ROOT)} ({len(posts)} posts)")

    if stale:
        sys.exit(f"error: {', '.join(stale)} out of date — run scripts/build.py and commit")
    if check:
        print(f"ok: sitemap.xml and feed.xml are current ({len(posts)} posts, all linked)")


if __name__ == "__main__":
    main()
