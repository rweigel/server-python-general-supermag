"""
Usage:
  python locations.py --help
  python locations.py

Reads ../data/inventory.json and fetch one minute of data on each station's
last available day to get geographic latitude and longitude. Writes results
to ../data/locations.json.
"""

import logging

from util import configure_logging, set_logging_level

logger = configure_logging(__name__, level=logging.INFO)


def fetch_location(station_id, isotime, output_dir, user_id='superhapi', update=False):
  from data import sm_data

  extent = 60
  data = sm_data(user_id, station_id, isotime, extent, extra_parameters=['geo'])

  if isinstance(data, Exception):
    return None
  if not isinstance(data, list) or len(data) == 0:
    return None

  first_row = data[0]
  if 'glat' not in first_row or 'glon' not in first_row:
      return None

  return (first_row['glat'], first_row['glon'])


def fetch_locations(inventory, output_dir, user_id='superhapi', update=False, write_output=True, output_file=None):
  if output_file is None:
    output_file = output_dir / 'locations.json'
  existing_locations = _read_locations(output_file)

  locations = {}
  for entry in inventory:
    station_id = entry['id']

    existing_row = existing_locations.get(station_id)
    if not update and existing_row:
      if _has_location(existing_row.get('start', {})) or _has_location(existing_row.get('stop', {})):
        logger.debug(f"Station {station_id} already has location, skipping fetch.")
        locations[station_id] = existing_row
        continue

    stop_isotime = f"{entry['stopDate']}T23:59Z"
    location_stop = fetch_location(station_id, stop_isotime, output_dir, user_id=user_id, update=update)

    start_isotime = f"{entry['startDate']}T00:00Z"
    location_start = fetch_location(station_id, start_isotime, output_dir, user_id=user_id, update=update)

    if location_start is not None and location_stop is not None and location_start != location_stop:
      logger.debug(f"Warning: Station {station_id} has different locations at start and stop times.")

    start_location = _location_record(start_isotime, location_start)
    stop_location = _location_record(stop_isotime, location_stop)

    if _has_location(start_location) or _has_location(stop_location):
      locations[station_id] = {
        'geo_location_changed': not _locations_match(start_location, stop_location),
        'start': start_location,
        'stop': stop_location,
      }
    else:
      if existing_row:
        logger.debug(f"Failed to fetch location for station {station_id}, but existing location found. Keeping existing location.")
        locations[station_id] = existing_row
      else:
        logger.debug(f"Failed to fetch location for station {station_id}, and no existing location found. Adding empty location.")
        locations[station_id] = {
          'geo_location_changed': False,
          'start': _location_record('', None),
          'stop': _location_record('', None),
        }

  if write_output:
    _write_locations(locations, output_file)

  return locations


def _has_location(location_record):
  return location_record.get('glat', '') != '' and location_record.get('glon', '') != ''


def _location_record(isotime, location):
  if location is None:
    return {
      'datetime': isotime if isotime is not None else '',
      'glat': '',
      'glon': '',
    }

  return {
    'datetime': isotime,
    'glat': location[0],
    'glon': location[1],
  }


def _locations_match(start_location, stop_location):
  if not _has_location(start_location) or not _has_location(stop_location):
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
      locations[station_id] = {
        'geo_location_changed': location.get(
          'geo_location_changed',
          not location.get('nochange', _locations_match(start_location, stop_location))
        ),
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
    locations[station_id] = {
      'geo_location_changed': location.get(
        'geo_location_changed',
        not location.get('nochange', _locations_match(start_location, stop_location))
      ),
      'start': start_location,
      'stop': stop_location,
    }

  return locations


def _normalize_location_record(location):
  if not isinstance(location, dict):
    return _location_record('', None)

  return {
    'datetime': location.get('datetime', location.get('at', location.get('start', ''))),
    'glat': location.get('glat', ''),
    'glon': location.get('glon', ''),
  }


def _write_locations(locations, output_file):
  import json

  output_file.parent.mkdir(parents=True, exist_ok=True)
  with output_file.open('w') as stream:
    json.dump(locations, stream, indent=2)
    stream.write('\n')

  logger.info(f'Wrote {output_file} with {len(locations)} station locations')

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
    description='Create a locations.json file from inventory.json using one-minute SuperMAG geo fetches.'
  )
  parser.add_argument(
    '--inventory-file',
    default=Path(__file__).resolve().parent.parent / 'data' / 'inventory.json',
    type=Path,
    help='Path to combined inventory.json file.',
  )
  parser.add_argument(
    '--output-dir',
    default=Path(__file__).resolve().parent.parent / 'data',
    type=Path,
    help='Path to write locations output file(s).',
  )
  parser.add_argument(
    '--station-id',
    default=None,
    help='Fetch location data only for the given station ID.',
  )
  parser.add_argument(
    '--update',
    action='store_true',
    help='Refetch stations even when locations.json already has location.',
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
    import data

    set_logging_level(logging.DEBUG, [__name__, data.__name__])
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
    output_file = args.output_dir / f'locations-{args.station_id}.json'

  logger.debug(f"Found {len(inventory)} stations")
  locations = fetch_locations(
    inventory,
    args.output_dir,
    update=args.update,
    write_output=True,
    output_file=output_file,
  )
