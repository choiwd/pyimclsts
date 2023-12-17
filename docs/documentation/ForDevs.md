---
layout: page
title: For Developers
description: ~
---
# Motivation and Rationale

So, in this section, I'm going to just give an overall view and present the main reasons for some design decisions that might help whoever wants to contribute to or fork this project. I'm not going into much detail, because I'll assume that if you're doing so, you must have some python background.

## Imports

The first thing you must have notice is the local generation of messages, that is, the `pyimc_generated` folder. It was implemented this way so that you can work with any IMC version, without changing the main library. Of course, this will not hold in case a big change happens, such as a change in the header fields, because the main library assumes this fixed header. This "messes up" the imports, since the python interpreter will have to import the library during runtime. It is nothing critical, but makes type checking and static code analysis more difficult.

## asyncio and multiprocessing

Working so intensively on low-level tasks such as serializing and CRC calculations is not exactly suited for Python. I would say that going back and forth from Python objects to byte strings is a big overhead. An attempt to alleviate this issue was the usage of the multiprocessing module, which didn't gave great results. It was a little slower than the current approach with asyncio. You can find some "deprecated" multiprocessing code along the way, so if you ever try to optimize it, just keep in mind that this approach was attempted.

## Message classes and descriptor protocol

You may find weird the usage of the descriptor protocol and the usage of an `Attributes` attribute. Well, the descriptor protocol is indeed mostly deprecated. Initially, I intended to use it to make safer applications (by checking the types of the message fields) but it turns out, in Python, you, as a library developer, can't prevent an error from happening. You can't reliably force/enforce anything on the user on the type level. "We are all consenting adults", they say, don't they? An error/exception when the user assign `int` where `str` is expected, whether thrown by me (by using descriptors) or by the serializer, makes no difference. The program will crash either way. So instead, I'm using descriptors just to give a better error message, that is, my approach became rather "to teach/help the user". That's also why `Attributes`, which is a class attribute (low memory cost for its benefits) exists.

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
