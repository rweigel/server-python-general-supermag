Create metadata for SuperMAG HAPI server

`bin/inventory.py` creates [inventory.json](http://mag.gmu.edu/git-data/server-python-general-supermag/data/inventory.json), which contains an array
with objects of station availability information. See `python inventory.py --help` for options.

`bin/catalog.py` creates the HAPI catalog response [catalog.json](http://mag.gmu.edu/git-data/server-python-general-supermag/data/catalog.json) based on `inventory.json`.
