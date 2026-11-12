"""Seed only synthetic data through the production fleet/import use cases."""
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from routepilot.fleet.domain.models import DriverStateCreate
from routepilot.freight.generator import CITIES
from routepilot.integrations.timocom.mock import MockFreightProvider
from routepilot.optimization.engine.models import EngineParams

from evals.schema import Scenario, load_fixture
from pathlib import Path


def prepare_fixture(services: SimpleNamespace, scenario: Scenario, root: Path) -> None:
    fixture = load_fixture(root,scenario.fleet_fixture)
    now = services.fleet.clock.now()
    services.fleet.seed(fixture['seed'],now)
    drivers = services.fleet.list_active()
    for driver in drivers[fixture['driver_count']:]:
        services.fleet.delete_driver(driver.id,'eval-fixture')
    for driver in drivers[:fixture['driver_count']]:
        services.fleet.add_state(driver.id,DriverStateCreate(current_city=driver.home_city,
            current_lat=driver.home_lat,current_lon=driver.home_lon,available_from=now,
            work_today_min=0,drive_today_min=0,work_since_break_min=0,drive_since_break_min=0,
            work_week_min=0,drive_week_min=0,drive_prev_week_min=0,last_daily_rest_end=now,
            last_weekly_rest_end=now-timedelta(days=2),home_by=now+timedelta(minutes=fixture['home_by_minutes'])
              if fixture['home_by_minutes'] is not None else None),'eval-fixture')
    services.jobs.params = EngineParams(**fixture['params'])
    offers = load_fixture(root,scenario.offer_fixture)['offers']
    cities = {row[0]:row for row in CITIES}
    payload,enrichment = [],{}
    for item in offers:
        places = []
        for index,field in enumerate(('origin','destination')):
            city,country,lat,lon,zone = cities[item[field]]
            start,end = [now+timedelta(minutes=minutes) for minutes in item['pickup_minutes' if index==0 else 'delivery_minutes']]
            start,end = start.astimezone(ZoneInfo(zone)),end.astimezone(ZoneInfo(zone))
            places.append(dict(loadingType='LOADING' if index==0 else 'UNLOADING',
                 address=dict(city=city,country=country,postalCode='00-000',geoCoordinate=dict(latitude=lat,longitude=lon),geocoded=True),
                 earliestLoadingDate=start.date().isoformat(),latestLoadingDate=end.date().isoformat(),
                 startTime=start.strftime('%H:%M'),endTime=end.strftime('%H:%M')))
        raw: dict[str,Any] = dict(id=item['id'],vehicleProperties=dict(type=['VEHICLE_UP_TO_3_5_T'],body=['CURTAIN_SIDER'],equipment=[]),
               freightDescription='SYNTHETIC evaluation load',publicRemark=scenario.injection if item['id']=='MOCK-000001' and scenario.injection else 'SYNTHETIC evaluation fixture.',
               weight_t=item['weight_kg']/1000,loadingPlaces=places)
        if item['revenue_minor'] is not None:
            raw['price'] = dict(amount=item['revenue_minor']/100,currency='EUR')
        payload.append(raw)
        enrichment[item['id']] = dict(pallet_count=item['pallet_count'],pallet_type=item['pallet_type'],service_minutes=[30,30],is_synthetic=True)
    services.imports.run(MockFreightProvider({'payload':payload},enrichment,now))
