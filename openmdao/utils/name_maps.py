"""Maps between promoted/relative/absolute names and name pairs."""


def rel_name2abs_name(system, rel_name):
    """
    Map relative variable name to absolute variable name.

    Parameters
    ----------
    system : <System>
        System to which the given name is relative.
    rel_name : str
        Given relative variable name.

    Returns
    -------
    str
        Absolute variable name.
    """
    return rel_name if system.pathname is '' else system.pathname + '.' + rel_name


def abs_name2rel_name(system, abs_name):
    """
    Map relative variable name to absolute variable name.

    Parameters
    ----------
    system : <System>
        System to which the given name is relative.
    abs_name : str
        Given absolute variable name.

    Returns
    -------
    str
        Relative variable name.
    """
    return abs_name if system.pathname is '' else abs_name[len(system.pathname) + 1:]


def rel_key2abs_key(system, rel_key):
    """
    Map relative variable name pair to absolute variable name pair.

    Parameters
    ----------
    system : <System>
        System to which the given key is relative.
    rel_key : (str, str)
        Given relative variable name pair.

    Returns
    -------
    (str, str)
        Absolute variable name pair.
    """
    return (rel_name2abs_name(system, rel_key[0]), rel_name2abs_name(system, rel_key[1]))


def abs_key2rel_key(system, abs_key):
    """
    Map relative variable name pair to absolute variable name pair.

    Parameters
    ----------
    system : <System>
        System to which the given key is relative.
    abs_key : (str, str)
        Given absolute variable name pair.

    Returns
    -------
    (str, str)
        Relative variable name pair.
    """
    return (abs_name2rel_name(system, abs_key[0]), abs_name2rel_name(system, abs_key[1]))


def prom_name2abs_name(system, prom_name, type_):
    """
    Map the given promoted name to the absolute name.

    This is only valid when the name is unique; otherwise, a KeyError is thrown.

    Parameters
    ----------
    system : <System>
        System to which prom_name is relative.
    prom_name : str
        Promoted variable name in the owning system's namespace.
    type_ : str
        Either 'input' or 'output'.

    Returns
    -------
    str or None
        Absolute variable name or None if prom_name is invalid.
    """
    prom2abs_list = system._var_allprocs_prom2abs_list[type_]

    if prom_name in prom2abs_list:
        abs_list = prom2abs_list[prom_name]
        if len(abs_list) == 1:
            return abs_list[0]
        else:
            # looks like an aliased input, which must be set via the connected output
            src_name = system._conn_global_abs_in2out.get(abs_list[0])
            if src_name and src_name in system._var_abs2prom['output']:
                src_name = system._var_abs2prom['output'][src_name]  # use promoted name
            if src_name:  # input is connected
                raise RuntimeError("The promoted name {} is invalid because it refers to "
                                   "multiple inputs: [{}]. "
                                   "Access the value from the connected output variable {} instead."
                                   .format(prom_name, ' ,'.join(abs_list), src_name))
            else:
                raise RuntimeError("The promoted name {} is invalid because it refers to "
                                   "multiple inputs: [{}] that are not connected to an output "
                                   "variable.".format(prom_name, ', '.join(abs_list)))
    else:
        return None


def name2abs_name(system, name, names, type_):
    """
    Map the given promoted or relative name to the absolute name.

    This is only valid when the name is unique; otherwise, a KeyError is thrown.

    Parameters
    ----------
    system : <System>
        System to which name is relative.
    name : str
        Promoted or relative variable name in the owning system's namespace.
    names : dict or list of str
        List of valid names.
    type_ : str
        Either 'input' or 'output'.

    Returns
    -------
    str or None
        Absolute variable name if unique abs_name found or None otherwise.
    """
    abs_name1 = prom_name2abs_name(system, name, type_)
    if abs_name1 in names:
        return abs_name1

    abs_name2 = rel_name2abs_name(system, name)
    if abs_name2 in names:
        return abs_name2


def prom_key2abs_key(system, prom_key):
    """
    Map the given promoted name pair to the absolute name pair.

    The first name is an output, and the second name can be an output or an input.
    If the second name is non-unique, a KeyError is thrown.

    Parameters
    ----------
    system : <System>
        System to which prom_key is relative.
    prom_key : (str, str)
        Promoted name pair of sub-Jacobian.

    Returns
    -------
    (str, str) or None
        Absolute name pair of sub-Jacobian or None is prom_key is invalid.
    """
    abs_name0 = prom_name2abs_name(system, prom_key[0], 'output')

    abs_name1in = prom_name2abs_name(system, prom_key[1], 'input')
    abs_name1out = prom_name2abs_name(system, prom_key[1], 'output')
    if abs_name1in is None and abs_name1out is None:
        abs_name1 = None
    elif abs_name1in is None:
        abs_name1 = abs_name1out
    elif abs_name1out is None:
        abs_name1 = abs_name1in
    else:
        msg = 'The promoted name "{}" is invalid because it is non-unique.'
        raise KeyError(msg.format(prom_key[1]))

    if abs_name0 is not None and abs_name1 is not None:
        return (abs_name0, abs_name1)


def key2abs_key(system, key):
    """
    Map the given absolute, promoted or relative name pair to the absolute name pair.

    The first name is an output, and the second name can be an output or an input.
    If the second name is non-unique, a KeyError is thrown.

    Parameters
    ----------
    system : <System>
        System to which prom_key is relative.
    key : (str, str)
        Promoted or relative name pair of sub-Jacobian.

    Returns
    -------
    (str, str) or None
        Absolute name pair of sub-Jacobian if unique abs_key found or None otherwise.
    """
    if key in system._subjacs_info:
        return key

    abs2meta = system._var_abs2meta

    abs_key = prom_key2abs_key(system, key)
    if abs_key is not None:
        return abs_key

    abs_key = rel_key2abs_key(system, key)
    if abs_key[0] in abs2meta and abs_key[1] in abs2meta:
        return abs_key
    else:
        return None
