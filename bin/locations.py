"""
Usage:
  python locations.py --help

Read ../data/inventory.json and fetch one minute of data on each station's
last available day to get geographic latitude and longitude.
"""


def read_locations_csv(output_file):
  import csv

  locations = {}
  if not output_file.exists():
    return locations

  with output_file.open(newline='') as stream:
    reader = csv.reader(stream)
    for row in reader:
      if len(row) < 3:
        continue
      station_id, glat, glon = row[0], row[1], row[2]
      locations[station_id] = [station_id, glat, glon]

  return locations


def fetch_locations(inventory, existing_locations, user_id='superhapi', update=False):
  from data import sm_data

  locations = []
  for entry in inventory:
    station_id = entry['id']
    existing_row = existing_locations.get(station_id)
    if existing_row and existing_row[1] != '' and existing_row[2] != '' and not update:
      locations.append(existing_row)
      continue

    start = f"{entry['stopDate']}T00:00Z"
    extent = 60
    data = sm_data(user_id, station_id, start, extent, extra_parameters=['geo'])
    if isinstance(data, Exception):
      locations.append([station_id, '', ''])
      continue

    if not data:
      if existing_row:
        locations.append(existing_row)
      else:
        locations.append([station_id, '', ''])
      continue

    first_row = data[0]
    if 'glat' not in first_row or 'glon' not in first_row:
      if existing_row:
        locations.append(existing_row)
      else:
        locations.append([station_id, '', ''])
      continue

    locations.append([station_id, first_row['glat'], first_row['glon']])

  return locations


def parse_args():
  import argparse
  from pathlib import Path

  parser = argparse.ArgumentParser(
    description='Create a locations.csv file from inventory.json using one-minute SuperMAG geo fetches.'
  )
  parser.add_argument(
    '--inventory-file',
    default=Path(__file__).resolve().parent.parent / 'data' / 'inventory.json',
    type=Path,
    help='Path to combined inventory.json file.',
  )
  parser.add_argument(
    '--output-file',
    default=Path(__file__).resolve().parent.parent / 'data' / 'locations.csv',
    type=Path,
    help='Path to write locations CSV output.',
  )
  parser.add_argument(
    '--update',
    action='store_true',
    help='Refetch stations even when locations.csv already has location.',
  )
  return parser.parse_args()


if __name__ == '__main__':
  import csv
  import json

  args = parse_args()

  inventory = json.loads(args.inventory_file.read_text())
  locations = read_locations_csv(args.output_file)
  locations = fetch_locations(inventory, locations, update=args.update)

  args.output_file.parent.mkdir(parents=True, exist_ok=True)
  with args.output_file.open('w', newline='') as stream:
    writer = csv.writer(stream)
    for location in locations:
      writer.writerow(location)

  print(f'Wrote {args.output_file} with {len(locations)} station locations')

  # Print missing locations to console
  missing_locations = [loc for loc in locations if loc[1] == '' or loc[2] == '']
  if missing_locations:
    print(f'Missing locations for {len(missing_locations)} stations:')
    for loc in missing_locations:
      print(f'  Station ID: {loc[0]}')
