# poetry-pep621-compat

Experimental Poetry plugin to add support for PEP 621.

This project is a POC, and is not intended for production use.

## Supported fields

| PEP 621 field | Poetry field | Lossless? |Notes |
| --- | --- | --- | --- |
| `name` | `name` | ✅ | |
| `version` | `version` | ⚠️ | For dynamic versions, we set `0.0.0` |
| author | authors | ✅ | |
| maintainers | maintainers | ✅ | |
| description | description | ✅ | |
| license | license | ⚠️ | PEP621 has text or file, Poetry is always text |
| keywords | keywords | ✅ | |
| classifiers | classifiers | ⚠️ | Poetry will automatically add Python version and license classifiers. |
| requires-python | dependencies["python"] | ✅ | Might need to convert. |
| readme | readme | ✅ | |
| urls["Homepage] | homepage | ~ | No 1:1 mapping, but we usually find it in `urls` |
| urls["Documentation] | documentation | ~ | No 1:1 mapping, but we usually find it in `urls` |
| urls["Repository] | repository | ~ | No 1:1 mapping, but we usually find it in `urls` |
| urls | urls | ~ | We removed `Homepage`, `Documentation` and `Repository` |
| scripts | scripts | ✅ | We ignore type of scripts |
| . | include / exclude | ❌ | This is a build-backend specification |
| . | packages | ❌ | This is a build-backend specification |

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
