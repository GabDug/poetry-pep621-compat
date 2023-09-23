# poetry-pep621-compat

Experimental Poetry plugin to add support for PEP 621.

!!! warning Disclaimer

    This project is a POC, and is not intended for production use.
    Monkey-patching Poetry with ugly code is not a good idea.
    It has a lot of flaws, and has been tested on 1 (one) project only.

## Objective

Proof-of-concept that shows it would be possible for Poetry to support working with PEP621 standard `pyproject.toml`.

While Poetry may add more granularity for some fields, like dependencies that get non standard-options, many projects don't need such features and would probably benefit for using a standard.

This POC does not implement any merging of standard `project` and Poetry `tool.poetry` config. It may be added, to allow using standard PEP621 `project`, while getting some Poetry goodies, like pinning a dependency to a specific registry.

As there are to my knowledge, no commonly used getter and setter for the properties, this POC will monkey-patch and intercept all read and writes to the `pyproject.toml` file.

Thus it will "fake" a Poetry compliant pyproject.toml, created from the standard `project`.

## Supported read fields

| PEP 621 `project` field | Poetry `tool.poetry` field | Lossless? | Notes                                                                 |
| ----------------------- | -------------------------- | --------- | --------------------------------------------------------------------- |
| `name`                  | `name`                     | ✅         |                                                                       |
| `version`               | `version`                  | ⚠️         | For dynamic versions, we set `0.0.0`                                  |
| `author`                | `authors`                  | ✅         |                                                                       |
| `maintainers`           | `maintainers`              | ✅         |                                                                       |
| `description`           | `description`              | ✅         |                                                                       |
| `license`               | `license`                  | ⚠️         | PEP621 has text or file, Poetry is always text                        |
| `keywords`              | `keywords`                 | ✅         |                                                                       |
| `classifiers`           | `classifiers`              | ⚠️         | Poetry will automatically add Python version and license classifiers. |
| `requires-python`       | `dependencies.python`      | ✅         |                                                                       |
| `readme`                | `readme`                   | ✅         |                                                                       |
| `urls."Homepage`        | `homepage`                 | ~         | No 1:1 mapping, but we usually find it in `urls`                      |
| `urls.Documentation`    | `documentation`            | ~         | No 1:1 mapping, but we usually find it in `urls`                      |
| `urls.Repository`       | `repository`               | ~         | No 1:1 mapping, but we usually find it in `urls`                      |
| `urls`                  | `urls`                     | ~         | We removed `Homepage`, `Documentation` and `Repository`               |
| `scripts`               | `scripts`                  | ✅         | We ignore type of scripts                                             |
| .                       | `include` / `exclude`      | ❌         | This is a build-backend specification                                 |
| .                       | `packages`                 | ❌         | This is a build-backend specification                                 |

## Supported write fields

Only `dependencies` and `version` are currently supported.

It means that the supported commands are supported:

- `poetry version <new-version>`
- `poetry add`
- `poetry show`

## Dependencies

- GIT SSH urls not tested
- GIT Urls with subdirectory not tested
- GIT Urls with branch not tested
- GIT Urls for Eggs not tested

- Local path URLS not supported
- Remote path URLS not supported

- Different sources with markers for the same package not supported

## Dev dependencies

Has there are no dev dependencies in PEP 621, we will use:

- optional dependencies dev group if it exists
- PDM dev dependencies if it exists

## Dynamic fields

Not supported yet.


## TODO

- Test that everything still works with a regular Poetry project
- AWFUL performance
- Validation
- Merging
