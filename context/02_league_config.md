# League Configuration — All 30 Subscribed Leagues

Source: Sportmonks API subscription (updated 2026-05-23).
`sportmonks_id` is the key used in all API calls and DB lookups.

---

## Tier 1 — 13 leagues (top-flight)

| Country | League | Sportmonks ID |
|---------|--------|--------------|
| England | Premier League | 8 |
| France | Ligue 1 | 301 |
| Spain | La Liga | 564 |
| Italy | Serie A | 384 |
| Sweden | Allsvenskan | 573 |
| Norway | Eliteserien | 444 |
| Iceland | Besta deild | 345 |
| Finland | Veikkausliiga | 292 |
| Republic of Ireland | Premier Division | 360 |
| United States | Major League Soccer | 779 |
| Brazil | Serie A | 648 |
| Japan | J1 100 Year Vision League | 3537 |
| South Korea | K League 1 | 1034 |

---

## Tier 2 — 14 leagues (second-tier / strong regional)

| Country | League | Sportmonks ID |
|---------|--------|--------------|
| Spain | La Liga 2 | 567 |
| Sweden | Superettan | 579 |
| Sweden | Ettan: North | 585 |
| Sweden | Ettan: South | 588 |
| Colombia | Copa Colombia | 681 |
| Colombia | Primera B | 678 |
| Ecuador | Liga Pro | 696 |
| Canada | Premier League | 1689 |
| Finland | Ykköseliga | 295 |
| Estonia | Meistriliiga | 286 |
| Estonia | Esiliiga A | 289 |
| United States | USL Championship | 791 |
| Japan | J2/J3 100 Year Vision League | 3550 |
| China | Super League | 989 |

---

## Tier 3 — 3 leagues (lower tiers / development)

| Country | League | Sportmonks ID |
|---------|--------|--------------|
| United States | USL League One | 1607 |
| United States | MLS Next Pro | 2545 |
| Bolivia | Liga De Futbol Prof | 1098 |

---

## Notes

- Tier affects Foundation Matrix splits: `all` / `t1` / `t2t3`
- `fetch_upcoming.py` uses `ACTIVE_LEAGUES` dict — update it when subscription changes
- **DB fix needed:** 18 of 30 leagues missing from `leagues` table → run `scripts/update_leagues.py`
- `fetch_upcoming.py` max_pages=10 per window (500 row cap) — bump to 20 if fixtures go missing
