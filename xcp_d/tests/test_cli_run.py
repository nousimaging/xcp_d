"""Tests for functions in the cli.run module."""
import logging
import os
from copy import deepcopy
from pathlib import Path

import pytest

from xcp_d.cli import run

build_log = logging.getLogger()
build_log.setLevel(10)


class FakeOptions:
    """A structure to mimic argparse opts."""

    def __init__(self, **entries):
        self.__dict__.update(entries)


@pytest.fixture(scope="module")
def base_opts():
    """Create base options."""
    opts_dict = {
        "fmri_dir": Path("dset"),
        "output_dir": Path("out"),
        "work_dir": Path("work"),
        "analysis_level": "participant",
        "lower_bpf": 0.01,
        "upper_bpf": 0.1,
        "bandpass_filter": True,
        "fd_thresh": 0.3,
        "min_time": 100,
        "motion_filter_type": "notch",
        "band_stop_min": 12,
        "band_stop_max": 18,
        "motion_filter_order": 1,
        "input_type": "fmriprep",
        "cifti": True,
        "process_surfaces": True,
        "fs_license_file": Path(os.environ["FS_LICENSE"]),
    }
    opts = FakeOptions(**opts_dict)
    return opts


def test_validate_parameters_01(base_opts):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)
    _, return_code = run._validate_parameters(deepcopy(opts), build_log)
    assert return_code == 0


def test_validate_parameters_02(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)
    # Set output to same as input
    opts.output_dir = opts.fmri_dir

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert "The selected output folder is the same as the input" in caplog.text
    assert return_code == 1


def test_validate_parameters_03(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)
    # Set a bad analysis level
    opts.analysis_level = "group"

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert 'Please select analysis level "participant"' in caplog.text
    assert "The selected output folder is the same as the input" not in caplog.text
    assert return_code == 1


def test_validate_parameters_04(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    assert opts.bandpass_filter is True

    # Disable bandpass_filter to False indirectly
    opts.lower_bpf = -1
    opts.upper_bpf = -1

    opts, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert opts.bandpass_filter is False
    assert "Bandpass filtering is disabled." in caplog.text
    assert return_code == 0


def test_validate_parameters_05(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    # Set upper BPF below lower one
    opts.lower_bpf = 0.01
    opts.upper_bpf = 0.001

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert "must be lower than" in caplog.text
    assert return_code == 1


def test_validate_parameters_06(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    # Disable censoring
    opts.fd_thresh = 0

    opts, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert opts.min_time == 0
    assert opts.motion_filter_type is None
    assert opts.band_stop_min is None
    assert opts.band_stop_max is None
    assert opts.motion_filter_order is None
    assert "Framewise displacement-based scrubbing is disabled." in caplog.text
    assert return_code == 0


def test_validate_parameters_07(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    # Set notch filter with no min or max
    opts.motion_filter_type = "notch"
    opts.band_stop_min = None
    opts.band_stop_max = None

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert "Please set both" in caplog.text
    assert return_code == 1


def test_validate_parameters_08(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    # Set min > max for notch filter
    opts.motion_filter_type = "notch"
    opts.band_stop_min = 18
    opts.band_stop_max = 12

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert "must be lower than" in caplog.text
    assert return_code == 1


def test_validate_parameters_09(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    # Set min <1 for notch filter
    opts.motion_filter_type = "notch"
    opts.band_stop_min = 0.01

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert "suspiciously low." in caplog.text
    assert return_code == 0


def test_validate_parameters_10(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    # Set lp without min
    opts.motion_filter_type = "lp"
    opts.band_stop_min = None
    opts.band_stop_max = None

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert "Please set '--band-stop-min'" in caplog.text
    assert return_code == 1


def test_validate_parameters_11(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    # Set min > max for notch filter
    opts.motion_filter_type = "lp"
    opts.band_stop_min = 0.01
    opts.band_stop_max = None

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert "suspiciously low." in caplog.text
    assert return_code == 0


def test_validate_parameters_12(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    # Set min > max for notch filter
    opts.motion_filter_type = "lp"
    opts.band_stop_min = 12
    opts.band_stop_max = 18

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert "'--band-stop-max' is ignored" in caplog.text
    assert return_code == 0


def test_validate_parameters_13(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    # Set min > max for notch filter
    opts.motion_filter_type = None
    opts.band_stop_min = 12
    opts.band_stop_max = 18

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert "'--band-stop-min' and '--band-stop-max' are ignored" in caplog.text
    assert return_code == 0


def test_validate_parameters_14(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    # Set min > max for notch filter
    opts.input_type = "dcan"
    opts.cifti = False

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert "cifti processing (--cifti) will be enabled automatically." in caplog.text
    assert return_code == 0


def test_validate_parameters_15(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    # Set min > max for notch filter
    opts.input_type = "dcan"
    opts.process_surfaces = False

    opts, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert opts.cifti is True
    assert "(--warp-surfaces-native2std) will be enabled automatically." in caplog.text
    assert return_code == 0


def test_validate_parameters_16(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    # Set min > max for notch filter
    opts.input_type = "dcan"
    opts.process_surfaces = False

    opts, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert opts.process_surfaces is True
    assert "(--warp-surfaces-native2std) will be enabled automatically." in caplog.text
    assert return_code == 0


def test_validate_parameters_17(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)

    # Set min > max for notch filter
    opts.process_surfaces = True
    opts.cifti = False

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert "you must enable cifti processing" in caplog.text
    assert return_code == 1


def test_validate_parameters_18(base_opts):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)
    opts.fs_license_file = None

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert return_code == 0


def test_validate_parameters_19(base_opts, caplog):
    """Test run._validate_parameters."""
    opts = deepcopy(base_opts)
    opts.fs_license_file = Path("/path/to/missing/folder")

    _, return_code = run._validate_parameters(deepcopy(opts), build_log)

    assert "Freesurfer license DNE" in caplog.text
    assert return_code == 1
