"""This module acts as a stub to avoid a dependency for the numpy package.

If the numpy package is not available, MPyC still runs but with less functionality.
Use of NumPy can be disabled to avoid loading the numpy package.

If NumPy is enabled (available and not disabled), the MPyC runtime supports array
types---along with vectorized implementations---for secure numbers and the underlying
finite field types. The array types are accessible through the 'array' attribute,
e.g., for secint48=mpc.SecInt(48), the array type is secint48.array and the array type
for the underlying prime field is secint48.field.array.

... work in progress for MPyC version 0.9
"""

import os
import logging


def _item_shape(shape, key):
    """Return shape of item a[key] for any array a of given shape.

    The item's shape is calculated quickly as a function of the given shape and key,
    assuming key fits with the given shape.

    If key does not fit the given shape, errors will generally not be raised to avoid
    costly checks.

    Alternatively, the item's shape could be obtained as a[key].shape for dummy array
    a=np.empty(shape), but this potentially consumes a large amount of memory.
    """
    # TODO: handle field acces  a['field-name']
    if not isinstance(key, tuple):
        key = (key,)
    if len(key) == 1 and isinstance(key[0], np.ndarray) and \
       key[0].dtype == bool and shape == key[0].shape:  # fast path
        return (key[0].sum(),)

    try:
        # Replace ellipsis ... in key by 0 or more : slices, depending on occurences of np.newaxis.
        # NB: tests like "Ellipsis in key" trigger elementwise ==-testing for arrays; to avoid
        # this use key0 as a pruned version of key with everything but .../newaxis collapsed to 0.
        key0 = tuple(a if a is Ellipsis or a is np.newaxis else 0 for a in key)
        if Ellipsis in key0:
            if key0.count(Ellipsis) > 1:
                raise IndexError('only a single ellipsis allowed')

            i = key0.index(Ellipsis)
            ii = i - key0[:i].count(np.newaxis)
            delta = len(shape) + key0.count(np.newaxis) - (len(key) - 1)
            expansion = tuple(slice(s) for s in shape[ii:ii + delta])  # no expansion if delta<=0
            key = key[:i] + expansion + key[i+1:]

        if all(isinstance(a, (int, slice)) and not isinstance(a, bool) or a is np.newaxis
               for a in key):
            # basic indexing
            shape_item = []
            i = 0  # still to process shape[i:]
            for k in key:
                if isinstance(k, int):
                    # delete axis i
                    i += 1
                elif isinstance(k, slice):
                    # keep axis i with length of slice k
                    shape_item.append(len(range(*k.indices(shape[i]))))  # ValueError if k.step=0
                    i += 1
                else:  # k is np.newaxis
                    # insert new axis
                    shape_item.append(1)

            if i > len(shape):
                raise IndexError('key too long for shape')

            # append remaining axes
            shape_item.extend(shape[i:])
            return tuple(shape_item)

        # advanced indexing
        # Use keya as version of key with everything but slice/newaxis converted to arrays.
        keya = tuple(a if isinstance(a, (slice, np.ndarray)) or a is np.newaxis else np.array(a)
                     for a in key)
        indexing_arrays = []
        separated = False
        last_pos = -1  # index of last array in keya
        bool_0darray_count = 0
        for i, a in enumerate(keya):
            if isinstance(a, np.ndarray):
                separated = separated or (len(indexing_arrays) > 0 and last_pos < i-1)
                last_pos = i
                if a.dtype != bool:
                    indexing_arrays.append(a)
                else:
                    if a.ndim == 0:
                        bool_0darray_count += 1
                        a = np.atleast_1d(a)
                    indexing_arrays.extend(a.nonzero())
        shape_advanced = np.broadcast_shapes(*(a.shape for a in indexing_arrays))

        shape_item = []
        if separated:
            shape_item.extend(shape_advanced)
        i = 0  # still to process shape[i:]
        for k in keya:
            if isinstance(k, slice):
                # keep axis i with length of slice k
                shape_item.append(len(range(*k.indices(shape[i]))))  # ValueError if k.step=0
                i += 1
            elif k is np.newaxis:
                # insert new axis
                shape_item.append(1)
            elif separated:
                # skip axis unless indexing array is boolean 0d-array
                if not (k.dtype == bool and k.ndim == 0):
                    i += 1
            elif shape_advanced is not None:
                # skip axes for indexing arrays (except for boolean 0d-arrays)
                shape_item.extend(shape_advanced)
                shape_advanced = None
                i += len(indexing_arrays) - bool_0darray_count

        if i > len(shape):
            raise IndexError('key too long for shape')

        # append remaining axes
        shape_item.extend(shape[i:])
        return tuple(shape_item)

    except Exception as e:
        logging.debug(f'Exception "{e}" in mpyc.numpy._item_shape for {shape=} {key=}')
        # Let Numpy generate error message by calling a[key] for dummy array a of given shape:
        np.empty(shape)[key]


try:
    if os.getenv('MPYC_NONUMPY') == '1':
        raise ImportError

    import numpy as np
    np._item_shape = _item_shape
except ImportError:
    del _item_shape
    np = None
