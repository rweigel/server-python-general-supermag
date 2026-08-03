
import logging

logger = logging.getLogger(__name__)

def data(dataset, parameters, start, stop, format=None, config=None):

  import pathlib

  import supermag

  options = (config or {}).get("options", {})

  data_dir = pathlib.Path(options.get("DATA_DIR", "data"))
  if not data_dir.is_absolute():
    data_dir = pathlib.Path(__file__).parent / ".." / data_dir

  logging.basicConfig(level=options.get("LOG_LEVEL", None))
  if "LOG_LEVEL" in options:
    supermag.util.logger.setLevel(options["LOG_LEVEL"])

  stationid, baseline, cadence, frame = dataset.split('/')
  baseline = baseline.split('_')[1]
  kwargs = {
    'baseline': baseline,
    'delta': 'none',
    'format': 'csv-hapi',
    'parameters': parameters,
    'cadence': cadence,
    'cache': True,
    'use_cache': True,
    'output_dir': data_dir,
    'cafile': None
  }

  part_length = 86400
  # Compute extent from start and stop
  import datetime as dt
  extent = dt.datetime.fromisoformat(stop) - dt.datetime.fromisoformat(start)
  extent = extent.total_seconds()
  starts = []
  for i in range(0, int(extent // part_length) + 1):
    start_part = (dt.datetime.fromisoformat(start) + dt.timedelta(seconds=i*part_length))
    starts.append(start_part.strftime('%Y-%m-%dT%H:%M:%SZ'))
    logger.debug(f"start_part = {start_part}, part_length = {part_length}")

  for start_part in starts:
    yield f"{start_part}, {part_length}\n"
    #return supermag.data(userid, stationid, start_part, extent, **kwargs)


if __name__ == "__main__":
  from hapiserver.cli import cl_call
  cl_call(data)