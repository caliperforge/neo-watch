import re
from urllib.request import Request, urlopen

from neowatch.poll import USER_AGENT

PREVIOUS = "https://www.minorplanetcenter.net/iau/NEO/ToConfirm_PrevDes.html"
MPECS = "https://www.minorplanetcenter.net/mpec/RecentMPECs.html"
OBSERVATIONS = "https://cgi.minorplanetcenter.net/cgi-bin/showobsorbs.cgi?Obj={}&obs=y"


def _get(url: str) -> str:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} answered {response.status}")
        return response.read().decode()


def previous() -> dict[str, str | None]:
    body = _get(PREVIOUS)
    fates: dict[str, str | None] = {temp: None for temp, _ in re.findall(r"<li> (\S+) (was|does) ", body)}
    fates |= {temp: re.sub(r"</?sub>", "", desig) for desig, temp in re.findall(r"<li>\s*(.+?) = (\S+) \(", body)}
    return fates


def circulars() -> dict[str, str]:
    entries = re.findall(r'<li><a href="([^"]+)"><i>MPEC</i>.*\n\s*<ul>\n\s*<li>(.+)', _get(MPECS))
    return {title: "https://www.minorplanetcenter.net" + href for href, title in entries}


def stations(id: str) -> list[str]:
    (block,) = re.findall(r"<pre>(.*?)</pre>", _get(OBSERVATIONS.format(id)), re.DOTALL)
    return sorted({line[77:80] for line in block.splitlines() if line.strip()})
