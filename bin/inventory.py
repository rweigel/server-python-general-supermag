"""
For usage, see:
  python inventory.py --help
General usage: Get inventory on each day since 1970-01-01 through tomorrow.
  python inventory.py
Short tests:
  python inventory.py --start 1970-01-01 --stop 1970-01-10
  python inventory.py --start 1970-01-01 --stop 1970-01-10 --no-update
"""

BASE_URL = "https://supermag.jhuapl.edu/lib/services/inventory.php"

def create_inventory(start, stop, output_dir):

  import json
  import datetime as dt

  def _write_files(inventory, output_dir):
    import gzip

    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_file = output_dir / 'inventory.json'
    timestamp = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    archive_file = output_dir / 'archive' / f'inventory-{timestamp}.json.gz'
    archive_file.parent.mkdir(parents=True, exist_ok=True)

    print(f'Writing {inventory_file} with {len(inventory)} stations')
    with inventory_file.open('w') as stream:
      json.dump(inventory, stream, indent=2)
      stream.write('\n')

    print(f'Writing {archive_file}')
    with gzip.open(archive_file, 'wt') as stream:
      json.dump(inventory, stream, indent=2)
      stream.write('\n')


  inventories = get_inventories(args.start, args.stop, **kwargs)

  print(f'Reading {len(inventories)} inventories')

  # Key: station id, value: dict of dates data available
  station_availability = {}
  for inventory_date, station_ids in inventories.items():

    s = '' if len(station_ids) == 1 else 's'
    print(f'  Found {len(station_ids)} station{s} on {inventory_date}')
    for station_id in station_ids:

      if station_id not in station_availability:
        station_availability[station_id] = []

      station_availability[station_id].append(inventory_date)

    s = '' if len(station_availability) == 1 else 's'
  print(f'Creating inventory.json with {len(station_availability)} stations')
  inventory = []
  for station_id, available_dates in station_availability.items():
    available_dates = sorted(available_dates)
    entry = {
        'id': station_id,
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

  for entry in inventory:
    print(f"  {entry['id']}: Data range: {entry['startDate']}-{entry['stopDate']} | Unavailable: {len(entry.get('unavailable', []))}/{n_days} ({100-entry['available_percent']:.1f}%)")

  _write_files(inventory, output_dir)

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
    print("Getting inventory for {}".format(file_date))

    output_file = inventory_file_path(inventory_dir, current)
    if output_file.exists() and not update:
      print(f'  Found cache: {output_file.relative_to(output_dir)}')
      with output_file.open() as stream:
        import json
        payload = json.load(stream)
      inventory_data[file_date] = payload['stations'] if isinstance(payload, dict) else []
      continue

    if requested > 0 and delay > 0:
      time.sleep(delay)

    payload = _get_one_inventory(current, timeout=timeout)
    requested += 1
    stations = payload.get('stations', []) if isinstance(payload, dict) else []
    output_file = write_inventory_file(inventory_dir, current, payload)
    print(f'  {output_file.relative_to(output_dir)}: {len(stations)} stations')
    inventory_data[file_date] = payload['stations'] if isinstance(payload, dict) else []

  return inventory_data


def _get_one_inventory(start, timeout=5):
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

  print(f"  Fetching {inventory_url(start)}")
  with urlopen(inventory_url(start), timeout=timeout) as response:
    return json.load(response)


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
  import datetime as dt
  from pathlib import Path

  default_start = '1970-01-01'
  tomorrow = dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1)
  default_stop  = (tomorrow).isoformat()
  default_timeout = 5
  default_request_delay = 0.0

  epilog =  'Examples:\n'
  epilog += '  python3 catalog.py # Makes requests inventory on each day since 1970-01-01 through today.\n'
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
    default=default_timeout,
    type=int,
    help=f'HTTP timeout in seconds for each fetch. Default: {default_timeout}.',
  )
  parser.add_argument(
    '--no-update',
    action='store_true',
    help="Don't refetch and overwrite existing inventory files. Only fetch missing inventories.",
  )
  parser.add_argument(
    '--delay',
    default=default_request_delay,
    type=float,
    help=f'Delay in seconds between actual HTTP requests. Default: {default_request_delay}.',
  )
  return parser.parse_args()


if __name__ == '__main__':

  args = parse_args()

  kwargs = {
    'output_dir': args.output_dir,
    'update': args.no_update is False,
    'timeout': args.timeout,
    'delay': args.delay,
  }

  create_inventory(args.start, args.stop, args.output_dir)
