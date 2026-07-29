def info(dataset, config=None):

  if __package__:
    from bin.catalog import catalog
  else:
    from catalog import catalog

  resp = catalog(depth='all', config=config, dataset=dataset)

  return resp

if __name__ == "__main__":
  from hapiserver.cli import cl_call
  cl_call(info)