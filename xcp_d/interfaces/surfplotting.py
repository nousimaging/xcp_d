# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Surface plotting interfaces."""

from nipype import logging
from nipype.interfaces.base import (
    BaseInterfaceInputSpec,
    File,
    SimpleInterface,
    TraitedSpec,
    traits,
)

from xcp_d.utils.execsummary import generate_brain_sprite, ribbon_to_statmap
from xcp_d.utils.filemanip import fname_presuffix
from xcp_d.utils.plot import plot_svgx, plotimage

LOGGER = logging.getLogger("nipype.interface")


class _PlotImageInputSpec(BaseInterfaceInputSpec):
    in_file = File(exists=True, mandatory=True, desc="plot image")


class _PlotImageOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc="out image")


class PlotImage(SimpleInterface):
    """Python class to plot x,y, and z of image data."""

    input_spec = _PlotImageInputSpec
    output_spec = _PlotImageOutputSpec

    def _run_interface(self, runtime):
        self._results["out_file"] = fname_presuffix(
            self.inputs.in_file, suffix="_file.svg", newpath=runtime.cwd, use_ext=False
        )

        self._results["out_file"] = plotimage(self.inputs.in_file, self._results["out_file"])

        return runtime


class _BrainPlotxInputSpec(BaseInterfaceInputSpec):
    in_file = File(exists=True, mandatory=True, desc="stats file")
    template = File(exists=True, mandatory=True, desc="mask file ")


class _BrainPlotxOutputSpec(TraitedSpec):
    plot_file = File(exists=True, mandatory=True, desc="zscore html")


class BrainPlotx(SimpleInterface):
    """This class create brainsprite with overlay as stats image."""

    input_spec = _BrainPlotxInputSpec
    output_spec = _BrainPlotxOutputSpec

    def _run_interface(self, runtime):

        self._results["plot_file"] = fname_presuffix(
            "brainsprite_out_",
            suffix="file.html",
            newpath=runtime.cwd,
            use_ext=False,
        )

        self._results["plot_file"] = generate_brain_sprite(
            template_image=self.inputs.template,
            stat_map=self.inputs.in_file,
            out_file=self._results["plot_file"],
        )

        return runtime


class _PlotSVGDataInputSpec(BaseInterfaceInputSpec):
    rawdata = File(exists=True, mandatory=True, desc="Raw data")
    regressed_data = File(exists=True, mandatory=True, desc="Data after regression")
    residual_data = File(exists=True, mandatory=True, desc="Data after filtering")
    filtered_motion = File(
        exists=True,
        mandatory=True,
        desc="TSV file with filtered motion parameters.",
    )
    mask = File(exists=True, mandatory=False, desc="Bold mask")
    tmask = File(exists=True, mandatory=False, desc="Temporal mask")
    seg_data = File(exists=True, mandatory=False, desc="Segmentation file")
    TR = traits.Float(default_value=1, desc="Repetition time")
    dummy_scans = traits.Int(
        0,
        usedefault=True,
        desc="Number of dummy volumes to drop from the beginning of the run.",
    )


class _PlotSVGDataOutputSpec(TraitedSpec):
    before_process = File(exists=True, mandatory=True, desc=".SVG file before processing")
    after_process = File(exists=True, mandatory=True, desc=".SVG file after processing")


class PlotSVGData(SimpleInterface):
    """Plot fd, dvars, and carpet plots of the bold data before and after regression/filtering.

    It takes in the data that's regressed, the data that's filtered and regressed,
    as well as the segmentation files, TR, FD, bold_mask and unprocessed data.

    It outputs the .SVG files before after processing has taken place.
    """

    input_spec = _PlotSVGDataInputSpec
    output_spec = _PlotSVGDataOutputSpec

    def _run_interface(self, runtime):

        before_process_fn = fname_presuffix(
            "carpetplot_before_",
            suffix="file.svg",
            newpath=runtime.cwd,
            use_ext=False,
        )

        after_process_fn = fname_presuffix(
            "carpetplot_after_",
            suffix="file.svg",
            newpath=runtime.cwd,
            use_ext=False,
        )

        self._results["before_process"], self._results["after_process"] = plot_svgx(
            preprocessed_file=self.inputs.rawdata,
            residuals_file=self.inputs.regressed_data,
            denoised_file=self.inputs.residual_data,
            tmask=self.inputs.tmask,
            dummy_scans=self.inputs.dummy_scans,
            TR=self.inputs.TR,
            mask=self.inputs.mask,
            filtered_motion=self.inputs.filtered_motion,
            seg_data=self.inputs.seg_data,
            processed_filename=after_process_fn,
            unprocessed_filename=before_process_fn,
        )

        return runtime


class _RibbontoStatmapInputSpec(BaseInterfaceInputSpec):
    ribbon = File(exists=True, mandatory=True, desc="ribbon ")
    # other settings or files will be added later from T2 ##


class _RibbontoStatmapOutputSpec(TraitedSpec):
    out_file = File(exists=True, mandatory=True, desc="ribbon > pial and white")


class RibbontoStatmap(SimpleInterface):
    """Convert cortical ribbon to stat map."""

    input_spec = _RibbontoStatmapInputSpec
    output_spec = _RibbontoStatmapOutputSpec

    def _run_interface(self, runtime):

        self._results["out_file"] = fname_presuffix(
            "pial_white_", suffix=".nii.gz", newpath=runtime.cwd, use_ext=False
        )

        self._results["out_file"] = ribbon_to_statmap(
            ribbon=self.inputs.ribbon, outfile=self._results["out_file"]
        )

        return runtime
