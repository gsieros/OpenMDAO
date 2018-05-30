"""Define the AssembledJacobian class."""
from __future__ import division, print_function

from collections import defaultdict

from six import iteritems

import numpy as np

from openmdao.jacobians.jacobian import Jacobian
from openmdao.matrices.dense_matrix import DenseMatrix
from openmdao.matrices.coo_matrix import COOMatrix
from openmdao.matrices.csr_matrix import CSRMatrix
from openmdao.matrices.csc_matrix import CSCMatrix
from openmdao.utils.units import get_conversion

SUBJAC_META_DEFAULTS = {
    'rows': None,
    'cols': None,
    'value': None,
    'approx': None,
    'dependent': False,
}


class AssembledJacobian(Jacobian):
    """
    Assemble dense global <Jacobian>.

    Attributes
    ----------
    _view_ranges : dict
        Maps system pathnames to jacobian sub-view ranges
    _int_mtx : <Matrix>
        Global internal Jacobian.
    _ext_mtx : {str: <Matrix>, ...}
        External Jacobian for each viewing subsystem.
    _keymap : dict
        Mapping of original (output, input) key to (output, source) in cases
        where the input has src_indices.
    _mask_caches : dict
        Contains masking arrays for when a subset of the variables are present in a vector, keyed
        by the input._names set.
    _matrix_class : type
        Class used to create Matrix objects.
    _subjac_iters : dict
        Mapping of system pathname to tuple of lists of absolute key tuples used to index into
        the jacobian.
    """

    def __init__(self, matrix_class):
        """
        Initialize all attributes.

        Parameters
        ----------
        matrix_class : type
            Class to use to create internal matrices.
        """
        global Component
        # avoid circular imports
        from openmdao.core.component import Component

        super(AssembledJacobian, self).__init__()
        self._view_ranges = {}
        self._int_mtx = None
        self._ext_mtx = {}
        self._keymap = {}
        self._mask_caches = {}
        self._matrix_class = matrix_class

        self._subjac_iters = defaultdict(lambda: None)

    def _initialize(self):
        """
        Allocate the global matrices.
        """
        # var_indices are the *global* indices for variables on this proc
        system = self._system
        is_top = system.pathname == ''

        abs2meta = system._var_abs2meta

        self._int_mtx = int_mtx = self._matrix_class(system.comm)
        ext_mtx = self._matrix_class(system.comm)

        iproc = system.comm.rank
        abs2idx = system._var_allprocs_abs2idx['nonlinear']
        sizes = system._var_sizes['nonlinear']['output']
        out_ranges = self._out_ranges = {}
        for name in system._var_allprocs_abs_names['output']:
            start = np.sum(sizes[iproc, :abs2idx[name]])
            out_ranges[name] = (start, start + sizes[iproc, abs2idx[name]])

        sizes = system._var_sizes['nonlinear']['input']
        in_ranges = self._in_ranges = {}
        for name in system._var_allprocs_abs_names['input']:
            start = np.sum(sizes[iproc, :abs2idx[name]])
            in_ranges[name] = (start, start + sizes[iproc, abs2idx[name]])

        abs2prom_out = system._var_abs2prom['output']
        conns = {} if isinstance(system, Component) else system._conn_global_abs_in2out
        keymap = self._keymap
        abs_key2shape = self._abs_key2shape

        # create the matrix subjacs
        for abs_key, (info, shape) in iteritems(self._subjacs_info):
            res_abs_name, wrt_abs_name = abs_key
            # because self._subjacs_info is shared among all 'related' assembled jacs,
            # we use out_ranges (and later in_ranges) to weed out keys outside of this jac
            if res_abs_name not in out_ranges:
                continue
            res_offset, _ = out_ranges[res_abs_name]

            if wrt_abs_name in abs2prom_out:
                out_offset, _ = out_ranges[wrt_abs_name]
                int_mtx._add_submat(abs_key, info, res_offset, out_offset, None, shape)
                keymap[abs_key] = abs_key
            elif wrt_abs_name in in_ranges:
                if wrt_abs_name in conns:  # connected input
                    out_abs_name = conns[wrt_abs_name]
                    # calculate unit conversion
                    in_units = abs2meta[wrt_abs_name]['units']
                    out_units = abs2meta[out_abs_name]['units']
                    if in_units and out_units and in_units != out_units:
                        factor, _ = get_conversion(out_units, in_units)
                        if factor == 1.0:
                            factor = None
                    else:
                        factor = None

                    out_offset, _ = out_ranges[out_abs_name]
                    src_indices = abs2meta[wrt_abs_name]['src_indices']

                    # need to add an entry for d(output)/d(source)
                    # instead of d(output)/d(input)
                    abs_key2 = (res_abs_name, out_abs_name)
                    keymap[abs_key] = abs_key2

                    shape = abs_key2shape(abs_key2)

                    int_mtx._add_submat(abs_key, info, res_offset, out_offset,
                                        src_indices, shape, factor)

                elif not is_top:  # input is connected to something outside current system
                    ext_mtx._add_submat(abs_key, info, res_offset,
                                        in_ranges[wrt_abs_name][0], None, shape)

        sizes = system._var_sizes
        iproc = system.comm.rank
        out_size = np.sum(sizes['nonlinear']['output'][iproc, :])

        int_mtx._build(out_size, out_size)
        if ext_mtx._submats:
            in_size = np.sum(sizes['nonlinear']['input'][iproc, :])
            ext_mtx._build(out_size, in_size)
        else:
            ext_mtx = None

        self._ext_mtx[system.pathname] = ext_mtx

    def _init_view(self, system):
        """
        Determine the _ext_mtx for a sub-view of the assemble jacobian.

        Parameters
        ----------
        system : <System>
            The system being solved using a sub-view of the jacobian.
        """
        abs2meta = system._var_abs2meta
        ranges = self._view_ranges[system.pathname]

        ext_mtx = self._matrix_class(system.comm)
        conns = {} if isinstance(system, Component) else system._conn_global_abs_in2out

        iproc = self._system.comm.rank
        sizes = self._system._var_sizes['nonlinear']['input']
        abs2idx = self._system._var_allprocs_abs2idx['nonlinear']
        in_offset = {n: np.sum(sizes[iproc, :abs2idx[n]]) for n in
                     system._var_abs_names['input'] if n not in conns}

        subjacs_info = self._subjacs_info

        sizes = self._system._var_sizes['nonlinear']['output']
        for s in system.system_iter(recurse=True, include_self=True, typ=Component):
            for res_abs_name in s._var_abs_names['output']:
                res_offset = np.sum(sizes[iproc, :abs2idx[res_abs_name]])
                res_size = abs2meta[res_abs_name]['size']

                for in_abs_name in s._var_abs_names['input']:
                    if in_abs_name not in conns:
                        abs_key = (res_abs_name, in_abs_name)

                        if abs_key not in subjacs_info:
                            continue

                        info, shape = subjacs_info[abs_key]
                        ext_mtx._add_submat(abs_key, info, res_offset - ranges[0],
                                            in_offset[in_abs_name] - ranges[2], None, shape)

        if ext_mtx._submats:
            sizes = system._var_sizes
            iproc = system.comm.rank
            out_size = np.sum(sizes['nonlinear']['output'][iproc, :])
            in_size = np.sum(sizes['nonlinear']['input'][iproc, :])
            ext_mtx._build(out_size, in_size)
        else:
            ext_mtx = None

        self._ext_mtx[system.pathname] = ext_mtx

    def _update(self):
        """
        Read the user's sub-Jacobians and set into the global matrix.
        """
        system = self._system
        int_mtx = self._int_mtx
        ext_mtx = self._ext_mtx[system.pathname]
        subjacs = self._subjacs

        subjac_iters = self._subjac_iters[system.pathname]
        if subjac_iters is None:
            keymap = self._keymap
            seen = set()
            global_conns = {} if isinstance(system, Component) else system._conn_global_abs_in2out
            output_names = system._var_abs_names['output']
            input_names = system._var_abs_names['input']

            # This is the level where the AssembledJacobian is slotted.
            # The of and wrt are the inputs and outputs that it sees, if they are in the subjacs.
            # TODO - For top level FD, the subjacs might not contain all derivs.

            iters = []
            iters_in_ext = []
            for res_abs_name in output_names:
                for out_abs_name in output_names:
                    abs_key = (res_abs_name, out_abs_name)
                    if abs_key in subjacs:
                        if abs_key in int_mtx._submats:
                            iters.append((abs_key, abs_key, False))
                        else:
                            # This happens when the src is an indepvarcomp that is
                            # contained in the system.
                            of, wrt = abs_key
                            for tgt, src in iteritems(global_conns):
                                if src == wrt and (of, tgt) in int_mtx._submats:
                                    iters.append((of, tgt), abs_key, False)
                                    break

                for in_abs_name in input_names:
                    abs_key = (res_abs_name, in_abs_name)
                    if abs_key in subjacs:
                        if in_abs_name in global_conns:
                            mapped = keymap[abs_key]
                            if mapped in seen:
                                iters.append((mapped, abs_key, True))
                            else:
                                iters.append((mapped, abs_key, False))
                                seen.add(mapped)
                        elif ext_mtx is not None:
                            iters_in_ext.append(abs_key)

            self._subjac_iters[system.pathname] = (iters, iters_in_ext)
        else:
            iters, iters_in_ext = subjac_iters

        for key1, key2, do_add in iters:
            if do_add:
                int_mtx._update_add_submat(key2, subjacs[key2])
            else:
                int_mtx._update_submat(key2, subjacs[key2])

        for key in iters_in_ext:
            ext_mtx._update_submat(key, subjacs[key])

    def _apply(self, d_inputs, d_outputs, d_residuals, mode):
        """
        Compute matrix-vector product.

        Parameters
        ----------
        d_inputs : Vector
            inputs linear vector.
        d_outputs : Vector
            outputs linear vector.
        d_residuals : Vector
            residuals linear vector.
        mode : str
            'fwd' or 'rev'.
        """
        system = self._system
        int_mtx = self._int_mtx
        if system.pathname in self._ext_mtx:
            ext_mtx = self._ext_mtx[system.pathname]
        else:
            ext_mtx = None

        if system._views_assembled_jac:
            ranges = self._view_ranges[system.pathname]
            int_ranges = (ranges[0], ranges[1], ranges[0], ranges[1])
        else:
            int_ranges = None

        # TODO: remove the _unscaled_context call here (and in DictionaryJacobian)
        # and do it outside so that we can avoid an unnecessary extra unscaling/rescaling
        # in _apply_linear
        with system._unscaled_context(
                outputs=[d_outputs], residuals=[d_residuals]):
            if mode == 'fwd':
                if d_outputs._names and d_residuals._names:
                    d_residuals.iadd_data(int_mtx._prod(d_outputs.get_data(), mode, int_ranges))

                if ext_mtx is not None and d_inputs._names and d_residuals._names:

                    # Masking
                    try:
                        mask = self._mask_caches[d_inputs._names]
                    except KeyError:
                        mask = ext_mtx._create_mask_cache(d_inputs)
                        self._mask_caches[d_inputs._names] = mask

                    d_residuals.iadd_data(ext_mtx._prod(d_inputs.get_data(), mode, None, mask=mask))

            else:  # rev
                dresids = d_residuals.get_data()
                if d_outputs._names and d_residuals._names:
                    d_outputs.iadd_data(int_mtx._prod(dresids, mode, int_ranges))

                if ext_mtx is not None and d_inputs._names and d_residuals._names:

                    # Masking
                    try:
                        mask = self._mask_caches[d_inputs._names]
                    except KeyError:
                        mask = ext_mtx._create_mask_cache(d_inputs)
                        self._mask_caches[d_inputs._names] = mask

                    d_inputs.iadd_data(ext_mtx._prod(dresids, mode, None, mask=mask))


class DenseJacobian(AssembledJacobian):
    """
    Assemble dense global <Jacobian>.
    """

    def __init__(self):
        """
        Initialize all attributes.
        """
        super(DenseJacobian, self).__init__(matrix_class=DenseMatrix)


class COOJacobian(AssembledJacobian):
    """
    Assemble sparse global <Jacobian> in Coordinate list format.
    """

    def __init__(self):
        """
        Initialize all attributes.
        """
        super(COOJacobian, self).__init__(matrix_class=COOMatrix)


class CSRJacobian(AssembledJacobian):
    """
    Assemble sparse global <Jacobian> in Compressed Row Storage format.
    """

    def __init__(self):
        """
        Initialize all attributes.
        """
        super(CSRJacobian, self).__init__(matrix_class=CSRMatrix)


class CSCJacobian(AssembledJacobian):
    """
    Assemble sparse global <Jacobian> in Compressed Col Storage format.
    """

    def __init__(self):
        """
        Initialize all attributes.
        """
        super(CSCJacobian, self).__init__(matrix_class=CSCMatrix)
