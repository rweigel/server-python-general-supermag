import logging

from util import configure_logging, set_logging_level

logger = configure_logging(__name__, level=logging.INFO)


def catalog(inventory, output_dir):

  import copy

  description = """
  Ground-based magnetometer dataset IDs have the form 
  {station_id}/PT1M/{baseline_choice}/{frame}, where
  {baseline_choice} is 'baseline_none', 'baseline_yearly' (yearly trend removed),
  or 'baseline_all' (yearly trend and start value subtracted); 
  see https://supermag.jhuapl.edu/mag/?fidelity=low&tab=description. {frame} 
  = 'XYZ' corresponds to geographic coordinates (X=North, Y=East, Z=vertical down); 
  frame = 'NEZ' corresponds to local geomagnetic coordinates 
  (N=North, E=East, Z=vertical down).
  """
  # Join description lines and remove leading/trailing whitespace
  description = ' '.join(line.strip() for line in description.strip().splitlines())

  note = """
  The location given in this metadata is the first valid glat, glon of the 
  station found by requesting data on startDate. If this does not match the 
  location on the last valid glat, glon on stopDate, then this JSON response 
  will include a warning. In this case, the location of the station must be 
  obtained from the dataset parameters glat and glon.
  """
  note = ' '.join(line.strip() for line in note.strip().splitlines())

  datasetCitation = 'https://supermag.jhuapl.edu/info/?page=rulesoftheroad'
  description_nez = 'N_geo, E_geo, Z_geo, the local geomagnetic N, E, Z vector components'
  description_xyz = 'N_geo, E_geo, Z_geo, the geographic N, E, Z vector components'
  additionalMetadata = [
      {
        "name": "iaga",
        "content": None
      },
      {
        "name": "baselines",
        "contentURL": "https://supermag.jhuapl.edu/mag/?fidelity=low&tab=description",
        "content": "Subtract the daily variations and yearly trend (using Gjerloev, 2012)"
      }
  ]

  parameters = [
    {
      "length": 24,
      "name": "Time",
      "type": "isotime",
      "units": "UTC"
    },
    {
      "name": "Field_Vector",
      "type": "double",
      "units": "nT",
      "size": [
        3
      ],
      "fill": "999999.0",
      "description": None,
      "label": [
        "X",
        "Y",
        "Z"
      ]
    },
    {
      "name": "mlt",
      "type": "double",
      "units": "hours",
      "fill": None,
      "description": "magnetic local time in fractional hours"
    },
    {
      "name": "mcolat",
      "type": "double",
      "units": "degrees",
      "fill": None,
      "description": "magnetic colatitude in degrees"
    },
    {
      "name": "sza",
      "type": "double",
      "units": "degrees",
      "fill": None,
      "description": "solar zenith angle in degrees"
    },
    {
      "name": "decl",
      "type": "double",
      "units": "degrees",
      "fill": "0",
      "description": "declination in degrees computed using the IGRF model"
    },
    {
      "name": "glon",
      "type": "double",
      "units": "degrees",
      "fill": "0",
      "description": "geographic longitude in degrees"
    },
    {
      "name": "glat",
      "type": "double",
      "units": "degrees",
      "fill": "0",
      "description": "geographic latitude in degrees"
    }
  ]

  cadence = 'PT1M'
  catalog = []
  for entry in inventory:
    for sub_dataset in ['baseline_none', 'baseline_yearly', 'baseline_all']:
      for sub_sub_dataset in ['XYZ', 'NEZ']:

        cadence_str = ""
        if cadence == 'PT1M':
          cadence_str = "at 1-minute cadence"
        if cadence == 'PT1S':
          cadence_str = "at 1-second cadence"

        title = f"Data from magnetometer station {entry['id']} {cadence_str} with baseline removal option '{sub_dataset}' "

        if sub_sub_dataset == 'NEZ':
          parameters[1]['description'] = description_nez
          title += "in local geomagnetic coordinates ('NEZ')"
        if sub_sub_dataset == 'XYZ':
          parameters[1]['description'] = description_xyz
          title += "in geographic coordinates ('XYZ')"

        additionalMetadataCopy = copy.deepcopy(additionalMetadata)
        additionalMetadataCopy[0]['content'] = entry['id']

        dataset = {
          'id': f"{entry['id']}/{sub_dataset}/{cadence}/{sub_sub_dataset}",
          'title': title,
          'info': {
            'startDate': entry['startDate'] + 'T00:00Z',
            'stopDate': entry['stopDate'] + 'T23:59Z',
            'cadence': cadence,
            'maxRequestDuration': 'P1Y',
            'datasetCitation': datasetCitation,
            'description': description,
            'note': [note],
            'warning': None,
            'location': None,
            'additionalMetadata': additionalMetadataCopy,
            'parameters': parameters
          }
        }

        _set_location_info(entry, dataset)

        if dataset['info']['warning'] is None:
          del dataset['info']['warning']
        if dataset['info']['location'] is None:
          del dataset['info']['location']

        catalog.append(dataset)

  return catalog


def _write_files(catalog, catalog_dir, station_id=None):
  catalog_dir.parent.mkdir(parents=True, exist_ok=True)

  if station_id is not None:
    catalog_dir = catalog_dir / "partial"
  station_id_str = f"-{station_id}" if station_id is not None else ""

  catalog_file = catalog_dir / f'catalog-all{station_id_str}.json'
  json_string = json.dumps(catalog, indent=2) + '\n'
  logger.debug('Writing %s', catalog_file)
  catalog_file.write_text(json_string)

  for dataset in catalog:
    del dataset['info']

  catalog_file = catalog_dir / f'catalog{station_id_str}.json'
  json_string = json.dumps(catalog, indent=2) + '\n'
  logger.debug('Writing %s', catalog_file)
  catalog_file.write_text(json_string)


def _read_inventory(inventory_file, station_id=None):
  logger.debug('Reading %s', inventory_file)
  inventory = json.loads(inventory_file.read_text())
  if station_id is not None:
    inventory = [entry for entry in inventory if entry.get('id') == station_id]
    if not inventory:
      raise ValueError(f"Station ID not found in inventory: {station_id}")
    logger.info('Filtered inventory to station %s', station_id)
  return inventory


def _set_location_info(entry, dataset):

  location = entry['location']
  error_start = location['start'].get('error', None)
  error_stop = location['stop'].get('error', None)

  missing_location_warning = (
    'Use the dataset parameters glat and glon for per-record geographic location. '
    'See additionalMetadata/locationDeterminationDetails for details.'
  )

  if location['geo_location_changed'] is None:
    missing_location_warning = f"Station location metadata is not available on startDate and/or stopDate. {missing_location_warning}"
    dataset['info']['warning'] = [missing_location_warning]

  if location['geo_location_changed'] is True:
    missing_location_warning = f"Station location changed during the time period covered by this dataset. {missing_location_warning}"
    dataset['info']['warning'] = [missing_location_warning]

  if location['geo_location_changed'] is not None:
    if not error_start:
      dataset['info']['location'] = [location['start']['glat'], location['stop']['glon']]
    elif not error_stop:
      dataset['info']['location'] = [location['stop']['glat'], location['stop']['glon']]

  if location['geo_location_changed'] is not False:
    location_metadata = {
      'name': 'locationDeterminationDetails',
      'content': location
    }
    dataset['info']['additionalMetadata'].append(location_metadata)


def parse_args():
  import argparse
  from pathlib import Path

  data_dir = Path(__file__).resolve().parent.parent / "data"
  parser = argparse.ArgumentParser(description='Create catalog-all.json from inventory.json')
  parser.add_argument(
    '--inventory-file',
    default=data_dir / 'inventory.json',
    type=Path,
    help='Path to inventory.json input file.',
  )
  parser.add_argument(
    '--station-id',
    default=None,
    help='Only include datasets for the given station ID.',
  )
  parser.add_argument(
    '--output-dir',
    default=data_dir,
    type=Path,
    help='Path to write catalog.json and catalog-all.json.',
  )
  parser.add_argument(
    '--no-print',
    action='store_true',
    help='Do not print catalog JSON to console.',
  )
  parser.add_argument(
    '--debug',
    action='store_true',
    help='Enable debug logging.',
  )

  args = parser.parse_args()

  return args


if __name__ == "__main__":

  import json
  args = parse_args()

  if args.debug:
    set_logging_level(logging.DEBUG, [__name__])
    logger.debug('Debug logging enabled')

  inventory = _read_inventory(args.inventory_file, station_id=args.station_id)

  catalog = catalog(inventory, args.output_dir)

  _write_files(catalog, args.output_dir, station_id=args.station_id)

  if not args.no_print:
    json_string = json.dumps(catalog, indent=2) + '\n'
    print(json_string)