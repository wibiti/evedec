evedec
======
Reads ~~and decrypts~~ the Eve Online client's code.ccp, extracts the compiled python code files, and passes them to uncompyle2 to decompile.
~~* Searches for decryption key in the blue.dll file.~~
* Requires uncompyle2 for actual decompilation.
* Uses multiple processes to speed up decompilation.

Expects a evedec.ini file to specify Eve install location and output directory, e.g.:
```
[main]
eve_path = C:\Program Files (x86)\CCP\EVE\
store_path = ..\
```

