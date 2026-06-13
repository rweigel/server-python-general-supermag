def catalog(inventory, output_dir):

  description = "Baseline choices are 'baseline_none', 'baseline_yearly' (yearly trends removed), or 'baseline_all' (yearly and start value subtracted). Datasets ending in 'XYZ' are geographic coordinates (X=North, Y=East, Z=vertical down); 'NEZ' are local geomagnetic coordinates (N=North, E=East, Z=vertical down)."
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
      },
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
      "description": "declination  in degrees computed using the IGRF model"
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

        additionalMetadata[0]['content'] = entry['id']

        dataset = {
          'id': f"{entry['id']}/PT1M/{sub_dataset}/{sub_sub_dataset}",
          'info': {
            'startDate': entry['startDate'],
            'stopDate': entry['stopDate'],
            'cadence': 'PT1M',
            'maxRequestDuration': 'P1Y',
            'datasetCitation': datasetCitation,
            'description': description,
            'additionalMetadata': additionalMetadata,
            'parameters': parameters
          }
        }

      catalog.append(dataset)

  return catalog

if __name__ == "__main__":

  import sys
  import json
  import pathlib

  if len(sys.argv) != 3:
    print(f"Usage: {sys.argv[0]} <inventory.json> <output_dir>")
    sys.exit(1)

  data_dir = pathlib.Path(__file__).resolve().parent.parent / "data"
  inventory_file = data_dir / "inventory.json"
  catalog_file = data_dir / "catalog.json"

  inventory = json.loads(inventory_file.read_text())
  catalog = catalog(inventory, data_dir)

  catalog_file.parent.mkdir(parents=True, exist_ok=True)

  json_string = json.dumps(catalog, indent=2) + '\n'
  catalog_file.write_text(json_string)

  print(json_string)