"""Tests for pixelart_creator.logic.procgen — seeded deterministic generators.

Covers REQ-P8-LOGIC-012 (seeded determinism; content written via reversible
commands; ``MAX_PROCGEN_DIMENSION``) and -013. Every generator is a pure
function of ``(params, seed)`` — same seed → identical output — and writes
through a reversible ``FunctionCommand`` (``apply ∘ undo = identity``).
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import procgen
from pixelart_creator.logic.constants import (
    DEFAULT_PROCGEN_SEED,
    MAX_PROCGEN_DIMENSION,
)
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode
from pixelart_creator.logic.procgen import ProcgenError, make_procgen_command

RED = (255, 0, 0, 255)
WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)

_STOCHASTIC = ("value_noise", "gradient_noise", "opensimplex", "cellular_automata")


def _doc(width=8, height=8, palette=None) -> Document:
    return Document(width, height, palette=palette or Palette([BLACK, WHITE, RED]))


def _leaf(doc):
    return iter_layers(doc.frames[0].layers)[0].buffer


def _make(doc, algorithm, seed=1, **params):
    params.setdefault("frequency", 3)
    return make_procgen_command(doc, algorithm=algorithm, params=params, seed=seed)


# --------------------------------------------------------------------------- #
# Algorithm vocabulary + command shape                                         #
# --------------------------------------------------------------------------- #


def test_algorithms_vocabulary():
    assert procgen.ALGORITHMS == (
        procgen.ALGO_VALUE_NOISE,
        procgen.ALGO_GRADIENT_NOISE,
        procgen.ALGO_OPENSIMPLEX,
        procgen.ALGO_CELLULAR,
        procgen.ALGO_DITHERED_GRADIENT,
    )


@pytest.mark.parametrize("algorithm", _STOCHASTIC)
def test_command_is_reversible(algorithm):
    # REQ-P8-LOGIC-012 / SC-L012-1 (R-29): written via commands; content is
    # written via a reversible command (apply ∘ undo = identity).
    doc = _doc()
    buf = _leaf(doc)
    before = buf.data.copy()
    cmd = _make(doc, algorithm, seed=5)
    assert isinstance(cmd, Command)
    assert np.array_equal(buf.data, before)  # returned UNAPPLIED
    cmd.execute()
    assert not np.array_equal(buf.data, before)
    cmd.undo()
    assert np.array_equal(buf.data, before)


def test_dithered_gradient_reversible_and_within_palette():
    palette = Palette([BLACK, WHITE])
    doc = _doc(palette=palette)
    buf = _leaf(doc)
    cmd = make_procgen_command(
        doc,
        algorithm=procgen.ALGO_DITHERED_GRADIENT,
        params={"direction": "horizontal", "dither": "ordered"},
        seed=0,
    )
    cmd.execute()
    # Every generated pixel is one of the palette colours (output ⊆ palette).
    palette_set = {BLACK, WHITE}
    produced = {tuple(int(c) for c in px) for px in buf.data.reshape(-1, 4)}
    assert produced <= palette_set
    cmd.undo()


def test_dithered_gradient_requires_palette():
    doc = Document(8, 8, palette=Palette())  # empty palette
    with pytest.raises(ProcgenError):
        make_procgen_command(
            doc, algorithm=procgen.ALGO_DITHERED_GRADIENT, params={}, seed=0
        )


@pytest.mark.parametrize("direction", ["horizontal", "vertical"])
@pytest.mark.parametrize("dither", ["ordered", "floyd_steinberg"])
def test_dithered_gradient_directions_and_modes(direction, dither):
    doc = _doc(palette=Palette([BLACK, WHITE]))
    buf = _leaf(doc)
    before = buf.data.copy()
    cmd = make_procgen_command(
        doc,
        algorithm=procgen.ALGO_DITHERED_GRADIENT,
        params={"direction": direction, "dither": dither},
        seed=0,
    )
    cmd.execute()
    assert not np.array_equal(buf.data, before)
    cmd.undo()
    assert np.array_equal(buf.data, before)


def test_dithered_gradient_rejects_bad_direction():
    doc = _doc(palette=Palette([BLACK, WHITE]))
    with pytest.raises(ProcgenError):
        make_procgen_command(
            doc,
            algorithm=procgen.ALGO_DITHERED_GRADIENT,
            params={"direction": "diagonal"},
            seed=0,
        )


def test_dithered_gradient_rejects_bad_dither():
    doc = _doc(palette=Palette([BLACK, WHITE]))
    with pytest.raises(ProcgenError):
        make_procgen_command(
            doc,
            algorithm=procgen.ALGO_DITHERED_GRADIENT,
            params={"dither": "nonesuch"},
            seed=0,
        )


def test_valid_colour_params_change_ramp():
    # Explicit RGBA color_low/color_high are accepted (JSON-native list of 4).
    doc = _doc()
    buf = _leaf(doc)
    cmd = make_procgen_command(
        doc,
        algorithm="value_noise",
        params={"color_low": [10, 20, 30, 255], "color_high": [200, 100, 50, 255]},
        seed=1,
    )
    cmd.execute()
    produced = {tuple(int(c) for c in px) for px in buf.data.reshape(-1, 4)}
    # Every produced colour lies on the low→high ramp (channels within bounds).
    for r, g, b, a in produced:
        assert 10 <= r <= 200 and a == 255


def test_zero_width_region_rejected():
    doc = _doc()
    with pytest.raises(ProcgenError):
        make_procgen_command(doc, algorithm="value_noise", params={"width": 0}, seed=1)


def test_frequency_below_one_rejected():
    doc = _doc()
    with pytest.raises(ProcgenError):
        make_procgen_command(
            doc, algorithm="value_noise", params={"frequency": 0}, seed=1
        )


def test_cellular_iterations_out_of_range_rejected():
    doc = _doc()
    with pytest.raises(ProcgenError):
        make_procgen_command(
            doc, algorithm="cellular_automata", params={"iterations": 999}, seed=1
        )


# --------------------------------------------------------------------------- #
# Determinism — same seed identical, different seed differs (REQ-P8-LOGIC-012)   #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("algorithm", _STOCHASTIC)
def test_same_seed_identical_output(algorithm):
    doc_a, doc_b = _doc(), _doc()
    _make(doc_a, algorithm, seed=123).execute()
    _make(doc_b, algorithm, seed=123).execute()
    assert np.array_equal(_leaf(doc_a).data, _leaf(doc_b).data)


@pytest.mark.parametrize("algorithm", _STOCHASTIC)
def test_different_seed_differs(algorithm):
    doc_a, doc_b = _doc(), _doc()
    _make(doc_a, algorithm, seed=1).execute()
    _make(doc_b, algorithm, seed=2).execute()
    assert not np.array_equal(_leaf(doc_a).data, _leaf(doc_b).data)


def test_default_seed_constant():
    assert procgen.DEFAULT_PROCGEN_SEED is DEFAULT_PROCGEN_SEED


def test_seed_defaults_to_default_procgen_seed():
    doc_a, doc_b = _doc(), _doc()
    make_procgen_command(
        doc_a, algorithm="value_noise", params={"frequency": 2}
    ).execute()
    make_procgen_command(
        doc_b,
        algorithm="value_noise",
        params={"frequency": 2},
        seed=DEFAULT_PROCGEN_SEED,
    ).execute()
    assert np.array_equal(_leaf(doc_a).data, _leaf(doc_b).data)


# --------------------------------------------------------------------------- #
# Target / region resolution + validation                                      #
# --------------------------------------------------------------------------- #


def test_region_confines_write():
    doc = _doc()
    buf = _leaf(doc)
    before = buf.data.copy()
    _make(doc, "value_noise", seed=3, x=0, y=0, width=4, height=4).execute()
    # Outside the 4x4 region is unchanged.
    assert np.array_equal(buf.data[4:, 4:], before[4:, 4:])


def test_target_by_layer_id():
    doc = _doc()
    layers = iter_layers(doc.frames[0].layers)
    doc.add_layer("second")
    layers = iter_layers(doc.frames[0].layers)
    target = layers[1]
    other = layers[0]
    other_before = other.buffer.data.copy()
    make_procgen_command(
        doc,
        algorithm="value_noise",
        params={"layer_id": target.layer_id, "frequency": 2},
        seed=1,
    ).execute()
    assert not np.array_equal(target.buffer.data, other_before)
    assert np.array_equal(other.buffer.data, other_before)  # untouched


def test_unknown_layer_id_rejected():
    doc = _doc()
    with pytest.raises(ProcgenError):
        make_procgen_command(
            doc, algorithm="value_noise", params={"layer_id": 999999}, seed=1
        )


def test_bad_layer_id_type_rejected():
    doc = _doc()
    with pytest.raises(ProcgenError):
        make_procgen_command(
            doc, algorithm="value_noise", params={"layer_id": "x"}, seed=1
        )


def test_frame_index_out_of_range_rejected():
    doc = _doc()
    with pytest.raises(ProcgenError):
        make_procgen_command(
            doc, algorithm="value_noise", params={"frame_index": 9}, seed=1
        )


def test_non_rgba_target_rejected():
    doc = Document(8, 8, mode=ColorMode.INDEXED, palette=Palette([BLACK, WHITE]))
    with pytest.raises(ProcgenError):
        make_procgen_command(doc, algorithm="value_noise", params={}, seed=1)


# --------------------------------------------------------------------------- #
# Errors + bounds (REQ-P8-LOGIC-012 / -013)                                     #
# --------------------------------------------------------------------------- #


def test_unknown_algorithm_rejected():
    doc = _doc()
    with pytest.raises(ProcgenError):
        make_procgen_command(doc, algorithm="no_such", params={}, seed=1)


def test_bad_seed_type_rejected():
    doc = _doc()
    with pytest.raises(ProcgenError):
        make_procgen_command(doc, algorithm="value_noise", params={}, seed="x")
    with pytest.raises(ProcgenError):
        make_procgen_command(doc, algorithm="value_noise", params={}, seed=True)


def test_max_procgen_dimension_enforced(monkeypatch):
    monkeypatch.setattr(procgen, "MAX_PROCGEN_DIMENSION", 4)
    doc = _doc(8, 8)
    with pytest.raises(ProcgenError):
        make_procgen_command(
            doc, algorithm="value_noise", params={"width": 8, "height": 8}, seed=1
        )


def test_max_procgen_dimension_single_sourced():
    assert procgen.MAX_PROCGEN_DIMENSION is MAX_PROCGEN_DIMENSION


def test_negative_region_rejected():
    doc = _doc()
    with pytest.raises(ProcgenError):
        make_procgen_command(doc, algorithm="value_noise", params={"x": -1}, seed=1)


def test_bad_param_types_rejected():
    doc = _doc()
    with pytest.raises(ProcgenError):
        make_procgen_command(
            doc, algorithm="value_noise", params={"frequency": "x"}, seed=1
        )


def test_cellular_density_out_of_range_rejected():
    doc = _doc()
    with pytest.raises(ProcgenError):
        make_procgen_command(
            doc, algorithm="cellular_automata", params={"density": 2.0}, seed=1
        )


def test_octaves_bound_rejected():
    doc = _doc()
    with pytest.raises(ProcgenError):
        make_procgen_command(
            doc, algorithm="value_noise", params={"octaves": 99}, seed=1
        )


def test_colour_param_validation():
    doc = _doc()
    with pytest.raises(ProcgenError):
        make_procgen_command(
            doc,
            algorithm="value_noise",
            params={"color_low": [0, 0, 0]},  # not 4-length
            seed=1,
        )


# --------------------------------------------------------------------------- #
# Hypothesis — seeded determinism over random valid params                     #
# --------------------------------------------------------------------------- #


@given(
    algorithm=st.sampled_from(_STOCHASTIC),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
    frequency=st.integers(min_value=1, max_value=4),
)
def test_property_seeded_output_is_reproducible(algorithm, seed, frequency):
    doc_a, doc_b = _doc(), _doc()
    make_procgen_command(
        doc_a, algorithm=algorithm, params={"frequency": frequency}, seed=seed
    ).execute()
    make_procgen_command(
        doc_b, algorithm=algorithm, params={"frequency": frequency}, seed=seed
    ).execute()
    assert np.array_equal(_leaf(doc_a).data, _leaf(doc_b).data)
