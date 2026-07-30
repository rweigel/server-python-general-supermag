
import logging

logger = logging.getLogger(__name__)

def catalog(depth=None, config=None, dataset=None):

  import supermag

  options = (config or {}).get("options", {})

  def _resolve_dir(path):
    import pathlib
    path = pathlib.Path(path)
    if not path.is_absolute():
      path = pathlib.Path(__file__).parent / ".." / path
    return path

  supermag.util.set_log_dir(_resolve_dir(options.get("LOG_DIR", "log")))
  logging.basicConfig(level=options.get("LOG_LEVEL", None))
  if "LOG_LEVEL" in options:
    supermag.util.logger.setLevel(options["LOG_LEVEL"])

  args = {
          "start": "1970-01-01",
          "stop": "1970-01-03",

          "output_dir": _resolve_dir(options.get("DATA_DIR", "data")),

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