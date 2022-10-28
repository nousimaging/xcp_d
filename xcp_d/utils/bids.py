# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Utilities for fmriprep bids derivatives and layout.

Most of the code is copied from niworkflows.
A PR will be submitted to niworkflows at some point.
"""
import os
import warnings

from bids import BIDSLayout
from nipype import logging
from packaging.version import Version

LOGGER = logging.getLogger("nipype.interface")


class BIDSError(ValueError):
    """A generic error related to BIDS datasets.

    Parameters
    ----------
    message : str
        The error message.
    bids_root : str
        The path to the BIDS dataset.
    """

    def __init__(self, message, bids_root):
        indent = 10
        header = (
            f'{"".join(["-"] * indent)} BIDS root folder: "{bids_root}" '
            f'{"".join(["-"] * indent)}'
        )
        self.msg = (
            f"\n{header}\n{''.join([' '] * (indent + 1))}{message}\n"
            f"{''.join(['-'] * len(header))}"
        )
        super(BIDSError, self).__init__(self.msg)
        self.bids_root = bids_root


class BIDSWarning(RuntimeWarning):
    """A generic warning related to BIDS datasets."""

    pass


def collect_participants(
    bids_dir, participant_label=None, strict=False, bids_validate=False
):
    """Collect a list of participants from a BIDS dataset.

    Parameters
    ----------
    bids_dir : str or pybids.layout.BIDSLayout
    participant_label : None or str, optional
    strict : bool, optional
    bids_validate : bool, optional

    Returns
    -------
    found_label

    Examples
    --------
    Requesting all subjects in a BIDS directory root:
    #>>> collect_participants(str(datadir / 'ds114'), bids_validate=False)
    ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10']

    Requesting two subjects, given their IDs:
    #>>> collect_participants(str(datadir / 'ds114'), participant_label=['02', '04'],
    #...                      bids_validate=False)
    ['02', '04']
    ...
    """
    if isinstance(bids_dir, BIDSLayout):
        layout = bids_dir
    else:
        layout = BIDSLayout(str(bids_dir), validate=bids_validate, derivatives=True)

    all_participants = set(layout.get_subjects())

    # Error: bids_dir does not contain subjects
    if not all_participants:
        raise BIDSError(
            "Could not find participants. Please make sure the BIDS derivatives "
            "are accessible to Docker/ are in BIDS directory structure.",
            bids_dir,
        )

    # No --participant-label was set, return all
    if not participant_label:
        return sorted(all_participants)

    if isinstance(participant_label, str):
        participant_label = [participant_label]

    # Drop sub- prefixes
    participant_label = [
        sub[4:] if sub.startswith("sub-") else sub for sub in participant_label
    ]
    # Remove duplicates
    participant_label = sorted(set(participant_label))
    # Remove labels not found
    found_label = sorted(set(participant_label) & all_participants)
    if not found_label:
        raise BIDSError(
            f"Could not find participants [{', '.join(participant_label)}]",
            bids_dir,
        )

    # Warn if some IDs were not found
    notfound_label = sorted(set(participant_label) - all_participants)
    if notfound_label:
        exc = BIDSError(
            f"Some participants were not found: {', '.join(notfound_label)}",
            bids_dir,
        )
        if strict:
            raise exc
        warnings.warn(exc.msg, BIDSWarning)

    return found_label


def collect_data(
    bids_dir,
    participant_label,
    task=None,
    bids_validate=False,
    bids_filters=None,
    cifti=False,
):
    """Collect data from a BIDS dataset.

    Parameters
    ----------
    bids_dir
    participant_label
    task
    bids_validate
    bids_filters

    Returns
    -------
    layout : pybids.layout.BIDSLayout
    subj_data : dict
    """
    layout = BIDSLayout(
        str(bids_dir),
        validate=bids_validate,
        derivatives=True,
        config=["bids", "derivatives"],
    )

    # TODO: Add and test fsaverage.
    PREFERRED_SPACES = {
        False: [
            "MNI152NLin6Asym",
            "MNI152NLin2009cAsym",
            "MNIInfant",
        ],
        True: [
            "fsLR",
        ],
    }
    allowed_spaces = PREFERRED_SPACES[cifti]

    queries = {
        "regfile": {"datatype": "anat", "suffix": "xfm"},
        "bold": {"datatype": "func", "suffix": "bold", "desc": ["preproc", None]},
        "t1w": {"datatype": "anat", "suffix": "T1w"},
        "seg_data": {"datatype": "anat", "suffix": "dseg"},
        "pial": {"datatype": "anat", "suffix": "pial"},
        "wm": {"datatype": "anat", "suffix": "smoothwm"},
        "midthickness": {"datatype": "anat", "suffix": "midthickness"},
        "inflated": {"datatype": "anat", "suffix": "inflated"},
    }

    bids_filters = bids_filters or {}
    for acq, entities in bids_filters.items():
        queries[acq].update(entities)

    # Override the default allowed extensions for BOLD data so we don't accidentally
    # collect both surface and volumetric files.
    # Don't override if already set by the bids filters.
    if "extension" not in queries["bold"].keys():
        queries["bold"]["extension"] = ".dtseries.nii" if cifti else ".nii.gz"

    # Set valid extensions for the file types.
    # Don't override if already set by the bids filters or for BOLD data.
    for acq, entities in queries.items():
        if "extension" not in queries[acq].keys():
            queries[acq]["extension"] = ["nii", "nii.gz", "dtseries.nii", "h5", "gii"]

    if task:
        queries["bold"]["task"] = task

    # Select the best available space
    if "space" not in queries["bold"]:
        for space in allowed_spaces:
            bold_data = layout.get(
                space=space,
                **queries["bold"],
            )
            if bold_data:
                queries["bold"]["space"] = space
                break

    if not bold_data:
        allowed_space_str = ", ".join(allowed_spaces)
        raise ValueError(f"No BOLD data found in allowed spaces ({allowed_space_str}).")

    # Grab the first (and presumably best) density and resolution if there are multiple.
    # This probably works well for resolution (1 typically means 1x1x1,
    # 2 typically means 2x2x2, etc.), but probably doesn't work well for density.
    resolutions = layout.get_res(**queries["bold"])
    densities = layout.get_den(**queries["bold"])
    if len(resolutions) > 1:
        queries["bold"]["resolution"] = resolutions[0]

    if len(densities) > 1:
        queries["bold"]["density"] = densities[0]

    subj_data = {
        dtype: sorted(
            layout.get(
                return_type="file",
                subject=participant_label,
                **query,
            )
        )
        for dtype, query in queries.items()
    }

    return layout, subj_data


def select_registrationfile(subj_data):
    """Select a registration file from a derivatives dataset.

    Parameters
    ----------
    subj_data : dict
        Dictionary where keys are filetypes and values are filenames.

    Returns
    -------
    mni_to_t1w : str
        Path to the MNI-to-T1w transform file.
    t1w_to_mni : str
        Path to the T1w-to-MNI transform file.
    """
    regfile = subj_data["regfile"]

    # get the file with the template name
    template1 = "MNI152NLin6Asym"  # default for fmriprep / nibabies with cifti output
    template2 = "MNI152NLin2009cAsym"  # default template for fmriprep,dcan and hcp
    template3 = "MNIInfant"  # nibabies

    mni_to_t1w = None
    t1w_to_mni = None

    for j in regfile:
        if (
            "from-" + template1 in j
            or ("from-" + template2 in j and mni_to_t1w is None)
            or ("from-" + template3 in j and mni_to_t1w is None)
        ):
            mni_to_t1w = j
        elif (
            "to-" + template1 in j
            or ("to-" + template2 in j and t1w_to_mni is None)
            or ("to-" + template3 in j and t1w_to_mni is None)
        ):
            t1w_to_mni = j
    # for validation, we need to check presence of MNI152NLin2009cAsym
    # if not we use MNI152NLin2006cAsym for nibabies
    # print(mni_to_t1w)

    return mni_to_t1w, t1w_to_mni


def extract_t1w_seg(subj_data):
    """Select preprocessed T1w and segmentation files.

    Parameters
    ----------
    subj_data : dict

    Returns
    -------
    selected_t1w_file : str
        Preprocessed T1-weighted file.
    selected_t1w_seg_file : str
        Segmentation file.
    """
    import fnmatch
    import os

    selected_t1w_file, selected_t1w_seg_file = None, None
    for t1w_file in subj_data["t1w"]:
        t1w_filename = os.path.basename(t1w_file)
        # Select the native T1w-space preprocessed T1w file (i.e., no "space" entity).
        if not fnmatch.fnmatch(t1w_filename, "*_space-*"):
            selected_t1w_file = t1w_file

    for t1w_seg_file in subj_data["seg_data"]:
        t1w_seg_filename = os.path.basename(t1w_seg_file)
        # Select the native T1w-space segmentation file (i.e., no "space" entity).
        # Also don't want aseg in the segmentation file name.
        # TODO: Use BIDSLayout for this.
        if not (
            fnmatch.fnmatch(t1w_seg_filename, "*_space-*")
            or fnmatch.fnmatch(t1w_seg_filename, "*aseg*")
        ):
            selected_t1w_seg_file = t1w_seg_file

    if not selected_t1w_file:
        raise ValueError("No T1w file found.")

    if not selected_t1w_seg_file:
        raise ValueError("No segmentation file found.")

    return selected_t1w_file, selected_t1w_seg_file


def write_dataset_description(fmri_dir, xcpd_dir):
    """Write dataset_description.json file for derivatives.

    Parameters
    ----------
    fmri_dir : str
        Path to the BIDS derivative dataset being ingested.
    xcpd_dir : str
        Path to the output xcp-d dataset.
    """
    import json
    import os

    from xcp_d.__about__ import DOWNLOAD_URL, __version__

    orig_dset_description = os.path.join(fmri_dir, "dataset_description.json")
    if not os.path.isfile(orig_dset_description):
        dset_desc = {}

    else:
        with open(orig_dset_description, "r") as fo:
            dset_desc = json.load(fo)

        assert dset_desc["DatasetType"] == "derivative"

    # Update dataset description
    dset_desc["Name"] = "XCP-D: A Robust Postprocessing Pipeline of fMRI data"
    generated_by = dset_desc.get("GeneratedBy", [])
    generated_by.insert(
        0,
        {
            "Name": "xcp_d",
            "Version": __version__,
            "CodeURL": DOWNLOAD_URL,
        },
    )
    dset_desc["GeneratedBy"] = generated_by
    dset_desc["HowToAcknowledge"] = "Include the generated boilerplate in the methods section."

    xcpd_dset_description = os.path.join(xcpd_dir, "dataset_description.json")
    if os.path.isfile(xcpd_dset_description):
        with open(xcpd_dset_description, "r") as fo:
            old_dset_desc = json.load(fo)

        old_version = old_dset_desc["GeneratedBy"][0]["Version"]
        if Version(__version__).public != Version(old_version).public:
            LOGGER.warning(f"Previous output generated by version {old_version} found.")

    else:
        with open(xcpd_dset_description, "w") as fo:
            json.dump(dset_desc, fo, indent=4, sort_keys=True)


def get_preproc_pipeline_info(input_type, fmri_dir):
    """Get preprocessing pipeline information from the dataset_description.json file."""
    import json
    import os

    info_dict = {}

    dataset_description = os.path.join(fmri_dir, "dataset_description.json")
    if os.path.isfile(dataset_description):
        with open(dataset_description) as f:
            dataset_dict = json.load(f)

        info_dict["version"] = dataset_dict['GeneratedBy'][0]['Version']
    else:
        info_dict["version"] = "unknown"

    if input_type == "fmriprep":
        info_dict["references"] = "[@esteban2019fmriprep;@esteban2020analysis, RRID:SCR_016216]"
    elif input_type == "dcan":
        info_dict["references"] = "[@Feczko_Earl_perrone_Fair_2021;@feczko2021adolescent]"
    elif input_type == "hcp":
        info_dict["references"] = "[@hcppipelines]"
    elif input_type == "nibabies":
        info_dict["references"] = "[@goncalves_mathias_2022_7072346]"
    else:
        raise ValueError(f"Unsupported input_type '{input_type}'")

    return info_dict


def _add_subject_prefix(subid):
    """Extract or compile subject entity from subject ID.

    Parameters
    ----------
    subid : str
        A subject ID (e.g., 'sub-XX' or just 'XX').

    Returns
    -------
    str
        Subject entity (e.g., 'sub-XX').
    """
    if subid.startswith('sub-'):
        return subid
    return '-'.join(('sub', subid))


def _getsesid(filename):
    """Get session id from filename if available.

    Parameters
    ----------
    filename : str
        The BIDS filename from which to extract the session ID.

    Returns
    -------
    ses_id : str or None
        The session ID in the filename.
        If the file does not have a session entity, ``None`` will be returned.
    """
    ses_id = None
    base_filename = os.path.basename(filename)

    file_id = base_filename.split('_')
    for k in file_id:
        if 'ses' in k:
            ses_id = k.split('-')[1]
            break

    return ses_id
