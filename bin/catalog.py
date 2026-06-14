import logging

from util import configure_logging, set_logging_level

logger = configure_logging(__name__, level=logging.INFO)


def catalog(inventory, output_dir):

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
  The location given in this metadata is the location of the station at startDate.
  If this does not match the location at at stopDate, then this JSON response 
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

  missing_location_warning = (
    'No fixed station location metadata is available for this inventory entry. '
    'Use the dataset parameters glat and glon for per-record geographic location.'
  )

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

  catalog = []
  for entry in inventory:
    for sub_dataset in ['baseline_none', 'baseline_yearly', 'baseline_all']:
      for sub_sub_dataset in ['XYZ', 'NEZ']:

        if sub_sub_dataset == 'NEZ':
          parameters[1]['description'] = description_nez
        if sub_sub_dataset == 'XYZ':
          parameters[1]['description'] = description_xyz

        dataset = {
          'id': f"{entry['id']}/PT1M/{sub_dataset}/{sub_sub_dataset}",
          'info': {
            'startDate': entry['startDate'] + 'T00:00Z',
            'stopDate': entry['stopDate'] + 'T23:59Z',
            'cadence': 'PT1M',
            'maxRequestDuration': 'P1Y',
            'datasetCitation': datasetCitation,
            'description': description,
            'note': [note],
            'additionalMetadata': additionalMetadata,
            'location': None,
            'parameters': parameters
          }
        }

        if 'geo_location_start' in entry:
          dataset['info']['location'] = [
                        entry['geo_location_start']['lat'],
                        entry['geo_location_start']['lon']
                    ]
          if entry.get('geo_location_changed', True):
            dataset['info']['warning'] = [missing_location_warning]



      catalog.append(dataset)

  return catalog


def parse_args():
  import argparse
  from pathlib import Path

  data_dir = Path(__file__).resolve().parent.parent / "data"
  default_catalog_file = data_dir / 'catalog-all.json'
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
    '--catalog-file',
    default=default_catalog_file,
    type=Path,
    help='Path to write catalog-all.json.',
  )
  parser.add_argument(
    '--debug',
    action='store_true',
    help='Enable debug logging.',
  )
  args = parser.parse_args()
  if args.station_id is not None and args.catalog_file == default_catalog_file:
    args.catalog_file = data_dir / 'partial'/ f'catalog-{args.station_id}.json'
  return args


if __name__ == "__main__":

  import json
  args = parse_args()

  if args.debug:
    set_logging_level(logging.DEBUG, [__name__])
    logger.debug('Debug logging enabled')

  inventory_file = args.inventory_file
  catalog_file = args.catalog_file

  logger.debug('Reading %s', inventory_file)
  inventory = json.loads(inventory_file.read_text())
  if args.station_id is not None:
    inventory = [entry for entry in inventory if entry.get('id') == args.station_id]
    if not inventory:
      raise ValueError(f"Station ID not found in inventory: {args.station_id}")
    logger.info('Filtered inventory to station %s', args.station_id)
  catalog = catalog(inventory, catalog_file.parent)

  catalog_file.parent.mkdir(parents=True, exist_ok=True)

  json_string = json.dumps(catalog, indent=2) + '\n'
  logger.debug('Writing %s', catalog_file)
  catalog_file.write_text(json_string)

  print(json_string)