"""
Writes combined inventory file ../data/inventory.json based on content of files
in ../data/inventories

For usage, see:
  python inventory.py --help

Create combined inventory file using daily inventory from 1970-01-01 through tomorrow
  Re-fetch daily inventory files
    python inventory.py --update-inventory
  Use cached inventory files when available
    python inventory.py

Short tests:
  python inventory.py --start 1970-01-01 --stop 1970-01-10
  python inventory.py --start 1970-01-01 --stop 1970-01-10 --update-inventory
"""

import logging

from util import _path_relative_to_cwd, configure_logging, set_logging_level

logger = configure_logging(__name__, level=logging.INFO)

BASE_URL = "https://supermag.jhuapl.edu/lib/services/inventory.php"

def create_combined_inventory(start, stop, output_dir,
                              update_inventory=False,
                              update_locations=False,
                              station_id=None,
                              partial_output=False,
                              timeout=5,
                              delay=0.0):

  inventories = get_inventories(args.start, args.stop,
                                output_dir=args.output_dir,
                                update=update_inventory,
                                timeout=timeout,
                                delay=delay)

  logger.info(f'Parsing {len(inventories)} inventories')
  requested_station_id = station_id

  # Key: station id, value: dict of dates data available
  station_availability = {}
  for inventory_date, station_ids in inventories.items():

    s = '' if len(station_ids) == 1 else 's'
    logger.info(f'  Found {len(station_ids)} station{s} on {inventory_date}')
    for station_id in station_ids:

      if station_id not in station_availability:
        station_availability[station_id] = []

      station_availability[station_id].append(inventory_date)


  s = '' if len(station_availability) == 1 else 's'
  logger.info(f'Creating combined inventory with {len(station_availability)} stations')
  inventory = []
  for inventory_station_id, available_dates in station_availability.items():
    available_dates = sorted(available_dates)
    entry = {
        'id': inventory_station_id,
        'startDate': available_dates[0],
        'stopDate': available_dates[-1],
        'available_percent': 100.0
      }

    all_dates = _date_range(available_dates[0], available_dates[-1], format='str')
    n_days = len(all_dates)
    if len(all_dates) != len(available_dates):
      entry['available'] = available_dates
      entry['available_percent'] = 100 * len(available_dates) / len(all_dates)
      entry['unavailable'] = sorted(set(all_dates) - set(available_dates))

    inventory.append(entry)

  if requested_station_id is not None:
    inventory = [entry for entry in inventory if entry['id'] == requested_station_id]
    if not inventory:
      raise ValueError(f"Station ID not found in combined inventory: {requested_station_id}")
    logger.info(f'Filtered inventory to station {requested_station_id}')

  logger.info("Getting geographic locations for each station")
  geo_locations = _get_locations(
    inventory,
    output_dir,
    start=start,
    stop=stop,
    station_id=requested_station_id,
    partial_output=partial_output,
    update=update_locations,
  )

  logger.info("Inventory summary")
  for entry in inventory:
    if entry['id'] in geo_locations:
      location = geo_locations[entry['id']]
      entry['location'] = location

    logger.info(f"{entry['id']}: ")
    logger.info(f"  startDate: {entry['startDate']}")
    logger.info(f"  stopDate:  {entry['stopDate']}")
    logger.info(f"  Unavailable: {len(entry.get('unavailable', []))}/{n_days} ({100-entry['available_percent']:.1f}%)")
    logger.info(f"  Geographic location changed: {entry.get('geo_location_changed', False)}")
    for date_key in ['start', 'stop']:
      if entry.get('location', {}).get(date_key, {}).get('error'):
        msg = f"{date_key}Date: {entry['location'][date_key]['error']}"
        logger.info(f"  Error fetching geographic location on {msg}")
      elif entry.get('location', {}).get(date_key):
        glat = entry['location'][date_key]['glat']
        glon = entry['location'][date_key]['glon']
        logger.info(f"  Geographic location on {date_key}Date (lat, lon): ({glat}°, {glon}°)")


  _write_files(
    inventory,
    output_dir,
    start=start,
    stop=stop,
    station_id=requested_station_id,
    partial_output=partial_output,
  )

  return inventory


def get_inventories(start, stop, output_dir='catalog', update=False, timeout=0.0, delay=5):

  import time

  def parse_date(value):
    import datetime as dt
    return dt.datetime.strptime(value, '%Y-%m-%d').replace(tzinfo=dt.timezone.utc)

  def inventory_file_path(output_dir, start):
    return output_dir / f"inventory-{start:%Y-%m-%d}.json"

  def write_inventory_file(output_dir, start, payload):
    import json
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = inventory_file_path(output_dir, start)
    output_file.write_text(json.dumps(payload, indent=2) + '\n')
    return output_file

  start = parse_date(start)
  stop = parse_date(stop)
  if stop < start:
    raise ValueError('stop must be on or after start')

  inventory_dir = output_dir / 'inventories'

  inventory_data = {}
  requested = 0
  for current in _date_range(start, stop):

    file_date = current.strftime('%Y-%m-%d')
    logger.info("Getting inventory for {}".format(file_date))

    output_file = inventory_file_path(inventory_dir, current)
    if output_file.exists() and not update:
      logger.info(f'  Found cache: {_path_relative_to_cwd(output_file)}')
      with output_file.open() as stream:
        import json
        payload = json.load(stream)
      inventory_data[file_date] = payload['stations'] if isinstance(payload, dict) else []
      continue

    if requested > 0 and delay > 0:
      time.sleep(delay)

    payload = _get_inventory(current, timeout=timeout)
    requested += 1
    stations = payload.get('stations', []) if isinstance(payload, dict) else []
    output_file = write_inventory_file(inventory_dir, current, payload)
    logger.info(f'  {_path_relative_to_cwd(output_file)}: {len(stations)} stations')
    inventory_data[file_date] = payload['stations'] if isinstance(payload, dict) else []

  return inventory_data


def _get_locations(entry, output_dir, start, stop, station_id=None, partial_output=False, update=False):
  from locations import fetch_locations

  output_file = output_dir / 'locations.json'
  if station_id is not None:
    output_file = output_dir / 'partial' / f'locations-{station_id}.json'
  elif partial_output:
    output_file = output_dir / 'partial' / f'locations-{start}-{stop}.json'

  return fetch_locations(entry, output_dir, update=update, output_file=output_file)


def _get_inventory(start, timeout=5):
  import json
  from urllib.request import urlopen

  def inventory_url(start):
    from urllib.parse import urlencode
    query = urlencode({
      'service': 'inventory',
      'start': start.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
      'interval': 1440,
      'fidelity': '60s',
    })
    return f'{BASE_URL}?{query}'

  logger.debug(f"  Fetching {inventory_url(start)}")
  with urlopen(inventory_url(start), timeout=timeout) as response:
    return json.load(response)


def _write_files(inventory, output_dir, start, stop, station_id=None, partial_output=False):

  import json
  import gzip
  import datetime as dt

  output_dir.mkdir(parents=True, exist_ok=True)
  timestamp = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
  if station_id is None:
    if partial_output:
      inventory_file = output_dir / 'partial' / f'inventory-{start}-{stop}.json'
      archive_file = None
    else:
      inventory_file = output_dir / 'inventory.json'
      archive_file = output_dir / 'archive' / f'inventory-{timestamp}.json.gz'
      archive_file.parent.mkdir(parents=True, exist_ok=True)
  else:
    inventory_file = output_dir / 'partial' / f'inventory-{station_id}.json'
    archive_file = None

  inventory_file.parent.mkdir(parents=True, exist_ok=True)

  logger.info(f'Writing {_path_relative_to_cwd(inventory_file)} with {len(inventory)} stations')
  with inventory_file.open('w') as stream:
    json.dump(inventory, stream, indent=2)
    stream.write('\n')

  if archive_file is None:
    return

  logger.info(f'Writing {_path_relative_to_cwd(archive_file)} with {len(inventory)} stations')
  with gzip.open(archive_file, 'wt') as stream:
    json.dump(inventory, stream, indent=2)
    stream.write('\n')


def _date_range(start, stop, format='datetime'):
  import datetime as dt

  if isinstance(start, str):
    start = dt.datetime.strptime(start, '%Y-%m-%d').replace(tzinfo=dt.timezone.utc)
  if isinstance(stop, str):
    stop = dt.datetime.strptime(stop, '%Y-%m-%d').replace(tzinfo=dt.timezone.utc)

  dates = []
  current = start
  while current <= stop:
    if format == 'datetime':
      dates.append(current)
    if format == 'str':
      dates.append(current.strftime('%Y-%m-%d'))
    current += dt.timedelta(days=1)

  return dates


def parse_args():
  import argparse
  import sys
  import datetime as dt
  from pathlib import Path

  default_start = '1970-01-01'
  tomorrow = dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1)
  default_stop  = (tomorrow).isoformat()
  default_timeout = 5
  default_request_delay = 0.0

  epilog =  'Examples:\n'
  epilog += '  python3 inventory.py\n'
  epilog += '  python3 inventory.py --update-inventory\n'
  epilog += '  python3 inventory.py --update-locations\n'
  epilog += '  python3 inventory.py --start 2000-01-01 --stop 2000-01-03 --update-inventory --update-locations\n'
  epilog += 'If --station-id, --start, or --stop is given, output is written to OUTPUT_DIR/partial\n'
  parser = argparse.ArgumentParser(
    description='Fetch daily SuperMAG inventories and create HAPI catalog response.',
    epilog=epilog,
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )

  output_dir = Path(__file__).resolve().parent.parent / 'data'
  parser.add_argument(
    '--start',
    default=default_start,
    help=f'First UTC day to fetch, in YYYY-MM-DD format. Default: {default_start}.',
  )
  parser.add_argument(
    '--stop',
    default=default_stop,
    help=f'Last UTC day to fetch, in YYYY-MM-DD format. Default: {default_stop}.',
  )
  parser.add_argument(
    '--output-dir',
    default=output_dir,
    type=Path,
    help=f'Base directory for outputs. Default: {_path_relative_to_cwd(output_dir)}.',
  )
  parser.add_argument(
    '--station-id',
    default=None,
    help='Only include the given station ID in the combined inventory output.',
  )
  parser.add_argument(
    '--timeout',
    default=default_timeout,
    type=int,
    help=f'HTTP timeout in seconds for each fetch. Default: {default_timeout}.',
  )
  parser.add_argument(
    '--update-inventory',
    action='store_true',
    help='Refetch and overwrite existing daily inventory files.',
  )
  parser.add_argument(
    '--update-locations',
    action='store_true',
    help='Refetch station locations even when cached locations already exist.',
  )
  parser.add_argument(
    '--delay',
    default=default_request_delay,
    type=float,
    help=f'Delay in seconds between actual HTTP requests. Default: {default_request_delay}.',
  )
  parser.add_argument(
    '--debug',
    action='store_true',
    help='Enable debug logging.',
  )
  args = parser.parse_args()
  args.partial_output = '--start' in sys.argv[1:] or '--stop' in sys.argv[1:]
  return args


if __name__ == '__main__':

  args = parse_args()

  if args.debug:
    import data
    import locations

    set_logging_level(logging.DEBUG, [__name__, locations.__name__, data.__name__])
    logger.debug('Debug logging enabled')

  kwargs = {
    'update_inventory': args.update_inventory,
    'update_locations': args.update_locations,
    'station_id': args.station_id,
    'partial_output': args.partial_output,
    'timeout': args.timeout,
    'delay': args.delay,
  }

  create_combined_inventory(args.start, args.stop, args.output_dir, **kwargs)
