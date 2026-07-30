import logging
logger = logging.getLogger(__name__)

def info(dataset, config=None):

  if __package__:
    from bin.catalog import catalog
  else:
    from catalog import catalog

  options = (config or {}).get("options", {})
  logging.basicConfig(level=options.get("LOG_LEVEL", None))
  resp = catalog(depth='all', config=config, dataset=dataset)

  return resp

if __name__ == "__main__":
  from hapiserver.cli import cl_call
  cl_call(info)