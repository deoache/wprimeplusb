import json
import copy
import correctionlib
import numpy as np
import awkward as ak
import importlib.resources
from typing import Type
from pathlib import Path
from .utils import unflat_sf
from coffea.analysis_tools import Weights
from analysis.corrections.utils import pog_years, get_pog_json


# ----------------------------------
# lepton scale factors
# -----------------------------------
#
# Electron
#    - ID: wp80noiso?
#    - Recon: RecoAbove20?
#    - Trigger: ?
#
# working points: (Loose, Medium, RecoAbove20, RecoBelow20, Tight, Veto, wp80iso, wp80noiso, wp90iso, wp90noiso)
#
class ElectronCorrector:
    """
    Electron corrector class

    Parameters:
    -----------
    events:
        events collection
    hlt:
        high level trigger branch
    weights:
        Weights object from coffea.analysis_tools
    year:
        Year of the dataset {'2016', '2017', '2018'}
    variation:
        if 'nominal' (default) add 'nominal', 'up' and 'down'
        variations to weights container. else, add only 'nominal' weights.
    """

    def __init__(
        self,
        events: ak.Array,
        weights: Type[Weights],
        year: str = "2017",
        variation: str = "nominal",
    ) -> None:
        self.electrons = events.selected_electrons
        self.variation = variation

        # flat electrons array
        self.e, self.n = ak.flatten(events.selected_electrons), ak.num(
            events.selected_electrons
        )

        # weights container
        self.weights = weights

        # define correction set
        self.cset = correctionlib.CorrectionSet.from_file(
            get_pog_json(json_name="electron", year=year)
        )
        self.year = year
        self.pog_year = pog_years[year]

    def add_trigger_weight(self, trigger_mask, trigger_match_mask):
        """
        add electron Trigger weights

        trigger_mask:
            mask array of events passing the analysis trigger
        trigger_match_mask:
            mask array of DeltaR matched trigger objects
        """
        # get 'in-limits' electrons
        electron_pt_mask = (self.e.pt > 10.0) & (self.e.pt < 499.999)
        electron_eta_mask = np.abs(self.e.eta) < 2.4
        trigger_mask = ak.flatten(ak.ones_like(self.electrons.pt) * trigger_mask) > 0
        trigger_match_mask = ak.flatten(trigger_match_mask)

        in_electron_mask = (
            electron_pt_mask & electron_eta_mask & trigger_mask & trigger_match_mask
        )
        in_electrons = self.e.mask[in_electron_mask]

        # get electrons transverse momentum and pseudorapidity (replace None values with some 'in-limit' value)
        electron_pt = ak.fill_none(in_electrons.pt, 10.0)
        electron_eta = ak.fill_none(in_electrons.eta, 0.0)

        # get eletron trigger correction
        cset = correctionlib.CorrectionSet.from_file(
            f"wprime_plus_b/data/correction_electron_trigger_{self.year}.json.gz"
        )
        nominal_sf = unflat_sf(
            cset["trigger_eff"].evaluate(electron_pt, electron_eta),
            in_electron_mask,
            self.n,
        )
        self.weights.add(
            name=f"electron_trigger",
            weight=nominal_sf,
        )

    def add_id_weight(self, id_working_point: str) -> None:
        """
        add electron identification scale factors to weights container

        Parameters:
        -----------
            id_working_point:
                Working point {'Loose', 'Medium', 'Tight', 'wp80iso', 'wp80noiso', 'wp90iso', 'wp90noiso'}
        """
        id_wps = {
            # mva ID working points https://twiki.cern.ch/twiki/bin/view/CMS/MultivariateElectronIdentificationRun2
            "wp80iso": self.e.mvaFall17V2Iso_WP80,
            "wp90iso": self.e.mvaFall17V2Iso_WP90,
            "wp80noiso": self.e.mvaFall17V2noIso_WP80,
            "wp90noiso": self.e.mvaFall17V2noIso_WP90,
            # cutbased ID working points https://twiki.cern.ch/twiki/bin/view/CMS/CutBasedElectronIdentificationRun2
            "loose": self.e.cutBased == 2,
            "medium": self.e.cutBased == 3,
            "tight": self.e.cutBased == 4,
        }
        # get 'in-limits' electrons
        electron_pt_mask = (self.e.pt > 10.0) & (
            self.e.pt < 499.999
        )  # potential problems with pt > 500 GeV
        electron_id_mask = id_wps[id_working_point]
        in_electron_mask = electron_pt_mask & electron_id_mask
        in_electrons = self.e.mask[in_electron_mask]

        # get electrons transverse momentum and pseudorapidity (replace None values with some 'in-limit' value)
        electron_pt = ak.fill_none(in_electrons.pt, 10.0)
        electron_eta = ak.fill_none(in_electrons.eta, 0.0)

        # remove '_UL' from year
        year = self.pog_year.replace("_UL", "")

        # get nominal scale factors
        nominal_sf = unflat_sf(
            self.cset["UL-Electron-ID-SF"].evaluate(
                year, "sf", id_working_point, electron_eta, electron_pt
            ),
            in_electron_mask,
            self.n,
        )
        if self.variation == "nominal":
            # get 'up' and 'down' scale factors
            up_sf = unflat_sf(
                self.cset["UL-Electron-ID-SF"].evaluate(
                    year, "sfup", id_working_point, electron_eta, electron_pt
                ),
                in_electron_mask,
                self.n,
            )
            down_sf = unflat_sf(
                self.cset["UL-Electron-ID-SF"].evaluate(
                    year, "sfdown", id_working_point, electron_eta, electron_pt
                ),
                in_electron_mask,
                self.n,
            )
            # add scale factors to weights container
            self.weights.add(
                name=f"electron_id_{id_working_point}",
                weight=nominal_sf,
                weightUp=up_sf,
                weightDown=down_sf,
            )
        else:
            self.weights.add(
                name=f"electron_id_{id_working_point}",
                weight=nominal_sf,
            )

    def add_reco_weight(self, reco: str) -> None:
        """
        add electron reconstruction scale factors to weights container

        reco: {RecoAbove20, RecoBelow20}
        """
        electron_pt_mask = {
            "RecoAbove20": (self.e.pt > 20) & (self.e.pt < 499.999),
            "RecoBelow20": (self.e.pt > 10) & (self.e.pt < 20),
        }
        # get 'in-limits' electrons
        in_electron_mask = electron_pt_mask[reco]
        in_electrons = self.e.mask[in_electron_mask]

        # get electrons transverse momentum and pseudorapidity (replace None values with some 'in-limit' value)
        electrons_pt_limits = {"RecoAbove20": 21, "RecoBelow20": 15}
        electron_pt = ak.fill_none(in_electrons.pt, electrons_pt_limits[reco])
        electron_eta = ak.fill_none(in_electrons.eta, 0.0)

        # remove _UL from year
        year = self.pog_year.replace("_UL", "")

        # get nominal scale factors
        nominal_sf = unflat_sf(
            self.cset["UL-Electron-ID-SF"].evaluate(
                year, "sf", reco, electron_eta, electron_pt
            ),
            in_electron_mask,
            self.n,
        )
        if self.variation == "nominal":
            # get 'up' and 'down' scale factors
            up_sf = unflat_sf(
                self.cset["UL-Electron-ID-SF"].evaluate(
                    year, "sfup", reco, electron_eta, electron_pt
                ),
                in_electron_mask,
                self.n,
            )
            down_sf = unflat_sf(
                self.cset["UL-Electron-ID-SF"].evaluate(
                    year, "sfdown", reco, electron_eta, electron_pt
                ),
                in_electron_mask,
                self.n,
            )
            # add scale factors to weights container
            self.weights.add(
                name=f"electron_{reco}",
                weight=nominal_sf,
                weightUp=up_sf,
                weightDown=down_sf,
            )
        else:
            self.weights.add(
                name=f"electron_{reco}",
                weight=nominal_sf,
            )