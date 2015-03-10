# PRTG Client #

This is a command line interface to the [PRTG](http://www.paessler.com/) API which allows bulk tagging, sensor and
device listing for use with [prtg-py](https://github.com/ielia/prtg-py).


## <a name="installation"></a> Installation ##

Preconditions: Python 3.x.

1. Download (clone) `prtg-py` repository from [https://github.com/ielia/prtg-py](https://github.com/ielia/prtg-py)

2. Inside the repository directory, execute a normal Python project installation:

    ```
    python setup.py install
    ```

    This will install all the dependencies for prtg-py.

3. Clone `prtgcli` repository from [https://github.com/ielia/prtgcli](https://github.com/ielia/prtgcli)

4. Perform the same installation instructions from point 2 with the directory of `prtgcli`.


## Development Installation ##

Preconditions: All the same for Installation, plus `virtualenv`.

1. Create a virtual environment in a directory of your choice. E.g.:

    ```
    virtualenv --python=python3.4 venv-prtg-3.4
    ```

    This virtual environment needs to be created with Python 3.x

2. Continue from the normal [installation instructions](#installation).


## Usage ##

From a console/terminal, you can execute `prtgcli`. E.g.:

   ```
   prtgcli -e 'https://prtg.paessler.com' -u demo -p demodemo ls
   ```

Help message:

   ```
   prtgcli --help
   ```
