from scraper import parse_feed

SAMPLE = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Stocks Rally</title><link>https://www.wsj.com/a</link>
<description>&lt;p&gt;Shares &lt;b&gt;rose&lt;/b&gt;.&lt;/p&gt;</description>
<pubDate>Tue, 14 Oct 2026 12:00:00 GMT</pubDate><guid>abc</guid></item>
<item><title>No date</title><link>https://www.wsj.com/b</link><pubDate>garbage</pubDate></item>
</channel></rss>"""


def test_parse_feed():
    a, b = parse_feed(SAMPLE, "wsj_markets")
    assert a.title == "Stocks Rally"
    assert a.summary == "Shares rose ."
    assert a.published.startswith("2026-10-14T12:00:00")
    assert a.guid == "abc"
    assert b.published == "" and b.guid == b.link
