# Vinculum for Python

Run configured queries from Python 3.10 or later using the v1 API introduced in Vinculum 0.2.0.

## Install

Once this repository is on GitHub, replace `OWNER` with its account or organization name.

```sh
python -m pip install "vinculum-client @ git+https://github.com/OWNER/vinculum-python.git"
```

For a private repository, configure Git authentication for GitHub. To install an extracted copy instead, run `python -m pip install .` in this directory.

## Query

Set `VINCULUM_TOKEN` in your environment. Pass the deployment URL, including any reverse proxy prefix such as `/vinculum`. The client appends `/v1/queries/{name}` for the configured query you call.

```python
from vinculum_client import VinculumClient

with VinculumClient("https://server.company.org/vinculum") as client:
    result = client.query("time_series_many", {"series_ids": [1, 2, 3]})

print(result.rows)
print(result.row_count, result.truncated)
```

Pass `token=` to provide a token explicitly. The default HTTP timeout is 30 seconds and can be set with `timeout=`. The context manager closes the HTTP session. For a longer-lived client, call `close()` when finished.

Pass a dictionary of JSON values as the second argument. Lists map to JSON arrays, including `[]` and `[1]`. Omit the dictionary for a query without parameters. `QueryResult.rows` is a list of dictionaries. Vinculum's date, time, and decimal strings stay as strings.

### Errors

```python
from vinculum_client import VinculumClient, VinculumError

with VinculumClient("https://server.company.org/vinculum") as client:
    try:
        result = client.query("time_series_many", {"series_ids": [1]})
    except VinculumError as error:
        print(error.code, error.status_code, str(error))
```

API failures expose the server's code, HTTP status, and diagnostic. A network failure uses code `transport_error` and `None` for the status.

## Publish this source

From this directory, use an authenticated GitHub CLI and replace `OWNER` with the destination.

```sh
git init -b main
git add .
git commit -m "Add Vinculum Python client"
gh repo create OWNER/vinculum-python --private --source=. --push
```

Run the package tests with `python -m pip install '.[test]'` and `python -m pytest`.
