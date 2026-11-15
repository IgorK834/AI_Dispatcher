# Research: how LTL transport works, and how RoutePilot plans it today

> **Status:** research note, 2026-11-15. It changes no specification, contract or code. Every change it proposes in §8 needs a specification (and owner approval) first. All figures for RoutePilot come from the **synthetic** demo generators (`is_synthetic = true`). Prices in the worked example are **illustrative assumptions**, not market data.

## 1. Summary

- **LTL (less-than-truckload) is a fill-the-van business.** A consignment of 1–4 pallets pays only a share of a full-van price. A van earns money only when several consignments are on board at the same time. So a good plan collects many pallets in a small pickup area, drives them together along one corridor, delivers them in a small delivery area, then collects a return load near the last drop.
- **RoutePilot's engine can already do this.** The search lets a driver pick up several offers before delivering any of them, with a pallet and kg check on every step (`GOLD-001`: `pick A → pick B → drop A → pick C → drop B → drop C`).
- **The plans still come out as chains (A→B, then B→C) because of the inputs, not the solver core.** Measured on seeded demo data (§6.2):
  - 81% of offers have **no consolidation partner**: no other offer picked up within 50 km on the same day and delivered within 100 km.
  - In the fleet profit solution, **half of the plans never carry more than one order at a time**.
  - The vans run at **46% pallet fill and 40% weight fill**, averaged per km. Empty kilometres are only 11%. The van is seldom empty, but it is usually **half empty**.
- **Root causes, in order of impact:**
  1. Demo prices follow a full-van model: `rate × distance`, with no link to pallets or weight. A 1-pallet order pays as much as a 10-pallet order on the same lane, so a lone 1-pallet order already looks profitable.
  2. Offers are scattered at random over 39 city centres in 11 countries, so pickups are almost never close together.
  3. Offer weight is random (40–1 085 kg) and not linked to the pallet count, so one order often uses most of a van's 765–1 085 kg payload.
  4. When the pool is capped, offers are ranked one at a time by revenue per km. Offers that would be cheap to add next to another offer get no credit for it.

## 2. Terms

| Term | Meaning |
|---|---|
| **FTL** (full truckload) | One customer hires the whole vehicle. Priced per vehicle and per km or lane. The vehicle goes straight from A to B. |
| **PTL** (partial truckload) | A large part of the vehicle (in practice about 6–10 loading metres on a trailer) for one customer. It travels directly, often shared with one or two other loads. |
| **LTL** (less-than-truckload) | Small consignments (1–n pallets) from many customers share one vehicle. Priced per pallet, loading metre or weight. |
| **Groupage** | The European name for LTL that runs through a **hub-and-spoke network**: collect, sort at a hub, run a linehaul between hubs, sort again, deliver. |
| **Direct LTL / partial loads** | LTL **without hubs**. One vehicle collects several consignments and delivers them directly on one trip. This is the model for a small van fleet. |
| **LDM** (loading metre) | Metre of loading-floor length across the full width: `length × width / 2.4`. 1 EUR pallet (1.2 × 0.8 m) = **0.4 LDM**. |
| **EP** (pallet equivalent) | RoutePilot's capacity unit: EUR = 1, industrial 1200×1000 = 1.5, half pallet = 0.5 ([prefilter.py](../apps/api/src/routepilot/optimization/engine/prefilter.py)). |
| **Milk run** | One vehicle visits several pickup and/or delivery points on one planned round, instead of one vehicle per point. |
| **Backhaul** | A load taken on the way back towards base, so the return leg is not driven empty. |
| **Load factor** | Share of capacity used, best measured per km: `Σ(EP on board × km) / Σ(EP capacity × km)`. |

## 3. How LTL works in the market

### 3.1 Two operating models

**A. Hub-and-spoke groupage (large networks).** Carriers collect small consignments from many customers, combine them at a hub and ship them together. At the destination hub they split the load and deliver each consignment separately. Long legs between hubs run as full trucks. LTL and groupage volumes are combined in hub operations. This needs terminals, sorting and scheduled departures, so it does not fit a fleet of five vans.

**B. Direct LTL (vans and small carriers).** The vehicle does not go through hubs: it *"stops directly at different loading and unloading points along its route"* (Rhenus). A van takes partial loads ("doładunki"), collects them along its way and delivers them without sorting. **This is the model RoutePilot should plan for.**

### 3.2 What a direct-LTL van trip looks like

```
 base ──► [PICKUP CLUSTER]  ──────── corridor / linehaul ────────►  [DELIVERY CLUSTER]
           P1 P2 P3 P4                (van 70–100 % full)             D1 D2 D3 D4
           radius ≈ 30–80 km                                          radius ≈ 50–150 km
                                                                           │
 base ◄── [DELIVERY CLUSTER 2] ◄──── corridor back (backhaul) ◄─── [PICKUP CLUSTER 2]
           D5 D6 D7                                                  P5 P6 P7  (near D4)
```

1. **Collect.** Visit 3–6 shippers close together (an industrial area, a town and its suburbs), on the same day or half-day. The van fills up step by step.
2. **Linehaul.** Drive the full van along **one corridor** (e.g. Upper Silesia → Saxony). These kilometres earn the most, because every pallet on board pays for them.
3. **Distribute.** Drop in the destination region. The order of drops follows the loading order (last in, first out on a curtain-sider loaded from the back).
4. **Re-load near the last drop.** Pick up return consignments as close as possible to the last delivery, heading towards base. Deadhead (empty) km are kept short.
5. **Home.** Return to base before the weekend deadline.

Rules of thumb that follow from this:

- **Close pickups, similar destinations.** Two consignments go well together when their pickups are close, their deliveries are close **and** their time windows overlap. A consignment that heads the opposite way is a cost, even if it is cheap to pick up.
- **Fill is earned on the long leg.** Ten pallets over 400 km pay for the 400 km ten times over. One pallet over the same 400 km pays for it once.
- **Short local detours are cheap; corridor changes are expensive.** A 15 km detour to add 2 pallets is almost always worth it. A 150 km detour is almost never worth it.
- **For 3.5 t vans, weight usually binds before space.** A 10 EP van carries only ~0.8–1.1 t. With ordinary pallets (150–300 kg each) the van "weighs out" at 4–7 pallets. Light, bulky consignments are the best fit, so price per kg matters as much as price per pallet.
- **Time windows decide what can be combined.** Pickup windows in a cluster must fit a single morning or day. Delivery windows must fit one distribution run.
- **Working time is part of the plan.** Every extra stop costs service time (loading, paperwork, waiting) and counts as working time.

### 3.3 How LTL is priced

| Pricing unit | Typical use | Notes |
|---|---|---|
| **Per pallet** | Common lanes, standard pallets | Often by distance band or zone; the price per pallet falls as the pallet count rises |
| **Per loading metre (LDM)** | European groupage | `LDM = length × width / 2.4`; stackable goods count half; usually a 1 LDM minimum |
| **Per weight** (e.g. per 100 kg / CWT) | Heavy goods; US LTL | Rate per 100 kg falls in weight tiers; carriers charge on weight if it exceeds a per-LDM threshold (often 1 750–1 850 kg/LDM) |
| **Density / freight class** | US LTL (NMFC) | Density is the main driver; lane volume matters too |
| **Surcharges** | All | Fuel surcharge, tail lift, time slot, waiting time |

Market facts that matter for the planning model:

- **A small consignment pays a share of a full-van price, not the full price.** One source puts the point where groupage costs about half an FTL price at ~6 LDM on a 13.6 LDM trailer. That is about 44% of the space for 50% of the price, so the price per space is higher for small loads. The carrier earns that premium only if the rest of the space is sold too.
- **Price follows the lane, not only the km.** Busy corridors price lower than thin or remote ones.
- **Minimum charges** make very small consignments (1 pallet, short distance) relatively expensive for the shipper and attractive for the carrier, if they fit into an existing trip.

### 3.4 Economics: the break-even fill

With an all-in cost per km `c` (fuel + vehicle + driver time) and a per-pallet rate `r` (€ per EP per km), the van covers its costs on a leg only when it carries on average

```
EP_on_board ≥ c / r
```

Illustration with RoutePilot's demo cost profile: fuel ≈ 10 l/100 km × 1.81 €/l ≈ 0.18 €/km, vehicle 0.12 €/km, driver 14 €/h at ~70 km/h ≈ 0.20 €/km, so **c ≈ 0.50 €/km**. Take an *assumed* LTL rate of **r = 0.12 €/EP/km**: the demo full-van rate of 0.85 €/km spread over 10 EP, plus a ~40% small-consignment premium. Then:

- break-even = 0.50 / 0.12 ≈ **4.2 EP on board on every km** (~42% of a 10 EP van);
- at 8 EP on board: revenue 0.96 €/km → margin ≈ **+0.46 €/km**;
- at 2 EP on board: revenue 0.24 €/km → margin ≈ **−0.26 €/km**.

So in LTL, the **load factor decides profit**. Under per-pallet pricing, a chain of 1–3 pallet loads loses money on every km. That is why carriers consolidate.

### 3.5 KPIs that LTL planners watch

| KPI | Formula | Why |
|---|---|---|
| Load factor (EP) | Σ(EP × km) / Σ(capacity EP × km) | Main driver of profit (§3.4) |
| Load factor (kg) | Σ(kg × km) / Σ(payload × km) | Vans usually weigh out first |
| Empty-km share | empty km / total km | EU average ≈ 20% of road freight vehicle-km (2020); 24% domestic, 13% international |
| Revenue per km | revenue / total km | Compares plans of different length |
| Revenue per EP-km | revenue / Σ(EP × km) | Checks the tariff |
| Stops per trip, km per stop | — | Cost of consolidation (service time, detours) |
| Consignments on board (max/avg) | — | Shows whether the plan consolidates at all |

## 4. How a good plan should look (target behaviour)

For one driver over the horizon, the **target** plan has these properties:

1. **Pickup cluster:** 2–6 pickups within a small radius (≈ 30–80 km) and a compatible time window (same day / half-day).
2. **One corridor:** all consignments of that cluster are delivered in one destination region (≈ 50–150 km radius), in the direction of travel.
3. **High fill on the long leg:** the longest leg of the trip has the most EP/kg on board (target ≥ 70% of the binding dimension, weight or pallets).
4. **Backhaul near the last drop:** the next pickup cluster starts close to the last delivery and leads towards base or the next corridor.
5. **Short empty legs:** empty km only from base to the first pickup, between clusters, and home.
6. **Loading order respected:** drop order matches load order, or the plan says it was not checked.
7. **Legal profile and home-by deadline** held, as today.

A chain of single orders (A→B, B→C, C→D with one order on board at a time) is a valid plan, but it is the **fallback** when no consolidation partner exists, not the normal shape.

## 5. Worked example (illustrative)

Driver in Katowice, 10 EP / 1 085 kg van. Distances are rounded road estimates. Cost `c = 0.50 €/km` plus ~7 € per stop (30 min of driver time). Two tariffs: the **app's current demo tariff** (`rate × distance`, any pallet count; PL→DE 0.68 €/km, DE→DE and DE→PL 0.476 €/km, minimum 120 €) and the **assumed LTL tariff** (`0.12 €/EP/km`, minimum 60 €).

**Plan 1: chain of single orders (what RoutePilot produces today)**

| Leg | On board | km |
|---|---|---|
| Katowice → Dresden | order A, 2 EP / 600 kg | 400 |
| Dresden → Leipzig | order B, 3 EP / 450 kg | 115 |
| Leipzig → Wrocław | order C, 2 EP / 500 kg | 350 |
| **Total** | max 1 order, ≈ 2.3 EP | **865** |

**Plan 2: consolidated direct LTL (target shape)**

| Phase | Stops | km | On board after phase |
|---|---|---|---|
| Collect around Katowice | Gliwice 3 EP/270 kg, Chorzów 2 EP/180 kg, Tychy 2 EP/200 kg, Bielsko-Biała 2 EP/250 kg | 90 | 9 EP / 900 kg |
| Linehaul to Saxony | — | 400 | 9 EP / 900 kg |
| Distribute | Dresden, Chemnitz, Leipzig | 180 | 0 |
| Backhaul collect around Leipzig/Dresden | 3 pickups, 8 EP / 850 kg towards Wrocław/Opole/Katowice | 60 | 8 EP / 850 kg |
| Linehaul back + drops | Wrocław, Opole, Katowice | 450 | 0 |
| **Total** | 14 stops | **1 180** | avg ≈ 6.8 EP per km |

**Result**

| | Revenue (app tariff) | Revenue (LTL tariff) | Cost | Profit (app tariff) | Profit (LTL tariff) |
|---|---|---|---|---|---|
| Plan 1: chain | 272 + 120 + 167 = **559 €** | 96 + 60 + 84 = **240 €** | 433 + 42 = **475 €** | **+84 €** | **−235 €** |
| Plan 2: consolidated | 4 × ~430 km × 0.68 + 3 × ~400 km × 0.476 ≈ **1 740 €** | 9 EP × ~430 km × 0.12 + 8 EP × ~400 km × 0.12 ≈ **850 €** | 590 + 98 = **688 €** | ≈ **+1 050 €** | **≈ +160 €** |

How to read it:

- Under the **LTL tariff**, only the consolidated plan makes money. The chain loses money on every km (2.3 EP on board < 4.2 EP break-even).
- Under the **app's tariff**, the chain is already profitable, so the engine has no economic pressure to consolidate. The consolidated plan would look far too profitable (seven consignments, each paid like a full van), but the demo data almost never contains such a cluster (§6.2), so the engine never sees it.
- The real lesson: the tariff decides whether consolidation is **necessary**, and the geography decides whether it is **possible**. Today the demo data makes it unnecessary *and* nearly impossible.

## 6. How it works in RoutePilot today

### 6.1 Pipeline (FEAT-003 engine)

1. **Prefilter per driver** ([prefilter.py](../apps/api/src/routepilot/optimization/engine/prefilter.py)): status, vehicle/body/equipment, price, coordinates, pallets and kg of each offer **on its own** against the van, horizon, pickup reachable. If more than `max_pool_per_driver = 60` offers remain, it keeps the top 60 by `revenue / (deadhead + loaded km)` of each offer **alone** ([prefilter.py:99-110](../apps/api/src/routepilot/optimization/engine/prefilter.py:99)).
2. **Branch-and-bound per driver** ([search.py](../apps/api/src/routepilot/optimization/engine/search.py)): from each state, the moves are "deliver any offer on board" or "pick up any offer from the pool" ([search.py:108-112](../apps/api/src/routepilot/optimization/engine/search.py:108)), up to `max_offers_per_plan = 6` ([models.py:130-134](../apps/api/src/routepilot/optimization/engine/models.py:130)). Each step checks working time, windows and **two-dimensional capacity (EP and kg)** ([schedule.py](../apps/api/src/routepilot/optimization/engine/schedule.py)). Top-K plans by profit, fastest and fuel.
3. **Fleet assignment** ([fleet.py](../apps/api/src/routepilot/optimization/engine/fleet.py)): exact set packing; each offer goes to at most one driver; total profit is maximised and must not be worse than the single-order and greedy baselines.

**What is already right for LTL:** interleaved pickups and deliveries (a pickup-and-delivery problem with time windows and profits), EP + kg capacity checked at every step, fuel that depends on load, return-to-base, and a fleet-level choice. The `GOLD-001` golden case is exactly an LTL sequence. The **solver can consolidate; the inputs give it no reason and almost no chance to.**

### 6.2 Measurements on demo data

Method: scratch scripts (not committed) reuse `bench/fleet_5x60.py::build_instance`, which uses the repository generators and the haversine routing provider (straight-line based, no external call).

**Consolidation potential of the offers** (5 seeds × 150 offers, 740 offers with coordinates):

| Metric | Value |
|---|---|
| Offers with ≥ 1 partner (pickup ≤ 50 km, same day, delivery ≤ 100 km) | **138 / 740 = 18.6%** |
| Mean number of partners per offer | 0.24 |
| Distinct origin→destination city pairs (3 seeds, 450 offers) | 368 (82% of offers are on a lane of their own) |
| Median / mean straight-line offer distance | 407 km / 482 km |
| Mean weight / mean pallets per offer (3 seeds) | 604 kg / 3.9 EP |

**What the engine chose** (fleet profit solution, 3 seeds, **fallback parameters** `max_offers_per_plan = 4`, `horizon_days = 3`, `top_k = 5`, used to keep runtime short; defaults may produce somewhat fuller plans):

| Metric | Value |
|---|---|
| Plans / offers in plans | 14 / 32 (2.3 offers per plan) |
| Plans with max **1** order on board at a time | **7 of 14** |
| Plans with max 2 / 3 orders on board | 6 / 1 |
| Pallet load factor (EP-km) | **46%** |
| Weight load factor (kg-km) | **40%** |
| Empty-km share | 11% |

So the user-visible pattern ("A→B then B→C, mostly one company on board") is confirmed: half of the plans are pure chains, and the van carries on average less than half of what it could.

### 6.3 Root causes (with code)

| # | Cause | Where | Effect |
|---|---|---|---|
| 1 | **Full-van tariff for every offer.** `amount = max(120, round(rate × distance × noise))`; the rate depends only on the countries, not on pallets or kg. | [generator.py:184-189](../apps/api/src/routepilot/freight/generator.py:184) | A 1-pallet order pays like 10 pallets, so a chain of small orders is profitable and consolidation is never needed (§5). |
| 2 | **Scattered geography.** Origin and destination drawn uniformly from 39 city centres (12 PL, 27 abroad); 45% domestic; points are exact city centres. | [generator.py:12-50](../apps/api/src/routepilot/freight/generator.py:12), [generator.py:141-143](../apps/api/src/routepilot/freight/generator.py:141) | Almost no pickups close together heading the same way (18.6% have a partner). There are no "suburb" points, so "close radius" means only "same city". |
| 3 | **Weight unrelated to pallets.** `weight = randint(40, 1085)` for any pallet count (1–10). Van payloads are 765–1 085 kg. | [generator.py:144-148](../apps/api/src/routepilot/freight/generator.py:144), [fleet/generator.py:12-18](../apps/api/src/routepilot/fleet/generator.py:12) | A single order uses ~60% of payload on average (604 kg). Many pairs cannot share a van, even when pallets fit (e.g. 1 EP at 1 000 kg). |
| 4 | **Time spread.** Pickup day drawn from the working days of the week, start hour 6–14, window 2–8 h; delivery day from distance (`ceil(km/600) − 1`). | [generator.py:130-160](../apps/api/src/routepilot/freight/generator.py:130) | Even same-city offers often fall on different days. |
| 5 | **Pool cap ranks offers alone.** `revenue / (deadhead + loaded km)` per offer, top 60. | [prefilter.py:99-110](../apps/api/src/routepilot/optimization/engine/prefilter.py:99) | Long, well-paid single lanes win. Cheap add-ons next to another offer get no credit. This matters only when the pool exceeds 60. |
| 6 | **No load-factor feedback.** Plans report `empty_km` but no load factor; the profit objective is correct, but with tariff #1 it does not reward fill. | [models.py:211-240](../apps/api/src/routepilot/optimization/engine/models.py:211) | The dispatcher cannot see that a plan is half empty. |
| 7 | **Loading order not modelled** (warning `LOADING_ORDER_NOT_MODELLED` on curtain-siders). | [schedule.py:350](../apps/api/src/routepilot/optimization/engine/schedule.py:350) | Acceptable for the MVP (side loading), but real LTL drop order follows load order. |

## 7. Gap table: target vs today

| Aspect | Target LTL behaviour | RoutePilot today |
|---|---|---|
| Plan shape | Collect cluster → corridor → distribute → backhaul | Mostly chain A→B→C, 1–2 orders on board |
| Pricing | Per EP / LDM / kg, falling with volume, minimum charge, lane-dependent | Per km per offer, independent of size (demo) |
| Pickup proximity | Many consignments within 30–80 km on the same day | City centres only; 18.6% of offers have a partner |
| Direction | Consignments share a corridor | Random destinations |
| Weight vs pallets | Correlated (≈ 100–400 kg per EP) | Independent (40–1 085 kg for 1–10 EP) |
| Binding capacity | Usually weight for vans | Checked (EP + kg) ✓ |
| Interleaved pickup/delivery | Yes | Yes ✓ (search + `GOLD-001`) |
| Candidate selection | Values synergy with nearby offers | Per-offer revenue/km |
| KPIs shown | Load factor EP/kg, revenue per km, empty km | Empty km, distance, profit; no load factor |
| Return to base | Backhaul near last drop | Return to base ✓; backhaul only by chance |

## 8. Proposals (not implemented; each needs a specification and owner approval)

Ordered by expected impact. Items 1–3 change **demo data** (FEAT-002 generator, golden values may move). Items 4–6 change the **engine or contracts** (FEAT-003/004/005).

1. **LTL tariff in the offer generator.** Price = `max(min_charge, Σ EP × distance_band_rate(km) × degression(EP)) × lane_factor × noise`, plus a weight rule (charge by kg when kg/EP is high). Keep `rate_provenance = "assumption"` and document the formula in `price_formula`. → Chains of 1–2 pallets stop being profitable on their own; consolidation becomes necessary (§3.4).
2. **Clustered geography.** Generate offers around "shipper zones": a city plus several jittered points within ~10–60 km. Generate destinations along a few corridors (e.g. Silesia → Saxony, Wielkopolska → Berlin/Hamburg, Łódź → Warsaw) with weights, and put several offers per zone on the same day. → Consolidation becomes possible. Target: ≥ 50% of offers with a partner (metric from §6.2).
3. **Weight correlated with pallets.** `weight ≈ EP × U(80, 350) kg`, with a few dense exceptions kept for the `HEAVY_FOR_8EP` / `TOO_HEAVY_ALL` test tags. → Realistic weight-out behaviour for 3.5 t vans.
4. **Synergy-aware pool cap.** When the pool exceeds 60, rank offers by their best *marginal* profit when inserted next to other pool offers (cheapest insertion), or keep the k nearest neighbours of each top offer. → Cluster members are not cut before the search sees them.
5. **Load-factor KPIs on plans.** Add `load_factor_ep`, `load_factor_kg` and `max_onboard` to `RoutePlan` and to the plan API/UI. → The dispatcher sees "half-empty" at a glance. This is a contract change, so `make openapi` and EN/PL texts are needed.
6. **New golden case for a cluster.** A hand-computed case with four pickups in one zone, one corridor and a backhaul, where the consolidated plan must beat the best chain. → Locks the target behaviour in tests (`make test-props`).

Not proposed for the MVP: hub/cross-dock modelling (no hubs in a 5-van fleet), loading-order (LIFO) modelling, and a separate clustering stage before routing (cluster-first, route-second). The current exact search plus items 2 and 4 should be enough at this scale.

## 9. Method and limits

- Market sources are mostly carrier pages, blogs and calculator sites; treat their numbers as indicative. Eurostat is the only official statistic used. No current zone tariff tables were found.
- The LTL tariff (0.12 €/EP/km) and the stop cost in §3.4 and §5 are **assumptions** made for the illustration, not measured prices.
- The §6.2 measurements use haversine-based distances, 3–5 seeds and, for the engine run, the fallback parameters. Default parameters and road routing may change the numbers somewhat, but not the cause (the input data).
- Scratch measurement scripts were not added to the repository.

## 10. Sources

- Rhenus — groupage transport and network: https://www.rhenus.group/road-transport/groupage-transport/ ; https://www.rhenus.group/uk/en/transport/road-freight/groupage-transport-europe
- DHL Freight — pallets, LTL and groupage; PTL/FTL: https://www.dhl.com/fr-en/home/our-divisions/freight/road-freight/pallets-less-than-truck-load-ltl-and-groupage.html ; https://www.dhl.com/fr-en/home/our-divisions/freight/road-freight/direct-part-and-full-truck-loads-ptl-ftl.html
- Raben — European consolidation hubs: https://ukraine.raben-group.com/en/news/read-more/european-logistics-hubs-how-consolidation-centers-are-transforming-freight-transport-in-europe
- Loading metres and groupage pricing examples: https://dev.to/soap/how-loading-metres-ldm-actually-work-in-european-groupage-freight-with-pricing-examples-4gid ; https://calcargo.pages.dev/en/blog/ftl-vs-ltl-when-is-full-truck-worth-it ; https://quicargo.com/calculate-loadingmeters/
- LTL pricing factors (US): https://arcb.com/blog/mastering-ltl-freight-pricing ; https://www.dat.com/resources/?p=18422 ; https://www.globaltranz.com/resource-hub/ltl-freight-rates/
- Milk run: https://www.sennder.com/glossary/milk-run ; https://racklify.com/encyclopedia/milk-run-vs-direct-shipments-cost-service-and-risk-tradeoffs/
- Eurostat — empty road freight kilometres: https://ec.europa.eu/eurostat/web/products-eurostat-news/-/ddn-20211210-1 ; https://ec.europa.eu/eurostat/statistics-explained/index.php/Road_freight_transport_by_journey_characteristics
- Pickup-and-delivery heuristics (insertion, cluster-first route-second): https://portal.mardi4nfdi.de/wiki/Publication:2433432 ; https://arxiv.org/pdf/2511.07681
- Van partial-load price lists (example): https://zipmend.com/en/freight-forwarder-luxembourg
