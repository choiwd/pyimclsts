---
layout: page
title: For Developers
description: ~
---
# Motivation and Rationale

# Updating the package

- You might need:
```shell
    $ python3 -m pip install --upgrade twine
```
- Build with:
```shell
    $ python3 -m build
```
- Upload to PyPI with:
```shell
    $ python3 -m twine upload dist/*
```
