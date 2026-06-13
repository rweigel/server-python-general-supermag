import logging

format = '%(levelname)s:%(name)s:%(funcName)s(): %(message)s'
format = '%(funcName)s(): %(message)s'

logging.basicConfig(level=logging.DEBUG, format=format)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def get(url):
  import urllib.request
  import importlib
  certspec = importlib.util.find_spec("certifi")
  if certspec is not None:
    import certifi

  logger.debug("Fetching URL: %s", url)
  try:
    logger.debug("  Trying certifi.where().")
    cafile = certifi.where()
  except:
    logger.debug("  certifi.where() raised an exception.")
    cafile = ''

  try:
    logger.debug(f"  Getting response using urllib.request.urlopen('{url}', cafile='{cafile}')")
    response = urllib.request.urlopen(url, cafile=cafile)
  except TypeError:
    logger.debug(f"  Getting response using urllib.request.urlopen('{url}')")
    response = urllib.request.urlopen(url)

  logger.debug("  Fetched URL: %s", url)

  return response


def sm_data_parse_response(response, format=None):
  import re
  import json

  with response:
    longstring = response.read().decode('utf-8')
    logger.debug(f"Raw response string: {longstring}")
    # JSON does not allow NaN
    longstring = re.sub(r'\b(?:NaN|nan|Infinity|inf|-Infinity|-inf)\b', 'null', longstring, flags=re.IGNORECASE)
    logger.debug(f"Raw response string after re.sub(): {longstring}")

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
    from datetime import datetime, timezone
    import pandas as pd
    df = pd.DataFrame(data_rows, columns=header)

    # Add a Time column in ISO format
    df['tval_iso'] = df['tval'].apply(
      lambda x: datetime.fromtimestamp(x, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    )

    # Add a datetime column
    df['tval_datetime'] = pd.to_datetime(df.index)

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

  response = get(url)
  data_json = sm_data_parse_response(response, format='json')

  return data_json


def hapi_data(stationid, start, stop, parameters=None):
  #from supermag_api import supermag_getdata
  from datetime import datetime

  baseline = 'yearly'  # default baseline
  delta = 'default'    # default delta
  if "baseline_none" in stationid:
    baseline = 'none'
  if "baseline_yearly" in stationid:
    baseline = 'yearly'
  if "baseline_all" in stationid:
    baseline = 'default'
    delta = 'start'

  parameters_known = ['Time', 'glon', 'glat', 'mlt', 'mcolat', 'decl', 'sza', 'N_nez', 'N_geo', 'E_nez', 'E_geo', 'Z_nez', 'Z_geo']
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

  userid = 'superhapi'
  stationid = stationid.split('/')[0]
  extent = int((stop_dt - start_dt).total_seconds())
  kwargs = {
    'baseline': baseline,
    'delta': delta,
    'extra_parameters': ['mlt', 'mag', 'geo', 'decl', 'sza']
  }
  data = sm_data(userid, stationid, start, extent, **kwargs)

  df = reformat(data, format='dataframe')

  # Rename tval_iso to Time
  df = df.rename(columns={'tval_iso': 'Time'})

  csv = df[parameters].to_csv(index=False, header=True)

  return csv


if __name__ == "__main__":
  data = hapi_data('HBK/baseline_yearly/PT1M', '2019-11-15T10:40Z', '2019-11-15T10:41Z')
  print(data)
