---
layout: full
homepage: true
#disable_anchors: true
description: Python bindings for the IMC message protocol of the LSTS toolchain.
---

## PyIMCLSTS

This tool reads the IMC schema from a XML file, locally creates files containing the messages and connects (imports) the main global machinery.

See `/example` to check an example implementation of the Follow Reference maneuver.

<div class="row">
<div class="col-lg-6" markdown="1">

## Installation
{:.mt-lg-0}

The package is hosted in the PyPi repository and the source code is available on GitHub.

### Installing

```shell
$ pip3 install pyimclsts
```

Or, if you are cloning the repo, from the folder where pyproject.toml is located:
```
$ pip3 install .
```

### Extracting/Generating messages:

Choose a folder and have a version of the IMC schema, that is, a file named IMC.xml. Otherwise, it will automatically fetch the latest IMC version from the LSTS git repository. Just run:
```shell
$ python3 -m pyimclsts.extract
```

This will locally extract the IMC.xml as Python classes. You will see a folder called `pyimc_generated` which contains base messages, bitfields and enumerations from the IMC.xml file. They can be locally loaded using, for example:
```python
import pyimc_generated as pg
```

</div>
<div class="col-lg-6" markdown="1">

## Features
{:.mt-lg-0}

### Pure Python

This package uses only Python code, which means it can run wherever Python runs.

### Multi-version

By creating messages locally and installing only the shared functions, it is possible to work with different versions of the IMC on the same Python environment.

### Type annotations and docstrings

To help code and understand the IMC schema, type hints and docstrings were added wherever possible.

</div>
</div>