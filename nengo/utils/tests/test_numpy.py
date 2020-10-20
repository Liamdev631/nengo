import importlib
import itertools

import numpy as np
import pytest

import nengo.utils.numpy as npext
from nengo._vendor.scipy import expm
from nengo.exceptions import ValidationError
from nengo.utils.numpy import array, array_hash, as_shape, broadcast_shape, meshgrid_nd


def test_meshgrid_nd(allclose):
    a = [0, 0, 1]
    b = [1, 2, 3]
    c = [23, 42]
    expected = [
        np.array(
            [
                [[0, 0], [0, 0], [0, 0]],
                [[0, 0], [0, 0], [0, 0]],
                [[1, 1], [1, 1], [1, 1]],
            ]
        ),
        np.array(
            [
                [[1, 1], [2, 2], [3, 3]],
                [[1, 1], [2, 2], [3, 3]],
                [[1, 1], [2, 2], [3, 3]],
            ]
        ),
        np.array(
            [
                [[23, 42], [23, 42], [23, 42]],
                [[23, 42], [23, 42], [23, 42]],
                [[23, 42], [23, 42], [23, 42]],
            ]
        ),
    ]
    actual = meshgrid_nd(a, b, c)
    assert allclose(expected, actual)


@pytest.mark.parametrize("nnz", [7, 300])
def test_array_hash_sparse(nnz, rng):
    scipy_sparse = pytest.importorskip("scipy.sparse")

    if nnz == 7:
        shape = (5, 5)
        idxs_a = ([0, 0, 1, 2, 3, 3, 4], [0, 2, 3, 4, 2, 4, 0])
        idxs_b = ([0, 1, 1, 2, 3, 3, 4], [1, 2, 3, 4, 2, 4, 0])

        data_a = [1.0, 2.0, 1.5, 2.3, 1.2, 2.5, 1.8]
        data_b = [1.0, 1.0, 1.5, 2.3, 1.2, 2.5, 1.8]
    else:
        shape = (100, 100)

        idxs_a = np.unravel_index(rng.permutation(np.prod(shape))[:nnz], shape)
        idxs_b = np.unravel_index(rng.permutation(np.prod(shape))[:nnz], shape)

        data_a = rng.uniform(-1, 1, size=nnz)
        data_b = rng.uniform(-1, 1, size=nnz)

    matrices = [[] for _ in range(6)]

    for (rows, cols), data in itertools.product((idxs_a, idxs_b), (data_a, data_b)):

        csr = scipy_sparse.csr_matrix((data, (rows, cols)), shape=shape)
        matrices[0].append(csr)
        matrices[1].append(csr.tocsc())
        matrices[2].append(csr.tocoo())
        matrices[3].append(csr.tobsr())
        matrices[4].append(csr.todok())
        matrices[5].append(csr.tolil())
        # matrices[6].append(csr.todia())  # warns about inefficiency

    # ensure hash is reproducible
    for matrix in (m for kind in matrices for m in kind):
        assert array_hash(matrix) == array_hash(matrix)

    # ensure hash is different for different matrices
    for kind in matrices:
        hashes = [array_hash(matrix) for matrix in kind]
        assert len(np.unique(hashes)) == len(
            kind
        ), f"Different matrices should have different hashes: {hashes}"


def test_expm(rng, allclose):
    scipy_linalg = pytest.importorskip("scipy.linalg")
    for a in [np.eye(3), rng.randn(10, 10), -10 + rng.randn(10, 10)]:
        assert allclose(scipy_linalg.expm(a), expm(a))


def test_as_shape_errors():
    """Tests errors generated by the `as_shape` function"""
    with pytest.raises(ValueError, match="cannot be safely converted to a shape"):
        as_shape(1.0)  # float is noniterable and noninteger


def test_brodcast_shape():
    assert broadcast_shape(shape=(3, 2), length=3) == (1, 3, 2)
    assert broadcast_shape(shape=(3, 2), length=4) == (1, 1, 3, 2)
    assert broadcast_shape(shape=(3, 2), length=2) == (3, 2)


def test_array():
    assert array([1, 2, 3], dims=4).shape == (3, 1, 1, 1)
    assert array([1, 2, 3], dims=1).shape == (3,)
    assert array([1, 2, 3], min_dims=2).shape == (3, 1)
    assert array([1, 2, 3], min_dims=1).shape == (3,)

    x = array([1, 2, 3], readonly=True)
    with pytest.raises(ValueError, match="read-only"):
        x[0] = 3

    with pytest.raises(ValidationError, match="Input cannot be cast to array"):
        array([[1, 2, 3]], dims=1)


def test_rfftfreq_fallback(monkeypatch):
    np_rfftfreq = np.fft.rfftfreq
    monkeypatch.delattr(np.fft, "rfftfreq")
    importlib.reload(npext)

    for n in (3, 4, 8, 9):
        for d in (1.0, 3.4, 9.8):
            assert np.allclose(npext.rfftfreq(n, d=d), np_rfftfreq(n, d=d))
