"""Test functions in xcp_d.utils.utils."""
import os

import numpy as np
import pandas as pd
import pytest
from nilearn import masking

from xcp_d.utils import utils


def test_estimate_brain_radius(ds001419_data):
    """Ensure that the brain radius estimation function returns the right value."""
    bold_mask = ds001419_data["brain_mask_file"]

    radius = utils.estimate_brain_radius(bold_mask, head_radius="auto")
    assert radius == 78.12350298308195

    radius = utils.estimate_brain_radius(bold_mask, head_radius=50)
    assert radius == 50


def test_butter_bandpass():
    """Test butter_bandpass."""
    n_volumes, n_voxels = 100, 1000
    data = np.random.random((n_volumes, n_voxels))
    sampling_rate = 0.5  # TR of 2 seconds
    filters = [
        {"low_pass": 0.1, "high_pass": 0.01},
        {"low_pass": 0.1, "high_pass": 0},
        {"low_pass": 0, "high_pass": 0.01},
    ]
    for filter in filters:
        filtered_data = utils.butter_bandpass(
            data=data,
            sampling_rate=sampling_rate,
            **filter,
        )
        assert filtered_data.shape == (n_volumes, n_voxels)

    with pytest.raises(ValueError, match="Filter parameters are not valid."):
        utils.butter_bandpass(
            data=data,
            sampling_rate=sampling_rate,
            low_pass=0,
            high_pass=0,
        )


def test_denoise_with_nilearn(ds001419_data, tmp_path_factory):
    """Test xcp_d.utils.utils.denoise_with_nilearn."""
    tmpdir = tmp_path_factory.mktemp("test_denoise_with_nilearn")

    high_pass, low_pass, filter_order, TR = 0.01, 0.08, 2, 2

    preprocessed_bold = ds001419_data["nifti_file"]
    confounds_file = ds001419_data["confounds_file"]
    bold_mask = ds001419_data["brain_mask_file"]

    preprocessed_bold_arr = masking.apply_mask(preprocessed_bold, bold_mask)
    # Reduce the size of the data for the test
    preprocessed_bold_arr = preprocessed_bold_arr[:, ::3]
    n_volumes, n_voxels = preprocessed_bold_arr.shape

    # Select some confounds to use for denoising
    confounds_df = pd.read_table(confounds_file)
    reduced_confounds_df = confounds_df[["csf", "white_matter"]]
    reduced_confounds_df["linear_trend"] = np.arange(reduced_confounds_df.shape[0])
    reduced_confounds_df["intercept"] = np.ones(reduced_confounds_df.shape[0])
    reduced_confounds_file = os.path.join(tmpdir, "confounds.tsv")
    reduced_confounds_df.to_csv(reduced_confounds_file, sep="\t", index=False)

    # Create the censoring file
    censoring_df = confounds_df[["framewise_displacement"]]
    censoring_df["framewise_displacement"] = censoring_df["framewise_displacement"] > 0.3
    n_censored_volumes = censoring_df["framewise_displacement"].sum()
    assert n_censored_volumes > 0
    temporal_mask = os.path.join(tmpdir, "censoring.tsv")
    censoring_df.to_csv(temporal_mask, sep="\t", index=False)

    # First, try out filtering
    (
        uncensored_denoised_bold,
        interpolated_filtered_bold,
    ) = utils.denoise_with_nilearn(
        preprocessed_bold=preprocessed_bold_arr,
        confounds_file=reduced_confounds_file,
        temporal_mask=temporal_mask,
        low_pass=low_pass,
        high_pass=high_pass,
        filter_order=filter_order,
        TR=TR,
    )

    assert uncensored_denoised_bold.shape == (n_volumes, n_voxels)
    assert interpolated_filtered_bold.shape == (n_volumes, n_voxels)

    # Now, no filtering
    (
        uncensored_denoised_bold,
        interpolated_filtered_bold,
    ) = utils.denoise_with_nilearn(
        preprocessed_bold=preprocessed_bold_arr,
        confounds_file=reduced_confounds_file,
        temporal_mask=temporal_mask,
        low_pass=None,
        high_pass=None,
        filter_order=None,
        TR=TR,
    )

    assert uncensored_denoised_bold.shape == (n_volumes, n_voxels)
    assert interpolated_filtered_bold.shape == (n_volumes, n_voxels)

    # Next, do the orthogonalization
    reduced_confounds_df["signal__test"] = confounds_df["global_signal"]

    # Move intercept to end of dataframe
    reduced_confounds_df = reduced_confounds_df[
        [c for c in reduced_confounds_df.columns if c not in ["intercept"]] + ["intercept"]
    ]
    orth_confounds_file = os.path.join(tmpdir, "orth_confounds.tsv")
    reduced_confounds_df.to_csv(orth_confounds_file, sep="\t", index=False)
    (
        uncensored_denoised_bold,
        interpolated_filtered_bold,
    ) = utils.denoise_with_nilearn(
        preprocessed_bold=preprocessed_bold_arr,
        confounds_file=orth_confounds_file,
        temporal_mask=temporal_mask,
        low_pass=low_pass,
        high_pass=high_pass,
        filter_order=filter_order,
        TR=TR,
    )
    assert uncensored_denoised_bold.shape == (n_volumes, n_voxels)
    assert interpolated_filtered_bold.shape == (n_volumes, n_voxels)

    # Finally, run without denoising
    (
        uncensored_denoised_bold,
        interpolated_filtered_bold,
    ) = utils.denoise_with_nilearn(
        preprocessed_bold=preprocessed_bold_arr,
        confounds_file=None,
        temporal_mask=temporal_mask,
        low_pass=low_pass,
        high_pass=high_pass,
        filter_order=filter_order,
        TR=TR,
    )
    assert uncensored_denoised_bold.shape == (n_volumes, n_voxels)
    assert interpolated_filtered_bold.shape == (n_volumes, n_voxels)


def test_list_to_str():
    """Test the list_to_str function."""
    lst = ["a"]
    string = utils.list_to_str(lst)
    assert string == "a"

    lst = ["a", "b"]
    string = utils.list_to_str(lst)
    assert string == "a and b"

    lst = ["a", "b", "c"]
    string = utils.list_to_str(lst)
    assert string == "a, b, and c"


def test_get_bold2std_and_t1w_xfms(ds001419_data):
    """Test get_bold2std_and_t1w_xfms."""
    bold_file_nlin2009c = ds001419_data["nifti_file"]
    nlin2009c_to_anat_xfm = ds001419_data["template_to_anat_xfm"]
    anat_to_native_xfm = ds001419_data["anat_to_native_xfm"]

    # MNI152NLin2009cAsym --> MNI152NLin2009cAsym/T1w
    (
        xforms_to_mni,
        xforms_to_mni_invert,
        xforms_to_t1w,
        xforms_to_t1w_invert,
    ) = utils.get_bold2std_and_t1w_xfms(
        bold_file_nlin2009c,
        nlin2009c_to_anat_xfm,
        anat_to_native_xfm,
    )
    assert len(xforms_to_mni) == 1
    assert len(xforms_to_mni_invert) == 1
    assert len(xforms_to_t1w) == 1
    assert len(xforms_to_t1w_invert) == 1

    # MNI152NLin6Asym --> MNI152NLin2009cAsym/T1w
    bold_file_nlin6asym = bold_file_nlin2009c.replace(
        "space-MNI152NLin2009cAsym_",
        "space-MNI152NLin6Asym_",
    )
    nlin6asym_to_anat_xfm = nlin2009c_to_anat_xfm.replace(
        "from-MNI152NLin2009cAsym_",
        "from-MNI152NLin6Asym_",
    )
    (
        xforms_to_mni,
        xforms_to_mni_invert,
        xforms_to_t1w,
        xforms_to_t1w_invert,
    ) = utils.get_bold2std_and_t1w_xfms(
        bold_file_nlin6asym,
        nlin6asym_to_anat_xfm,
        anat_to_native_xfm,
    )
    assert len(xforms_to_mni) == 1
    assert len(xforms_to_mni_invert) == 1
    assert len(xforms_to_t1w) == 1
    assert len(xforms_to_t1w_invert) == 1

    # MNIInfant --> MNI152NLin2009cAsym/T1w
    bold_file_infant = bold_file_nlin2009c.replace(
        "space-MNI152NLin2009cAsym_",
        "space-MNIInfant_cohort-1_",
    )
    infant_to_anat_xfm = nlin2009c_to_anat_xfm.replace(
        "from-MNI152NLin2009cAsym_",
        "from-MNIInfant+1_",
    )
    (
        xforms_to_mni,
        xforms_to_mni_invert,
        xforms_to_t1w,
        xforms_to_t1w_invert,
    ) = utils.get_bold2std_and_t1w_xfms(
        bold_file_infant,
        infant_to_anat_xfm,
        anat_to_native_xfm,
    )
    assert len(xforms_to_mni) == 1
    assert len(xforms_to_mni_invert) == 1
    assert len(xforms_to_t1w) == 1
    assert len(xforms_to_t1w_invert) == 1

    # T1w --> MNI152NLin2009cAsym/T1w
    bold_file_t1w = bold_file_nlin2009c.replace("space-MNI152NLin2009cAsym_", "space-T1w_")
    (
        xforms_to_mni,
        xforms_to_mni_invert,
        xforms_to_t1w,
        xforms_to_t1w_invert,
    ) = utils.get_bold2std_and_t1w_xfms(
        bold_file_t1w,
        nlin2009c_to_anat_xfm,
        anat_to_native_xfm,
    )
    assert len(xforms_to_mni) == 1
    assert len(xforms_to_mni_invert) == 1
    assert len(xforms_to_t1w) == 1
    assert len(xforms_to_t1w_invert) == 1

    # T1w --> MNI152NLin6Asym --> MNI152NLin2009cAsym/T1w
    bold_file_t1w = bold_file_nlin2009c.replace("space-MNI152NLin2009cAsym_", "space-T1w_")
    (
        xforms_to_mni,
        xforms_to_mni_invert,
        xforms_to_t1w,
        xforms_to_t1w_invert,
    ) = utils.get_bold2std_and_t1w_xfms(
        bold_file_t1w,
        nlin6asym_to_anat_xfm,
        anat_to_native_xfm,
    )
    assert len(xforms_to_mni) == 2
    assert len(xforms_to_mni_invert) == 2
    assert len(xforms_to_t1w) == 1
    assert len(xforms_to_t1w_invert) == 1

    # native --> MNI152NLin2009cAsym/T1w
    bold_file_native = bold_file_nlin2009c.replace("space-MNI152NLin2009cAsym_", "")
    (
        xforms_to_mni,
        xforms_to_mni_invert,
        xforms_to_t1w,
        xforms_to_t1w_invert,
    ) = utils.get_bold2std_and_t1w_xfms(
        bold_file_native,
        nlin2009c_to_anat_xfm,
        anat_to_native_xfm,
    )
    assert len(xforms_to_mni) == 2
    assert len(xforms_to_mni_invert) == 2
    assert len(xforms_to_t1w) == 1
    assert len(xforms_to_t1w_invert) == 1

    # native --> MNI152NLin6Asym --> MNI152NLin2009cAsym/T1w
    bold_file_native = bold_file_nlin2009c.replace("space-MNI152NLin2009cAsym_", "")
    (
        xforms_to_mni,
        xforms_to_mni_invert,
        xforms_to_t1w,
        xforms_to_t1w_invert,
    ) = utils.get_bold2std_and_t1w_xfms(
        bold_file_native,
        nlin6asym_to_anat_xfm,
        anat_to_native_xfm,
    )
    assert len(xforms_to_mni) == 3
    assert len(xforms_to_mni_invert) == 3
    assert len(xforms_to_t1w) == 1
    assert len(xforms_to_t1w_invert) == 1

    # tofail --> MNI152NLin2009cAsym/T1w
    bold_file_tofail = bold_file_nlin2009c.replace("space-MNI152NLin2009cAsym_", "space-tofail_")
    with pytest.raises(ValueError, match="Transform does not match BOLD space"):
        utils.get_bold2std_and_t1w_xfms(
            bold_file_tofail,
            nlin2009c_to_anat_xfm,
            anat_to_native_xfm,
        )

    tofail_to_anat_xfm = nlin2009c_to_anat_xfm.replace("from-MNI152NLin2009cAsym_", "from-tofail_")
    with pytest.raises(ValueError, match="Space 'tofail'"):
        utils.get_bold2std_and_t1w_xfms(
            bold_file_tofail,
            tofail_to_anat_xfm,
            anat_to_native_xfm,
        )


def test_get_std2bold_xfms(ds001419_data):
    """Test get_std2bold_xfms.

    get_std2bold_xfms finds transforms to go from the input file's space to MNI152NLin6Asym.
    """
    bold_file_nlin2009c = ds001419_data["nifti_file"]

    # MNI152NLin2009cAsym --> MNI152NLin6Asym
    xforms_to_mni = utils.get_std2bold_xfms(bold_file_nlin2009c)
    assert len(xforms_to_mni) == 1

    # MNI152NLin6Asym --> MNI152NLin6Asym
    bold_file_nlin6asym = bold_file_nlin2009c.replace(
        "space-MNI152NLin2009cAsym_",
        "space-MNI152NLin6Asym_",
    )
    xforms_to_mni = utils.get_std2bold_xfms(bold_file_nlin6asym)
    assert len(xforms_to_mni) == 1

    # MNIInfant --> MNI152NLin6Asym
    bold_file_infant = bold_file_nlin2009c.replace(
        "space-MNI152NLin2009cAsym_",
        "space-MNIInfant_cohort-1_",
    )
    xforms_to_mni = utils.get_std2bold_xfms(bold_file_infant)
    assert len(xforms_to_mni) == 2

    # tofail --> MNI152NLin6Asym
    bold_file_tofail = bold_file_nlin2009c.replace("space-MNI152NLin2009cAsym_", "space-tofail_")
    with pytest.raises(ValueError, match="Space 'tofail'"):
        utils.get_std2bold_xfms(bold_file_tofail)


def test_fwhm2sigma():
    """Test fwhm2sigma."""
    fwhm = 8
    sigma = utils.fwhm2sigma(fwhm)
    assert np.allclose(sigma, 3.39728)


def test_select_first():
    """Test _select_first."""
    lst = ["a", "b", "c"]
    assert utils._select_first(lst) == "a"

    lst = "abc"
    assert utils._select_first(lst) == "a"
