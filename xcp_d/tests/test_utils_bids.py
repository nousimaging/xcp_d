"""Tests for the xcp_d.utils.bids module."""
import json
import os

import pytest
from bids.layout import BIDSLayout

import xcp_d.utils.bids as xbids


def test_collect_participants(datasets):
    """Test collect_participants.

    This also covers BIDSError and BIDSWarning.
    """
    bids_dir = datasets["ds001419"]
    with pytest.raises(xbids.BIDSError, match="Could not find participants"):
        xbids.collect_participants(bids_dir, participant_label="fail")

    with pytest.warns(xbids.BIDSWarning, match="Some participants were not found"):
        xbids.collect_participants(bids_dir, participant_label=["01", "fail"])

    with pytest.raises(xbids.BIDSError, match="Some participants were not found"):
        xbids.collect_participants(bids_dir, participant_label=["01", "fail"], strict=True)

    found_labels = xbids.collect_participants(bids_dir, participant_label=None)
    assert found_labels == ["01"]

    found_labels = xbids.collect_participants(bids_dir, participant_label="01")
    assert found_labels == ["01"]


def test_collect_data_pnc(datasets):
    """Test the collect_data function."""
    bids_dir = datasets["ds001419"]

    # NIFTI workflow, but also get a BIDSLayout
    layout, subj_data = xbids.collect_data(
        bids_dir=bids_dir,
        input_type="fmriprep",
        participant_label="01",
        task=None,
        bids_validate=False,
        bids_filters=None,
        cifti=False,
        layout=None,
    )

    assert len(subj_data["bold"]) == 5
    assert "space-MNI152NLin2009cAsym" in subj_data["bold"][0]
    assert os.path.basename(subj_data["t1w"]) == "sub-01_desc-preproc_T1w.nii.gz"
    assert "space-" not in subj_data["t1w"]
    assert "to-MNI152NLin2009cAsym" in subj_data["anat_to_template_xfm"]
    assert "from-MNI152NLin2009cAsym" in subj_data["template_to_anat_xfm"]

    # CIFTI workflow
    _, subj_data = xbids.collect_data(
        bids_dir=bids_dir,
        input_type="fmriprep",
        participant_label="01",
        task="rest",
        bids_validate=False,
        bids_filters=None,
        cifti=True,
        layout=layout,
    )

    assert len(subj_data["bold"]) == 1
    assert "space-fsLR" in subj_data["bold"][0]
    assert "space-" not in subj_data["t1w"]
    assert os.path.basename(subj_data["t1w"]) == "sub-01_desc-preproc_T1w.nii.gz"
    assert "to-MNI152NLin6Asym" in subj_data["anat_to_template_xfm"]
    assert "from-MNI152NLin6Asym" in subj_data["template_to_anat_xfm"]


def test_collect_data_nibabies(datasets):
    """Test the collect_data function."""
    bids_dir = datasets["nibabies"]
    layout = BIDSLayout(
        bids_dir,
        validate=False,
        derivatives=True,
        config=["bids", "derivatives"],
    )

    # NIFTI workflow
    _, subj_data = xbids.collect_data(
        bids_dir=bids_dir,
        input_type="fmriprep",
        participant_label="01",
        task=None,
        bids_validate=False,
        bids_filters=None,
        cifti=False,
        layout=layout,
    )

    assert len(subj_data["bold"]) == 1
    assert "space-MNIInfant" in subj_data["bold"][0]
    assert "cohort-1" in subj_data["bold"][0]
    assert os.path.basename(subj_data["t1w"]) == "sub-01_ses-1mo_run-001_desc-preproc_T1w.nii.gz"
    assert "space-" not in subj_data["t1w"]
    assert "to-MNIInfant" in subj_data["anat_to_template_xfm"]
    assert "from-MNIInfant" in subj_data["template_to_anat_xfm"]

    # CIFTI workflow
    with pytest.raises(FileNotFoundError):
        _, subj_data = xbids.collect_data(
            bids_dir=bids_dir,
            input_type="fmriprep",
            participant_label="01",
            task=None,
            bids_validate=False,
            bids_filters=None,
            cifti=True,
            layout=layout,
        )


def test_collect_mesh_data(datasets):
    """Test collect_mesh_data."""
    layout = BIDSLayout(datasets["fmriprep_without_freesurfer"], validate=False, derivatives=True)
    mesh_available, standard_space_mesh, _ = xbids.collect_mesh_data(layout, "01")
    assert mesh_available is False
    assert standard_space_mesh is False

    layout = BIDSLayout(datasets["ds001419"], validate=False, derivatives=True)
    mesh_available, standard_space_mesh, _ = xbids.collect_mesh_data(layout, "01")
    assert mesh_available is True
    assert standard_space_mesh is False


def test_write_dataset_description(datasets, tmp_path_factory, caplog):
    """Test write_dataset_description."""
    tmpdir = tmp_path_factory.mktemp("test_write_dataset_description")
    dset_description = os.path.join(tmpdir, "dataset_description.json")

    # The function expects a description file in the fmri_dir.
    with pytest.raises(FileNotFoundError, match="Dataset description DNE"):
        xbids.write_dataset_description(tmpdir, tmpdir)
    assert not os.path.isfile(dset_description)

    # It will work when we give it a real fmri_dir.
    fmri_dir = datasets["ds001419"]
    xbids.write_dataset_description(fmri_dir, tmpdir)
    assert os.path.isfile(dset_description)

    # Now overwrite the description.
    xbids.write_dataset_description(fmri_dir, tmpdir)
    assert os.path.isfile(dset_description)

    # Now change the version and re-run the function.
    with open(dset_description, "r") as fo:
        desc = json.load(fo)

    desc["GeneratedBy"][0]["Version"] = "0.0.1"
    with open(dset_description, "w") as fo:
        json.dump(desc, fo, indent=4)

    assert "Previous output generated by version" not in caplog.text
    xbids.write_dataset_description(fmri_dir, tmpdir)
    assert "Previous output generated by version" in caplog.text


def test_get_preproc_pipeline_info(datasets):
    """Test get_preproc_pipeline_info."""
    input_types = ["fmriprep", "nibabies", "hcp", "dcan"]
    for input_type in input_types:
        info_dict = xbids.get_preproc_pipeline_info(input_type, datasets["ds001419"])
        assert "references" in info_dict.keys()

    with pytest.raises(ValueError, match="Unsupported input_type"):
        xbids.get_preproc_pipeline_info("fail", datasets["ds001419"])

    with pytest.raises(FileNotFoundError, match="Dataset description DNE"):
        xbids.get_preproc_pipeline_info("fmriprep", ".")


def test_get_tr(ds001419_data):
    """Test _get_tr."""
    t_r = xbids._get_tr(ds001419_data["nifti_file"])
    assert t_r == 3.0

    t_r = xbids._get_tr(ds001419_data["cifti_file"])
    assert t_r == 3.0


def test_get_freesurfer_dir(datasets):
    """Test get_freesurfer_dir and get_freesurfer_sphere."""
    with pytest.raises(NotADirectoryError, match="No FreeSurfer derivatives found."):
        xbids.get_freesurfer_dir(".")

    fs_dir = xbids.get_freesurfer_dir(datasets["nibabies"])
    assert os.path.isdir(fs_dir)

    # Create fake FreeSurfer folder so there are two possible folders
    tmp_fs_dir = os.path.join(os.path.dirname(fs_dir), "freesurfer-fail")
    os.mkdir(tmp_fs_dir)
    with pytest.raises(ValueError, match="More than one candidate"):
        xbids.get_freesurfer_dir(datasets["nibabies"])
    os.rmdir(tmp_fs_dir)

    fs_dir = xbids.get_freesurfer_dir(datasets["pnc"])
    assert os.path.isdir(fs_dir)

    sphere_file = xbids.get_freesurfer_sphere(fs_dir, "1648798153", "L")
    assert os.path.isfile(sphere_file)

    sphere_file = xbids.get_freesurfer_sphere(fs_dir, "sub-1648798153", "L")
    assert os.path.isfile(sphere_file)

    with pytest.raises(FileNotFoundError, match="Sphere file not found at"):
        sphere_file = xbids.get_freesurfer_sphere(fs_dir, "fail", "L")


def test_get_entity(datasets):
    """Test get_entity."""
    fname = os.path.join(datasets["ds001419"], "sub-01", "anat", "sub-01_desc-preproc_T1w.nii.gz")
    entity = xbids.get_entity(fname, "space")
    assert entity == "T1w"

    fname = os.path.join(
        datasets["ds001419"],
        "sub-01",
        "func",
        "sub-01_task-rest_desc-preproc_bold.nii.gz",
    )
    entity = xbids.get_entity(fname, "space")
    assert entity == "native"
    entity = xbids.get_entity(fname, "desc")
    assert entity == "preproc"
    entity = xbids.get_entity(fname, "fail")
    assert entity is None

    fname = os.path.join(
        datasets["ds001419"],
        "sub-01",
        "fmap",
        "sub-01_fmapid-auto00001_desc-coeff1_fieldmap.nii.gz",
    )
    with pytest.raises(ValueError, match="Unknown space"):
        xbids.get_entity(fname, "space")
