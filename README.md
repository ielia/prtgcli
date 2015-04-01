# PRTG Client #

This is a command line interface to the [PRTG](http://www.paessler.com/) API which allows bulk tagging, and listing of
groups, sensors and devices for use with [prtg-py](https://github.com/ielia/prtg-py).


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

2. Enter the virtual environment:

    ```
    . *{VIRTUALENV_DIRECTORY}*/bin/activate
    ```

    You will notice the name of the virtual environment in your prompt, in brackets at the beginning.

3. Continue from the normal [installation instructions](#installation).


## Usage ##

From a console/terminal, you can execute `prtgcli`. E.g.:

    prtgcli -e 'https://prtg.paessler.com' -u demo -p demodemo ls

Help message:

    prtgcli --help

## Rule Set ##

The rule set will be specified in a YAML file with the following format:

    rules:
      -
        attribute: {MATCHING_ATTRIBUTE_NAME}
        pattern: {MATCHING_PATTERN}
        prop: {PROPERTY_NAME}
        update: {BOOLEAN_UPDATE_VALUE}
        value:
          - {TAG1}
          - {TAG2}
          - ...
        remove:
          - {TAGX}
          - {TAGY}
          - ...
      -
        ...

You can find an example in this same directory, in the file '`rules.yaml`'.

The rules are run sequentially, in the order they are specified in the YAML file.

### Structure ###

* **`attribute`**: PRTG entity (group/device/sensor) attribute to which the `pattern` will apply. E.g.: `name`.
* **`pattern`**: Regular expression (will be compiled by Python's `re` package) with which to match the `attribute`.
* **`prop`**: Property (attribute) of the PRTG entity to be changed. E.g.: `tags`.
* **`update`**: Boolean flag (either `True` or `False`, with that casing) that specifies whether the value will be added
                to the current one (current also in terms of rule application) and the `remove` section will be applied
                or that the `value` will overwrite the current one.
* **`formatting`**: A string that will be passed to Python's `string.format` function to overwrite the property value
                    with the corresponding expression (E.g.: `formatting: "x{entity.name}x"` and a `name: "NAME"` will
                    result in `name = "xNAMEx"`).
* **`rollback_formatting`**: This property rollbacks a previous formatting. It receives the same string as the previous
                             property and attempts to roll the change back.
* **`value`**: List of values of update/replacement. See `update` above.
* **`remove`**: List of values that will be removed from the original. Will only be applied when `update` is `True`.

### Examples ###

#### Example 1 ####

##### PRTG Contents #####

    group = { id: 1, name: 'the group', tags: 'TAG1' }
    devices = [
        { id: 123, name: 'some device', parentid: 1, tags: ['existing'], inherited_tags: ['TAG1'] }
        { id: 124, name: 'some other device', parentid: 1, tags: ['tagX'], inherited_tags: ['TAG1'] }
        { id: 125, name: 'something else', parentid: 1, tags: ['tagY'], inherited_tags: ['TAG1'] }
    ]

##### File: rules.yaml #####

    rules:
      -
        attribute: name
        pattern: "^.*device"
        prop: tags
        update: True
        value:
          - TAG1
          - TAG2
          - TAG3
          - existing
      -
        attribute: name
        pattern: "^.*other"
        prop: tags
        update: True
        value:
          - TAG4
        remove:
          - TAG1
          - TAG2
          - tagX
          - tagZ
      -
        attribute: name
        pattern: "^something"
        prop: tags
        update: False
        value:
          - myTag

##### Command line #####

    prtgcli apply -r rules.yaml -c devices

##### Resulting devices #####

    devices = [
        { id: 123, name: 'some device', parentid: 1, tags: ['existing', 'TAG2', 'TAG3'], inherited_tags: ['TAG1'] }
        { id: 124, name: 'some other device', parentid: 1, tags: ['TAG3', 'existing', 'TAG4'], inherited_tags: ['TAG1'] }
        { id: 125, name: 'something else', parentid: 1, tags: ['myTag'], inherited_tags: ['TAG1'] }
    ]

##### Explanation #####

1. The first rule matches the first two devices' names, so it will be applied to them.

    a. The device `123` will be added `TAG1`, `TAG2`, `TAG3` and `existing` tags, but since `TAG1` is inherited and
       `existing` is already in the list of tags of the device, it will only get the middle two (`TAG2` and `TAG3`).

    b. The device `123` will be added `TAG1`, `TAG2`, `TAG3` and `existing` tags, but since `TAG1` is inherited, it will
       only get the latter three (`TAG2` and `TAG3`, `existing`).

    *At this point, we have the following:*

        devices = [
            { id: 123, name: 'some device', parentid: 1, tags: ['existing', 'TAG2', 'TAG3'], inherited_tags: ['TAG1'] }
            { id: 124, name: 'some other device', parentid: 1, tags: ['tagX', 'TAG2', 'TAG3', 'existing'], inherited_tags: ['TAG1'] }
            { id: 125, name: 'something else', parentid: 1, tags: ['tagY'], inherited_tags: ['TAG1'] }
        ]

2. The second rule matches only the second device (`124`).

    a. The device `124` will be added `TAG4` and removed `TAG1`, `TAG2`, `tagX` and `tagZ` tags, but since `TAG1` is
       inherited and not really part of the devices' tags, and `tagZ` is not part of the tags, it will effectively get
       added `TAG4` and removed `TAG2` and `tagX`.

    *At this point, we have the following:*

        devices = [
            { id: 123, name: 'some device', parentid: 1, tags: ['existing', 'TAG2', 'TAG3'], inherited_tags: ['TAG1'] }
            { id: 124, name: 'some other device', parentid: 1, tags: ['TAG3', 'existing', 'TAG4'], inherited_tags: ['TAG1'] }
            { id: 125, name: 'something else', parentid: 1, tags: ['tagY'], inherited_tags: ['TAG1'] }
        ]

3. The third rule matches only the last device (`125`).

    a. The device `125` will have its tags cleared (due to `update: False`) and will have added `myTag` tag.

    *At this point, we have the following:*

        devices = [
            { id: 123, name: 'some device', parentid: 1, tags: ['existing', 'TAG2', 'TAG3'], inherited_tags: ['TAG1'] }
            { id: 124, name: 'some other device', parentid: 1, tags: ['TAG3', 'existing', 'TAG4'], inherited_tags: ['TAG1'] }
            { id: 125, name: 'something else', parentid: 1, tags: ['myTag'], inherited_tags: ['TAG1'] }
        ]

#### Example 2 ####

##### PRTG Contents #####

    group = { id: 1, name: 'the group' }
    devices = [
        { id: 123, name: 'some device', parentid: 1 }
        { id: 124, name: 'some other device', parentid: 1 }
    ]
    sensors = [
        { id: 4567, name: 'a sensor', parentid: 123 }
        { id: 4568, name: 'PING', parentid: 124 }
    ]

##### File: sensor-naming.yaml #####

    rules:
      -
        attribute: name
        pattern: "^PING"
        prop: name
        update: False
        formatting: "[{entity.name}]"
      -
        attribute: name
        pattern: "^PING"
        prop: name
        update: False
        formatting: "{parent.name} - {entity.name}"

##### Command line #####

    prtgcli apply -r sensor-naming.yaml -c sensors

##### Resulting sensors #####

    sensors = [
        { id: 4567, name: 'a sensor', parentid: 123 }
        { id: 4568, name: 'some other device - [PING]', parentid: 124 }
    ]

##### Explanation #####

1. The first rule will match the second sensor (`4568`).

    a. That sensor's name will be set to `[PING]`.

    *At this point, we have the following:*

        sensors = [
            { id: 4567, name: 'a sensor', parentid: 123 }
            { id: 4568, name: '[PING]', parentid: 124 }
        ]

2. The second rule will also match the second sensor (`4568`) only.

    a. That sensor's name will have its parent's name added to it (according to the format string indicated by
       `formatting`), so the resulting sensor's name will be `some other device` (parent's name), followed by ` - `,
       followed by `[PING]` (the current entity name in the rule execution chain).

    *At this point, we have the following:*

        sensors = [
            { id: 4567, name: 'a sensor', parentid: 123 }
            { id: 4568, name: 'some other device - [PING]', parentid: 124 }
        ]

#### Example 3 ####

##### PRTG Contents #####

    group = { id: 1, name: 'the group' }
    devices = [
        { id: 123, name: 'some device', parentid: 1 }
    ]
    sensors = [
        { id: 4567, name: 'some device - [PING]', parentid: 123 }
    ]

##### File: sensor-rollback.yaml #####

    rules:
      -
        attribute: name
        pattern: "^\\[.*\\]"
        prop: name
        update: False
        rollback_formatting: "{parent.name} - {entity.name}"
      -
        attribute: name
        pattern: "^\\[.*\\]"
        prop: name
        update: False
        rollback_formatting: "[{entity.name}]"

##### Command line #####

    prtgcli apply -r sensor-rollback.yaml -c sensors

##### Resulting sensors #####

    sensors = [
        { id: 4567, name: 'PING', parentid: 123 }
    ]

##### Explanation #####

1. The first rule will match the only sensor (`4567`).

    a. That sensor's name will be recovered from `{parent.name} - (.*)` (which is the same expression from
       `rollback_formatting`, escaped and replacing `{entity.name}`&mdash;`name` because it is the specified
       `prop`&mdash;for a group extraction reg.exp.). That regular expression will be populated with the sensor's
       parent's name, becoming `some device - (.*)`. This will result in the extraction of `[PING]`, thus setting its
       `name` to the extracted string.

    *At this point, we have the following:*

        sensors = [
            { id: 4567, name: '[PING]', parentid: 123 }
        ]

2. The second rule will, again, match the only sensor (`4567`).

    a. That sensor's name will be recovered from `\[(.*)\]` (which is the same expression from `rollback_formatting`,
       escaped and replacing `{entity.name}`&mdash;`name` because it is the specified `prop`&mdash;for a group
       extraction reg.exp.). This will result in the extraction of `PING`, thus setting its `name` to the extracted
       string.

    *At this point, we have the following:*

        sensors = [
            { id: 4567, name: 'PING', parentid: 123 }
        ]
