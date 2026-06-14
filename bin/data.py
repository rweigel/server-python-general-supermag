import logging

format = '%(levelname)s:%(name)s:%(funcName)s(): %(message)s'
format = '%(name)s:%(funcName)s(): %(message)s'
logging.basicConfig(level=logging.DEBUG, format=format)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def get(url):
  import urllib3
  import importlib

  certspec = importlib.util.find_spec("certifi")
  cafile = None
  if certspec is not None:
    import certifi

  logger.debug("Fetching URL: %s", url)
  try:
    logger.debug("  Trying certifi.where().")
    cafile = certifi.where()
  except Exception:
    logger.debug("  certifi.where() raised an exception.")
    cafile = None

  pool_kwargs = {}
  if cafile is not None:
    logger.debug(f"  Using CA certificates from certifi: {cafile}")
    pool_kwargs['ca_certs'] = cafile

  try:
    logger.debug("  Getting response using urllib3.PoolManager().request('GET', url)")
    http = urllib3.PoolManager(**pool_kwargs)
    response = http.request('GET', url)
  except Exception as error:
    logger.debug(f"  Failed: {error}")
    raise

  if response.status >= 400:
    response.release_conn()
    raise urllib3.exceptions.HTTPError(f"HTTP {response.status} for {url}")

  logger.debug("  Fetched URL: %s", url)

  return response


def sm_data_parse_response(response, format=None):
  import re
  import json

  try:
    longstring = response.data.decode('utf-8')
    logger.debug(f"Raw response string: {longstring}")
    # JSON does not allow NaN
    longstring = re.sub(r'\b(?:NaN|nan|Infinity|inf|-Infinity|-inf)\b', 'null', longstring, flags=re.IGNORECASE)
    logger.debug(f"Raw response string after re.sub(): {longstring}")
  finally:
    response.release_conn()

  if format is None:
    return longstring

  data_json = json.loads(longstring)
  logger.debug(f"Parsed JSON data: {data_json}")

  return data_json


def reformat(data_json, format='list'):
  """
  data_json is a list of dicts, each dict has the form
  {
    'tval': 1573814400.0,
    'ext': 60.0,
    'iaga': 'HBK',
    'glon': 27.709999,
    'glat': -25.879997,
    'mlt': 12.647217,
    'mcolat': 125.510384,
    'decl': -18.616241,
    'sza': 13.026016,
    'N': {'nez': 6.80695, 'geo': 9.677255},
    'E': {'nez': 10.103335, 'geo': 7.400181},
    'Z': {'nez': 2.049171, 'geo': 2.049171}
  }
  """

  header = []
  for key in data_json[0]:
    if isinstance(data_json[0][key], dict):
      for subkey in data_json[0][key]:
        header.append(f"{key}_{subkey}")
    else:
      header.append(key)

  logger.debug(f"Header: {header}")
  # Flatten json_data
  data_rows = []
  for entry in data_json:
    row = []
    for key in entry:
      if isinstance(entry[key], dict):
        for subkey in entry[key]:
          row.append(entry[key][subkey])
      else:
        row.append(entry[key])
    data_rows.append(row)

  logger.debug(f"Data: {data_rows}")

  if format == 'dataframe':
    import pandas
    from datetime import datetime, timezone

    df = pandas.DataFrame(data_rows, columns=header)

    # Add a Time column in ISO format
    df['tval_iso'] = df['tval'].apply(
      lambda x: datetime.fromtimestamp(x, tz=timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    )

    # Add a datetime column
    df['tval_datetime'] = pandas.to_datetime(df.index)

    # Put datetime and Time columns first
    df = df.loc[:, ['tval_datetime', 'tval_iso'] + header]

    return df

  return [header] + data_rows


def sm_data(userid, stationid, start, extent, baseline='yearly', delta='default', extra_parameters=None):
  # Call the SuperMAG API to get the data

  flag_list = []
  if delta is not None:
    if delta not in ['start', 'default', None]:
      raise ValueError("Invalid delta value. Must be one of: 'start', 'default', None")
    flag_list.append(f"delta={delta}")

  baseline = 'default'
  if baseline is not None:
    if baseline not in ['yearly', 'default', 'none', None]:
      raise ValueError("Invalid baseline value. Must be one of: 'yearly', 'none', 'default'")
    flag_list.append(f"baseline={baseline}")

  flagstring = '&'.join(flag_list)

  if extra_parameters:
    extra_parameters_allowed = ['mlt', 'mag', 'geo', 'decl', 'sza']
    for parameter in extra_parameters:
      if parameter not in extra_parameters_allowed:
        raise ValueError(f"Invalid extra parameter: {parameter}. Allowed parameters are: {extra_parameters_allowed}")
    flagstring += '&' + '&'.join(extra_parameters)

  url = "https://supermag.jhuapl.edu/services/data-api.php?python&nohead&"
  url += f"start={start}&extent={extent}&logon={userid}&station={stationid.upper()}&{flagstring}"

  try:
    response = get(url)
    data_json = sm_data_parse_response(response, format='json')
  except Exception as error:
    logger.debug("sm_data() failed for station %s: %s", stationid, error)
    return error

  return data_json


def hapi_data(dataset_id, start, stop, parameters, header=False):
  from datetime import datetime

  baseline = 'yearly'  # default baseline
  delta = 'default'    # default delta
  if "baseline_none" in dataset_id:
    baseline = 'none'
  if "baseline_yearly" in dataset_id:
    baseline = 'yearly'
  if "baseline_all" in dataset_id:
    baseline = 'default'
    delta = 'start'

  parameters_known = ['Time', 'Field_Vector', 'mlt', 'mcolat', 'sza', 'decl']

  if parameters is not None:
    for parameter in parameters:
      if parameter not in parameters_known:
        raise ValueError(f"Invalid parameter: {parameter}. Allowed parameters are: {parameters_known}")
    parameters = parameters.copy()
    if 'Time' not in parameters:
      parameters.insert(0, 'Time')
  else:
    parameters = parameters_known.copy()

  try:
    start_dt = datetime.strptime(start, '%Y-%m-%dT%H:%MZ')
    stop_dt = datetime.strptime(stop, '%Y-%m-%dT%H:%MZ')
  except ValueError:
    raise ValueError("Start and stop times must be in ISO format: YYYY-MM-DDTHH:MMZ")

  if stop_dt < start_dt:
    raise ValueError("Stop time must be after start time")

  user_id = 'superhapi'
  station_id = dataset_id.split('/')[0]
  extent = int((stop_dt - start_dt).total_seconds())
  kwargs = {
    'baseline': baseline,
    'delta': delta,
    'extra_parameters': ['mlt', 'mag', 'geo', 'decl', 'sza']
  }
  data = sm_data(user_id, station_id, start, extent, **kwargs)

  if isinstance(data, Exception):
    return ''

  try:
    df = reformat(data, format='dataframe')
  except Exception as error:
    logger.debug("Failed to reformat data for dataset %s: %s", dataset_id, error)
    return ''

  logger.debug("")
  logger.debug(f"DataFrame before subsetting parameters:\n{df}")

  if not df.empty and 'tval_iso' not in df.columns:
    logger.debug("Expected 'tval_iso' column not found in DataFrame. Available columns: %s", df.columns)
    return ''

  # Rename tval_iso to Time
  df = df.rename(columns={'tval_iso': 'Time'})

  frame = dataset_id.split('/')[-1]
  columns_nez = ['N_nez', 'E_nez', 'Z_nez']
  columns_geo = ['N_geo', 'E_geo', 'Z_geo']
  if 'Field_Vector' in parameters:
    if frame == 'NEZ':
      columns_keep = columns_nez
      df = df.drop(columns=columns_geo)
    if frame == 'XYZ':
      columns_keep = columns_geo
      df = df.drop(columns=columns_nez)
  else:
    columns_keep = []
    df = df.drop(columns=columns_nez + columns_geo)

  parameters.remove('Time')
  parameters.remove('Field_Vector')

  columns_return = ['Time'] + columns_keep
  for parameters in parameters:
    if parameters != 'Field_Vector':
      columns_return.append(parameters)

  if not set(columns_return).issubset(df.columns):
    logger.debug("Not all requested columns are available in the DataFrame. Requested: %s, Available: %s", columns_return, df.columns)
    return ''

  csv = df[columns_return].to_csv(index=False, header=header)

  return csv


def parse_args():
  import argparse
  parser = argparse.ArgumentParser(description='Create a catalog.json file from inventory.json')
  parser.add_argument(
    '--dataset',
    default='ABK/baseline_none/NEZ'
  )
  parser.add_argument(
    '--parameters',
    default=None
  )
  parser.add_argument(
    '--start',
    default='2001-01-01T00:00:00.000000Z',
    help='Start date (YYYY-MM-DDTHH:MM:SS.FFFFFFZ)'
  )
  parser.add_argument(
    '--stop',
    default='2001-01-01T00:01:00.000000Z',
    help='Start date (YYYY-MM-DDTHH:MM:SS.FFFFFFZ)'
  )
  parser.add_argument(
    '--header',
    action='store_true',
    help='Include header row in output CSV'
  )

  args = parser.parse_args()
  if args.parameters:
    args.parameters = [param.strip() for param in args.parameters.split(',')]

  args.start = args.start[0:16] + 'Z'
  args.stop = args.stop[0:16] + 'Z'

  return args


if __name__ == "__main__":
  args = parse_args()

  data = hapi_data(args.dataset, args.start, args.stop, args.parameters, header=args.header)
  print("\nHAPI data response:")
  print(data)
