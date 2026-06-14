"""
Usage:
  python locations.py --help
  python locations.py
"""

description = """Reads inventory.json and fetches data on each station's first
and last available day to get geographic latitude and longitude. Writes results
to locations.json.
"""

import logging
from util import _path_relative_to_cwd, configure_logging, set_logging_level

logger = configure_logging(__name__, level=logging.INFO)


def fetch_location(station_id, isotime, output_dir, value="first", user_id='superhapi', update=False):
  from data import sm_data

  extent = 60*60*24  # 1 day
  data, error = sm_data(user_id, station_id, isotime, extent, extra_parameters=['geo'])

  if error is not None:
    emsg = f"Failed to fetch data for station {station_id} on {isotime}: {error}"
    logger.debug(emsg)
    return None, emsg

  if not isinstance(data, list) or len(data) == 0:
    emsg = f"No data returned for station {station_id} on {isotime}"
    logger.debug(emsg)
    return None, emsg

  if value == "first":
    first_row = data[0]
  elif value == "last":
    first_row = data[-1]
  else:
    raise ValueError(f"Invalid value parameter: {value}. Must be 'first' or 'last'.")

  if 'glat' not in first_row or 'glon' not in first_row:
    return None, f"Missing 'glat' or 'glon' in data for station {station_id} at time {isotime}"

  return (first_row['glat'], first_row['glon']), None


def fetch_locations(inventory, output_dir, user_id='superhapi', update=False, write_output=True, output_file=None):

  if output_file is None:
    output_file = output_dir / 'locations.json'

  existing_locations = _read_locations(output_file)

  locations = {}
  for entry in inventory:
    station_id = entry['id']

    existing_location = existing_locations.get(station_id)
    if not update and existing_location:
      if _has_location(existing_location.get('start', {})) or _has_location(existing_location.get('stop', {})):
        logger.debug(f"Station {station_id} already has location, skipping fetch.")
        locations[station_id] = existing_location
        continue

    stop_isotime = f"{entry['stopDate']}"
    location_stop, error_stop = fetch_location(station_id, stop_isotime, output_dir, "last", user_id=user_id, update=update)

    start_isotime = f"{entry['startDate']}"
    location_start, error_start = fetch_location(station_id, start_isotime, output_dir, "first", user_id=user_id, update=update)

    if location_start is not None and location_stop is not None and location_start != location_stop:
      logger.debug(f"Warning: Station {station_id} has different locations at start and stop times.")

    start_location = _location_record(start_isotime, location_start, error_start)
    stop_location = _location_record(stop_isotime, location_stop, error_stop)

    if _has_location(start_location) or _has_location(stop_location):
      _match = _locations_match(start_location, stop_location)
      locations[station_id] = {
        'geo_location_changed': None if _match is None else not _match,
        'start': start_location,
        'stop': stop_location,
      }
    else:
      if existing_location:
        logger.debug(f"Failed to fetch location for station {station_id}, but existing location found. Keeping existing location.")
        locations[station_id] = existing_location
      else:
        logger.debug(f"Failed to fetch location for station {station_id}, and no existing location found. Adding empty location.")
        locations[station_id] = {
          'geo_location_changed': None,
          'start': _location_record('', None, error_start),
          'stop': _location_record('', None, error_stop)
        }

  if write_output:
    _write_locations(locations, output_file)

  return locations


def _has_location(location_record):
  a = location_record.get('glat', None) is not None
  b = location_record.get('glon', None) is not None
  return a and b


def _location_record(isotime, location, error):
  if error is not None:
    return {
      'datetime': isotime if isotime is not None else '',
      'glat': None,
      'glon': None,
      'error': error
    }

  return {
    'datetime': isotime,
    'glat': location[0],
    'glon': location[1]
  }


def _locations_match(start_location, stop_location):
  if not _has_location(start_location) or not _has_location(stop_location):
    return None

  if start_location.get('glat') is None or start_location.get('glon') is None:
    return None
  if stop_location.get('glat') is None or stop_location.get('glon') is None:
    return None

  return (
    start_location.get('glat') == stop_location.get('glat')
    and start_location.get('glon') == stop_location.get('glon')
  )


def _read_locations(output_file):
  import json

  locations = {}
  if not output_file.exists():
    logger.debug(f"No existing locations file found at {output_file}, starting with empty locations.")
    return locations
  else:
    logger.debug(f"Using existing locations from {output_file}")

  with output_file.open() as stream:
    payload = json.load(stream)

  for station_id, location in payload.items():
    if not isinstance(location, dict):
      continue
    if 'start' in location or 'stop' in location:
      start_location = _normalize_location_record(location.get('start', {}))
      stop_location = _normalize_location_record(location.get('stop', {}))
      if 'geo_location_changed' in location:
        _changed = location['geo_location_changed']
      elif 'nochange' in location:
        _changed = not location['nochange']
      else:
        _match = _locations_match(start_location, stop_location)
        _changed = None if _match is None else not _match
      locations[station_id] = {
        'geo_location_changed': _changed,
        'start': start_location,
        'stop': stop_location,
      }
      continue

    at_value = location.get('at', location.get('start', ''))
    start_location = _normalize_location_record({
      'datetime': at_value,
      'glat': location.get('glat', ''),
      'glon': location.get('glon', ''),
    })
    stop_location = _normalize_location_record({
      'datetime': at_value,
      'glat': location.get('glat', ''),
      'glon': location.get('glon', ''),
    })
    if 'geo_location_changed' in location:
      _changed = location['geo_location_changed']
    elif 'nochange' in location:
      _changed = not location['nochange']
    else:
      _match = _locations_match(start_location, stop_location)
      _changed = None if _match is None else not _match
    locations[station_id] = {
      'geo_location_changed': _changed,
      'start': start_location,
      'stop': stop_location,
    }

  return locations


def _normalize_location_record(location):
  if not isinstance(location, dict):
    return _location_record('', None)

  return {
    'datetime': location.get('datetime', location.get('at', location.get('start', ''))),
    'glat': location.get('glat', None),
    'glon': location.get('glon', None),
  }


def _write_locations(locations, output_file):
  import json

  output_file.parent.mkdir(parents=True, exist_ok=True)
  with output_file.open('w') as stream:
    json.dump(locations, stream, indent=2)
    stream.write('\n')

  logger.info(f'Wrote {_path_relative_to_cwd(output_file)} with {len(locations)} station locations')

  # Print missing locations to console
  missing_locations = [
    station_id for station_id, loc in locations.items()
    if not _has_location(loc.get('start', {})) and not _has_location(loc.get('stop', {}))
  ]
  if missing_locations:
    logger.error(f'Missing locations for {len(missing_locations)} stations:')
    for station_id in missing_locations:
      logger.error(f'  Station ID: {station_id}')


def parse_args():
  import argparse
  from pathlib import Path


  parser = argparse.ArgumentParser(
    description=description
  )
  inventory_file = Path(__file__).resolve().parent.parent / 'data' / 'inventory.json'
  output_dir = Path(__file__).resolve().parent.parent / 'data'
  parser.add_argument(
    '--inventory-file',
    default=inventory_file,
    type=Path,
    help=f'Path to combined inventory.json file. Default: {_path_relative_to_cwd(inventory_file)}',
  )
  parser.add_argument(
    '--output-dir',
    default=output_dir,
    type=Path,
    help=f'Path to write locations output file(s). Default: {_path_relative_to_cwd(output_dir)}',
  )
  parser.add_argument(
    '--station-id',
    default=None,
    help='Fetch location data only for the given station ID. Default: all stations.',
  )
  parser.add_argument(
    '--update',
    action='store_true',
    help='Refetch stations even when locations.json already has location information.',
  )
  parser.add_argument(
    '--debug',
    action='store_true',
    help='Enable debug logging.',
  )

  return parser.parse_args()


if __name__ == '__main__':
  import json

  args = parse_args()

  if args.debug:
    set_logging_level(logging.DEBUG, [__name__])
    logger.debug('Debug logging enabled')

  logger.debug(f"Reading {args.inventory_file}")
  inventory = json.loads(args.inventory_file.read_text())

  if args.station_id is not None:
    inventory = [entry for entry in inventory if entry.get('id') == args.station_id]
    if not inventory:
      raise ValueError(f"Station ID not found in inventory: {args.station_id}")
    logger.info(f"Filtered inventory to station {args.station_id}")

  output_file = args.output_dir / 'locations.json'
  if args.station_id is not None:
    output_file = args.output_dir / 'partial' / f'locations-{args.station_id}.json'

  logger.debug(f"Found {len(inventory)} stations")
  locations = fetch_locations(
    inventory,
    args.output_dir,
    update=args.update,
    write_output=True,
    output_file=output_file,
  )
