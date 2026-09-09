"""
Scraper UNGM (ungm.org) - place de marche des Nations Unies.

L'UI publique interroge POST /Public/Notice/Search (JSON) qui renvoie un
fragment HTML : lignes div.notice-table avec data-noticeid, cellules
resultTitle / deadline / date publiee / resultAgency / type / reference /
pays. Detail : https://www.ungm.org/Public/Notice/<noticeid>.
"""
from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from ..config import DEFAULT_HEADERS, REQUEST_TIMEOUT
from .base import BaseScraper, TenderItem

SEARCH_URL = "https://www.ungm.org/Public/Notice/Search"

PAYLOAD = {
    "PageIndex": 0, "PageSize": 30,
    "Title": "", "Description": "", "Reference": "",
    "PublishedFrom": "", "PublishedTo": "", "DeadlineFrom": "", "DeadlineTo": "",
    "Countries": [], "Agencies": [], "UNSPSCs": [], "NoticeTypes": [],
    "SortField": "DatePublished", "SortAscending": False,
    "isPicker": False, "NoticeTASStatus": [], "NoticeDisplayType": None,
    "TypeOfCompetitions": [],
}


class UngmScraper(BaseScraper):
    source_id = "ungm"
    source_name = "ONU - UNGM"
    source_url = "https://www.ungm.org/"
    default_zone = "international"

    def fetch(self) -> list[TenderItem]:
        headers = {
            **DEFAULT_HEADERS,
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        resp = requests.post(SEARCH_URL, json=PAYLOAD, headers=headers,
                             timeout=REQUEST_TIMEOUT + 10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        items: list[TenderItem] = []
        for row in soup.find_all("div", class_="notice-table"):
            notice_id = row.get("data-noticeid")
            title_el = row.find("div", class_="resultTitle")
            title = self.clean_text(title_el.get_text()) if title_el else None
            if not title or not notice_id:
                continue

            agency_el = row.find("div", class_="resultAgency")
            agency = self.clean_text(agency_el.get_text()) if agency_el else None

            deadline_el = row.find("div", class_="deadline")
            deadline = None
            if deadline_el:
                # ex: "19-Jul-2026 19:00 (GMT 2.00) 5.95..." -> garder la date
                txt = self.clean_text(deadline_el.get_text()) or ""
                deadline = txt.split(" ")[0] if txt else None

            # cellules sans classe : [date publiee] ... [type] ... [pays]
            plain_cells = [self.clean_text(c.get_text())
                           for c in row.find_all("div", role="cell")
                           if not c.get("class") or c.get("class") == ["tableCell"]]
            published = plain_cells[0] if plain_cells else None
            notice_type = plain_cells[1] if len(plain_cells) > 1 else None
            country_txt = plain_cells[2] if len(plain_cells) > 2 else None

            country, zone = self.guess_country_zone(
                f"{country_txt or ''} {title}", self.default_zone)

            items.append(TenderItem(
                title=title,
                url=f"https://www.ungm.org/Public/Notice/{notice_id}",
                source_id=self.source_id,
                source_name=self.source_name,
                zone=zone,
                entity=agency,
                category=self.guess_category(f"{notice_type or ''} {title}"),
                country=country or country_txt,
                published_date=published,
                deadline_date=deadline,
                description=notice_type,
                dedupe_key=f"ungm|{notice_id}",
            ))
        return items
