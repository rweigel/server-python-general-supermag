# Usage:
#   python catalog.py --help

BASE_URL = "https://supermag.jhuapl.edu/lib/services/inventory.php"

# Time between requests in seconds, to avoid overwhelming the server.
DEFAULT_REQUEST_DELAY = 0.1

# Timeout in seconds for each HTTP request.
DEFAULT_TIMEOUT = 5

def create_catalog(start, stop, catalog_dir):
  import datetime as dt
  import json

  inventory_dir = catalog_dir / 'inventories'

  start_date = dt.datetime.strptime(start, '%Y-%m-%d').date()
  stop_date = dt.datetime.strptime(stop, '%Y-%m-%d').date()
  if stop_date < start_date:
    raise ValueError('stop must be on or after start')

  def _inventory_date_from_file(catalog_file):
    import datetime as dt
    date_str = catalog_file.stem.removeprefix('inventory-')
    return dt.datetime.strptime(date_str, '%Y-%m-%d').date()


  def _available_value(available_dates):
    available_dates = sorted(available_dates)
    if not available_dates:
      return []

    expected_dates = set(_date_range(available_dates[0], available_dates[-1]))
    if expected_dates == set(available_dates):
      return None

    return [current.isoformat() for current in available_dates]


  def _availability_percent(available_dates):
    available_dates = sorted(available_dates)
    if not available_dates:
      return 0.0

    total_days = len(list(_date_range(available_dates[0], available_dates[-1])))
    return len(available_dates) / total_days


  def _unavailable_value(available_dates):
    available_dates = sorted(available_dates)
    if not available_dates:
      return []

    available_set = set(available_dates)
    return [
      current.isoformat()
      for current in _date_range(available_dates[0], available_dates[-1])
      if current not in available_set
    ]


  def _stations_from_payload(payload):
    if isinstance(payload, dict):
      return payload.get('stations', [])
    if isinstance(payload, list):
      return payload
    return []


  def _write_files(catalog):
    import gzip

    catalog_dir.mkdir(parents=True, exist_ok=True)
    catalog_file = catalog_dir / 'catalog.json'
    timestamp = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    catalog_snapshot_file = catalog_dir / 'catalogs' / f'catalog-{timestamp}.json.gz'
    catalog_snapshot_file.parent.mkdir(parents=True, exist_ok=True)

    with catalog_file.open('w') as stream:
      json.dump(catalog, stream, indent=2)
      stream.write('\n')

    with gzip.open(catalog_snapshot_file, 'wt') as stream:
      json.dump(catalog, stream, indent=2)
      stream.write('\n')

    print(f'Writing {catalog_file} with {len(catalog)} stations')
    print(f'Writing {catalog_snapshot_file}')


  station_ranges = {}
  inventory_files = list(inventory_dir.glob('inventory-*.json'))
  print(f'Reading {len(inventory_files)} inventory files in {inventory_dir}')

  for catalog_file in inventory_files:
    catalog_date = _inventory_date_from_file(catalog_file)
    if catalog_date < start_date or catalog_date > stop_date:
      continue
    date_iso = catalog_date.isoformat()
    with catalog_file.open() as stream:
      payload = json.load(stream)

    for station_id in _stations_from_payload(payload):
      station_info = station_ranges.setdefault(
        station_id,
        {
          'x_startDate': date_iso,
          'x_stopDate': date_iso,
          'dates': set(),
        },
      )
      if date_iso < station_info['x_startDate']:
        station_info['x_startDate'] = date_iso
      if date_iso > station_info['x_stopDate']:
        station_info['x_stopDate'] = date_iso
      station_info['dates'].add(catalog_date)

  catalog = [
    {
      'id': station_id,
      'x_startDate': station_info['x_startDate'],
      'x_stopDate': station_info['x_stopDate'],
      'x_unavailable': _unavailable_value(station_info['dates']),
      'x_availabile': _available_value(station_info['dates']),
      'x_availability_percent': _availability_percent(station_info['dates']),
    }
    for station_id, station_info in station_ranges.items()
  ]

  _write_files(catalog)

  return catalog


def get_inventories(start, stop,
                    output_dir='catalog',
                    update=False,
                    timeout=DEFAULT_TIMEOUT,
                    delay=DEFAULT_REQUEST_DELAY):

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

  output_dir = output_dir / 'inventories'

  written_files = []
  requested = 0
  for current in _date_range(start, stop):
    output_file = inventory_file_path(output_dir, current)
    if output_file.exists() and not update:
      print(f'{output_file}: (cached)')
      written_files.append(output_file)
      continue

    if requested > 0 and delay > 0:
      time.sleep(delay)

    payload = _get_one_inventory(current, timeout=timeout)
    requested += 1
    stations = payload.get('stations', []) if isinstance(payload, dict) else []
    output_file = write_inventory_file(output_dir, current, payload)
    print(f'{output_file}: {len(stations)} stations')
    written_files.append(output_file)

  return written_files


def _get_one_inventory(start, timeout=60):
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

  with urlopen(inventory_url(start), timeout=timeout) as response:
    return json.load(response)


def _date_range(start, stop):
  import datetime as dt
  current = start
  while current <= stop:
    yield current
    current += dt.timedelta(days=1)


def parse_args():
  import argparse
  import datetime as dt
  from pathlib import Path

  default_start = '1970-01-01'
  default_stop = (dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1)).isoformat()

  epilog =  'Examples:\n'
  epilog += '  python3 catalog.py # Makes requests for ~365x55 inventories.\n'
  epilog += '  python3 catalog.py --start 2000-01-01 --stop 2000-01-03 --output-dir catalog\n'
  epilog += '  python3 catalog.py --start 2000-01-01 --stop 2000-01-03 --output-dir catalog --update\n'
  parser = argparse.ArgumentParser(
    description='Fetch daily SuperMAG inventories and create HAPI catalog response.',
    epilog=epilog,
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )

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
    default=Path(__file__).resolve().parent.parent / 'data',
    type=Path,
    help='Base directory for outputs. Defaults to ../data relative to catalog.py.',
  )
  parser.add_argument(
    '--timeout',
    default=DEFAULT_TIMEOUT,
    type=int,
    help=f'HTTP timeout in seconds for each fetch. Default: {DEFAULT_TIMEOUT}.',
  )
  parser.add_argument(
    '--update',
    action='store_true',
    help='Refetch and overwrite existing inventory files instead of skipping them.',
  )
  parser.add_argument(
    '--delay',
    default=DEFAULT_REQUEST_DELAY,
    type=float,
    help=f'Delay in seconds between actual HTTP requests. Default: {DEFAULT_REQUEST_DELAY}.',
  )
  return parser.parse_args()


if __name__ == '__main__':

  args = parse_args()

  kwargs = {
    'output_dir': args.output_dir,
    'update': args.update,
    'timeout': args.timeout,
    'delay': args.delay,
  }

  get_inventories(args.start, args.stop, **kwargs)
  create_catalog(args.start, args.stop, args.output_dir)
