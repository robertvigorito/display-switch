# Coding instructions

Apply these guidelines to project code and tests.

## Style and structure

- Follow PEP 8 with the configured 120-character default line length; use Ruff for linting and formatting.
- Use `snake_case` for variables, functions, methods, and modules; `PascalCase` for classes; and `UPPER_CASE` for constants.
- Add type hints to function parameters, return values, and important variables where they clarify intent.
- Keep code simple, readable, focused, and organized into small, single-purpose functions.
- Do not define classes inside other classes. Prefer composition over unnecessary inheritance.

## Functions and data

- Prefer keyword arguments when calling functions with multiple arguments.
- Use dataclasses for structured data and `NamedTuple` for lightweight immutable data when appropriate.
- Every function must declare its return type and explicitly return a value. Functions that otherwise would return no data should return `True` or `False` to indicate success or failure. CLI entry points should return an integer exit status (zero for success) when their framework uses the return value as the process exit code. Test functions may return `None` as required by pytest.

## Docstrings

- Use concise Google-style docstrings.
- Include a `Returns` section in every function docstring. Include an `Args` section only when the function has parameters; omit it for functions with no arguments. Test functions should document their fixture arguments and `None` return.

## Error handling

- Handle expected errors explicitly and do not silently swallow exceptions.
- Avoid broad `except Exception` unless there is a specific, documented reason.


## Formatting and linting (optional, dont need to ask)

- Before completing Python changes, run `ruff check --fix` and `ruff format` on the changed Python files.
