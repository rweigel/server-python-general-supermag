
def catalog(depth=None, config=None, dataset=None):
  import os
  import pathlib

  os.environ.setdefault('SUPERMAG_LOG_DIR', str(pathlib.Path(__file__).parent / "../log"))

  import supermag

  args = {
          "start": "1970-01-01",
          "stop": "1970-01-03",

          "output_dir": pathlib.Path(__file__).parent / "../data",

          "update_inventory": False,

          "update_samples": False,

          # Set to True for testing edits to catalog.py
          "use_cached_inventory": False,

          # HAPI dataset ID to filter by
          "dataset": dataset,

          "cafile": None
  }

  cat = supermag.catalog('superhapi', **args)

  if depth is None:
    for entry in cat:
      del entry['info']

  return cat

if __name__ == "__main__":
  from hapiserver.cli import cl_call
  cl_call(catalog)